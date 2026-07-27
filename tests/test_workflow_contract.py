"""The workflow contract must be internally consistent and executable as written.

`docs/engineering/workflow.md` is a procedure two agents follow literally. A contradiction in it is
not a documentation defect -- it is a builder that refuses to resume its own branch, or a reviewer
that is told to run an agent the repository does not contain. Each guard below reproduces a defect
found by independent review of the workflow contract itself.
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_WORKFLOW = _ROOT / "docs" / "engineering" / "workflow.md"
_CONSTITUTION = _ROOT / "docs" / "engineering" / "constitution.md"
_AGENTS = _ROOT / "AGENTS.md"
_CLAUDE = _ROOT / "CLAUDE.md"

#: Board statuses, as the workflow declares them.
_STATUSES = (
    "Backlog",
    "Specifying",
    "Ready to Implement",
    "Implementing",
    "Reviewing",
    "Blocked",
    "Done",
)


def _text(path: Path) -> str:
    assert path.is_file(), f"required workflow document is missing: {path.relative_to(_ROOT)}"
    return path.read_text(encoding="utf-8")


def test_the_builder_guard_separates_starting_from_resuming() -> None:
    """A build permit is consumed at first start, so it cannot also gate resumption.

    The card is `Implementing` and the permit is gone the moment work begins. A guard that demands
    `Ready to Implement` plus the permit therefore locks the builder out of its own branch after any
    interruption -- including the review loop, which returns the card to `Implementing` by design.
    """
    for path in (_AGENTS, _WORKFLOW):
        text = _text(path)
        # The resume rule itself must name the status it applies to. A bare "resume it rather than
        # starting again" sitting beside a permit guard has no precedence and never fires.
        assert re.search(r"(?i)resum[^.]*\b(Implementing|Reviewing)\b", text), (
            f"{path.relative_to(_ROOT)} must state which in-progress status permits a resume. "
            "Without it the permit guard is the only reachable rule, and it locks the builder out "
            "of its own branch after any interruption."
        )
        # And the two guards must be disjoint: resuming cannot demand the permit that starting
        # already consumed.
        assert re.search(r"(?i)resum[^.]*\bwithout\b[^.]*permit", text), (
            f"{path.relative_to(_ROOT)} must state that resuming does not require the permit, "
            "which the first start consumed."
        )


def test_no_role_document_says_the_builder_opens_a_ready_pull_request() -> None:
    """The builder opens a draft; only a clean review earns the ready state (constitution §11).

    A role summary that still promises a ready pull request lets a literal reader skip the draft
    review entirely while believing it obeys the constitution.
    """
    for path in (_CONSTITUTION, _AGENTS, _CLAUDE):
        text = _text(path).lower()
        assert not re.search(r"opens?\s+(a|the)\s+ready\s+pull\s+request", text), (
            f"{path.relative_to(_ROOT)} still has the builder opening a ready pull request, which "
            "contradicts the draft-carries-the-review rule."
        )


def test_required_gates_are_never_described_as_a_maximum() -> None:
    """The risk class sets a mandatory minimum; scoped verification stays permitted.

    Wording that caps the gates at the class list suppresses a useful secret, platform or dependency
    check purely because the class does not enumerate it.
    """
    text = _text(_WORKFLOW)
    assert "no more, no less" not in text.lower(), (
        "the workflow must not describe required gates as a maximum"
    )
    steps = text.splitlines()
    gate_line = next((step for step in steps if re.search(r"^\s*\d+\s+Gates", step)), "")
    assert gate_line, "the build procedure must still name a Gates step"
    assert "at least" in gate_line.lower(), (
        "the Gates step must state the class gates are a minimum, not a ceiling"
    )


def test_the_review_loop_returns_the_card_to_reviewing() -> None:
    """A blocking finding sends the card back to `Implementing`; the fix must send it forward again.

    Without the return transition the board reports `Implementing` while a review is running, so the
    status field stops being the single source of truth it is declared to be.
    """
    text = _text(_WORKFLOW)
    fix_section = text[text.find("blocking finding") :]
    assert fix_section, "the workflow must describe what a blocking finding does"
    assert re.search(r"(?i)back to `?Reviewing", fix_section), (
        "the workflow must state that the card returns to `Reviewing` once the review fixes are "
        "pushed -- otherwise the review loop has no way back."
    )


def test_the_state_machine_is_declared_as_a_table_and_is_total() -> None:
    """Prose describes transitions one at a time; only a table shows a missing one.

    Both defects found in review -- the unreachable resume and the absent way back from a review fix
    -- were invisible in prose and obvious in a table. Every status must appear as both a source and
    a target, so no status is reachable with no way out.
    """
    text = _text(_WORKFLOW)
    marker = "## State transitions"
    assert marker in text, "the workflow must declare its transitions as a table, not only in prose"
    table = text[text.find(marker) :]
    table = table[: table.find("\n## ", 1) if "\n## " in table[1:] else len(table)]
    rows = [line for line in table.splitlines() if line.startswith("|") and "→" in line]
    assert rows, "the transition table must contain rows written as `from → to`"

    sources = {s for s in _STATUSES if any(re.search(rf"\|[^|]*{s}[^|]*→", r) for r in rows)}
    targets = {s for s in _STATUSES if any(re.search(rf"→[^|]*{s}", r) for r in rows)}
    assert set(_STATUSES) - {"Done"} <= sources, (
        f"these statuses have no way out: {sorted(set(_STATUSES) - {'Done'} - sources)}"
    )
    assert set(_STATUSES) - {"Backlog"} <= targets, (
        f"these statuses are unreachable: {sorted(set(_STATUSES) - {'Backlog'} - targets)}"
    )


def test_capabilities_the_repository_lacks_are_marked_as_not_yet_active() -> None:
    """The contract must not describe tooling that does not exist yet as though it were in force.

    The draft-before-review ordering, the per-class artifact matrix and the methodology reviewer
    all depend on work that has not landed. Stated in the present tense they produce a procedure no
    agent can execute; named with the issue that activates them they produce a plan.
    """
    text = _text(_WORKFLOW)
    lowered = text.lower()
    assert "not yet active" in lowered, (
        "the workflow must carry a section naming the parts that are not yet executable"
    )
    activation = text[lowered.find("not yet active") :]
    for issue in ("#109", "#110", "#112"):
        assert issue in activation, (
            f"the activation section must name {issue}, the change that makes its part executable"
        )
