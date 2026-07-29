"""Load and render the machine-readable engineering workflow contract.

The contract facts live in ``.ai/quality/workflow-contract.toml``. Markdown is a generated view:
the renderer owns each contract block, while a skeleton digest detects hand-written rules inserted
outside those blocks. This is deliberately narrow tooling for the repository's workflow documents,
not a general documentation generator.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import tomllib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from scripts.quality.classify import REPO_ROOT

CONTRACT_PATH = REPO_ROOT / ".ai" / "quality" / "workflow-contract.toml"

_WORKFLOW = Path("docs/engineering/workflow.md")
_AGENTS = Path("AGENTS.md")
_CLAUDE = Path("CLAUDE.md")
_CONSTITUTION = Path("docs/engineering/constitution.md")

_BLOCKS_BY_DOCUMENT: dict[Path, tuple[str, ...]] = {
    _WORKFLOW: (
        "statuses",
        "approval-order",
        "builder-guard",
        "build-sequence",
        "ready-order",
        "transitions",
        "activations",
    ),
    _AGENTS: ("builder-guard", "review-handover"),
    _CLAUDE: ("approval-order",),
    _CONSTITUTION: ("pr-order",),
}


@dataclass(frozen=True)
class Status:
    """One board status and its operator-facing meaning."""

    name: str
    meaning: str
    actor: str


@dataclass(frozen=True)
class BuilderGuard:
    """One complete condition/action tuple at the builder boundary."""

    name: str
    condition: str
    action: str


@dataclass(frozen=True)
class ApprovalStep:
    """One ordered approval action."""

    order: int
    action: str
    approved_written_last: bool


@dataclass(frozen=True)
class Transition:
    """One complete workflow transition."""

    source: str
    target: str
    actor: str
    trigger: str


@dataclass(frozen=True)
class Activation:
    """One unavailable capability, its owner, and its current fallback."""

    capability: str
    issue: int
    fallback: str


@dataclass(frozen=True)
class GateRule:
    """The lower-bound rule for verification gates."""

    relation: str
    scope: str
    additional_scoped_checks: bool


@dataclass(frozen=True)
class ReadyForReview:
    """The ordered fact that separates a draft from a mergeable pull request."""

    actor: str
    initial_pull_request_state: str
    requires_clean_independent_review: bool
    requires_readiness_check: bool
    merge_decider: str


@dataclass(frozen=True)
class WorkflowContract:
    """All machine-authoritative workflow facts."""

    statuses: tuple[Status, ...]
    builder_guards: tuple[BuilderGuard, ...]
    approval_steps: tuple[ApprovalStep, ...]
    transitions: tuple[Transition, ...]
    activations: tuple[Activation, ...]
    gate_rule: GateRule
    ready_for_review: ReadyForReview
    document_hashes: Mapping[str, str]


def _mapping(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a TOML table")
    return cast(dict[str, object], value)


def _tables(data: Mapping[str, object], field: str) -> tuple[dict[str, object], ...]:
    value = data.get(field)
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field} must be a non-empty TOML table array")
    return tuple(_mapping(row, f"{field}[]") for row in value)


def _string(data: Mapping[str, object], field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _integer(data: Mapping[str, object], field: str) -> int:
    value = data.get(field)
    if type(value) is not int:
        raise ValueError(f"{field} must be an integer")
    return value


def _boolean(data: Mapping[str, object], field: str, *, default: bool = False) -> bool:
    value = data.get(field, default)
    if type(value) is not bool:
        raise ValueError(f"{field} must be a boolean")
    return value


def _digest(data: Mapping[str, object], field: str) -> str:
    value = data.get(field)
    if not isinstance(value, list) or len(value) != 32:
        raise ValueError(f"{field} must contain the 32 bytes of one SHA-256 digest")
    octets = cast(list[object], value)
    if not all(type(octet) is int and 0 <= octet <= 255 for octet in octets):
        raise ValueError(f"{field} SHA-256 bytes must be integers from 0 through 255")
    return bytes(cast(list[int], octets)).hex()


def load_contract(path: Path = CONTRACT_PATH) -> WorkflowContract:
    """Load and fail closed on an incomplete or internally inconsistent contract."""
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    data = cast(dict[str, object], raw)
    if _integer(data, "version") != 1:
        raise ValueError("workflow contract version must be 1")

    statuses = tuple(
        Status(_string(row, "name"), _string(row, "meaning"), _string(row, "actor"))
        for row in _tables(data, "status")
    )
    guards = tuple(
        BuilderGuard(_string(row, "name"), _string(row, "condition"), _string(row, "action"))
        for row in _tables(data, "builder_guard")
    )
    approval_steps = tuple(
        ApprovalStep(
            _integer(row, "order"),
            _string(row, "action"),
            _boolean(row, "approved_written_last"),
        )
        for row in _tables(data, "approval_step")
    )
    transitions = tuple(
        Transition(
            _string(row, "source"),
            _string(row, "target"),
            _string(row, "actor"),
            _string(row, "trigger"),
        )
        for row in _tables(data, "transition")
    )
    activations = tuple(
        Activation(
            _string(row, "capability"),
            _integer(row, "issue"),
            _string(row, "fallback"),
        )
        for row in _tables(data, "activation")
    )

    gate = _mapping(data.get("gate_rule"), "gate_rule")
    ready = _mapping(data.get("ready_for_review"), "ready_for_review")
    hash_data = _mapping(data.get("document_hashes"), "document_hashes")
    document_hashes = {
        key: _digest(hash_data, key) for key in ("workflow", "agents", "claude", "constitution")
    }

    contract = WorkflowContract(
        statuses=statuses,
        builder_guards=guards,
        approval_steps=approval_steps,
        transitions=transitions,
        activations=activations,
        gate_rule=GateRule(
            _string(gate, "relation"),
            _string(gate, "scope"),
            _boolean(gate, "additional_scoped_checks"),
        ),
        ready_for_review=ReadyForReview(
            _string(ready, "actor"),
            _string(ready, "initial_pull_request_state"),
            _boolean(ready, "requires_clean_independent_review"),
            _boolean(ready, "requires_readiness_check"),
            _string(ready, "merge_decider"),
        ),
        document_hashes=document_hashes,
    )
    _validate_contract(contract)
    return contract


def _validate_contract(contract: WorkflowContract) -> None:
    status_names = [status.name for status in contract.statuses]
    if len(status_names) != len(set(status_names)):
        raise ValueError("workflow statuses must be unique")
    if {guard.name for guard in contract.builder_guards} != {"Start", "Resume"}:
        raise ValueError("builder_guard must contain exactly Start and Resume")

    ordered_steps = sorted(contract.approval_steps, key=lambda step: step.order)
    if [step.order for step in ordered_steps] != list(range(1, len(ordered_steps) + 1)):
        raise ValueError("approval_step order must be contiguous and start at 1")
    last_markers = [step.order for step in ordered_steps if step.approved_written_last]
    if last_markers != [ordered_steps[-1].order] or ordered_steps[-1].action != "add approved":
        raise ValueError("approved must be the final approval step")

    status_set = set(status_names)
    facts = [(item.source, item.target, item.actor, item.trigger) for item in contract.transitions]
    if len(facts) != len(set(facts)):
        raise ValueError("workflow transitions must be unique complete records")
    for transition in contract.transitions:
        if transition.source != "-" and transition.source not in status_set:
            raise ValueError(f"unknown transition source: {transition.source}")
        if transition.target not in status_set:
            raise ValueError(f"unknown transition target: {transition.target}")
    if any(transition.source == "Done" for transition in contract.transitions):
        raise ValueError("Done must remain terminal")

    if contract.gate_rule.relation != "minimum":
        raise ValueError("gate_rule.relation must remain minimum")
    if not contract.gate_rule.additional_scoped_checks:
        raise ValueError("gate_rule must allow every applicable scoped check")
    if contract.ready_for_review.initial_pull_request_state != "draft":
        raise ValueError("independent review must begin from a draft pull request")
    if not (
        contract.ready_for_review.requires_clean_independent_review
        and contract.ready_for_review.requires_readiness_check
    ):
        raise ValueError("ready-for-review requires both clean review and readiness")


def _start_marker(name: str) -> str:
    return f"<!-- workflow-contract:{name}:start -->"


def _end_marker(name: str) -> str:
    return f"<!-- workflow-contract:{name}:end -->"


def _replace_block(text: str, name: str, body: str) -> str:
    start = re.escape(_start_marker(name))
    end = re.escape(_end_marker(name))
    pattern = re.compile(rf"{start}\n.*?\n{end}", re.DOTALL)
    replacement = f"{_start_marker(name)}\n{body.rstrip()}\n{_end_marker(name)}"
    rendered, count = pattern.subn(lambda _: replacement, text)
    if count != 1:
        raise ValueError(f"document must contain exactly one generated block {name!r}")
    return rendered


def _render_statuses(contract: WorkflowContract) -> str:
    lines = ["| Status | Meaning | Who sets it |", "|---|---|---|"]
    lines.extend(
        f"| `{status.name}` | {status.meaning} | {status.actor} |" for status in contract.statuses
    )
    return "\n".join(lines)


def _render_approval_order(contract: WorkflowContract) -> str:
    lines = ["```"]
    for step in sorted(contract.approval_steps, key=lambda item: item.order):
        suffix = "          ← last" if step.approved_written_last else ""
        lines.append(f"{step.order}  {step.action}{suffix}")
    lines.append("```")
    return "\n".join(lines)


def _render_builder_guard(contract: WorkflowContract) -> str:
    lines = ["| Case | Condition | Then |", "|---|---|---|"]
    lines.extend(
        f"| **{guard.name}** | {guard.condition} | {guard.action} |"
        for guard in contract.builder_guards
    )
    return "\n".join(lines)


def _render_build_sequence(contract: WorkflowContract) -> str:
    gate = contract.gate_rule
    if (gate.relation, gate.scope, gate.additional_scoped_checks) != (
        "minimum",
        "risk class",
        True,
    ):
        raise ValueError("unsupported gate rendering facts")
    return "\n".join(
        (
            "```",
            "1  Impact          what depends on this? which tests are affected?",
            "2  Test plan       every AC-nn and INV-nn → exactly one named test",
            "3  Prove RED       write the test, run it, record the failure",
            "4  Build           the smallest coherent change; clean up nothing on the side",
            "5  Prove GREEN",
            "6  Gates           at least those of the risk class, plus any scoped check that "
            "applies",
            "7  Evidence        command, exit code, result",
            "8  Handover        open the draft PR and hand it to the independent reviewer",
            "9  Card            → Reviewing",
            "```",
        )
    )


def _render_ready_order(contract: WorkflowContract) -> str:
    ready = contract.ready_for_review
    return (
        f"{ready.actor} opens the pull request as a **{ready.initial_pull_request_state}** at the "
        "initial review handover. Once the independent review is clean and the readiness check "
        "passes for current HEAD, Codex marks it **ready for review**. That transition is the "
        f"signal that the change is {ready.merge_decider}'s to judge."
    )


def _render_transitions(contract: WorkflowContract) -> str:
    lines = ["| From → To | Who | When |", "|---|---|---|"]
    for transition in contract.transitions:
        source = "—" if transition.source == "-" else f"`{transition.source}`"
        lines.append(
            f"| {source} → `{transition.target}` | {transition.actor} | {transition.trigger} |"
        )
    return "\n".join(lines)


def _render_activations(contract: WorkflowContract) -> str:
    lines = ["| Part of this contract | Lands with | Until then |", "|---|---|---|"]
    lines.extend(
        f"| {activation.capability} | "
        f"[#{activation.issue}](https://github.com/QPlus-Capital/trading-system/issues/"
        f"{activation.issue}) | {activation.fallback} |"
        for activation in contract.activations
    )
    return "\n".join(lines)


def _render_agent_guard(contract: WorkflowContract) -> str:
    guards = {guard.name: guard for guard in contract.builder_guards}
    start = guards["Start"]
    resume = guards["Resume"]
    return "\n\n".join(
        (
            f"- **Starting new work.** Refuse unless {start.condition}. Then {start.action}.",
            f"- **Resuming.** When {resume.condition}, {resume.action}.",
        )
    )


def _render_agent_handover(contract: WorkflowContract) -> str:
    return "\n".join(
        (
            "4. **Prepare independent review** — complete current evidence and hand the final diff "
            "to Claude's fresh reviewer path by opening a **draft** pull request, moving the card "
            "to `Reviewing`, and handing over that draft. Include `Closes #<issue>` in the body.",
            "5. **Resolve the review** — fix every blocking finding with executable proof and "
            "return the card to `Reviewing` after each material fix.",
            "6. **Mark it ready for review** — only after the review is clean and the readiness "
            "check passes for current HEAD. Do not merge or enable autonomous merge.",
        )
    )


def _render_claude_approval(contract: WorkflowContract) -> str:
    actions = ", ".join(
        step.action for step in sorted(contract.approval_steps, key=lambda item: item.order)
    )
    return (
        "**Approval.** Present the complete issue body to Jan in the conversation — for R3 also "
        "the "
        "risk itself: limits touched, worst case if it is wrong, whether a running runner is "
        "affected. Only after Jan's explicit approval, and in this order: "
        f"{actions}. The `approved` label is written **last**, so a failure anywhere leaves the "
        "issue unapproved. Report only that the issue is approved — never a prompt or a call to "
        "action; when it is built is Jan's decision."
    )


def _render_constitution_pr_order(contract: WorkflowContract) -> str:
    ready = contract.ready_for_review
    return (
        f"A **{ready.initial_pull_request_state}** pull request is opened once implementation and "
        "deterministic verification are complete; it is what the independent review is performed "
        "on, so that every finding lands as an inline comment at the line it concerns. A pull "
        "request is marked **ready for review** only after that review and its remediation are "
        "complete — that is the point the readiness check gates, and it is the only state Jan is "
        "asked to merge from."
    )


_WORKFLOW_RENDERERS: tuple[tuple[str, Callable[[WorkflowContract], str]], ...] = (
    ("statuses", _render_statuses),
    ("approval-order", _render_approval_order),
    ("builder-guard", _render_builder_guard),
    ("build-sequence", _render_build_sequence),
    ("ready-order", _render_ready_order),
    ("transitions", _render_transitions),
    ("activations", _render_activations),
)


def render_document(path: Path, text: str, contract: WorkflowContract) -> str:
    """Regenerate every contract-owned block in one supported document."""
    if path == _WORKFLOW:
        renderers = _WORKFLOW_RENDERERS
    elif path == _AGENTS:
        renderers = (
            ("builder-guard", _render_agent_guard),
            ("review-handover", _render_agent_handover),
        )
    elif path == _CLAUDE:
        renderers = (("approval-order", _render_claude_approval),)
    elif path == _CONSTITUTION:
        renderers = (("pr-order", _render_constitution_pr_order),)
    else:
        raise ValueError(f"unsupported workflow document: {path}")

    rendered = text
    for name, renderer in renderers:
        rendered = _replace_block(rendered, name, renderer(contract))
    return rendered


def document_skeleton(path: Path, text: str) -> str:
    """Replace generated bodies with stable tokens so hand-written drift remains visible."""
    skeleton = text.replace("\r\n", "\n")
    for name in _BLOCKS_BY_DOCUMENT[path]:
        start = re.escape(_start_marker(name))
        end = re.escape(_end_marker(name))
        pattern = re.compile(rf"{start}\n.*?\n{end}", re.DOTALL)
        replacement = f"{_start_marker(name)}\n<{name}>\n{_end_marker(name)}"
        skeleton, count = pattern.subn(replacement, skeleton)
        if count != 1:
            raise ValueError(f"document must contain exactly one generated block {name!r}")
    return skeleton


def skeleton_digest(path: Path, text: str) -> str:
    """Return the deterministic digest for all non-generated document content."""
    skeleton = document_skeleton(path, text)
    return hashlib.sha256(skeleton.encode("utf-8")).hexdigest()


def check_documents(
    root: Path = REPO_ROOT,
    contract: WorkflowContract | None = None,
) -> tuple[str, ...]:
    """Return every generated-block or non-generated-skeleton drift."""
    model = contract or load_contract(root / CONTRACT_PATH.relative_to(REPO_ROOT))
    issues: list[str] = []
    hash_keys = {
        _WORKFLOW: "workflow",
        _AGENTS: "agents",
        _CLAUDE: "claude",
        _CONSTITUTION: "constitution",
    }
    for relative, hash_key in hash_keys.items():
        absolute = root / relative
        actual = absolute.read_text(encoding="utf-8")
        try:
            rendered = render_document(relative, actual, model)
            digest = skeleton_digest(relative, actual)
        except ValueError as exc:
            issues.append(f"{relative.as_posix()}: {exc}")
            continue
        if rendered != actual:
            issues.append(
                f"{relative.as_posix()}: generated workflow content is stale; regenerate it"
            )
        expected_digest = model.document_hashes[hash_key]
        if digest != expected_digest:
            issues.append(
                f"{relative.as_posix()}: non-generated workflow text drifted "
                f"(expected {expected_digest}, observed {digest})"
            )
    return tuple(issues)


def write_documents(
    root: Path = REPO_ROOT,
    contract: WorkflowContract | None = None,
) -> None:
    """Regenerate contract-owned blocks without blessing non-generated prose drift."""
    model = contract or load_contract(root / CONTRACT_PATH.relative_to(REPO_ROOT))
    for relative in _BLOCKS_BY_DOCUMENT:
        absolute = root / relative
        current = absolute.read_text(encoding="utf-8")
        absolute.write_text(render_document(relative, current, model), encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render or check the workflow contract documents")
    parser.add_argument(
        "--write",
        action="store_true",
        help="rewrite generated blocks (does not update non-generated skeleton digests)",
    )
    parser.add_argument(
        "--print-hashes",
        action="store_true",
        help="print current non-generated skeleton digests",
    )
    args = parser.parse_args(argv)
    contract = load_contract()
    if args.write:
        write_documents(contract=contract)
    if args.print_hashes:
        for relative, key in (
            (_WORKFLOW, "workflow"),
            (_AGENTS, "agents"),
            (_CLAUDE, "claude"),
            (_CONSTITUTION, "constitution"),
        ):
            digest = skeleton_digest(relative, (REPO_ROOT / relative).read_text(encoding="utf-8"))
            print(f"{key} = {digest}")
    issues = check_documents(contract=contract)
    for issue in issues:
        print(f"NOT VALID: {issue}")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
