# The loop recipes are written for Git Bash or a POSIX shell. From PowerShell,
# run the equivalent commands listed in docs/RUNBOOK.md: the recipes are the same
# commands spelled for a POSIX shell.
#
#   make setup   install the pinned dependencies and validate the package
#   make gate    run pytest, mypy, ruff and bandit
#   make serve   start the supplied mock (PORT and STATE override the defaults)
#   make score   run the scored run against the running mock
#   make demo    run the whole loop in one command
#   make eval    run the development eval suite
#   make clean   remove the state, submission and pytest scratch paths

PORT ?= 8765
STATE ?= .state/mock.sqlite
BASE_URL ?= http://127.0.0.1:$(PORT)

.PHONY: setup gate serve score demo eval clean

setup:
	uv sync --locked
	uv run --locked python tools/validate_package.py

gate:
	uv run --locked python -m pytest -q
	uv run --locked python -m mypy src tools evals
	uv run --locked python -m ruff check src tools evals
	uv run --locked python -m bandit -c pyproject.toml -r src tools evals

serve:
	uv run --locked python tools/runtime.py serve --port $(PORT) --state $(STATE)

score:
	uv run --locked python tools/scored_run.py --base-url $(BASE_URL)

demo:
	uv run --locked python -m src.run_loop

eval:
	uv run --locked python -m evals --suite evals/suites/dev.json

clean:
	rm -rf .state submissions pytest-of-mannk
