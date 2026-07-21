# Public chest manifests for reveal

Place fulfilled `chest-manifest-v1` JSON files here as `<offer-id>.json`.

The reveal app loads them via:

```
reveal.html?offer=<offer-id>
```

The fulfillment daemon can publish automatically:

```bash
python engine/fulfillment_daemon.py tick ... --reveal-outdir site/chests
```

Do not commit real buyer manifests with private linkage if that violates
privacy policy — prefer CDN/private hosting for live mint.
