"""The workflow documents are deterministic views of one machine-readable contract.

Earlier guards parsed selected prose back into facts. Independent review repeatedly demonstrated
that extra rows, duplicate rules, neighbouring contradictions, and synonymous inversions survived
those parsers. The TOML model is now authoritative. Generated blocks must reproduce it, and a
skeleton digest rejects hand-written contract rules anywhere else in the governed documents.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest
from scripts.quality.workflow_contract import (
    CONTRACT_PATH,
    WorkflowContract,
    check_documents,
    load_contract,
    render_document,
)

_ROOT = Path(__file__).resolve().parents[1]
_WORKFLOW = Path("docs/engineering/workflow.md")
_CONSTITUTION = Path("docs/engineering/constitution.md")
_AGENTS = Path("AGENTS.md")
_CLAUDE = Path("CLAUDE.md")
_CONTRACT_DOCUMENTS = (_WORKFLOW, _CONSTITUTION, _AGENTS, _CLAUDE)

# These required sets deliberately live in the test, outside the contract they constrain. A
# contract edit therefore cannot make a missing or invented record authorize itself.
_REQUIRED_STATUSES = frozenset(
    {
        ("Backlog", "A raw idea. One sentence is enough.", "Project automation (auto-add)"),
        (
            "Specifying",
            "Claude is working the idea into a specification with Jan.",
            "Claude",
        ),
        (
            "Ready to Implement",
            'Approved by Jan. Codex **may** build it — not "build it now".',
            "Claude, after Jan's explicit approval",
        ),
        ("Implementing", "Codex is building.", "Codex"),
        (
            "Reviewing",
            "The change is with the independent reviewer on the draft pull request.",
            "Codex, at handover",
        ),
        (
            "Blocked",
            "Waiting on a decision only Jan can make (constitution §13).",
            "Any agent",
        ),
        ("Done", "Merged.", "Project automation (item closed)"),
    }
)
_REQUIRED_TRANSITIONS = frozenset(
    {
        ("-", "Backlog", "project automation", "an issue is opened"),
        ("Backlog", "Specifying", "Claude", "Jan asks for the idea to be worked out"),
        ("Blocked", "Specifying", "Claude", "Jan decided"),
        (
            "Specifying",
            "Backlog",
            "Claude",
            "Jan defers the idea; the specification is kept",
        ),
        (
            "Specifying",
            "Ready to Implement",
            "Claude",
            "Jan approves; `approved` is written last",
        ),
        (
            "Ready to Implement",
            "Specifying",
            "Claude",
            "an approved issue must change; `approved` is removed first",
        ),
        (
            "Ready to Implement",
            "Implementing",
            "Codex",
            "build starts; `approved` is removed afterwards",
        ),
        (
            "Implementing",
            "Reviewing",
            "Codex",
            "the draft pull request is opened and handed over for review",
        ),
        ("Reviewing", "Implementing", "Claude", "a blocking finding"),
        ("Implementing", "Reviewing", "Codex", "the review fix is pushed"),
        (
            "Implementing",
            "Specifying",
            "Codex",
            "the specification is wrong, incomplete or unbuildable",
        ),
        (
            "Specifying",
            "Blocked",
            "Claude",
            "a decision only Jan can make is open",
        ),
        (
            "Ready to Implement",
            "Blocked",
            "any agent",
            "a decision only Jan can make is open",
        ),
        (
            "Implementing",
            "Blocked",
            "any agent",
            "a decision only Jan can make is open",
        ),
        (
            "Reviewing",
            "Blocked",
            "any agent",
            "a decision only Jan can make is open",
        ),
        (
            "Reviewing",
            "Done",
            "project automation",
            "the pull request merged and closed the issue",
        ),
    }
)
_REQUIRED_ACTIVATIONS: frozenset[tuple[str, int]] = frozenset()


def _normalize(text: str) -> str:
    return " ".join(text.split())


def test_workflow_contract_toml_is_valid_and_complete() -> None:
    """The source model carries every fact required by issue #107."""
    contract = load_contract()
    assert contract.statuses
    assert {guard.name for guard in contract.builder_guards} == {"Start", "Resume"}
    assert contract.transitions
    assert contract.activations == ()
    assert contract.gate_rule.relation == "minimum"
    assert contract.gate_rule.additional_scoped_checks
    assert contract.ready_for_review.initial_pull_request_state == "draft"
    assert contract.ready_for_review.requires_clean_independent_review
    assert contract.ready_for_review.requires_readiness_check
    assert contract.approval_steps[-1].action == "add approved"
    assert contract.approval_steps[-1].approved_written_last


