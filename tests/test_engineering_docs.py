"""The workflow document and the machine-readable contract must keep stating what they promise.

``docs/engineering/workflow.md`` is the single source of truth; ``CLAUDE.md`` and ``AGENTS.md`` are
short role documents that point to it, and ``.ai/workflow.toml`` is the same contract in the form
the tooling reads.

These guards do not compare the prose to the TOML -- that mirroring is exactly what drifted before.
They check the two things a merge of four documents into one can silently lose: a load-bearing
safety rule, and the classification of a money path.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest
from scripts.quality.classify import classify_path, load_model

_ROOT = Path(__file__).resolve().parents[1]
_CLAUDE = _ROOT / "CLAUDE.md"
_AGENTS = _ROOT / "AGENTS.md"
_WORKFLOW = _ROOT / "docs" / "engineering" / "workflow.md"
_CONTRACT = _ROOT / ".ai" / "workflow.toml"

_CLASSES = ("R0", "R1", "R2", "R3")


def _text(path: Path) -> str:
    assert path.is_file(), f"required engineering doc is missing: {path.relative_to(_ROOT)}"
    return path.read_text(encoding="utf-8")


def _class_of(path: str) -> str:
    """The class the PRODUCTION classifier assigns -- one implementation, so the model, the tooling
    and these guards cannot disagree."""
    return classify_path(path, load_model()).risk_class


# --------------------------------------------------------------- the role documents stay short
def test_role_documents_point_to_the_workflow() -> None:
    """Neither role document may become a second source of truth."""
    link = "docs/engineering/workflow.md"
    for path in (_CLAUDE, _AGENTS):
        assert link in _text(path), f"{path.name} must link to the workflow document"


def test_role_documents_stay_short() -> None:
    """A role document that grows back into a rulebook recreates the drift this merge removed."""
    for path in (_CLAUDE, _AGENTS):
        lines = len(_text(path).splitlines())
        assert lines <= 80, (
            f"{path.name} has grown to {lines} lines -- rules belong in the workflow document."
        )


# --------------------------------------------------------------- load-bearing rules stay stated
#: (phrase, files it must appear in). Kept to stable, load-bearing wording, not prose that will be
#: reworded. If a rule below is deliberately removed, this list is updated in the same change --
#: which is the point: dropping a safety rule cannot pass silently.
_REQUIRED: tuple[tuple[str, tuple[Path, ...]], ...] = (
    ("Co-Authored-By", (_WORKFLOW, _CLAUDE, _AGENTS)),
    ("float", (_WORKFLOW, _CLAUDE, _AGENTS)),
    ("holdout", (_WORKFLOW, _CLAUDE, _AGENTS)),
    ("0.18%", (_WORKFLOW, _CLAUDE, _AGENTS)),
    ("2.5%", (_WORKFLOW, _CLAUDE, _AGENTS)),
    ("Never touch a running live trade", (_WORKFLOW, _CLAUDE, _AGENTS)),
    ("two runners", (_WORKFLOW, _CLAUDE, _AGENTS)),
    ("fail closed", (_WORKFLOW, _CLAUDE, _AGENTS)),
    ("rsi_wpr_bb_signals", (_WORKFLOW, _CLAUDE, _AGENTS)),
    ("secret", (_WORKFLOW, _CLAUDE, _AGENTS)),
    ("english", (_WORKFLOW, _CLAUDE, _AGENTS)),
    ("out-of-sample", (_WORKFLOW, _CLAUDE, _AGENTS)),
    ("parity", (_WORKFLOW,)),
    ("lineage", (_WORKFLOW,)),
    ("net_r", (_WORKFLOW,)),
    ("constant basis", (_WORKFLOW,)),
    ("denominator", (_WORKFLOW,)),
    ("quiet window", (_WORKFLOW,)),
    ("squash merge", (_WORKFLOW,)),
    ("Never claim correctness without executable evidence", (_WORKFLOW,)),
    ("no gate may be weakened", (_WORKFLOW,)),
    ("feature branch", (_WORKFLOW,)),
    ("never red proves nothing", (_WORKFLOW,)),
)


@pytest.mark.parametrize("phrase,files", _REQUIRED, ids=lambda v: v if isinstance(v, str) else "")
def test_load_bearing_rule_is_stated(phrase: str, files: tuple[Path, ...]) -> None:
    for path in files:
        assert phrase.lower() in " ".join(_text(path).lower().split()), (
            f"'{phrase}' must appear in {path.relative_to(_ROOT)} -- a load-bearing rule went "
            "missing. If this was intentional, update _REQUIRED in the same change."
        )


def test_the_builder_and_reviewer_roles_stay_separated() -> None:
    """Claude never builds and Codex never reviews. Blurring the two removes the only independent
    check the workflow has."""
    workflow = " ".join(_text(_WORKFLOW).lower().split())
    assert "claude never builds" in workflow
    assert "codex never reviews" in workflow
    assert "there is no exception" in workflow
    assert "you never build" in " ".join(_text(_CLAUDE).lower().split())
    assert "you never review your own work" in " ".join(_text(_AGENTS).lower().split())


def test_governance_documents_name_no_person() -> None:
    """Documentation names the deciding human as 'the operator', never a person."""
    for path in (_WORKFLOW, _CLAUDE, _AGENTS, _CONTRACT):
        text = _text(path)
        assert not re.search(r"\bJan\b", text), (
            f"{path.relative_to(_ROOT)} names a person; the deciding human is 'the operator'."
        )
        assert "operator" in text.lower(), (
            f"{path.relative_to(_ROOT)} must name the deciding human as the operator"
        )


# --------------------------------------------------------------- the contract parses and holds
def test_risk_model_is_valid() -> None:
    contract = tomllib.loads(_text(_CONTRACT))
    model = contract["risk"]

    assert contract.get("version") == 2
    assert model.get("default_min_class") in _CLASSES
    assert model.get("docs_only_globs"), "docs-only globs must be defined for R0 detection"

    classes = model.get("classes", {})
    assert tuple(sorted(classes)) == _CLASSES, "exactly R0-R3 must be defined"
    for cid, spec in classes.items():
        assert spec.get("name"), f"{cid} needs a name"
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

    # Every gate a class requires must name the command that runs it.
    commands = contract["gates"]
    for cid, spec in classes.items():
        for gate in spec["gates"]:
            assert gate in commands, f"{cid} requires gate '{gate}' with no command defined"
            assert commands[gate].get("command"), f"gate '{gate}' needs a command"


def test_every_R3_live_money_path_is_in_the_model() -> None:
    """The money path must be classified R3 by matching, not left to a human's memory."""
    rules = tomllib.loads(_text(_CONTRACT))["risk"]["rules"]
    r3_globs = {r["glob"] for r in rules if r["min_class"] == "R3"}
    must_be_r3 = {
        "live/risk_control.py",
        "live/runner.py",
        "live/accounts.py",
        "live/mt5_bridge.py",
        "core/strategies/**",
        "core/broker.py",
        "research/regression.py",
        "research/portfolio/**",
        "research/engine/**",
        "research/stages/**",
    }
    missing = must_be_r3 - r3_globs
    assert not missing, f"these money/methodology paths must be R3 in the model: {sorted(missing)}"


