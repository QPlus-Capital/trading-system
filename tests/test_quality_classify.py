"""The change-risk classifier, the single implementation the model, tooling and guards share.

Covers the safe-by-default semantics directly: money paths are R3, an explicit rule beats the
docs-only shortcut, a plain doc is R0, tooling is R1, and anything unmatched is R2 -- never R1.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts.quality.classify import (
    Classification,
    Model,
    changed_paths,
    classify_path,
    classify_paths,
    load_model,
)


def _model() -> Model:
    return load_model()


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
        ("README.md", "R0"),  # plain doc
        ("docs/architecture.md", "R0"),
        ("scripts/quality/classify.py", "R1"),  # tooling with no gate role
        ("core/paths.py", "R2"),  # matched by core/** fallback
        (".env.example", "R2"),  # unmatched -> safe default, never R1
    ],
)
def test_classify_path(path: str, expected: str) -> None:
    assert classify_path(path, _model()).risk_class == expected


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
