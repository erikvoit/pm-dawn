.PHONY: check test compile

PYTHON ?= python

check: compile test

test:
	$(PYTHON) -m unittest discover tests

compile:
	$(PYTHON) -m py_compile \
		pm_dawn_core/*.py \
		epic-slice-plan/scripts/*.py \
		epic-slice-implement/scripts/*.py \
		jira-epic-review/scripts/*.py \
		jira-pr/scripts/*.py
