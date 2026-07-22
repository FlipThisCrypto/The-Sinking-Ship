# THE SINKING SHIP — common operator targets (Windows-friendly via make/GNU or WSL)
.PHONY: test validate sprites vectors roll-vectors smoke load sellout site-data grails share og-image brand-assets fairness-check ci lint secrets-check site-links validate-html preflight soak help

help:
	@echo "make test | validate | sprites | vectors | smoke | load | sellout | site-data | grails | share | og-image | fairness-check | lint | secrets-check | site-links | validate-html | preflight | soak | ci"


test:
	python -m pytest tests/ -q

validate:
	python engine/validate_configs.py

sprites:
	python engine/render_engine.py --validate-sprites

vectors:
	python scripts/export_fairness_vectors.py
	node site/js/verify_vectors.mjs
	node site/js/verify_manifest_shape.mjs

roll-vectors:
	python scripts/export_roll_vectors.py
	node site/js/verify_roll.mjs

smoke:
	python scripts/smoke_fulfillment.py

load:
	python scripts/load_test_rolls.py --chests 200 --p95-ms 100

sellout:
	python engine/simulate.py --profile sellout --seed ci --replicates 5 --check

site-data:
	python scripts/build_site_data.py
	python scripts/export_fairness_vectors.py

grails:
	python scripts/gen_grail_stubs.py

share:
	python scripts/gen_share_card.py --from-manifest site/demo_chest.json --out output/share_card.png

og-image:
	python scripts/gen_og_image.py

brand-assets:
	python scripts/build_brand_assets.py

fairness-check: vectors

lint:
	python -m ruff check .

secrets-check:
	python scripts/check_no_secrets.py

site-links:
	python scripts/check_site_links.py

validate-html:
	python scripts/validate_site_html.py

# Local mirror of .github/workflows/ci.yml (minus the matrix / Pages deploy).
preflight:
	@echo "usage: make preflight SALT=path/to.salt [DB=ledger.sqlite]"
	python scripts/ops_preflight.py --salt-file "$(SALT)" $(if $(DB),--db $(DB),)

soak:
	python scripts/soak_fulfillment.py --purchases 40

ci: lint secrets-check site-links validate-html validate sprites test smoke sellout load fairness-check roll-vectors
	@echo "make ci: all local CI gates green"


