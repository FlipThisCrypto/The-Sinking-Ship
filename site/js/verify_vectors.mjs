// SPDX-License-Identifier: MIT
// Node CLI: node site/js/verify_vectors.mjs [path/to/fairness_vectors.json]
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { verifyFairnessVectors } from "./shipgen_drbg.js";

const __dir = dirname(fileURLToPath(import.meta.url));
const path = process.argv[2] || join(__dir, "..", "fairness_vectors.json");
const doc = JSON.parse(readFileSync(path, "utf8"));
const r = await verifyFairnessVectors(doc);
console.log(JSON.stringify(r, null, 2));
process.exit(r.ok ? 0 : 1);
