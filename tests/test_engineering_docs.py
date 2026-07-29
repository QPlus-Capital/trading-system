"""The engineering docs and the machine-readable risk model must stay consistent.

The constitution is the single source of truth; AGENTS.md (builder, permanent Codex context) and
CLAUDE.md (reviewer, permanent Claude context) are short role documents that point to it. This
test fails if a load-bearing
rule stops being stated where it must be, if the three documents stop cross-referencing, or if the
risk model drifts from its prose companion -- so the split into three files cannot silently lose a
rule.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import pytest
from scripts.quality.classify import classify_path, load_model

_ROOT = Path(__file__).resolve().parents[1]
_CLAUDE = _ROOT / "CLAUDE.md"
_AGENTS = _ROOT / "AGENTS.md"
_CONSTITUTION = _ROOT / "docs" / "engineering" / "constitution.md"
_RISK_DOC = _ROOT / "docs" / "engineering" / "risk-classes.md"
_RISK_MODEL = _ROOT / ".ai" / "quality" / "risk-classes.toml"
_CLAUDE_SKILLS = _ROOT / ".claude" / "skills"
_CLAUDE_AGENTS = _ROOT / ".claude" / "agents"

_CLASSES = ("R0", "R1", "R2", "R3")


def _text(path: Path) -> str:
    assert path.is_file(), f"required engineering doc is missing: {path.relative_to(_ROOT)}"
    return path.read_text(encoding="utf-8")


def _model() -> dict[str, Any]:
    return tomllib.loads(_text(_RISK_MODEL))


def _class_of(path: str) -> str:
    """The class the PRODUCTION classifier assigns -- one implementation, so the model, the tooling
    and these guards cannot disagree."""
    return classify_path(path, load_model()).risk_class


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
    ("co-author", (_CLAUDE, _AGENTS)),
    ("float", (_CONSTITUTION, _CLAUDE, _AGENTS)),  # money is never float
    ("holdout", (_CONSTITUTION, _CLAUDE, _AGENTS)),  # the holdout is sacred
    ("parity", (_CONSTITUTION,)),  # backtest/live parity
    ("0.18%", (_CONSTITUTION, _CLAUDE, _AGENTS)),  # the internal risk limit
    ("lineage", (_CONSTITUTION,)),
    ("Never touch a running live trade", (_CLAUDE, _AGENTS)),
    ("Never claim correctness without executable evidence", (_CONSTITUTION,)),
    ("readiness check", (_AGENTS,)),  # builder's PR prohibition
    ("fail closed", (_CONSTITUTION, _CLAUDE, _AGENTS)),  # safety default
    ("signal engine", (_CONSTITUTION, _CLAUDE, _AGENTS)),  # the real parity boundary
    ("secret", (_CONSTITUTION, _CLAUDE, _AGENTS)),  # secrets rule
    ("english", (_CONSTITUTION, _CLAUDE, _AGENTS)),  # english-only repository
)


@pytest.mark.parametrize("phrase,files", _REQUIRED, ids=lambda v: v if isinstance(v, str) else "")
def test_load_bearing_rule_is_stated(phrase: str, files: tuple[Path, ...]) -> None:
    for path in files:
        assert phrase.lower() in _text(path).lower(), (
            f"'{phrase}' must appear in {path.relative_to(_ROOT)} -- a load-bearing rule went "
            "missing. If this was intentional, update _REQUIRED in the same change."
        )


def test_tool_contracts_bind_builder_and_reviewer_to_the_correct_files() -> None:
    agents = _text(_AGENTS)
    claude = _text(_CLAUDE)

    for marker in (
        "primary builder",
        "Development protocol",
        "Specify",
        "Analyse impact",
        "Design tests, then implement",
        # A draft PR carries the independent review; readiness gates the ready-for-review
        # transition, not the creation of the pull request.
        "Do not mark a pull request ready for review until",
        "Do not merge",
    ):
        assert marker.lower() in agents.lower(), f"AGENTS.md builder contract must define {marker}"
    for stale_reviewer_marker in ("independent-review contract", "critical, independent reviewer"):
        assert stale_reviewer_marker not in agents.lower(), (
            f"AGENTS.md must not retain the reviewer role marker {stale_reviewer_marker}"
        )

    for marker in (
        "primary reviewer",
        "conceptual designer",
        "Severity",
        "Procedure",
        "Cite `file:line`",
        "Do not invent findings",
    ):
        assert marker.lower() in claude.lower(), f"CLAUDE.md reviewer contract must define {marker}"
    for stale_builder_marker in ("claude builds", "development protocol"):
        assert stale_builder_marker not in claude.lower(), (
            f"CLAUDE.md must not retain the builder role marker {stale_builder_marker}"
        )


def test_role_contracts_preserve_exception_and_human_authority() -> None:
    for path in (_AGENTS, _CLAUDE, _CONSTITUTION):
        lowered = _text(path).lower()
        assert "either agent may build" in lowered, (
            f"{path.relative_to(_ROOT)} must preserve the highest-stakes trading exception"
        )
        decisions = ("business", "trading", "methodology", "live-money", "architecture", "risk")
        for decision in decisions:
            assert decision in lowered, (
                f"{path.relative_to(_ROOT)} must reserve {decision} decisions for Jan"
            )
        assert "jan" in lowered and "approves every merge" in lowered, (
            f"{path.relative_to(_ROOT)} must preserve Jan's merge authority"
        )
        assert "r3" in lowered and "never merge" in lowered, (
            f"{path.relative_to(_ROOT)} must prohibit autonomous R3 merges"
        )


def test_claude_runtime_files_match_the_primary_review_role() -> None:
    adversarial_skill = _text(_CLAUDE_SKILLS / "adversarial-review" / "SKILL.md").lower()
    assert "claude's primary workflow skill" in adversarial_skill
    assert "read-only and independent of the builder" in adversarial_skill

    reviewers = (
        "adversarial-code-reviewer.md",
        "live-money-reviewer.md",
        "test-quality-reviewer.md",
    )
    for name in reviewers:
        reviewer = _text(_CLAUDE_AGENTS / name).lower()
        assert "claude's primary" in reviewer, f"{name} must be part of Claude's primary path"
        assert "read-only" in reviewer, f"{name} must retain a read-only remit"

    for name in ("implement-change", "prepare-pr"):
        builder_skill = _text(_CLAUDE_SKILLS / name / "SKILL.md").lower()
        assert "only" in builder_skill and "highest-stakes trading" in builder_skill, (
            f"{name} must be limited to Claude's explicit builder exception"
        )


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


#: Concrete production paths whose classification is safety-critical. Each MUST resolve to R3, and
#: each must still exist so the guard cannot rot into asserting on a deleted path. Several were
#: gaps found in review: the money paths a weak model let slip to R1/R2.
_MUST_BE_R3 = (
    "live/risk_control.py",
    "live/runner.py",
    "live/accounts.py",
    "live/parity_check.py",  # signal parity — fell to the R1 default before review
    "core/instruments.py",  # a file, not a package — the dir glob never matched it
    "core/broker.py",
    "core/config/broker/ttp_markets_swaps.json",  # swap snapshot feeds swap_r; matched only core/**
    "research/regression.py",
    "research/portfolio/trades.py",
    "research/portfolio/stats.py",  # per-trade R/swap attribution
    "research/portfolio/factsheet.py",  # reported results; fell to research/** = R2 before review
    "research/portfolio/curves.py",  # equity/swap/holdout curves
    "research/engine/config.py",  # the config loader live shares — parity
    "research/engine/overfitting.py",  # DSR/PBO selection-bias methodology
    "research/engine/schedule_builder.py",  # selected execution params and protective exits
    "research/stages/select.py",
    ".ai/quality/risk-classes.toml",  # the model must not be able to weaken itself below R3
    ".ai/quality/finding-patterns",
    "core/data/mt5_csv.py",  # data ingestion -> every result
    "pyproject.toml",  # pins the engine / bridge versions
    "uv.lock",
    "justfile",  # the gate commands
    ".github/workflows/ci.yml",  # runs the gates
    ".claude/settings.json",  # project hooks gate every change
    ".claude/skills/specify-change/SKILL.md",  # executable workflow contract
    ".claude/agents/adversarial-code-reviewer.md",  # executable reviewer remit
    "docs/engineering/constitution.md",  # governance -- not a docs-only R0
    "docs/methodology.md",
    "docs/live-runbook.md",  # real-account ops -- not a docs-only R0
    "docs/strategies/rsi_wpr_bb.md",  # trial universe / DSR denominator
    "CLAUDE.md",
    "AGENTS.md",
)


@pytest.mark.parametrize("path", _MUST_BE_R3, ids=lambda p: p)
def test_money_path_classifies_as_R3(path: str) -> None:
    assert (_ROOT / path).exists(), (
        f"the classification guard names {path}, which no longer exists -- update _MUST_BE_R3."
    )
    got = _class_of(path)
    assert got == "R3", (
        f"{path} classifies as {got}, not R3. A money / methodology / result-integrity path must "
        "not be able to reach a PR without the R3 gates and a human merge."
    )


#: A plain, non-governance document is R0; unmatched code is at least R2 (never R1 by default).
_CLASSIFY_CASES = (
    ("README.md", "R0"),
    ("docs/architecture.md", "R2"),
    ("docs/engineering/constitution.md", "R3"),  # governance overrides docs-only
    ("scripts/foo.py", "R1"),
    ("core/paths.py", "R2"),
    ("monitoring/dashboard.py", "R2"),
)


@pytest.mark.parametrize("path,expected", _CLASSIFY_CASES, ids=lambda v: v)
def test_classification_of_representative_paths(path: str, expected: str) -> None:
    assert _class_of(path) == expected


def test_risk_doc_and_model_agree() -> None:
    doc = _text(_RISK_DOC)
    for cid in _CLASSES:
        assert cid in doc, f"{cid} is defined in the model but not documented in risk-classes.md"
    assert ".ai/quality/risk-classes.toml" in doc, "the doc must point at the model it describes"
    # The prose must NOT re-list the globs (they drift): the model is authoritative. Guard against
    # the specific stale form that already drifted once, and against re-introducing a raw glob list.
    assert "core/instruments/**" not in doc, "stale glob: the model uses core/instruments.py"
    assert "authoritative" in doc.lower(), "the doc must defer to the model as authoritative"
    # The documented unmatched-path fallback must match the model's actual default, so the companion
    # doc cannot tell an author a lower class than the model enforces.
    default = _model()["default_min_class"]
    assert f"`{default}`" in doc, f"the doc must state the unmatched fallback is {default}"
    assert "falls back to `R1`" not in doc, "stale: the model's unmatched fallback is R2, not R1"
    # The distinctive R3-only obligations must be described, not just named -- so the prose cannot
    # drift into promising less than the model enforces.
    lowered = doc.lower()
    for concept in ("mutation", "adversarial", "live-money", "autonomous merge"):
        assert concept in lowered, f"risk-classes.md must describe the R3 obligation '{concept}'"


def test_every_change_reaches_main_through_a_pull_request() -> None:
    """Every contributor-facing contract must require a feature branch and pull request."""
    required = "every change reaches `main` through a feature branch and pull request"
    for path in (_AGENTS, _CLAUDE, _CONSTITUTION, _ROOT / "README.md"):
        lowered = " ".join(_text(path).lower().split())
        assert required in lowered, (
            f"{path.relative_to(_ROOT)} must require every change to reach main through a feature "
            "branch and pull request"
        )
        assert "trivial r0" not in lowered and "straight to `main`" not in lowered, (
            f"{path.relative_to(_ROOT)} must not retain a direct-to-main exception"
        )
