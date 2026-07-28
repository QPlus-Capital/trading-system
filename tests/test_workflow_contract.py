"""The workflow contract must be internally consistent and executable as written.

`docs/engineering/workflow.md` is a procedure two agents follow literally. A contradiction in it is
not a documentation defect -- it is a builder that refuses to resume its own branch, or a reviewer
told to run an agent the repository does not contain.

Each guard below parses the contract into facts and asserts on those facts. An earlier version
asserted that certain phrases were present, and independent review demonstrated that all six such
guards passed while the property they claimed to protect was violated -- a document saying the
builder "opens a pull request and immediately marks it ready before independent review" satisfied
the draft-versus-ready guard, and deleting a required edge satisfied the totality guard. Presence of
a phrase is not the contract; the parsed table is.
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_WORKFLOW = _ROOT / "docs" / "engineering" / "workflow.md"
_CONSTITUTION = _ROOT / "docs" / "engineering" / "constitution.md"
_AGENTS = _ROOT / "AGENTS.md"
_CLAUDE = _ROOT / "CLAUDE.md"

_STATUSES = (
    "Backlog",
    "Specifying",
    "Ready to Implement",
    "Implementing",
    "Reviewing",
    "Blocked",
    "Done",
)

#: Every transition the workflow must declare. Deleting any one of them must fail a test, which a
#: source/target coverage check cannot detect -- a status stays "covered" through its other edges.
_REQUIRED_EDGES: frozenset[tuple[str, str]] = frozenset(
    {
        ("-", "Backlog"),
        ("Backlog", "Specifying"),
        ("Blocked", "Specifying"),
        ("Specifying", "Backlog"),
        ("Specifying", "Ready to Implement"),
        ("Ready to Implement", "Specifying"),
        ("Ready to Implement", "Implementing"),
        ("Implementing", "Reviewing"),
        ("Reviewing", "Implementing"),
        ("Implementing", "Specifying"),
        ("Specifying", "Blocked"),
        ("Ready to Implement", "Blocked"),
        ("Implementing", "Blocked"),
        ("Reviewing", "Blocked"),
        ("Reviewing", "Done"),
    }
)

#: Wording that turns the class gate list into a ceiling. Any of these makes a relevant secret,
#: platform or dependency check look prohibited.
_CEILING_PHRASES = (
    "no more, no less",
    "no other check",
    "no further check",
    "only those",
    "exactly those",
    "and nothing else",
)


def _text(path: Path) -> str:
    assert path.is_file(), f"required workflow document is missing: {path.relative_to(_ROOT)}"
    return path.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    """The body of one `## heading`, up to the next heading of the same level."""
    start = text.find(heading)
    assert start != -1, f"the workflow must contain the section {heading!r}"
    rest = text[start + len(heading) :]
    end = rest.find("\n## ")
    return rest if end == -1 else rest[:end]


def _rows(section: str) -> list[list[str]]:
    """Data rows of the first markdown table in a section, as stripped cell lists."""
    out: list[list[str]] = []
    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if all(set(c) <= {"-", ":"} for c in cells):  # the ---|--- separator
            continue
        out.append(cells)
    return out[1:] if out else []  # drop the header row


def _guard_section(text: str) -> str:
    """The builder-guard section: from the resume wording to the next heading."""
    start = re.search(r"(?i)\bresum(?:e|ing|ption)\b", text)
    assert start is not None, "the document must define resumption"
    rest = text[start.start() :]
    nxt = rest.find("\n## ", 1)
    return rest if nxt == -1 else rest[:nxt]


def _resume_rule(text: str) -> str:
    """The single line or bullet that states the resume condition, isolated from its neighbours.

    A table row `| **Resume** | … |` in the workflow, a `- **Resuming.** …` bullet in AGENTS.md.
    Anything else means the rule is no longer stated as one identifiable unit, which is itself a
    contract defect: two agents cannot follow a rule they have to reassemble from prose.
    """
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and re.search(r"(?i)\*\*Resume\*\*", stripped):
            return stripped
    block: list[str] = []
    for line in text.splitlines():
        if re.match(r"(?i)^\s*[-*]\s+\*\*Resum", line):
            block = [line]
        elif block:
            if not line.strip() or re.match(r"(?i)^\s*[-*]\s+\*\*", line):
                break
            block.append(line)
    assert block, "the document must state the resume condition as one identifiable rule"
    return " ".join(part.strip() for part in block)


def _edges(text: str) -> set[tuple[str, str]]:
    section = _section(text, "## State transitions")
    found: set[tuple[str, str]] = set()
    for cells in _rows(section):
        if "→" not in cells[0]:
            continue
        left, right = (part.strip().strip("`").strip() for part in cells[0].split("→", 1))
        found.add(("-" if left in {"", "—", "-"} else left, right))
    return found


def test_the_builder_guard_separates_starting_from_resuming() -> None:
    """A build permit is consumed at first start, so it cannot also gate resumption.

    The card is `Implementing` and the permit is gone the moment work begins. A guard demanding
    `Ready to Implement` plus the permit therefore locks the builder out of its own branch after any
    interruption -- including the review loop, which returns the card to `Implementing` by design.

    Resumption must also be bounded by ownership. A card alone cannot say who wrote the code, so a
    stale or foreign branch must not be resumable.
    """
    for path in (_AGENTS, _WORKFLOW):
        text = _text(path)
        # The RULE itself, not its neighbourhood. Scanning the surrounding region is what let an
        # earlier version of this guard pass while the rule had lost a status that merely happened
        # to appear elsewhere nearby.
        rule = _resume_rule(text)
        for status in ("Implementing", "Reviewing"):
            assert status in rule, (
                f"{path.relative_to(_ROOT)}'s resume rule must permit `{status}`. Both in-progress "
                "statuses are reachable when work is interrupted -- naming only one strands the "
                "other. Rule read: {rule!r}".format(rule=rule[:200])
            )
        assert re.search(r"(?i)without[^.|]{0,80}permit", rule), (
            f"{path.relative_to(_ROOT)} resume rule must state that resuming needs no permit, "
            "which the first start consumed."
        )
        assert re.search(r"(?i)issue number|<issue>", rule), (
            f"{path.relative_to(_ROOT)} resume rule must be bound to a branch carrying this issue "
            "number, otherwise an unrelated branch is resumable."
        )
        # The refusal clauses may sit outside the rule itself, but must exist in the same section.
        section = _guard_section(text)
        assert re.search(r"(?i)\bfork\b|outside this repository", section), (
            f"{path.relative_to(_ROOT)} must refuse a branch from outside this repository."
        )


def test_the_builder_never_reaches_ready_before_the_independent_review() -> None:
    """The builder opens a draft; only a clean review earns the ready state.

    A document may name both states and still describe the wrong order. This checks the ordering
    itself: wherever a document says a pull request is marked ready, that statement must be
    qualified by the review having happened first.
    """
    ready = re.compile(r"(?i)mark(?:s|ing|ed)?\s+(?:it\s+|the\s+pull\s+request\s+)?ready")
    qualifier = re.compile(
        r"(?i)only (?:after|once)|once .{0,60}(?:review|clean)|after .{0,60}review"
    )
    for path in (_CONSTITUTION, _AGENTS, _CLAUDE, _WORKFLOW):
        text = _text(path)
        assert not re.search(r"(?i)opens?\s+(?:a|the)\s+ready\s+pull\s+request", text), (
            f"{path.relative_to(_ROOT)} still has the builder opening a ready pull request."
        )
        for match in ready.finditer(text):
            window = text[max(0, match.start() - 200) : match.end() + 200]
            assert qualifier.search(window), (
                f"{path.relative_to(_ROOT)} marks a pull request ready without qualifying that the "
                f"independent review came first: ...{window.strip()[:160]}..."
            )


def test_required_gates_are_a_minimum_and_never_a_ceiling() -> None:
    """The risk class sets a mandatory minimum; scoped verification stays permitted.

    Wording that caps the gates at the class list suppresses a useful secret, platform or dependency
    check purely because the class does not enumerate it.
    """
    text = _text(_WORKFLOW)
    lowered = text.lower()
    for phrase in _CEILING_PHRASES:
        assert phrase not in lowered, (
            f"the workflow caps the required gates ({phrase!r}); the class list is a lower "
            "bound and any applicable scoped check stays permitted."
        )
    steps = text.splitlines()
    gate_line = next((step for step in steps if re.search(r"^\s*\d+\s+Gates", step)), "")
    assert gate_line, "the build procedure must still name a Gates step"
    assert "at least" in gate_line.lower(), (
        "the Gates step must state the class gates are a minimum, not a ceiling"
    )


def test_the_review_loop_has_a_declared_way_back_to_reviewing() -> None:
    """A blocking finding sends the card to `Implementing`; the fix must send it forward again.

    Checked against the transition table rather than the prose, because prose can assert the
    transition in one place and forbid it in another.
    """
    text = _text(_WORKFLOW)
    rows = _rows(_section(text, "## State transitions"))
    fix_rows = [
        cells
        for cells in rows
        if "→" in cells[0]
        and cells[0].replace("`", "").strip().startswith("Implementing")
        and "Reviewing" in cells[0]
        and re.search(r"(?i)fix", cells[-1])
    ]
    assert fix_rows, (
        "the transition table must carry an `Implementing → Reviewing` row triggered by the review "
        "fix; without it the board reports building while a review is running."
    )
    assert not re.search(r"(?i)never (?:move|go|return) back to `?Reviewing", text), (
        "the workflow forbids the very transition its table declares"
    )


def test_the_state_machine_declares_every_required_transition() -> None:
    """The table is the contract, and it must be complete and terminal-correct.

    A source/target coverage check cannot see a deleted edge, because the statuses it connects stay
    covered through their other edges. The required set is therefore enumerated explicitly.
    """
    text = _text(_WORKFLOW)
    found = _edges(text)
    missing = _REQUIRED_EDGES - found
    assert not missing, f"the transition table is missing required edges: {sorted(missing)}"

    leaving_done = {edge for edge in found if edge[0] == "Done"}
    assert not leaving_done, (
        f"`Done` is declared terminal but the table leaves it: {sorted(leaving_done)}"
    )

    assert not any(edge[0].lower() == "any" for edge in found), (
        "`any → …` is not a transition: it silently includes the terminal status. Name the exact "
        "permitted sources."
    )
    unknown = {s for edge in found for s in edge if s not in _STATUSES and s != "-"}
    assert not unknown, f"the table names statuses the board does not have: {sorted(unknown)}"


def test_every_unavailable_capability_carries_an_owner_and_a_fallback() -> None:
    """The contract must not describe tooling that does not exist yet as though it were in force.

    Naming the activating issue is not enough: without a fallback rule the procedure is not
    executable in the meantime, and without the correct owner the row would survive its own
    dependency landing.
    """
    text = _text(_WORKFLOW)
    section = _section(text, "## Not yet active")
    rows = _rows(section)
    assert rows, "the activation register must list the parts that are not yet executable"

    for cells in rows:
        assert len(cells) >= 3, (
            f"activation row needs capability, activating issue and fallback: {cells}"
        )
        capability, lands_with, fallback = cells[0], cells[1], cells[2]
        assert len(capability) > 10, f"activation row does not name a capability: {cells}"
        assert re.search(r"#\d+", lands_with), (
            f"activation row for {capability!r} does not name the change that activates it"
        )
        assert len(fallback) > 30, (
            f"activation row for {capability!r} has no usable fallback rule, so the procedure is "
            "not executable until its dependency lands"
        )


def test_the_transitional_review_rule_is_stated_at_constitution_precedence() -> None:
    """A lower-ranking document cannot suspend the constitution.

    The workflow states that the review currently runs on the branch, while the constitution
    requires it on a draft pull request. Whichever way that is resolved, the suspension has to be
    written where the rule it suspends lives -- otherwise a literal reader follows the constitution
    and the workflow simultaneously and cannot.
    """
    workflow = _text(_WORKFLOW)
    constitution = _text(_CONSTITUTION)
    branch_review = re.search(
        r"(?i)review .{0,60}(?:runs on the|on the) \*\*?pushed branch", workflow
    )
    if branch_review is None:
        return  # the fallback is gone: the draft path is executable and nothing needs suspending
    assert re.search(r"(?i)transitional rule", constitution), (
        "the workflow suspends the constitution's draft-review requirement, so the constitution "
        "must state that transitional rule itself -- a lower-ranking document cannot suspend a "
        "higher-ranking one."
    )
    assert re.search(r"(?i)pushed branch", constitution), (
        "the constitution's transitional rule must name the procedure that actually applies today"
    )
