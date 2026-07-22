// SPDX-License-Identifier: MIT
// CI harness: prove the JS roll port reproduces the Python engine bit-for-bit.
// Loads site/roll_vectors.json, recomputes placements + every chest manifest
// hash from the salt alone, and asserts they match. Exit non-zero on any drift.
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { RollEngine, derivePlacements, canonJson, hashObj } from "./shipgen_roll.js";
import { hexToBytes } from "./shipgen_drbg.js";

const here = dirname(fileURLToPath(import.meta.url));
const vectors = JSON.parse(readFileSync(join(here, "..", "roll_vectors.json"), "utf-8"));

function fail(msg) {
  console.error("FAIL:", msg);
  process.exit(1);
}

const salt = hexToBytes(vectors.salt_hex);
const engine = new RollEngine(vectors.config);

// 1) Placements recomputed from the salt must match the published set.
const placements = await derivePlacements(salt, engine);
if (canonJson(placements) !== canonJson(vectors.placements)) {
  fail("derived placements != published placements");
}

// 2) Every chest manifest hash must reproduce from (salt, inputs) alone.
let full = 0;
for (const c of vectors.chests) {
  const m = await engine.rollChest(
    salt, c.coin_id, c.tier, c.pass_ordinal, c.start_index, placements,
    vectors.provenance_hash, vectors.config_version_hash);
  if (m.manifest_hash !== c.manifest_hash) {
    fail(`${c.tier} coin=${c.coin_id.slice(0, 8)} ord=${c.pass_ordinal} start=${c.start_index}: `
      + `got ${m.manifest_hash} want ${c.manifest_hash}`);
  }
  if (c.manifest) {
    full++;
    // Deep structural check (not just the hash) on the embedded manifests.
    const want = { ...c.manifest };
    delete want.manifest_hash;
    const got = { ...m };
    delete got.manifest_hash;
    if (canonJson(got) !== canonJson(want)) fail(`${c.tier}: full manifest mismatch`);
    // And re-derive the hash independently.
    if ((await hashObj(got)) !== c.manifest.manifest_hash) fail(`${c.tier}: hashObj mismatch`);
  }
}

console.log(JSON.stringify({
  ok: true,
  chests_verified: vectors.chests.length,
  full_manifests_checked: full,
  placements: "match",
}, null, 2));
