"""The engineering docs and the machine-readable risk model must stay consistent.

The constitution is the single source of truth; CLAUDE.md (builder, permanent context) and
AGENTS.md (reviewer) are short role documents that point to it. This test fails if a load-bearing
rule stops being stated where it must be, if the three documents stop cross-referencing, or if the
risk model drifts from its prose companion -- so the split into three files cannot silently lose a
rule.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_CLAUDE = _ROOT / "CLAUDE.md"
_AGENTS = _ROOT / "AGENTS.md"
_CONSTITUTION = _ROOT / "docs" / "engineering" / "constitution.md"
_RISK_DOC = _ROOT / "docs" / "engineering" / "risk-classes.md"
_RISK_MODEL = _ROOT / ".ai" / "quality" / "risk-classes.toml"

_CLASSES = ("R0", "R1", "R2", "R3")


def _text(path: Path) -> str:
    assert path.is_file(), f"required engineering doc is missing: {path.relative_to(_ROOT)}"
    return path.read_text(encoding="utf-8")


# --------------------------------------------------------------- the three documents cross-link
def test_claude_and_agents_point_to_the_constitution() -> None:
    """Neither role document may become a second source of truth."""
    link = "docs/engineering/constitution.md"
    assert link in _text(_CLAUDE), "CLAUDE.md must link to the constitution"
    assert link in _text(_AGENTS), "AGENTS.md must link to the constitution"


# --------------------------------------------------------------- load-bearing rules stay stated
#: (phrase, files it must appear in). Kept to stable, load-bearing wording, not prose that will
#: be reworded. If a rule below is deliberately removed, this list is updated in the same change --
#: which is the point: dropping a safety rule cannot pass silently.
_REQUIRED: tuple[tuple[str, tuple[Path, ...]], ...] = (
    ("Co-Authored-By", (_CONSTITUTION,)),  # no AI co-author
    ("co-author", (_CLAUDE,)),
    ("float", (_CONSTITUTION, _CLAUDE)),  # money is never float
    ("holdout", (_CONSTITUTION, _CLAUDE)),  # the holdout is sacred
    ("parity", (_CONSTITUTION,)),  # backtest/live parity
    ("0.18%", (_CONSTITUTION, _CLAUDE)),  # the internal risk limit
    ("lineage", (_CONSTITUTION,)),
    ("Never touch a running live trade", (_CLAUDE,)),
    ("Never claim correctness without executable evidence", (_CONSTITUTION,)),
    ("readiness check", (_CLAUDE,)),  # PR prohibition
)


@pytest.mark.parametrize("phrase,files", _REQUIRED, ids=lambda v: v if isinstance(v, str) else "")
def test_load_bearing_rule_is_stated(phrase: str, files: tuple[Path, ...]) -> None:
    for path in files:
        assert phrase.lower() in _text(path).lower(), (
            f"'{phrase}' must appear in {path.relative_to(_ROOT)} -- a load-bearing rule went "
            "missing. If this was intentional, update _REQUIRED in the same change."
        )


def test_agents_is_a_review_contract() -> None:
    agents = _text(_AGENTS)
    for token in ("P0", "P1", "P2", "P3", "file:line"):
        assert token in agents, f"the review contract must define {token}"
    assert "do not invent findings" in agents.lower()


# --------------------------------------------------------------- the risk model parses and holds
def test_risk_model_is_valid() -> None:
    model = tomllib.loads(_text(_RISK_MODEL))

    assert model.get("version") == 1
    assert model.get("default_min_class") in _CLASSES
    assert model.get("docs_only_globs"), "docs-only globs must be defined for R0 detection"

    classes = model.get("classes", {})
    assert tuple(sorted(classes)) == _CLASSES, "exactly R0-R3 must be defined"
    for cid, spec in classes.items():
        assert spec.get("name"), f"{cid} needs a name"
        assert spec.get("description"), f"{cid} needs a description"
        assert spec.get("gates"), f"{cid} needs at least one gate"

    rules = model.get("rules", [])
    assert rules, "the risk model needs path rules"
    for rule in rules:
        assert set(rule) >= {"glob", "min_class", "reason"}, f"incomplete rule: {rule}"
        assert rule["min_class"] in _CLASSES, f"unknown class in {rule}"
        assert rule["reason"].strip(), f"rule needs a reason: {rule}"

    # Gates are cumulative: each class must require at least as many gates as the one below it.
    sizes = [len(classes[c]["gates"]) for c in _CLASSES]
    assert sizes == sorted(sizes), "higher risk classes must not require fewer gates"


def test_every_R3_live_money_path_is_in_the_model() -> None:
    """The money path must be classified R3 by matching, not left to a human's memory."""
    rules = tomllib.loads(_text(_RISK_MODEL))["rules"]
    r3_globs = {r["glob"] for r in rules if r["min_class"] == "R3"}
    must_be_r3 = {
        "live/risk_control.py",
        "live/runner.py",
        "live/accounts.py",
        "live/mt5_bridge.py",
        "core/strategies/**",
        "core/broker.py",
        "research/regression.py",
        "research/portfolio/trades.py",
        "research/engine/continuous.py",
        "research/stages/**",
    }
    missing = must_be_r3 - r3_globs
    assert not missing, f"these money/methodology paths must be R3 in the model: {sorted(missing)}"


def test_risk_doc_and_model_agree_on_the_classes() -> None:
    doc = _text(_RISK_DOC)
    for cid in _CLASSES:
        assert cid in doc, f"{cid} is defined in the model but not documented in risk-classes.md"
    assert ".ai/quality/risk-classes.toml" in doc, "the doc must point at the model it describes"
