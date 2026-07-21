# THE SINKING SHIP — common operator targets (Windows-friendly via make/GNU or WSL)
.PHONY: test validate sprites vectors smoke load sellout site-data grails share og-image fairness-check ci lint secrets-check site-links help

help:
	@echo "make test | validate | sprites | vectors | smoke | load | sellout | site-data | grails | share | og-image | fairness-check | lint | secrets-check | site-links | ci"

test:
	python -m pytest tests/ -q

validate:
	python engine/validate_configs.py

sprites:
	python engine/render_engine.py --validate-sprites

vectors:
	python scripts/export_fairness_vectors.py
	node site/js/verify_vectors.mjs

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

fairness-check: vectors

lint:
	python -m ruff check .

secrets-check:
	python scripts/check_no_secrets.py

site-links:
	python scripts/check_site_links.py

# Local mirror of .github/workflows/ci.yml (minus the matrix / Pages deploy).
ci: lint secrets-check site-links validate sprites test smoke sellout load fairness-check
	@echo "make ci: all local CI gates green"
