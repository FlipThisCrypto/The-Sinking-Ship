# ADR-0001 — Patterns adopted from reference implementation (BEPE LOVE)

**Status:** Accepted
**Date:** 2026-07-09

## Context

BEPE LOVE (`https://github.com/FlipThisCrypto/-BEPE_-LOVE`) is a live,
functional 2,222-supply Chia NFT project by the same team: Secure-the-Mint
offer-file mint, Netlify Functions + Netlify Blobs backend, WalletConnect v2
wallet layer, holder rewards, and two on-site games. Before building THE
SINKING SHIP's technical core we surveyed it read-only (a local clone at
`../reference/bepe-love/`, working tree marked read-only) to harvest
battle-tested Chia mechanisms and to record what we will deliberately do
differently. The survey was performed by four parallel reviewers over
(1) mint fulfillment, (2) wallet/offer handling, (3) rewards/gamification,
(4) the asset/metadata pipeline, with file-level citations.

Rule of engagement: **concepts and architecture are adapted; code is always
re-implemented fresh** in this repo under this project's license. Nothing is
copied, imported, or symlinked from the reference tree.

> **Responsible-disclosure note.** BEPE LOVE is a live production system owned
> by the same team. Any specific hardening gaps observed during the survey
> have been raised with that team privately. This public ADR describes only
> the *architecture and rationale* for THE SINKING SHIP's choices in general
> terms — it deliberately avoids step-by-step reproduction of any weakness in
> a live system. Where a past reference gap motivated a decision, it is stated
> as a design principle ("client claims must not be trusted as settlement"),
> not as an exploit recipe.

## Decision

### A. Adopted (proven, carried over as architecture)

1. **Offer file IS the payment rail — no custodial payment detection.**
   BEPE has no address watcher and no payment webhook; a pre-built
   Secure-the-Mint offer atomically swaps the buyer's XCH for the NFT in one
   transaction (`netlify/functions/mint-random.mjs`, `js/mint.js:140-181`).
   Double-fulfillment of a single offer is impossible at the chain level.
   Our P7 daemon keeps this model: fulfillment = handing out an offer; the
   chain is the settlement layer.

2. **Two-phase ledger: client claims are hints; only chain observation
   confirms.** BEPE's `/api/mint/confirm` writes only to a *pending* set;
   a scheduled reconciler promotes to *confirmed* exclusively from on-chain
   truth, and the public counter counts confirmed only while pending merely
   reduces "remaining" (`mint-confirm.mjs`, `mint-reconcile.mjs`,
   `mint-status.mjs`). This closed a real exploit (wallets reporting success
   without broadcasting — "counter pumping"). P7 adopts the three-state
   contract (`alreadyConfirmed / alreadyPending / pending`), the pending-TTL
   auto-recovery of abandoned dispenses, and a manual audit/recovery action
   alongside the cron reconciler.

3. **"No reservation — the chain is the lock" dispensing.** BEPE deliberately
   removed dispense-time holds (2026-06-05 rewrite); a token leaves the pool
   only on pending/confirmed. Eliminates hold-expiry bugs entirely.

4. **Tri-state wallet result classification (broadcast / rejected / unclear).**
   Hard-won Sage-vs-reference-wallet response-shape knowledge
   (`js/mint.js:140-181`): Sage returns a bare `{id: <64-hex>}`; some wallets
   ack sparsely, so "unclear" is treated as possibly-broadcast and recorded
   as pending — ambiguity can cost a temporary pending slot, never a lost sale
   and never a counter increment.

5. **Sage WalletConnect namespace rule: every method you will call goes in
   `requiredNamespaces`.** Sage refuses optional methods at pairing time
   (`js/wallet.js:118-153`). For us: `chia_takeOffer` and
   `chia_signMessageByAddress` are required from day one.

6. **Multi-method, multi-shape wallet RPC fallbacks.** Ordered attempts
   (`chia_getAddress` → `chia_getCurrentAddress`), response normalization
   across `{address}/{data}/bare-string` shapes, permission-error detection
   with a reconnect remediation message (`js/wallet.js:86-116`).

