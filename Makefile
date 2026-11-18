# byo-agent — one target per pillar. Make is a shortcut, not a framework.
PY := $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)

.PHONY: run dashboard trajectory eval gate lint

run:            ## chat in the terminal
	$(PY) -m byo

dashboard:      ## the browser cockpit -> http://127.0.0.1:7777
	$(PY) -m byo dashboard

trajectory:     ## render the newest recorded trajectory
	$(PY) -m byo trajectory

eval:           ## the offline deterministic suite
	$(PY) -m pytest -q evals/deterministic

gate:           ## the same suite, one line per check, non-zero on failure
	$(PY) -m pytest -v evals/deterministic

lint:           ## style
	$(PY) -m ruff check byo/ evals/
