# Contributing

This repository is a three-person pod's capstone, and the rules below are the ones the pod
already works by, written down so a new contributor finds them in the repository rather
than in a scratch directory. `docs/CONTRIBUTION.md` holds the lane table: who owns which
module, who demos what, and the git evidence behind each lane. Read it first.

## Branches

Name a branch `<login>/cof-<issue>-<kebab-title>`, where `<issue>` is the GitHub issue
number (not the COF-nn ticket number, which names the work in commit subjects) and
`<login>` is the account that pushes the branch, which is not always the GitHub login in
the lane table. Real examples from this repository:

- `kenmann01/cof-74-repo-hygiene`
- `kanitmann/cof-17-load-complaints-from-the-bank-into-working-records`
- `mani/cof-39-conflict-and-out-of-scope-escalation`
- `zacharypaulb/cof-8-add-a-three-job-ci-pipeline-for-the-application-source-tree`

Cut the branch from the head of the open pull request stack, not from a local main that
may be behind, and keep one concern per branch.

## Commits

The subject is `[COF-NN] Imperative sentence`, under 72 characters: `[COF-49] Read spans by
name on a coarse clock`. The body says what changed and why, in sentences, including the
failure the change removes. Two or three logical commits are better than one blob. Add
explicit paths, never `git add -A` or `git add .`.

## The gate

Four commands, all clean, before you ask for review:

```bash
uv sync --locked
uv run --locked pytest
uv run --locked mypy src tools evals
uv run --locked ruff check src tools evals
uv run --locked bandit -c pyproject.toml -r src tools evals
```

`pyproject.toml` enforces 100 percent coverage over `src`, `tools` and `evals`, so a new
branch or line needs its test in the same commit. Write the test first, run it, and keep
the verbatim failing line: the template asks for it. CI runs the same gate on every pull
request in `.github/workflows/checks.yml`, on Ubuntu and on `windows-latest`.

`tools/evaluate.py`, `tools/runtime.py` and `tools/validate_package.py` are supplied and
hash-checked. Do not edit them; they are excluded from coverage and from the linters for
that reason. Do not add a dependency or change `uv.lock` to get a test to pass.

Tests must not write into the checkout. When `TEMP` points somewhere Windows Python cannot
use, `tempfile` falls back to the repository root, so the scratch patterns in `.gitignore`
(`pytest-of-mannk/`, `tmp*/`, `eval-mock-*/`) keep `git status` clean after a run. If a new
test needs a temporary directory, use `tmp_path` and keep it out of the tree.

## Pull requests

Fill `.github/PULL_REQUEST_TEMPLATE.md`. It has the four sections the merged pull requests
use: `## What`, `## Why`, `## What to look hardest at`, `## How it was verified`, plus a
checklist. "How it was verified" takes commands and measured numbers, not adjectives.

`.github/CODEOWNERS` names the owner of each module. It asks for review; it does not
enforce it, because the repository's rulesets are disabled and enabling them is issue #6.
Review is still expected: a pull request waits for the owner of the modules it touches.

## Review

- One approving review is needed before merge, and a "changes requested" blocks it.
- The owner of the affected module reviews the change, even when the author is in another
  lane. Cross-module changes need both owners.
- The reviewer checks the diff against the ticket, the test that pins the behaviour, and
  the numbers in "How it was verified". The template's "What to look hardest at" section
  is where the author points at the tradeoff.
- Review the branch head, not an earlier commit: a fixed pull request is re-reviewed.

## Where the rules live

- `docs/CONTRIBUTION.md`: the lanes, the module owners and the demo rules.
- `.github/PULL_REQUEST_TEMPLATE.md`: the pull request body.
- `.github/CODEOWNERS`: who reviews which paths.
- `.github/dependabot.yml`: the weekly dependency update, grouped.
- `SECURITY.md`: how to report a vulnerability and what is in scope.
- `.editorconfig`: line endings, encoding, indentation.
- `AGENTS.md`: local session notes for whichever agent is working in the checkout. It is
  git-ignored and must never be committed, because it records the state of open pull
  requests rather than the repository's rules.

## On Windows

Set `PYTHONUTF8=1` before running anything, because some files are read with the default
encoding. The shell is Git Bash. Do not order by `time.time_ns()` in a test: on Windows
that clock advances in roughly 1 ms quanta, so two rows written in the same tick carry the
same timestamp. See the Windows note in `docs/CONTRIBUTION.md`.