def test_declared_statuses_exactly_match_required_records() -> None:
    """Every status fact is independently pinned in both directions."""
    contract = load_contract()
    declared = {(row.name, row.meaning, row.actor) for row in contract.statuses}
    assert declared == _REQUIRED_STATUSES, (
        f"missing={sorted(_REQUIRED_STATUSES - declared)}\n"
        f"unauthorized={sorted(declared - _REQUIRED_STATUSES)}"
    )


def test_declared_transitions_exactly_match_required_records() -> None:
    """Every complete transition fact is independently pinned in both directions."""
    contract = load_contract()
    declared = {(row.source, row.target, row.actor, row.trigger) for row in contract.transitions}
    assert declared == _REQUIRED_TRANSITIONS, (
        f"missing={sorted(_REQUIRED_TRANSITIONS - declared)}\n"
        f"unauthorized={sorted(declared - _REQUIRED_TRANSITIONS)}"
    )


def test_every_registered_activation_is_declared() -> None:
    """The declared activation registry is exact: no row may vanish or self-register."""
    contract = load_contract()
    declared = {(row.capability, row.issue) for row in contract.activations}
    assert declared == _REQUIRED_ACTIVATIONS, (
        f"missing={sorted(_REQUIRED_ACTIVATIONS - declared)}\n"
        f"unregistered={sorted(declared - _REQUIRED_ACTIVATIONS)}"
    )


def test_empty_activation_register_renders_and_validates(tmp_path: Path) -> None:
    """The combined #110/#112 end state is a valid empty generated table."""
    source = CONTRACT_PATH.read_text(encoding="utf-8")
    without_activations = re.sub(
        r"\n\[\[activation\]\]\n.*?(?=\n\[\[|\Z)",
        "",
        source,
        flags=re.DOTALL,
    )
    path = tmp_path / "workflow-contract.toml"
    path.write_text(without_activations, encoding="utf-8")
    contract = load_contract(path)
    assert contract.activations == ()
    rendered = render_document(
        _WORKFLOW,
        (_ROOT / _WORKFLOW).read_text(encoding="utf-8"),
        contract,
    )
    block = rendered.split("<!-- workflow-contract:activations:start -->", 1)[1].split(
        "<!-- workflow-contract:activations:end -->",
        1,
    )[0]
    assert "| Part of this contract | Lands with | Until then |" in block
    assert "[#" not in block


def test_workflow_contract_rejects_a_malformed_document_digest(tmp_path: Path) -> None:
    """Digest chunking avoids secret false positives without weakening integrity validation."""
    source = CONTRACT_PATH.read_text(encoding="utf-8")
    malformed, count = re.subn(
        r"(?m)^workflow = \[\d+",
        "workflow = [999",
        source,
        count=1,
    )
    assert count == 1
    path = tmp_path / "workflow-contract.toml"
    path.write_text(malformed, encoding="utf-8")
    with pytest.raises(ValueError, match="integers from 0 through 255"):
        load_contract(path)


def test_workflow_documents_match_the_machine_contract() -> None:
    """Regenerate and compare: any generated or hand-written drift is a failure."""
    assert check_documents() == ()


def test_rendering_emits_every_machine_contract_record() -> None:
    """A renderer may not silently omit a TOML record or one of its cells."""
    contract = load_contract()
    workflow_source = (_ROOT / _WORKFLOW).read_text(encoding="utf-8")
    workflow = _normalize(render_document(_WORKFLOW, workflow_source, contract))
    agents_source = (_ROOT / _AGENTS).read_text(encoding="utf-8")
    agents = _normalize(render_document(_AGENTS, agents_source, contract))
    claude_source = (_ROOT / _CLAUDE).read_text(encoding="utf-8")
    claude = _normalize(render_document(_CLAUDE, claude_source, contract))

    for status in contract.statuses:
        for value in (status.name, status.meaning, status.actor):
            assert _normalize(value) in workflow
    for transition in contract.transitions:
        for value in (transition.source, transition.target, transition.actor, transition.trigger):
            rendered_value = "—" if value == "-" else value
            assert _normalize(rendered_value) in workflow
    for guard in contract.builder_guards:
        assert _normalize(guard.name) in workflow
        for value in (guard.condition, guard.action):
            normalized = _normalize(value)
            assert normalized in workflow
            assert normalized in agents
    for activation in contract.activations:
        for value in (activation.capability, str(activation.issue), activation.fallback):
            assert _normalize(value) in workflow
    for step in contract.approval_steps:
        assert _normalize(step.action) in workflow
        assert _normalize(step.action) in claude