7. **Signature-gated claim protocol for anything of value.** Server-issued
   one-time nonce → `chia_signMessageByAddress` → server-side BLS
   verification → single batched payout with duplicate detection
   (`js/rewards.js:407-478`). This is the ready-made template for the honor
   badge system (spec Section 6): prove address control, verify eligibility
   server-side from on-chain facts, then issue.

8. **BigInt-safe JSON wire convention for mojo amounts** (`$bigint:` prefix +
   `JSON.parse` reviver; 1 XCH = 10^12 mojos exceeds `Number.MAX_SAFE_INTEGER`).
   A correctness requirement, not a style choice.

9. **Two-tier holder verification.** Third-party indexer lookups for
   display/UX only (cached, fail-empty); on-chain snapshots + signatures for
   anything worth money or badges. Client-side ownership data never touches
   reward math.

10. **Phase-gated reward rollout.** BEPE ships the reward ledger UI weeks
    before the hot wallet ever signs anything (`config.phase === 1` renders
    audit-only). Adopted verbatim for badges/rewards: audit-only first,
    payouts later.

11. **Pure, dependency-free game/roll engines.** `brawl-engine.js` has no DOM
    and no I/O so it can run identically client- and server-side. Our chest
    roll core follows this: one pure module (`engine/shipgen/`) used by
    `chest_roller.py`, `simulate.py`, and (post-reveal) a browser verifier —
    the strongest trust story a blind mint can offer.

12. **Operational tooling shape.** Secret-gated admin plane + dumb idempotent
    local pusher script with pre-flight ping, batch+backoff upload, and the
    **refuse-to-init-on-gaps** invariant (never open a mint with missing
    offers). Cold/hot wallet split with public explorer links for the
    treasury (transparency as an engagement surface).

13. **Two-layer metadata split.** Rich mint metadata (source of truth) →
    thin derived site manifest + pre-aggregated `stats.json` written in the
    same build pass, so landing-page hero numbers are always consistent with
    the manifest.

14. **Per-asset-class CDN cache tiers** (immutable images / short-cache data /
    always-revalidate code) — with the caveat in (C) about reveal-day flips.

### B. Adapted (good shape, changed for our scale or threat model)

1. **State storage.** BEPE keeps sets as single JSON blobs with etag CAS +
   bounded retries. Correct discipline, but O(n) per request and
   CAS-contended at 44,444 supply with mint-rush concurrency. P7 uses its own
   transactional store (SQLite; per-token rows, uniqueness constraints);
   any blob/KV copy is a read model, never the source of truth.

2. **Chain-truth source.** Deriving NFT identity by pattern-matching indexer
   display names is fragile and silently corruptible. We track
   `launcher_id`/`coin_id` explicitly from Secure-the-Mint generation time
   (we need `coin_id` for HMAC rolls anyway) and require the reconciler to
   *fail closed* — an incomplete chain scan may grow, but never shrink, the
   confirmed set, so a transient indexer hiccup can never return sold offers
   to the pool.

3. **Claim-token idempotency.** Single-use claim tokens are only as good as
   their enforcement; an advisory (skippable) check is equivalent to none.
   With no legacy clients to support, our claim-token validation is
   **mandatory**, with expiry and rate limiting — the confirm path rejects
   any request lacking a valid, unredeemed token.

4. **Admin auth.** Timing-safe secret comparison (not `===`), audit log of
   admin actions.

5. **Dispense order.** BEPE shuffles its queue with `Math.random` —
   unauditable. Our dispensing/roll order derives from the committed salt
   (HMAC), consistent with the provenance commitment.

6. **Image pipeline.** Keep the Pillow variant table + worker pool +
   skip-if-exists skeleton and the empirically tuned WEBP settings
   (240px/q78 thumb, 640px/q82 card, method=6); replace existence-based
   idempotency with content/mtime comparison, and don't commit ~1 GB of
   derived WEBP to git at 44,444 scale (bucket/IPFS instead).

