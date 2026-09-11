SHELL := /bin/bash
.DEFAULT_GOAL := help
.NOTPARALLEL:
export ENV VAR_FILE BACKEND_CONFIG PLAN_JSON

.PHONY: help fmt validate test lint verify plan policy policy-test demo python-test hooks-install harness-status risk-summary
help:
	@echo 'fmt | validate | test | lint | verify | plan | policy | policy-test | demo | hooks-install | harness-status | risk-summary'
fmt:
	@bash scripts/verify.sh fmt
validate:
	@bash scripts/verify.sh validate
test:
	@bash scripts/verify.sh test
lint:
	@bash scripts/verify.sh lint
verify:
	@bash scripts/verify.sh all
plan:
	@bash scripts/plan.sh
policy:
	@bash scripts/policy.sh
policy-test:
	@bash scripts/policy.sh test
demo:
	@python3 scripts/plan_summary.py fixtures/plans/safe.json --environment dev
	@ENV=dev PLAN_JSON=fixtures/plans/safe.json bash scripts/policy.sh
python-test:
	@python3 -m unittest discover -s scripts/tests -v
hooks-install:
	@python3 scripts/harness.py install
harness-status:
	@python3 scripts/harness.py status
risk-summary:
	@python3 scripts/plan_summary.py "$${PLAN_JSON:?Set PLAN_JSON to an absolute plan JSON path}" --environment "$${ENV:?Set ENV}" --fail-on-high-risk