def test_no_role_document_says_builder_opens_ready_pull_request() -> None:
    """Round-one Defect F3 remains a permanent negative and positive protection."""
    forbidden = "opens the ready pull request"
    for relative in (_CONSTITUTION, _AGENTS, _CLAUDE):
        raw = (_ROOT / relative).read_text(encoding="utf-8")
        text = re.sub(r"[*_`]", "", raw).casefold()
        assert forbidden not in text, f"{relative} reintroduced the superseded ready-PR role"

    contract = load_contract()
    assert contract.ready_for_review.initial_pull_request_state == "draft"
    assert contract.ready_for_review.requires_clean_independent_review
    assert contract.ready_for_review.requires_readiness_check


def _replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"counterexample anchor missing in {path}: {old!r}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _counterexample_repository(tmp_path: Path) -> dict[str, Path]:
    copied: dict[str, Path] = {}
    for relative in (*_CONTRACT_DOCUMENTS, CONTRACT_PATH.relative_to(_ROOT)):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_ROOT / relative, destination)
        copied[relative.as_posix()] = destination
    return copied


def _render_counterexample_documents(
    paths: dict[str, Path],
    contract: WorkflowContract,
) -> None:
    for relative in _CONTRACT_DOCUMENTS:
        path = paths[relative.as_posix()]
        source = path.read_text(encoding="utf-8")
        path.write_text(render_document(relative, source, contract), encoding="utf-8")


def _apply_counterexample(name: str, paths: dict[str, Path]) -> None:
    workflow = paths[_WORKFLOW.as_posix()]
    constitution = paths[_CONSTITUTION.as_posix()]
    agents = paths[_AGENTS.as_posix()]
    contract = paths[CONTRACT_PATH.relative_to(_ROOT).as_posix()]

    if name == "start-allows-missing-permit":
        _replace_once(agents, "`approved` present", "`approved` absent")
        _replace_once(workflow, "`approved` present", "`approved` absent")
    elif name == "ready-before-review-with-synonym":
        _replace_once(
            workflow,
            "Once the independent review is clean and the readiness check passes for current "
            "HEAD, Codex marks it **ready for review**.",
            "Before review begins, Codex changes the pull request from draft to "
            "**ready for review**.",
        )
    elif name == "gate-ceiling-with-unlisted-phrase":
        _replace_once(
            workflow,
            "at least those of the risk class, plus any scoped check that applies",
            "at least those of the risk class; additional scoped checks are forbidden",
        )
    elif name == "review-fix-owned-by-wrong-actor":
        _replace_once(
            workflow,
            "| `Implementing` → `Reviewing` | Codex | the review fix is pushed |",
            "| `Implementing` → `Reviewing` | Claude | the review fix is pushed |",
        )
    elif name == "unauthorized-extra-transition":
        _replace_once(
            workflow,
            "| `Reviewing` → `Done` | project automation | "
            "the pull request merged and closed the issue |",
            "| `Backlog` → `Done` | project automation | the issue is skipped |\n"
            "| `Reviewing` → `Done` | project automation | "
            "the pull request merged and closed the issue |",
        )
    elif name == "constitution-forbids-branch-review":
        _replace_once(
            constitution,
            "only after that review and its remediation are complete",
            "before that review and its remediation are complete",
        )
    elif name == "third-force-builder-guard-row":
        _replace_once(
            workflow,
            "| **Start** | card in `Ready to Implement`, `approved` present, `risk:Rn` present |",
            "| **Force** | any card and any branch | start without a permit |\n"
            "| **Start** | card in `Ready to Implement`, `approved` present, `risk:Rn` present |",
        )
    elif name == "third-agent-bullet-allows-unpermitted-start":
        _replace_once(
            agents,
            "Any other combination is a refusal:",
            "- **Emergency start.** Start without `approved` whenever the branch is local.\n\n"
            "Any other combination is a refusal:",
        )
    elif name == "duplicate-start-row-before-real-row":
        _replace_once(
            workflow,
            "| **Start** | card in `Ready to Implement`, `approved` present, `risk:Rn` present |",
            "| **Start** | card in `Backlog`, `approved` absent | start immediately |\n"
            "| **Start** | card in `Ready to Implement`, `approved` present, `risk:Rn` present |",
        )
    elif name == "second-state-transition-table":
        _replace_once(
            workflow,
            "`Done` is terminal:",
            "| From → To | Who | When |\n"
            "|---|---|---|\n"
            "| `Backlog` → `Done` | Codex | skip every gate |\n\n"
            "`Done` is terminal:",
        )
    elif name == "done-board-row-declares-nonterminal":
        _replace_once(
            workflow,
            "| `Done` | Merged. | Project automation (item closed) |",
            "| `Done` | Merged, but Codex may resume it. | Codex |",
        )
    elif name == "gate-ceiling-in-neighbouring-paragraph":
        _replace_once(
            workflow,
            "Step 3 carries the whole system:",
            "No additional check may run beyond the risk-class list.\n\n"
            "Step 3 carries the whole system:",
        )
    elif name == "constitution-reintroduces-ready-pr-opening":
        _replace_once(
            constitution,
            "opens the **draft** pull request that the independent review runs on",
            "opens the ready pull request that the independent review runs on",
        )
    elif name == "agents-reintroduces-ready-pr-opening":
        _replace_once(
            agents,
            "opens the **draft** pull request\nat the point the active workflow permits",
            "opens the ready pull request\nat the point the active workflow permits",
        )
    elif name == "missing-review-return-transition":
        _replace_once(
            contract,
            "[[transition]]\n"
            'source = "Reviewing"\n'
            'target = "Implementing"\n'
            'actor = "Claude"\n'
            'trigger = "a blocking finding"\n\n',
            "",
        )
    elif name == "unauthorized-backlog-done-contract-transition":
        with contract.open("a", encoding="utf-8") as stream:
            stream.write(
                "\n[[transition]]\n"
                'source = "Backlog"\n'
                'target = "Done"\n'
                'actor = "any agent"\n'
                'trigger = "the change looks small enough"\n'
            )
    elif name == "approval-transition-loses-jan-trigger":
        _replace_once(
            contract,
            'trigger = "Jan approves; `approved` is written last"',
            'trigger = "the specification is complete"',
        )
    elif name == "ready-status-loses-jan-approval-actor":
        _replace_once(
            contract,
            'actor = "Claude, after Jan\'s explicit approval"',
            'actor = "Claude"',
        )
    else:
        raise AssertionError(f"unknown counterexample: {name}")


