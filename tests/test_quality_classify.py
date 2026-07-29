"""The change-risk classifier, the single implementation the model, tooling and guards share.

Covers the safe-by-default semantics directly: money paths are R3, an explicit rule beats the
docs-only shortcut, a plain doc is R0, tooling is R1, and anything unmatched is R2 -- never R1.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from scripts.quality.classify import (
    REPO_ROOT,
    Classification,
    Model,
    Rule,
    changed_paths,
    classify_path,
    classify_paths,
    load_model,
)


def _model() -> Model:
    return load_model()


_ISSUE_109_CASES = (
    (".claude/skills/specify-change/SKILL.md", "R3"),
    (".claude/agents/adversarial-code-reviewer.md", "R3"),
    (".claude/settings.json", "R3"),
    ("docs/architecture.md", "R2"),
    ("README.md", "R0"),
    (".github/workflows/ci.yml", "R3"),
)


@pytest.mark.parametrize("path,expected", _ISSUE_109_CASES, ids=lambda value: value)
def test_issue_109_classifications(path: str, expected: str) -> None:
    """Issue 109's expected classes are literals, not values derived from the TOML under test."""
    assert classify_path(path, _model()).risk_class == expected


def test_issue_109_adds_the_claude_catch_all_without_replacing_settings() -> None:
    globs = [rule.glob for rule in _model().rules]
    assert globs.count(".claude/**") == 1
    assert globs.count(".claude/settings.json") == 1


def test_issue_109_removes_the_dead_workflow_r2_rule() -> None:
    workflow_rules = [rule for rule in _model().rules if rule.glob == ".github/workflows/**"]
    assert [(rule.min_class, rule.reason) for rule in workflow_rules] == [
        ("R3", "runs the gates in CI; a change here can stop enforcing them")
    ]


# ------------------------------------------------------------------ per-path classification
@pytest.mark.parametrize(
    "path,expected",
    [
        ("live/risk_control.py", "R3"),
        ("live/parity_check.py", "R3"),  # via the live/** catch-all
        ("core/data/mt5_csv.py", "R3"),  # ingestion
        ("pyproject.toml", "R3"),  # pins the engine
        ("justfile", "R3"),  # the gates
        ("docs/methodology.md", "R3"),  # governance overrides docs-only
        ("docs/engineering/constitution.md", "R3"),
        (".ai/quality/risk-classes.toml", "R3"),  # the model cannot weaken itself
        ("scripts/quality/classify.py", "R3"),  # the classifier decides everything else's gates
        ("README.md", "R0"),  # plain doc
        ("docs/architecture.md", "R2"),
        ("scripts/seed_data.py", "R1"),  # tooling with no gate role
        ("core/paths.py", "R2"),  # matched by core/** fallback
        (".env.example", "R2"),  # unmatched -> safe default, never R1
    ],
)
def test_classify_path(path: str, expected: str) -> None:
    assert classify_path(path, _model()).risk_class == expected


@pytest.mark.parametrize(
    "spelling",
    [
        "live/runner.py",
        "./live/runner.py",
        "live\\runner.py",
        str(REPO_ROOT / "live" / "runner.py"),
    ],
)
def test_path_spellings_classify_identically(spelling: str) -> None:
    """A leading ./, a backslash, or an absolute path must not drop a live file to the safe
    default."""
    assert classify_path(spelling, _model()).risk_class == "R3"


def test_an_explicit_rule_beats_the_docs_only_shortcut() -> None:
    """A governance .md matches its R3 rule, not the docs-only R0 fallback."""
    gov = classify_path("docs/engineering/risk-classes.md", _model())
    assert gov.risk_class == "R3"
    assert gov.reason and "governance" in gov.reason.lower()


def test_a_plain_document_reports_the_docs_only_reason() -> None:
    assert classify_path("README.md", _model()).reason == "plain documentation"


def test_an_unmatched_path_is_the_safe_default_not_r1() -> None:
    pc = classify_path("some/unmatched/thing.cfg", _model())
    assert pc.risk_class == "R2"
    assert "safe default" in pc.reason


# ------------------------------------------------------------------ change-set classification
def test_classify_paths_takes_the_highest_class() -> None:
    result = classify_paths(["README.md", "scripts/x.py", "live/runner.py"], _model())
    assert result.risk_class == "R3"


def test_reasons_are_the_top_class_paths_only() -> None:
    result = classify_paths(["README.md", "live/runner.py", "core/broker.py"], _model())
    # both live/runner and core/broker are R3; README (R0) contributes no reason
    assert result.risk_class == "R3"
    assert all(r != "plain documentation" for r in result.reasons)
    assert len(result.reasons) >= 1


def test_an_empty_change_set_is_r0() -> None:
    assert classify_paths([], _model()) == Classification("R0", ())


