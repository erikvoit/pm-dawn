.PHONY: check test compile lint

PYTHON ?= python

check: lint compile test

lint:
	ruff check .

test:
	$(PYTHON) -m unittest discover tests

compile:
	$(PYTHON) -m py_compile \
		pm_dawn_core/*.py \
		epic-slice-plan/scripts/*.py \
		epic-slice-implement/scripts/*.py \
		jira-epic-review/scripts/*.py \
		jira-pr/scripts/*.py
