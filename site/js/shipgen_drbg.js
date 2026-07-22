// SPDX-License-Identifier: MIT
// HMAC-SHA256-DRBG-v1 — browser/Node port of engine/shipgen/drbg.py (ADR-0002).
// Must match site/fairness_vectors.json golden KAT bit-for-bit.

export const ALGORITHM_ID = "HMAC-SHA256-DRBG-v1";

const MASK64 = (1n << 64n) - 1n;

function toBytes(data) {
  if (data instanceof Uint8Array) return data;
  if (typeof data === "string") return new TextEncoder().encode(data);
  throw new TypeError("expected Uint8Array or string");
}

/** HMAC-SHA256. Uses Web Crypto (browser) or Node crypto when available. */
export async function hmacSha256(key, message) {
  const k = toBytes(key);
  const m = toBytes(message);
  if (typeof globalThis.crypto?.subtle?.importKey === "function") {
    const cryptoKey = await globalThis.crypto.subtle.importKey(
      "raw", k, { name: "HMAC", hash: "SHA-256" }, false, ["sign"],
    );
    const sig = await globalThis.crypto.subtle.sign("HMAC", cryptoKey, m);
    return new Uint8Array(sig);
  }
  // Node.js fallback
  const { createHmac } = await import("node:crypto");
  return new Uint8Array(createHmac("sha256", Buffer.from(k)).update(Buffer.from(m)).digest());
}

export function hexToBytes(hex) {
  const h = hex.replace(/^0x/i, "").toLowerCase();
  if (h.length % 2) throw new Error("odd hex length");
  const out = new Uint8Array(h.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(h.slice(i * 2, i * 2 + 2), 16);
  return out;
}

export function bytesToHex(bytes) {
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

export function normalizeCoinId(coinIdHex) {
  let c = String(coinIdHex).trim().toLowerCase();
  if (c.startsWith("0x")) c = c.slice(2);
  if (c.length !== 64 || /[^0-9a-f]/.test(c)) {
    throw new Error(`coin_id must be 32 bytes of hex, got ${coinIdHex}`);
  }
  return c;
}

export async function deriveSeedKey(saltBytes, coinIdHex) {
  const coin = normalizeCoinId(coinIdHex);
  return hmacSha256(saltBytes, hexToBytes(coin));
}

export class Drbg {
  constructor(streamKeyBytes) {
    this._key = streamKeyBytes;
    this._counter = 0n;
    this._buf = new Uint8Array(0);
  }

  static async create(seedKey, label) {
    const key = await hmacSha256(seedKey, label);
    return new Drbg(key);
  }

  async _refill() {
    const ctr = new Uint8Array(8);
    let v = this._counter;
    for (let i = 7; i >= 0; i--) {
      ctr[i] = Number(v & 0xffn);
      v >>= 8n;
    }
    this._counter += 1n;
    const block = await hmacSha256(this._key, ctr);
    const next = new Uint8Array(this._buf.length + block.length);
    next.set(this._buf, 0);
    next.set(block, this._buf.length);
    this._buf = next;
  }

  async _take(n) {
    while (this._buf.length < n) await this._refill();
    const out = this._buf.slice(0, n);
    this._buf = this._buf.slice(n);
    return out;
  }

  async _u64() {
    const b = await this._take(8);
    let v = 0n;
    for (let i = 0; i < 8; i++) v = (v << 8n) | BigInt(b[i]);
    return v;
  }

  async randBelow(n) {
    if (n <= 0) throw new Error("rand_below requires n >= 1");
    if (n === 1) return 0;
    const nn = BigInt(n);
    const limit = ((MASK64 + 1n) / nn) * nn;
    for (;;) {
      const v = await this._u64();
      if (v < limit) return Number(v % nn);
    }
  }

  /** Uniform integer in [a, b] inclusive (mirror of drbg.py rand_int). */
  async randInt(a, b) {
    if (b < a) throw new Error("rand_int requires a <= b");
    return a + (await this.randBelow(b - a + 1));
  }

  /** Index proportional to integer weights (mirror of drbg.py weighted_index).
   *  `total` may be precomputed; the draw sequence is identical either way. */
  async weightedIndex(weights, total = null) {
    if (total === null) {
      total = 0;
      for (const w of weights) {
        if (w < 0) throw new Error("negative weight");
        total += w;
      }
    } else {
      for (const w of weights) if (w < 0) throw new Error("negative weight");
    }
    if (total <= 0) throw new Error("all weights are zero");
    const r = await this.randBelow(total);
    let acc = 0;
    for (let i = 0; i < weights.length; i++) {
      acc += weights[i];
      if (r < acc) return i;
    }
    throw new Error("unreachable");
  }

  /** k distinct integers from [0, population), in draw order. */
  async sampleDistinct(population, k) {
    if (population < 0 || k < 0) throw new Error("population and k must be >= 0");
    if (k > population) throw new Error("sample larger than population");
    if (k === 0) return [];
    const seen = new Set();
    const out = [];
    while (out.length < k) {
      const v = await this.randBelow(population);
      if (!seen.has(v)) {
        seen.add(v);
        out.push(v);
      }
    }
    return out;
  }
}

/** Run golden KAT from fairness_vectors.json drbg_kat block. */
export async function verifyDrbgKat(drbgKat) {
  const seed = new TextEncoder().encode(drbgKat.seed_key_utf8);
  const d = await Drbg.create(seed, drbgKat.label);
  const got = [];
  for (let i = 0; i < drbgKat.rand_below_1e6.length; i++) {
    got.push(await d.randBelow(1_000_000));
  }
  const expected = drbgKat.rand_below_1e6;
  const ok = got.length === expected.length && got.every((v, i) => v === expected[i]);
  return { ok, got, expected };
}

export async function verifyCoinNormalization(block) {
  const salt = hexToBytes(
    // salt not in coin_normalization — only seed path; verify normalize + derive shape
    "00".repeat(32),
  );
  // Just check normalize + that seed_key derivation is stable for the documented pair
  // when salt is known from commitment.salt_hex (caller may pass saltHex).
  return {
    ok: normalizeCoinId(block.input) === block.normalized,
    normalized: normalizeCoinId(block.input),
  };
}

export async function verifySeedKey(saltHex, coinBlock) {
  const salt = hexToBytes(saltHex);
  const seed = await deriveSeedKey(salt, coinBlock.input);
  const hex = bytesToHex(seed);
  return { ok: hex === coinBlock.seed_key_hex, got: hex, expected: coinBlock.seed_key_hex };
}

export async function verifyFairnessVectors(doc) {
  const results = {};
  results.drbg_kat = await verifyDrbgKat(doc.drbg_kat);
  results.coin_norm = {
    ok: normalizeCoinId(doc.coin_normalization.input) === doc.coin_normalization.normalized,
  };
  results.seed_key = await verifySeedKey(
    doc.commitment.salt_hex,
    doc.coin_normalization,
  );
  results.ok = results.drbg_kat.ok && results.coin_norm.ok && results.seed_key.ok;
  results.algorithm = doc.rng_algorithm;
  return results;
}