#: Concrete production paths whose classification is safety-critical. Each MUST resolve to R3, and
#: each must still exist so the guard cannot rot into asserting on a deleted path.
_MUST_BE_R3 = (
    "live/risk_control.py",
    "live/runner.py",
    "live/accounts.py",
    "live/parity_check.py",  # signal parity
    "core/instruments.py",  # a file, not a package -- the dir glob never matched it
    "core/broker.py",
    "core/config/broker/ttp_markets_swaps.json",  # swap snapshot feeds swap_r
    "research/regression.py",
    "research/portfolio/trades.py",
    "research/portfolio/stats.py",  # per-trade R/swap attribution
    "research/portfolio/factsheet.py",  # reported results
    "research/portfolio/curves.py",  # equity/swap/holdout curves
    "research/engine/config.py",  # the config loader live shares -- parity
    "research/engine/overfitting.py",  # DSR/PBO selection-bias methodology
    "research/engine/schedule_builder.py",  # selected execution params and protective exits
    "research/stages/select.py",
    "core/data/mt5_csv.py",  # data ingestion -> every result
    ".ai/workflow.toml",  # the contract must not be able to weaken itself below R3
    "pyproject.toml",  # pins the engine / bridge versions
    "uv.lock",
    "justfile",  # the gate commands
    ".github/workflows/ci.yml",  # runs the gates
    ".claude/settings.json",  # project hooks gate every change
    ".claude/skills/specify-change/SKILL.md",  # executable workflow contract
    ".claude/agents/adversarial-code-reviewer.md",  # executable reviewer remit
    "docs/engineering/workflow.md",  # governance -- not a docs-only R0
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
    ("docs/engineering/workflow.md", "R3"),  # governance overrides docs-only
    ("scripts/foo.py", "R1"),
    ("core/paths.py", "R2"),
    ("monitoring/dashboard.py", "R2"),
    ("tests/test_live_runner_cycle.py", "R2"),  # a deleted guard must be reviewed
)


@pytest.mark.parametrize("path,expected", _CLASSIFY_CASES, ids=lambda v: v)
def test_classification_of_representative_paths(path: str, expected: str) -> None:
    assert _class_of(path) == expected
