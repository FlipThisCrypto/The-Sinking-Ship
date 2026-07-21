// SPDX-License-Identifier: MIT
// Client-side chest-manifest-v1 structural checks (not full re-roll).
// Full fairness re-roll remains chest_roller.py / future JS port.

export function verifyManifestShape(m) {
  const problems = [];
  if (!m || typeof m !== "object") {
    return { ok: false, problems: ["not an object"] };
  }
  if (m.schema !== "chest-manifest-v1") {
    problems.push("schema must be chest-manifest-v1");
  }
  if (!Array.isArray(m.nfts) || m.nfts.length < 1) {
    problems.push("nfts must be a non-empty array");
  }
  if (m.quantity != null && Array.isArray(m.nfts) && m.quantity !== m.nfts.length) {
    problems.push("quantity does not match nfts.length");
  }
  if (typeof m.manifest_hash !== "string" || !/^[0-9a-f]{64}$/i.test(m.manifest_hash)) {
    problems.push("manifest_hash must be 64 hex chars");
  }
  if (!m.zone) problems.push("missing zone");
  if (!m.tier) problems.push("missing tier");
  for (let i = 0; i < (m.nfts || []).length; i++) {
    const e = m.nfts[i];
    if (!e || (e.type !== "generated" && e.type !== "grail")) {
      problems.push(`nfts[${i}].type invalid`);
      continue;
    }
    if (e.type === "generated" && !e.rarity_tier) {
      problems.push(`nfts[${i}] missing rarity_tier`);
    }
  }
  return { ok: problems.length === 0, problems };
}
