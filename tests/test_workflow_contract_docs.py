"""The workflow document and the machine-readable contract must keep stating what they promise.

``workflow/workflow.md`` is the single source of truth; ``CLAUDE.md`` and ``AGENTS.md`` are short
role documents that point to it, and ``workflow/workflow.toml`` is the same contract in the form the
tooling reads.

These guards do not compare the prose to the TOML -- that mirroring is exactly what drifted before.
They check the two things a merge of four documents into one can silently lose: a load-bearing
safety rule, and the classification of a money path.
"""

from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path

import pytest
from workflow.classify import classify_path, load_model

_ROOT = Path(__file__).resolve().parents[1]
_CLAUDE = _ROOT / "CLAUDE.md"
_AGENTS = _ROOT / "AGENTS.md"
_WORKFLOW = _ROOT / "workflow" / "workflow.md"
_CONTRACT = _ROOT / "workflow" / "workflow.toml"
_CI = _ROOT / ".github" / "workflows" / "ci.yml"

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
    link = "workflow/workflow.md"
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
    ("depends on another ticket", (_WORKFLOW,)),
    ("lean is the default", (_WORKFLOW,)),
    ("a specification fits on one page", (_WORKFLOW,)),
    ("ready for review, never as a draft", (_WORKFLOW,)),
    ("the builder starts the cycle", (_WORKFLOW,)),
    ("the operator can always start it by hand", (_WORKFLOW,)),
    ("proportionate to the diff", (_WORKFLOW,)),
    ("a review reports; it does not file", (_WORKFLOW,)),
    ("reports to the operator closes in german", (_WORKFLOW,)),
    ("a decision the operator must take is set off visibly", (_WORKFLOW,)),
    ("evidence never overlaps", (_WORKFLOW,)),
    ("mutation is measured once per ticket", (_WORKFLOW,)),
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


def test_ready_to_implement_never_holds_work_that_cannot_start() -> None:
    """`Ready to Implement` is a supply a builder may draw from now. A ticket that would have to
    wait for another ticket belongs in `Blocked`, or the column stops meaning anything."""
    workflow = " ".join(_text(_WORKFLOW).lower().split())
    assert "a builder may start *now*" in workflow or "may start *now*" in workflow
    assert "depends on another ticket" in workflow

    contract = tomllib.loads(_text(_CONTRACT))["board"]
    to_blocked = [t for t in contract["transitions"] if t["to"] == "Blocked"]
    assert to_blocked, "there must be a way into Blocked"
    assert any("another ticket" in t["trigger"] for t in to_blocked), (
        "at least one route into Blocked must cover a dependency, not only an operator decision"
    )
    # Coming back after a specification decision re-runs the release, because what the ticket
    # waited for has since changed. A mechanical stop in the build — the round cap, a hand-back
    # that never started — continues on the operator's word without a re-release: round three
    # proved that forcing a re-specification nobody wanted was the only legal exit, and round
    # five added the third way on: one more round for the capped cycle itself.
    exits = {t["to"]: t for t in contract["transitions"] if t["from"] == "Blocked"}
    assert set(exits) == {"Specifying", "Implementing", "Reviewing"}, (
        "Blocked has exactly three ways on: the release, the build, or one more round"
    )
    assert exits["Implementing"]["actor"] == "codex"
    assert "operator decided" in exits["Implementing"]["trigger"], (
        "the build continues only on the operator's decision, never on the guard's own"
    )
    assert exits["Reviewing"]["actor"] == "orchestrator"
    assert "operator decided" in exits["Reviewing"]["trigger"], (
        "one more round is granted by the operator, never taken by the cycle itself"
    )


def test_the_carve_out_cannot_take_the_lean_lane() -> None:
    """The lean lane cuts ceremony, never safety. One wrong line on these paths costs real money,
    so they get the full program at any diff size — this is the load-bearing half of the lane
    design, and the ticket that introduced it is not done unless this cannot regress."""
    from workflow.classify import load_review_scope, needs_full_review

    scope = load_review_scope()
    assert scope.full_min_changed_lines > 0

    always_full = (
        "live/risk_control.py",  # the risk limits
        "live/runner.py",  # sizing and order placement
        "live/mt5_bridge.py",  # the broker bridge
        "live/accounts.py",  # account identity
        "core/broker.py",  # money conversion
        "core/strategies/rsi_wpr_bb_signals.py",  # the shared signal engine
        "research/portfolio/sizing.py",  # research sizing
        "research/stages/select.py",  # selection and holdout
        "workflow/classify.py",  # the classifier itself
        "workflow/workflow.toml",  # the contract that defines this very boundary
    )
    for path in always_full:
        assert needs_full_review([path], 1, scope), (
            f"{path} took the lean lane — a money path must always get the full program"
        )

    # The lane exists for exactly this case: a small change somewhere ordinary.
    assert not needs_full_review(["docs/roadmap.md"], 5, scope)
    assert not needs_full_review(["monitoring/dashboard.py"], 50, scope)

    # And size alone escalates, whatever the path.
    assert needs_full_review(["docs/roadmap.md"], scope.full_min_changed_lines, scope)


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


