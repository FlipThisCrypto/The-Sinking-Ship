# Security Policy

## Supported surfaces

| Surface | Support |
|---|---|
| Generation engine (`engine/shipgen`, configs) | Current `main` only |
| Fulfillment daemon (testnet-first) | Current `main` only |
| Static site (`site/`) | Current GitHub Pages deploy |

There is no mainnet mint until the [launch checklist](docs/LAUNCH-CHECKLIST.md)
is green. Treat all live chain interaction as **testnet11** unless explicitly
announced otherwise.

## Reporting a vulnerability

Please use **GitHub Security Advisories** (preferred):

https://github.com/FlipThisCrypto/The-Sinking-Ship/security/advisories/new

If you cannot use advisories, open a **private** report path via the repository
maintainers — do **not** post mint salts, private keys, mTLS certs, or buyer
PII in public issues.

Public `security.txt`:  
https://flipthiscrypto.github.io/The-Sinking-Ship/.well-known/security.txt

## What is *not* a vulnerability

- Public trait weights, tier tables, and published fairness vectors (by design).
- Monte Carlo variance within the documented ±5% rarity tolerance.
- Demo reveal / fixture payment sources (offline only).
- Missing mainnet DID / royalty address placeholders until owner fill-in.

## Fairness disputes

After salt reveal, verify with:

```bash
python engine/chest_roller.py verify --manifest <chest.json> --salt-file <revealed.salt>
node site/js/verify_vectors.mjs
```

See [docs/INCIDENT-RUNBOOK.md](docs/INCIDENT-RUNBOOK.md) §5.

## Operator secrets

- Mint salt: offline CSPRNG, never committed (`*.salt` gitignored).
- Sage mTLS materials: local secrets only.
- Ledger DB backups: treat as sensitive during the mint window.