# ------------------------------------------------------------------ model loading is validated
def test_load_model_rejects_an_unknown_default(tmp_path: Path) -> None:
    bad = tmp_path / "m.toml"
    bad.write_text(
        'default_min_class = "R9"\ndocs_only_globs = ["*.md"]\n[[rules]]\n'
        'glob = "x"\nmin_class = "R3"\nreason = "y"\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="default_min_class"):
        load_model(bad)


def test_load_model_rejects_an_unknown_rule_class(tmp_path: Path) -> None:
    bad = tmp_path / "m.toml"
    bad.write_text(
        'default_min_class = "R2"\ndocs_only_globs = ["*.md"]\n[[rules]]\n'
        'glob = "x"\nmin_class = "R7"\nreason = "y"\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown class"):
        load_model(bad)


# ------------------------------------------------------------------ required gates
def test_required_gates_are_cumulative() -> None:
    model = _model()
    r1 = set(model.required_gates("R1"))
    r3 = set(model.required_gates("R3"))
    assert r1 <= r3, "higher classes must require at least the lower classes' gates"
    assert "no-autonomous-merge" in r3, "R3 must require a human merge"
    assert "no-autonomous-merge" not in r1, "R1 must not"


# ------------------------------------------------------------------ git integration
def test_changed_paths_is_empty_against_head() -> None:
    """A deterministic check that the git plumbing runs: HEAD...HEAD has no changes."""
    assert changed_paths("HEAD") == []


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _tracked_paths() -> tuple[str, ...]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    paths = tuple(raw.decode("utf-8") for raw in result.stdout.split(b"\0") if raw)
    assert "scripts/quality/classify.py" in paths
    assert ".ai/quality/risk-classes.toml" in paths
    assert len(paths) > 300
    return paths


def _model_before_issue_109(post_change: Model) -> Model:
    """Reverse only issue 109's three rule changes to reconstruct the committed predecessor."""
    removed = {".claude/**", "docs/architecture.md"}
    assert {rule.glob for rule in post_change.rules} >= removed
    rules = tuple(rule for rule in post_change.rules if rule.glob not in removed)
    rules += (
        Rule(
            ".github/workflows/**",
            "R2",
            "CI is a quality gate",
        ),
    )
    return Model(
        post_change.default_min_class,
        post_change.docs_only_globs,
        rules,
        post_change.gates,
    )


def test_issue_109_never_lowers_a_tracked_path_and_only_upgrades_its_scope() -> None:
    """INV-02 over the real repository, including an exact guard against an over-broad glob."""
    post_change = _model()
    pre_change = _model_before_issue_109(post_change)
    rank = {"R0": 0, "R1": 1, "R2": 2, "R3": 3}
    decreases: list[tuple[str, str, str]] = []
    unexpected_increases: list[tuple[str, str, str]] = []

    for path in _tracked_paths():
        before = classify_path(path, pre_change).risk_class
        after = classify_path(path, post_change).risk_class
        if rank[after] < rank[before]:
            decreases.append((path, before, after))
        expected_increase = path == "docs/architecture.md" or path.startswith(".claude/")
        if rank[after] > rank[before] and not expected_increase:
            unexpected_increases.append((path, before, after))

    assert decreases == []
    assert unexpected_increases == []


def test_removing_the_dead_workflow_r2_rule_changes_no_tracked_path_class() -> None:
    """Max-wins, rather than assumption, proves the removed R2 rule had no effect."""
    without_dead_rule = _model()
    with_dead_rule = Model(
        without_dead_rule.default_min_class,
        without_dead_rule.docs_only_globs,
        without_dead_rule.rules + (Rule(".github/workflows/**", "R2", "CI is a quality gate"),),
        without_dead_rule.gates,
    )

    changed = [
        path
        for path in _tracked_paths()
        if classify_path(path, without_dead_rule).risk_class
        != classify_path(path, with_dead_rule).risk_class
    ]
    assert changed == []


def test_a_git_mv_of_a_live_file_to_a_doc_still_classifies_r3(tmp_path: Path) -> None:
    """Rename detection would show only the destination (an R0 doc) and hide the R3 source; the
    classifier's --no-renames must surface both, so the change stays R3."""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "live").mkdir()
    (tmp_path / "live" / "runner.py").write_text("x = 1\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "base")
    base = _git(tmp_path, "rev-parse", "HEAD")
    _git(tmp_path, "checkout", "-qb", "feature")
    (tmp_path / "docs").mkdir()
    _git(tmp_path, "mv", "live/runner.py", "docs/runner.md")
    _git(tmp_path, "commit", "-qm", "rename live file to a doc")

    paths = changed_paths(base, root=tmp_path)
    assert "live/runner.py" in paths, "the renamed-away live source must still be visible"
    assert classify_paths(paths, _model()).risk_class == "R3"
