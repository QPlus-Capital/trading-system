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
import shutil
from pathlib import Path

import pytest

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

#: The transition table is an allowlist of complete facts. Source/target pairs are insufficient:
#: the two Implementing-to-Reviewing rows have different actors/triggers and are both load-bearing.
_ALLOWED_TRANSITIONS: frozenset[tuple[str, str, str, str]] = frozenset(
    {
        ("-", "Backlog", "project automation", "an issue is opened"),
        (
            "Backlog",
            "Specifying",
            "Claude",
            "Jan asks for the idea to be worked out",
        ),
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
            "the change is handed over for review — by opening the draft pull request, or, while "
            "the branch-review rule below applies, by pushing the branch and saying so",
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

_EXPECTED_AGENT_GUARD: dict[str, tuple[str, str]] = {
    "Start": (
        "Refuse unless the board card is in `Ready to Implement`, the label `approved` is present, "
        "and a `risk:Rn` label is present",
        "move the card to `Implementing` and **only afterwards** remove `approved` — the reverse "
        "order would destroy the permit if the status update failed",
    ),
    "Resume": (
        "the card is in `Implementing` or `Reviewing` **and** a branch exists in this repository "
        "whose name is `codex/<issue>-…` or `claude/<issue>-…` for this issue number",
        "Resume **without** a permit",
    ),
}

_EXPECTED_WORKFLOW_GUARD: dict[str, tuple[str, str]] = {
    "Start": (
        "card in `Ready to Implement`, `approved` present, `risk:Rn` present",
        "move the card to `Implementing`, **then** remove `approved`",
    ),
    "Resume": (
        "the card is in `Implementing` or `Reviewing`, **and** a branch exists in this repository "
        "whose name is `codex/<issue>-…` or `claude/<issue>-…` for **this** issue number",
        "continue on it **without** a permit — the first start already consumed it",
    ),
}

_EXPECTED_READY_FACTS = {
    "constitution": (
        "A pull request is marked **ready for review** only after that review and its remediation "
        "are complete — that is the point the readiness check gates, and it is the only state Jan "
        "is asked to merge from."
    ),
    "agents": (
        "6. **Mark it ready for review** — only after the review is clean and the readiness check "
        "passes for current HEAD. Do not merge or enable autonomous merge."
    ),
    "workflow": (
        "Once the review is clean, Codex marks the pull request **ready for review**. That "
        "transition is what the readiness check gates, and it is the signal that the change is "
        "Jan's to judge."
    ),
}

_EXPECTED_GATE_FACT = "at least those of the risk class, plus any scoped check that applies"

_EXPECTED_ACTIVATIONS: dict[str, tuple[int, str]] = {
    "The draft pull request carries the review": (
        124,
        "The pre-Bash hook blocks `gh pr create` until the readiness check passes, so the "
        "independent review runs on the **pushed branch** and the pull request is opened "
        "afterwards. Constitution §11 states this transitional rule itself, so it is not a lower "
        "document overriding a higher one.",
    ),
    "Artifact files scale by risk class": (
        124,
        "`task-artifacts.toml` requires all five files for every class, `spec.md` included. Write "
        "them.",
    ),
    "Board transitions performed by tooling": (
        110,
        "Agents call `gh` directly and are responsible for the ordering rules themselves.",
    ),
    "The `methodology-reviewer` subagent": (
        112,
        "The general code reviewer carries the constitution §4 methodology invariants, as it does "
        "today.",
    ),
    "Findings named `Blocker` / `Defect` / `Suspected defect` / `Note`": (
        112,
        "Severities are `P0`–`P3`, as the constitution §12 states.",
    ),
}

_EXPECTED_TRANSITIONAL_REVIEW = (124, True, True, True)


def _text(path: Path) -> str:
    assert path.is_file(), f"required workflow document is missing: {path.relative_to(_ROOT)}"
    return path.read_text(encoding="utf-8")


def _normalize(text: str) -> str:
    return " ".join(text.split())


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
    in_table = False
    for line in section.splitlines():
        if not line.startswith("|"):
            if in_table:
                break
            continue
        in_table = True
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if all(set(c) <= {"-", ":"} for c in cells):  # the ---|--- separator
            continue
        out.append(cells)
    return out[1:] if out else []  # drop the header row


def _named_bullet(text: str, name: str) -> str:
    block: list[str] = []
    for line in text.splitlines():
        if re.match(rf"^\s*[-*]\s+\*\*{re.escape(name)}\.\*\*", line):
            block = [line]
        elif block:
            if not line.strip() or re.match(r"(?i)^\s*[-*]\s+\*\*", line):
                break
            block.append(line)
    assert block, f"the document must state {name!r} as one identifiable rule"
    return _normalize(" ".join(part.strip() for part in block))


def _agent_guard_facts(text: str) -> dict[str, tuple[str, str]]:
    start = _named_bullet(text, "Starting new work")
    start = start.split("**Starting new work.**", 1)[1].strip()
    start_condition, start_action = start.split(". Then ", 1)
    start_action = start_action.removeprefix("Then ").removesuffix(".")

    resume = _named_bullet(text, "Resuming")
    resume = resume.split("**Resuming.**", 1)[1].strip()
    first_sentence = resume.split(". That is ", 1)[0]
    match = re.fullmatch(r"(Resume \*\*without\*\* a permit) when (.*)", first_sentence)
    assert match is not None, "AGENTS.md Resume must be one condition/action tuple"
    return {
        "Start": (_normalize(start_condition), _normalize(start_action)),
        "Resume": (_normalize(match.group(2)), _normalize(match.group(1))),
    }


def _workflow_guard_facts(text: str) -> dict[str, tuple[str, str]]:
    rows = _rows(_section(text, "## Phase 3 — Building (Codex)"))
    facts: dict[str, tuple[str, str]] = {}
    for cells in rows:
        assert len(cells) == 3, f"builder guard row must have three cells: {cells}"
        name = cells[0].replace("*", "")
        if name in {"Start", "Resume"}:
            facts[name] = (_normalize(cells[1]), _normalize(cells[2]))
    return facts


def _transitions(text: str) -> set[tuple[str, str, str, str]]:
    section = _section(text, "## State transitions")
    found: set[tuple[str, str, str, str]] = set()
    for cells in _rows(section):
        assert len(cells) == 3, (
            f"transition row must have source/target, actor and trigger: {cells}"
        )
        if "→" not in cells[0]:
            continue
        left, right = (part.strip().strip("`").strip() for part in cells[0].split("→", 1))
        source = "-" if left in {"", "—", "-"} else left
        found.add((source, right, _normalize(cells[1]), _normalize(cells[2])))
    return found


def _activation_facts(text: str) -> dict[str, tuple[int, str]]:
    rows = _rows(_section(text, "## Not yet active"))
    facts: dict[str, tuple[int, str]] = {}
    for cells in rows:
        assert len(cells) == 3, (
            f"activation row needs capability, activating issue and fallback: {cells}"
        )
        owner = re.search(r"#(?P<number>\d+)", cells[1])
        assert owner is not None, f"activation owner is not an issue number: {cells[1]!r}"
        facts[_normalize(cells[0])] = (int(owner.group("number")), _normalize(cells[2]))
    return facts


def _transitional_review_facts_from_constitution(text: str) -> tuple[int, bool, bool, bool]:
    section = _section(text, "## 11. Required evidence before a PR")
    owner = re.search(r"Transitional rule, until \[#(?P<number>\d+)\]", section)
    assert owner is not None, "constitution §11 must name the transitional review owner"
    normalized = _normalize(section)
    return (
        int(owner.group("number")),
        "readiness gate currently blocks the *creation* of a pull request" in normalized,
        "independent review is performed on the **pushed branch**" in normalized,
        "pull request is opened afterwards" in normalized,
    )


def _transitional_review_facts_from_workflow(text: str) -> tuple[int, bool, bool, bool]:
    activation = _activation_facts(text)["The draft pull request carries the review"]
    owner, fallback = activation
    return (
        owner,
        "pre-Bash hook blocks `gh pr create` until the readiness check passes" in fallback,
        "independent review runs on the **pushed branch**" in fallback,
        "pull request is opened afterwards" in fallback,
    )


def test_the_builder_guard_separates_starting_from_resuming() -> None:
    """A build permit is consumed at first start, so it cannot also gate resumption.

    The card is `Implementing` and the permit is gone the moment work begins. A guard demanding
    `Ready to Implement` plus the permit therefore locks the builder out of its own branch after any
    interruption -- including the review loop, which returns the card to `Implementing` by design.

    Resumption must also be bounded by ownership. A card alone cannot say who wrote the code, so a
    stale or foreign branch must not be resumable.
    """
    agent_facts = _agent_guard_facts(_text(_AGENTS))
    workflow_facts = _workflow_guard_facts(_text(_WORKFLOW))
    assert agent_facts == _EXPECTED_AGENT_GUARD, (
        "AGENTS.md Start/Resume condition-action tuples changed:\n"
        f"expected={_EXPECTED_AGENT_GUARD!r}\nfound={agent_facts!r}"
    )
    assert workflow_facts == _EXPECTED_WORKFLOW_GUARD, (
        "workflow.md Start/Resume condition-action tuples changed:\n"
        f"expected={_EXPECTED_WORKFLOW_GUARD!r}\nfound={workflow_facts!r}"
    )


def test_the_builder_never_reaches_ready_before_the_independent_review() -> None:
    """The builder opens a draft; only a clean review earns the ready state.

    A document may name both states and still describe the wrong order. This checks the ordering
    itself: wherever a document says a pull request is marked ready, that statement must be
    qualified by the review having happened first.
    """
    documents = {
        "constitution": _text(_CONSTITUTION),
        "agents": _text(_AGENTS),
        "workflow": _text(_WORKFLOW),
    }
    for name, expected in _EXPECTED_READY_FACTS.items():
        assert _normalize(expected) in _normalize(documents[name]), (
            f"{name} must state the one canonical ready-order fact exactly; synonyms or reordered "
            "conditions are not accepted because they can invert the review boundary."
        )
    assert "ready for review" not in _text(_CLAUDE).lower(), (
        "CLAUDE.md must defer the ready-order fact to the constitution rather than define a second "
        "variant."
    )


def test_required_gates_are_a_minimum_and_never_a_ceiling() -> None:
    """The risk class sets a mandatory minimum; scoped verification stays permitted.

    Wording that caps the gates at the class list suppresses a useful secret, platform or dependency
    check purely because the class does not enumerate it.
    """
    steps = _text(_WORKFLOW).splitlines()
    gate_line = next((step for step in steps if re.search(r"^\s*\d+\s+Gates", step)), "")
    assert gate_line, "the build procedure must still name a Gates step"
    match = re.fullmatch(r"\s*\d+\s+Gates\s+(?P<fact>.+)", gate_line)
    assert match is not None, "the Gates step must be one identifiable lower-bound fact"
    assert _normalize(match.group("fact")) == _EXPECTED_GATE_FACT, (
        "the Gates fact must state the exact lower bound and scoped-check allowance; a blocklist "
        "cannot enumerate every possible ceiling phrase"
    )


def test_the_review_loop_has_a_declared_way_back_to_reviewing() -> None:
    """A blocking finding sends the card to `Implementing`; the fix must send it forward again.

    Checked against the transition table rather than the prose, because prose can assert the
    transition in one place and forbid it in another.
    """
    review_fix = ("Implementing", "Reviewing", "Codex", "the review fix is pushed")
    assert review_fix in _transitions(_text(_WORKFLOW)), (
        "the transition table must assign the review-fix handover to Codex with its exact trigger; "
        "source/target alone cannot distinguish it from the initial review handover"
    )


def test_the_state_machine_declares_every_required_transition() -> None:
    """The table is the contract, and it must be complete and terminal-correct.

    A source/target coverage check cannot see a deleted edge, because the statuses it connects stay
    covered through their other edges. The required set is therefore enumerated explicitly.
    """
    found = _transitions(_text(_WORKFLOW))
    assert found == _ALLOWED_TRANSITIONS, (
        "the transition table must equal the complete allowlist of source, target, actor and "
        "trigger facts:\n"
        f"missing={sorted(_ALLOWED_TRANSITIONS - found)!r}\n"
        f"unauthorized={sorted(found - _ALLOWED_TRANSITIONS)!r}"
    )


def test_every_unavailable_capability_carries_an_owner_and_a_fallback() -> None:
    """The contract must not describe tooling that does not exist yet as though it were in force.

    Naming the activating issue is not enough: without a fallback rule the procedure is not
    executable in the meantime, and without the correct owner the row would survive its own
    dependency landing.
    """
    found = _activation_facts(_text(_WORKFLOW))
    assert found == _EXPECTED_ACTIVATIONS, (
        "the activation register must equal the approved capability-to-owner-to-fallback map:\n"
        f"expected={_EXPECTED_ACTIVATIONS!r}\nfound={found!r}"
    )


def test_the_transitional_review_rule_is_stated_at_constitution_precedence() -> None:
    """A lower-ranking document cannot suspend the constitution.

    The workflow states that the review currently runs on the branch, while the constitution
    requires it on a draft pull request. Whichever way that is resolved, the suspension has to be
    written where the rule it suspends lives -- otherwise a literal reader follows the constitution
    and the workflow simultaneously and cannot.
    """
    constitution = _transitional_review_facts_from_constitution(_text(_CONSTITUTION))
    workflow = _transitional_review_facts_from_workflow(_text(_WORKFLOW))
    assert constitution == _EXPECTED_TRANSITIONAL_REVIEW, (
        f"constitution §11 transitional facts changed: {constitution!r}"
    )
    assert workflow == _EXPECTED_TRANSITIONAL_REVIEW, (
        f"workflow transitional facts changed: {workflow!r}"
    )
    assert constitution == workflow, (
        "constitution §11 and the workflow fallback must normalize to the same owner, creation "
        "boundary, review surface and PR timing"
    )


_CONTRACT_PATHS = {
    "workflow": _WORKFLOW,
    "constitution": _CONSTITUTION,
    "agents": _AGENTS,
    "claude": _CLAUDE,
}


def _replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"counterexample anchor missing in {path}: {old!r}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _counterexample_documents(tmp_path: Path) -> dict[str, Path]:
    copied: dict[str, Path] = {}
    for name, source in _CONTRACT_PATHS.items():
        destination = tmp_path / source.relative_to(_ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        copied[name] = destination
    return copied


def _apply_counterexample(name: str, paths: dict[str, Path]) -> None:
    if name == "start-allows-missing-permit":
        _replace_once(paths["agents"], "`approved` is present", "`approved` is absent")
        _replace_once(paths["workflow"], "`approved` present", "`approved` absent")
    elif name == "ready-before-review-with-synonym":
        _replace_once(
            paths["workflow"],
            "Once the review is clean, Codex marks the pull request **ready for review**.",
            "Before the review begins, Codex changes the pull request from draft to "
            "**ready for review**.",
        )
    elif name == "gate-ceiling-with-unlisted-phrase":
        _replace_once(
            paths["workflow"],
            "at least those of the risk class, plus any scoped check that applies",
            "at least those of the risk class; additional scoped checks are forbidden",
        )
    elif name == "review-fix-owned-by-wrong-actor":
        _replace_once(
            paths["workflow"],
            "| `Implementing` → `Reviewing` | Codex | the review fix is pushed |",
            "| `Implementing` → `Reviewing` | Claude | the review fix is pushed |",
        )
    elif name == "unauthorized-extra-transition":
        _replace_once(
            paths["workflow"],
            "| `Reviewing` → `Done` | project automation | "
            "the pull request merged and closed the issue |",
            "| `Backlog` → `Done` | project automation | the issue is skipped |\n"
            "| `Reviewing` → `Done` | project automation | "
            "the pull request merged and closed the issue |",
        )
    elif name == "activation-points-to-wrong-issue":
        text = paths["workflow"].read_text(encoding="utf-8")
        owner = "[#124](https://github.com/QPlus-Capital/trading-system/issues/124)"
        assert text.count(owner) >= 2
        paths["workflow"].write_text(
            text.replace(
                owner,
                "[#109](https://github.com/QPlus-Capital/trading-system/issues/109)",
                2,
            ),
            encoding="utf-8",
        )
    elif name == "constitution-forbids-branch-review":
        _replace_once(
            paths["constitution"],
            "the independent review is performed on the **pushed branch** and the pull request is\n"
            "opened afterwards.",
            "the **pushed branch** must never be reviewed; the independent review waits until "
            "after the\npull request is opened.",
        )
    else:
        raise AssertionError(f"unknown counterexample: {name}")


@pytest.mark.parametrize(
    ("counterexample", "guard_name"),
    (
        (
            "start-allows-missing-permit",
            "test_the_builder_guard_separates_starting_from_resuming",
        ),
        (
            "ready-before-review-with-synonym",
            "test_the_builder_never_reaches_ready_before_the_independent_review",
        ),
        (
            "gate-ceiling-with-unlisted-phrase",
            "test_required_gates_are_a_minimum_and_never_a_ceiling",
        ),
        (
            "review-fix-owned-by-wrong-actor",
            "test_the_review_loop_has_a_declared_way_back_to_reviewing",
        ),
        (
            "unauthorized-extra-transition",
            "test_the_state_machine_declares_every_required_transition",
        ),
        (
            "activation-points-to-wrong-issue",
            "test_every_unavailable_capability_carries_an_owner_and_a_fallback",
        ),
        (
            "constitution-forbids-branch-review",
            "test_the_transitional_review_rule_is_stated_at_constitution_precedence",
        ),
    ),
)
def test_contract_guard_rejects_semantic_counterexample(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    counterexample: str,
    guard_name: str,
) -> None:
    """Every guard must fire on the concrete semantic violation it exists to prevent."""
    paths = _counterexample_documents(tmp_path)
    _apply_counterexample(counterexample, paths)
    monkeypatch.setitem(globals(), "_ROOT", tmp_path)
    monkeypatch.setitem(globals(), "_WORKFLOW", paths["workflow"])
    monkeypatch.setitem(globals(), "_CONSTITUTION", paths["constitution"])
    monkeypatch.setitem(globals(), "_AGENTS", paths["agents"])
    monkeypatch.setitem(globals(), "_CLAUDE", paths["claude"])
    guard = globals()[guard_name]
    assert callable(guard)
    with pytest.raises(AssertionError):
        guard()
