"""The engineering docs and the machine-readable risk model must stay consistent.

The constitution is the single source of truth; CLAUDE.md (builder, permanent context) and
AGENTS.md (reviewer) are short role documents that point to it. This test fails if a load-bearing
rule stops being stated where it must be, if the three documents stop cross-referencing, or if the
risk model drifts from its prose companion -- so the split into three files cannot silently lose a
rule.
"""

from __future__ import annotations

import fnmatch
import tomllib
from pathlib import Path
from typing import Any

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_CLAUDE = _ROOT / "CLAUDE.md"
_AGENTS = _ROOT / "AGENTS.md"
_CONSTITUTION = _ROOT / "docs" / "engineering" / "constitution.md"
_RISK_DOC = _ROOT / "docs" / "engineering" / "risk-classes.md"
_RISK_MODEL = _ROOT / ".ai" / "quality" / "risk-classes.toml"

_CLASSES = ("R0", "R1", "R2", "R3")
_RANK = {c: i for i, c in enumerate(_CLASSES)}


def _text(path: Path) -> str:
    assert path.is_file(), f"required engineering doc is missing: {path.relative_to(_ROOT)}"
    return path.read_text(encoding="utf-8")


def _model() -> dict[str, Any]:
    return tomllib.loads(_text(_RISK_MODEL))


def _classify(path: str, model: dict[str, Any]) -> str:
    """The class a changed path resolves to: the highest matched rule, else the default.

    This mirrors the intended classifier semantics (the production CLI is built on top of this in a
    later PR); it exists here so the money-path guarantees below are executable rather than asserted
    on token presence. ``fnmatchcase`` is deterministic across platforms; ``*`` spans ``/`` so
    ``core/**`` matches a nested file.
    """
    matched = [
        r["min_class"] for r in model["rules"] if fnmatch.fnmatchcase(path, r["glob"])
    ]
    if matched:  # an explicit rule always wins over the docs-only shortcut
        return str(max(matched, key=lambda c: _RANK[c]))
    if any(fnmatch.fnmatchcase(path, g) for g in model["docs_only_globs"]):
        return "R0"
    return str(model["default_min_class"])


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
    ("fail closed", (_CONSTITUTION, _CLAUDE)),  # safety default
    ("signal engine", (_CONSTITUTION, _CLAUDE)),  # the real parity boundary
    ("secret", (_CONSTITUTION, _CLAUDE)),  # secrets rule
    ("english", (_CONSTITUTION, _CLAUDE)),  # english-only repository
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
    ".ai/quality/finding-patterns.toml",
    "core/data/mt5_csv.py",  # data ingestion -> every result
    "pyproject.toml",  # pins the engine / bridge versions
    "uv.lock",
    "justfile",  # the gate commands
    ".github/workflows/ci.yml",  # runs the gates
    "docs/engineering/constitution.md",  # governance -- not a docs-only R0
    "docs/methodology.md",
    "CLAUDE.md",
    "AGENTS.md",
)


@pytest.mark.parametrize("path", _MUST_BE_R3, ids=lambda p: p)
def test_money_path_classifies_as_R3(path: str) -> None:
    assert (_ROOT / path).exists(), (
        f"the classification guard names {path}, which no longer exists -- update _MUST_BE_R3."
    )
    got = _classify(path, _model())
    assert got == "R3", (
        f"{path} classifies as {got}, not R3. A money / methodology / result-integrity path must "
        "not be able to reach a PR without the R3 gates and a human merge."
    )


#: A plain, non-governance document is R0; unmatched code is at least R2 (never R1 by default).
_CLASSIFY_CASES = (
    ("README.md", "R0"),
    ("docs/architecture.md", "R0"),
    ("docs/engineering/constitution.md", "R3"),  # governance overrides docs-only
    ("scripts/foo.py", "R1"),
    ("core/paths.py", "R2"),
    ("monitoring/dashboard.py", "R2"),
)


@pytest.mark.parametrize("path,expected", _CLASSIFY_CASES, ids=lambda v: v)
def test_classification_of_representative_paths(path: str, expected: str) -> None:
    assert _classify(path, _model()) == expected


def test_risk_doc_and_model_agree() -> None:
    doc = _text(_RISK_DOC)
    for cid in _CLASSES:
        assert cid in doc, f"{cid} is defined in the model but not documented in risk-classes.md"
    assert ".ai/quality/risk-classes.toml" in doc, "the doc must point at the model it describes"
    # The prose must NOT re-list the globs (they drift): the model is authoritative. Guard against
    # the specific stale form that already drifted once, and against re-introducing a raw glob list.
    assert "core/instruments/**" not in doc, "stale glob: the model uses core/instruments.py"
    assert "authoritative" in doc.lower(), "the doc must defer to the model as authoritative"
    # The distinctive R3-only obligations must be described, not just named -- so the prose cannot
    # drift into promising less than the model enforces.
    lowered = doc.lower()
    for concept in ("mutation", "adversarial", "live-money", "autonomous merge"):
        assert concept in lowered, f"risk-classes.md must describe the R3 obligation '{concept}'"


def test_direct_to_main_exception_is_R0_only_everywhere() -> None:
    """CLAUDE.md and the constitution must agree: only a trivial R0 change may skip the PR.

    Positive assertion, not just the absence of the old ``R0/R1`` spelling: each document must state
    that R0 (and not a broader class) is what may go straight to main.
    """
    for path in (_CLAUDE, _CONSTITUTION):
        lowered = _text(path).lower()
        assert "r0/r1" not in lowered, f"{path.relative_to(_ROOT)} still lets R1 reach main"
        assert "trivial r0" in lowered and "straight to `main`" in lowered, (
            f"{path.relative_to(_ROOT)} must state that only a trivial R0 change goes straight to "
            "main."
        )
