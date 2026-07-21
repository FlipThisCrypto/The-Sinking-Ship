# THE SINKING SHIP — Incident runbook

Operator procedures for mint-window failures. Prefer **fail-closed** over
shipping chests under uncertainty. Pair with
[TODO-P7-fulfillment.md](TODO-P7-fulfillment.md) and
[SCUTTLING-PROCEDURE.md](SCUTTLING-PROCEDURE.md).

**Default posture:** pause new fulfillment if confirmation truth is incomplete;
never invent chain state; never re-roll a coin that already has a stored
manifest hash.

---

## 0. Severity and first 5 minutes

| Severity | Meaning | First action |
|---|---|---|
| **SEV-1** | Payments confirmed, chests not delivering; double-mint risk | Stop `reconcile` / ticks; snapshot ledger |
| **SEV-2** | Polling/RPC flapping; delayed delivery | Fail-closed (ticks error, height not advanced); page status |
| **SEV-3** | Marketing site / reveal demo degraded | CDN/Pages recovery; mint path unaffected |

**Always collect before changing state:**

```bash
python engine/fulfillment_daemon.py status --db "$LEDGER_DB"
python engine/fulfillment_daemon.py export-audit --db "$LEDGER_DB" --out "incident-audit-$(date +%Y%m%dT%H%M%S).json"
# Windows PowerShell: use Get-Date -Format yyyyMMddTHHmmss
copy /Y "%LEDGER_DB%" "ledger-backup-%DATE%.sqlite"   # or Copy-Item on PowerShell
```

Publish a short status line (X/Discord/site banner): what is broken, what is
still safe (e.g. “takes accepted; claims delayed”).

---

## 1. Coinset / chain RPC down or incomplete

**Symptoms:** ticks log `payment scan incomplete — fail closed`; `errors` in
tick summary; last polled height not advancing; buyers see pending forever.

**Expected safe behavior:** `CoinsetPollingSource` **raises** when transport
fails or `complete` is false — ledger height must **not** advance.

**Response:**

1. Confirm fail-closed: re-run one tick; expect `errors` and **no** new
   `fulfilled` for unconfirmed coins.
2. Check operator URL health (`GET {base}/height`, purchases endpoint).
3. Do **not** switch to fixture or a partial mock on mainnet/testnet mint.
4. If RPC is degraded for >15 minutes: stop automated `reconcile` cron; leave
   STM offers as-is (chain is source of truth for payment).
5. When RPC recovers: run `reconcile` with normal fixture/coinset args; verify
   `status` shows backlog draining without `errors`.
6. Export audit after recovery; reconcile buyer support tickets against
   `coin_id` rows.

**Do not:** lower confirmation requirements; mark CONFIRMED from webhook alone
(`StmWebhookIngest` is PENDING hint only).

---

## 2. Double-pay / double-fulfill attempt

**Symptoms:** same `coin_id` appears twice in webhook or poll; buyer retries
claim; operator re-runs tick after crash mid-fulfill.

**Expected safe behavior:** ledger is idempotent on `coin_id`; stored
`manifest_hash` is sticky; second fulfill reuses the same roll.

**Response:**

1. `status` + ledger row for the `coin_id` — note `state`, `manifest_hash`,
   `offer_id`.
2. If state is `fulfilled`: re-issue or re-post the **same** claim offer if
   needed; **do not** delete the row or re-roll.
3. If state is `rolled` (crash between roll and offer): re-run tick / `_fulfill_one`
   path — mint/offer only, same manifest (covered by tests).
4. If two distinct coin ids paid for “one” intent: both are valid payments;
   fulfill both within budget or refuse with explicit reason if budget blocks.
5. Export refused list if any: `export-refused`.

**Do not:** change salt, placements, or start_index manually to “fix” a chest.

---

## 3. Budget exhaustion mid-window

**Symptoms:** `refused` rows with public mint budget reasons; `status` shows
supply_consumed ≈ public_mint_budget.

**Response:**

1. Confirm budget from `config/tiers.json` / `status` (do not raise budget ad hoc).
2. Stop selling additional Dive Pass inventory if not already sold out.
3. Communicate scarcity; remaining refused buyers get documented refusal JSON.
4. Scuttling still applies to **unminted** capacity at window close — refused
   confirmed pays need human policy (refund offer path is off-chain/ops).

---

## 4. Reveal / marketing site down (GitHub Pages)

**Symptoms:** 404 or stale site; fairness self-check cannot load vectors; reveal
demo fails to fetch `demo_chest.json`.

**Impact:** mint fulfillment is **independent** of Pages if daemon runs on ops
host. Fairness verification for users is degraded.

**Response:**

1. Check Actions → “Deploy site to GitHub Pages” + repo Pages settings
   (Source = GitHub Actions).
2. Re-run `workflow_dispatch` on deploy-pages; confirm artifact includes
   `fairness_vectors.json`, `demo_chest.json`, versioned assets.
3. Hard-refresh / cache-bust query params (deploy stamps `?v=SHA`).
4. Temporary fallback: point status post at raw GitHub paths for
   `site/fairness_vectors.json` and instruct `node site/js/verify_vectors.mjs`
   or `chest_roller.py verify` after salt reveal.
5. If only reveal demo breaks: landing + fairness still communicate odds.

---

## 5. Fairness / commitment dispute

**Symptoms:** third party claims manifests do not verify; vectors fail in browser.

**Response:**

1. Confirm published commitment hash matches pre-mint publication channel.
2. Locally: `python scripts/export_fairness_vectors.py` then
   `node site/js/verify_vectors.mjs` on the **committed** tree.
3. For a specific chest: `chest_roller.py verify --manifest … --salt-file …`
   only **after** public salt reveal (never share salt early).
4. If a genuine engine bug is found post-commitment: **stop mint**, public
   disclosure, do not silently reweight. Scuttle / remediation is a governance
   decision — see scuttling doc.

---

## 6. Sage / mTLS mint path failure

**Symptoms:** dry-run OK, live mint errors; health check fails.

**Response:**

1. Keep payments fail-closed; do not fulfill without mint capability if offers
   cannot be built.
2. Verify cert paths, network (`testnet11` vs mainnet), `SageRpcClient.health`.
3. Fall back to documented dry-run only on non-production; production requires
   repair of Sage path before draining `rolled` backlog.
4. Never hand-edit launcher ids in the ledger.

---

## 7. Communications template (short)

> THE SINKING SHIP status: [issue]. Payments are [accepting/paused]. Chest
> delivery is [normal/delayed/paused]. We fail closed on incomplete chain data —
> we will not invent confirmations. Next update: [time]. Fairness docs:
> https://flipthiscrypto.github.io/The-Sinking-Ship/fairness.html

---

## 8. Post-incident

- [ ] Audit export archived with incident id
- [ ] Ledger backup stored offline
- [ ] Root cause + whether config/code change needed
- [ ] Update this runbook if a new failure mode appeared
- [ ] If mint window ended under incident: coordinate with scuttling procedure
