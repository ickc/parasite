SHELL = /usr/bin/env bash

.PHONY: test lint docs serve clean

# in pixi's development environment: pixi run test
test:
	python -m pytest -vv --cov=src --cov-report term --cov-branch tests

lint:
	ruff check src tests

# the documentation, built with parasite (docs/makefile)
docs:
	$(MAKE) -C docs docs

serve:
	$(MAKE) -C docs serve

clean:
	$(MAKE) -C docs clean

print-%:
	$(info $* = $($*))
