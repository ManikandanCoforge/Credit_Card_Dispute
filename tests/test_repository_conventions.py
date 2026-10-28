"""The repository conventions, kept where a contributor can find them.

The pull request template, the code owners map, the dependency update rules,
the CI workflow and the ignore list are the pod's rules. Until COF-74 they
lived in a scratch directory on one laptop. These tests assert their structure
only, so the wording inside them can change without a test change, and they
read files from the checkout without starting a process.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GITHUB = ROOT / ".github"
TEMPLATE = GITHUB / "PULL_REQUEST_TEMPLATE.md"
CODEOWNERS = GITHUB / "CODEOWNERS"
DEPENDABOT = GITHUB / "dependabot.yml"
WORKFLOW = GITHUB / "workflows" / "checks.yml"
IGNORE = ROOT / ".gitignore"
SECURITY = ROOT / "SECURITY.md"
CONTRIBUTING = ROOT / "CONTRIBUTING.md"
EDITORCONFIG = ROOT / ".editorconfig"
CONTRIBUTION = ROOT / "docs" / "CONTRIBUTION.md"

SECTIONS = (
    "## What",
    "## Why",
    "## What to look hardest at",
    "## How it was verified",
)
SCRATCH = (
    ".local/",
    ".pack/",
    ".pack-open-prs.json",
    "pytest-of-mannk/",
    "tmp*/",
    "eval-mock-*/",
)
PUBLISHED = (
    "reports/*",
    "!reports/scored-run.md",
    "!reports/scored-run.json",
    "!reports/meters.jsonl",
)
JOBS = {"bandit", "env-files", "lint", "pytest", "pytest-windows"}


def _lines(path):
    return path.read_text(encoding="utf-8").splitlines()


def _lane_rows():
    """The cells of every row in the lane table of docs/CONTRIBUTION.md."""
    rows = []
    inside = False
    for line in _lines(CONTRIBUTION):
        if line.startswith("| Person |"):
            inside = True
            continue
        if not inside:
            continue
        if not line.startswith("|"):
            break
        if set(line.replace("|", "").strip()) <= set("-: "):
            continue
        rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return rows


def _lane_modules():
    """The module paths the lane table names, without a leading slash."""
    modules = []
    for row in _lane_rows():
        modules.extend(re.findall(r"`((?:src|tools|evals|docs)/[^`]+)`", row[3]))
    return sorted(set(modules))


def _lane_logins():
    """The GitHub logins the lane table names, without a leading at sign."""
    return {row[1].strip("`") for row in _lane_rows()}


def _rules():
    """Every ownership rule, as its pattern and the logins it names."""
    rules = []
    for line in _lines(CODEOWNERS):
        entry = line.split("#", 1)[0].strip()
        if not entry:
            continue
        pattern, *owners = entry.split()
        rules.append((pattern, owners))
    return rules


def _owners_of(path, rules):
    """The owners of the last rule that matches a repository path.

    A rule ending in a slash owns every path under it, any other rule owns the
    paths it matches, and the last matching rule wins, as GitHub applies it.
    Both sides are compared without the leading slash CODEOWNERS writes.
    """
    owners = []
    for pattern, named in rules:
        target = path.lstrip("/")
        prefix = pattern.lstrip("/")
        if prefix.endswith("/"):
            if target.startswith(prefix):
                owners = named
        elif target == prefix:
            owners = named
    return owners


def _jobs():
    """The job names under the jobs key of the checks workflow, and their lines."""
    lines = _lines(WORKFLOW)
    jobs = {}
    current = None
    for line in lines[lines.index("jobs:") + 1 :]:
        if re.fullmatch(r"  [a-z0-9-]+:", line):
            current = line[2:-1]
            jobs[current] = []
        elif current is not None:
            jobs[current].append(line)
    return jobs


def test_the_pull_request_template_keeps_the_four_sections():
    headings = [line for line in _lines(TEMPLATE) if line.startswith("## ")]
    assert headings == list(SECTIONS)


def test_the_pull_request_template_checklist_covers_the_gate():
    text = "\n".join(_lines(TEMPLATE))
    for requirement in (
        "pytest -q",
        "mypy src tools evals",
        "ruff check src tools evals",
        "bandit -c pyproject.toml -r src tools evals",
        "100",
        "supplied tool",
        "secret",
    ):
        assert requirement in text, requirement


def test_code_owners_owns_every_module_in_the_lane_table():
    rules = _rules()
    modules = _lane_modules()
    assert len(modules) >= 4
    for module in modules:
        owners = _owners_of(module, rules)
        assert owners, f"no CODEOWNERS rule owns {module}"
        assert all(owner.startswith("@") for owner in owners), owners


def test_code_owners_names_only_logins_the_lane_table_names():
    logins = _lane_logins()
    assert logins
    named = {owner.lstrip("@") for _, owners in _rules() for owner in owners}
    assert named <= logins, sorted(named - logins)


def test_code_owners_says_that_review_is_asked_and_not_enforced():
    preamble = "\n".join(line for line in _lines(CODEOWNERS) if line.startswith("#"))
    assert "asks for review" in preamble
    assert "does not enforce" in preamble
    assert "403" in preamble


def test_the_community_files_exist_and_say_something():
    assert "## Reporting a vulnerability" in "\n".join(_lines(SECURITY))
    assert "## The gate" in "\n".join(_lines(CONTRIBUTING))
    assert "root = true" in "\n".join(_lines(EDITORCONFIG))
    for path in (SECURITY, CONTRIBUTING, EDITORCONFIG):
        assert len(_lines(path)) > 10, path


def test_the_ignore_list_covers_the_local_scratch():
    lines = _lines(IGNORE)
    for pattern in SCRATCH:
        assert pattern in lines, pattern


def test_the_ignore_list_keeps_the_published_artifacts():
    lines = _lines(IGNORE)
    for pattern in PUBLISHED:
        assert pattern in lines, pattern


def test_the_workflow_keeps_every_job_under_a_timeout_with_pinned_actions():
    jobs = _jobs()
    assert set(jobs) == JOBS
    for name, body in jobs.items():
        assert any(line.strip().startswith("timeout-minutes:") for line in body), name
        uses = [line.strip() for line in body if "- uses:" in line]
        assert uses, name
        for line in uses:
            assert re.search(r"- uses: \S+@[0-9a-f]{40} # v[0-9]", line), f"{name}: {line}"


def test_the_workflow_cancels_superseded_runs_and_stays_read_only():
    text = "\n".join(_lines(WORKFLOW))
    assert "permissions:\n  contents: read" in text
    assert "group: ${{ github.workflow }}-${{ github.ref }}" in text
    assert "cancel-in-progress: true" in text


def test_dependabot_updates_uv_weekly_in_two_groups():
    text = "\n".join(_lines(DEPENDABOT))
    assert 'package-ecosystem: "uv"' in text
    assert 'directory: "/"' in text
    assert 'interval: "weekly"' in text
    assert "open-pull-requests-limit: 3" in text
    assert re.search(r"^\s+dev-tooling:$", text, re.M)
    assert re.search(r"^\s+runtime:$", text, re.M)
