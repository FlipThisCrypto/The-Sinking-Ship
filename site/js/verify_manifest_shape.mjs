// SPDX-License-Identifier: MIT
// Node smoke: shape-check site/demo_chest.json with the browser helper.
import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";
import { verifyManifestShape } from "./manifest_verify.js";

const here = dirname(fileURLToPath(import.meta.url));
const demo = JSON.parse(readFileSync(join(here, "..", "demo_chest.json"), "utf8"));
const r = verifyManifestShape(demo);
if (!r.ok) {
  console.error("FAIL", r.problems);
  process.exit(1);
}
console.log(JSON.stringify({ ok: true, nfts: demo.nfts.length, hash: demo.manifest_hash.slice(0, 16) }));
