# THE SINKING SHIP — common operator targets (Windows-friendly via make/GNU or WSL)
.PHONY: test validate vectors smoke load site-data grails share fairness-check help

help:
	@echo "make test | validate | vectors | smoke | load | site-data | grails | share | fairness-check"

test:
	python -m pytest tests/ -q

validate:
	python engine/validate_configs.py

vectors:
	python scripts/export_fairness_vectors.py
	node site/js/verify_vectors.mjs

smoke:
	python scripts/smoke_fulfillment.py

load:
	python scripts/load_test_rolls.py --chests 200 --p95-ms 100

site-data:
	python scripts/build_site_data.py
	python scripts/export_fairness_vectors.py

grails:
	python scripts/gen_grail_stubs.py

share:
	python scripts/gen_share_card.py --from-manifest site/demo_chest.json --out output/share_card.png

fairness-check: vectors