def test_the_document_and_ci_agree_on_the_runner() -> None:
    """The CI contract names the configured runner and its isolation limits in one place."""
    runner_variables = set(re.findall(r"vars\.([A-Z][A-Z0-9_]*)", _text(_CI)))
    assert runner_variables == {"CI_LINUX_RUNNER"}

    workflow = " ".join(_text(_WORKFLOW).split())
    assert "CI_LINUX_RUNNER" in workflow
    for limit in (
        "holds no `.env`",
        "holds no broker credentials",
        "does not run as an administrator",
        "does not run on the trading machine",
    ):
        assert limit in workflow


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
    "workflow/workflow.toml",  # the contract must not be able to weaken itself below R3
    "pyproject.toml",  # pins the engine / bridge versions
    "uv.lock",
    "justfile",  # the gate commands
    ".github/workflows/ci.yml",  # runs the gates
    ".claude/settings.json",  # project hooks gate every change
    ".claude/skills/specify-change/SKILL.md",  # executable workflow contract
    ".claude/agents/adversarial-code-reviewer.md",  # executable reviewer remit
    "workflow/workflow.md",  # governance -- not a docs-only R0
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
    ("workflow/workflow.md", "R3"),  # the contract governs every other change
    ("workflow/classify.py", "R3"),
    ("core/paths.py", "R2"),
    ("monitoring/dashboard.py", "R2"),
    ("tests/test_live_runner_cycle.py", "R2"),  # a deleted guard must be reviewed
)


@pytest.mark.parametrize("path,expected", _CLASSIFY_CASES, ids=lambda v: v)
def test_classification_of_representative_paths(path: str, expected: str) -> None:
    assert _class_of(path) == expected


def test_every_workflow_subprocess_decode_names_utf8() -> None:
    """`gh` and `git` answer in UTF-8 on every platform; ``text=True`` without an encoding
    decodes with the platform codec instead. On Windows that is cp1252: the reader thread died
    on the first typographic quote inside a review body, and ``subprocess.run`` returned *empty
    text with returncode 0* -- the cycle then read a posted, well-formed verdict as "no verdict
    at all" (#186). Fail-open at the loop's one exit condition, so the decode is pinned at the
    source for every present and future call site under ``workflow/``."""

    offenders: list[str] = []
    for path in sorted((_ROOT / "workflow").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            is_spawn = (
                isinstance(func, ast.Attribute)
                and func.attr in {"run", "Popen", "check_output"}
                and isinstance(func.value, ast.Name)
                and func.value.id == "subprocess"
            )
            if not is_spawn:
                continue
            keywords = {keyword.arg for keyword in node.keywords}
            if ("text" in keywords or "universal_newlines" in keywords) and (
                "encoding" not in keywords
            ):
                offenders.append(f"{path.relative_to(_ROOT)}:{node.lineno}")
    assert not offenders, (
        "these subprocess calls decode with the platform codec; on Windows one typographic "
        f"quote returns empty text with returncode 0: {offenders}"
    )


def test_the_document_states_what_protects_main_and_what_does_not() -> None:
    document = _text(_WORKFLOW).lower()
    match = re.search(
        r"^### main branch protection\s+(?P<section>.*?)(?=^### |^## )",
        document,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match is not None, "the main-branch protection section is missing"
    section = " ".join(match.group("section").split())

    assert "enforces all four rules only while this is a public repository" in section
    assert "does not enforce them while this is a private repository" in section
    assert "resumes enforcing all four rules when the repository is public again" in section
    assert "git push --no-verify` can skip it" in section
    assert "squash-only merging and no merge while `required-checks` is red" in section
    assert "have no local equivalent" in section
    assert "a checkout on a revision that predates the tracked hook is not protected" in section
    assert "rerunning `just install-hooks` cannot add content absent from that revision" in section