7. **Manifest scale.** 2,222 entries ≈ 783 KB single file → ~15.7 MB at our
   supply. Shard (chunked or columnar) and make `stats.json` the only payload
   the pre-reveal landing page needs.

8. **Offer custody.** Offers generated offline, stored server-side, dealt one
   per request, never committed to the repo — adopted; but our dispenser
   response must be **opaque** (see C1) and rate-limited.

### C. Deliberately different (would break THE SINKING SHIP if copied)

1. **Blind mint vs. enumerable mint.** BEPE returns `tokenNumber` + full
   trait render at dispense time and even shows the traits of a refused
   draw — users can re-roll for rares. Correct for their "refuse and redraw"
   design; **fatal** for a blind mint. Our dispenser returns an opaque offer
   with no token identity; token↔metadata linkage stays server-side until
   the take confirms; trait manifests are published only at reveal, with the
   pre-mint commitment hash (spec 5.4) standing in for transparency.

2. **No pre-reveal manifest publication.** BEPE publishes all art + traits +
   ranks before mint. We publish `SHA-256(config + weights + grail placements
   + RNG algorithm + salt)` pre-mint and the full data only at reveal.

3. **Provenance from scratch.** The reference repo contains **no** hashing,
   provenance, or CHIP-0007 `data_hash`/`metadata_hash` computation at all —
   that pipeline lived outside the repo. Our P5/P6 build commit–reveal and
   metadata hashing as first-class, tested code.

4. **Client-reported anything never feeds value.** BEPE's leaderboard trusts
   a client-supplied fingerprint (documented v1 deferral) — safe only because
   it pays nothing. Chest outcomes here are `HMAC-SHA256(salt, coin_id)` —
   server-deterministic from on-chain facts; honor-badge eligibility derives
   exclusively from verifiable events (mint participation, holding duration
   at snapshots), never from client-reported scores.

5. **Strict CHIP-0007.** BEPE's metadata shape is "CHIP-0007-ish" with a
   nonstandard `data.identifier` extension, and downstream code needs a
   four-way fallback just to find a token number. We emit strict CHIP-0007
   (`format`, `series_number`/`series_total`, full collection block) so no
   consumer ever needs heuristics.

6. **Vendored wallet dependencies.** BEPE hot-loads `@walletconnect/sign-client`
   from esm.sh with no integrity hash on the page that pushes spend requests
   to wallets. We vendor/pin all wallet-critical JS.

7. **DID usage.** BEPE uses no DID anywhere. Per spec 5.4 we mint from a
   project DID with on-chain royalty; identity layering otherwise follows
   BEPE (fingerprint = tag, address = lookup, signature = authorization).

8. **Implement the offer-file download fallback for real.** BEPE documents a
   manual `.offer` download path for wallets without `chia_takeOffer` but
   never implemented it; the reveal app (P8) ships it.

## Consequences

- P7's interface stubs (this session) encode: adapter-based payment/confirm
  surface, three-state confirm contract, fail-closed reconciler, mandatory
  claim tokens, SQLite ledger, opaque dispensing, launcher_id-keyed identity.
- The honor badge system (Section 6) reuses the challenge–sign–verify claim
  protocol and phase-gated rollout rather than inventing new mechanisms.
- The roll core is a pure, I/O-free module so holders can re-verify chests
  in a browser post-reveal.
- We accept the cost of building the provenance/hashing layer, the
  fulfillment ledger, and the rewards backend from scratch — the reference
  proves the web/wallet layer but its trust-critical reward backend is
  closed-source (Cloudflare Worker) and its provenance layer doesn't exist.
- Wallet-compat knowledge (Sage namespace rule, tri-state take results,
  response-shape probing) is inherited as documented requirements in the
  P7/P8 TODO docs instead of being rediscovered in production.