_COUNTEREXAMPLES = (
    "start-allows-missing-permit",
    "ready-before-review-with-synonym",
    "gate-ceiling-with-unlisted-phrase",
    "review-fix-owned-by-wrong-actor",
    "unauthorized-extra-transition",
    "constitution-forbids-branch-review",
    "third-force-builder-guard-row",
    "third-agent-bullet-allows-unpermitted-start",
    "duplicate-start-row-before-real-row",
    "second-state-transition-table",
    "done-board-row-declares-nonterminal",
    "gate-ceiling-in-neighbouring-paragraph",
    "constitution-reintroduces-ready-pr-opening",
    "agents-reintroduces-ready-pr-opening",
    "missing-review-return-transition",
    "unauthorized-backlog-done-contract-transition",
    "approval-transition-loses-jan-trigger",
    "ready-status-loses-jan-approval-actor",
)
_CONTRACT_RECORD_COUNTEREXAMPLES = frozenset(
    {
        "missing-review-return-transition",
        "unauthorized-backlog-done-contract-transition",
        "approval-transition-loses-jan-trigger",
        "ready-status-loses-jan-approval-actor",
    }
)


@pytest.mark.parametrize("counterexample", _COUNTEREXAMPLES)
def test_contract_rendering_rejects_semantic_counterexample(
    tmp_path: Path,
    counterexample: str,
) -> None:
    """Every supplied semantic violation must become generated-document drift."""
    paths = _counterexample_repository(tmp_path)
    _apply_counterexample(counterexample, paths)
    contract = load_contract(paths[CONTRACT_PATH.relative_to(_ROOT).as_posix()])
    if counterexample in _CONTRACT_RECORD_COUNTEREXAMPLES:
        _render_counterexample_documents(paths, contract)

    declared_statuses = {(row.name, row.meaning, row.actor) for row in contract.statuses}
    declared_transitions = {
        (row.source, row.target, row.actor, row.trigger) for row in contract.transitions
    }
    declared_activations = {(row.capability, row.issue) for row in contract.activations}
    totality_errors = (
        declared_statuses != _REQUIRED_STATUSES
        or declared_transitions != _REQUIRED_TRANSITIONS
        or declared_activations != _REQUIRED_ACTIVATIONS
    )
    assert check_documents(tmp_path, contract) or totality_errors, (
        f"the machine contract accepted semantic counterexample {counterexample!r}"
    )
