<!-- Keep the four sections. Open the pull request as a draft while the gate is red. -->

## What

<!-- The files and modules that changed, and the behaviour a reader can observe now. -->

## Why

<!-- The COF-nn ticket, the issue it closes, and the measurement or failure that made the change worth making. -->

## What to look hardest at

<!-- Two or three places where review attention pays most, and the tradeoff you accepted there. -->

## How it was verified

<!-- The commands you ran and the numbers they printed: the RED line, the GREEN line, and the full gate. -->

Before you ask for review:

- [ ] The gate ran and its numbers are in "How it was verified": `python -m pytest -q`, `python -m mypy src tools evals`, `python -m ruff check src tools evals`, `python -m bandit -c pyproject.toml -r src tools evals`.
- [ ] Coverage is at 100 percent, with no uncovered line under `src`, `tools` or `evals`.
- [ ] Docs updated where the change moves behaviour a reader relies on.
- [ ] No supplied tool modified: `tools/evaluate.py`, `tools/runtime.py`, `tools/validate_package.py`.
- [ ] No secret and no real customer data in the diff: no key, no card number, no name from a real complaint.
