"""Read and move one card on the GitHub project board.

The board's ``Status`` field is the single source of truth for where a change stands, so this tool
is the only thing that writes it. Two properties matter more than features:

**One card, one query.** Everything a decision needs -- the project item, the project, the status
field, its options, the current status, and the labels -- arrives in a single GraphQL request keyed
by *issue number*. The predecessor listed the whole project to find one card and re-resolved static
identifiers on every command, which exhausted the account's GraphQL budget and left the board
unreadable for forty minutes on 2026-07-30.

**Fail closed.** A transition the contract does not list is refused. A status the automation owns is
refused. Every write is read back, and a write that did not take effect is an error, never a shrug.

CLI::

    uv run python -m workflow.board status <issue>
    uv run python -m workflow.board move <issue> "Ready to Implement"
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = REPO_ROOT / "workflow" / "workflow.toml"

_OWNER = "QPlus-Capital"
_REPO = "trading-system"
_STATUS_FIELD = "Status"

_CARD_QUERY = """
query($owner:String!, $repo:String!, $number:Int!) {
  repository(owner:$owner, name:$repo) {
    issue(number:$number) {
      number
      title
      state
      labels(first:20){nodes{name}}
      projectItems(first:5){
        nodes{
          id
          project{ id number title }
          fieldValueByName(name:"Status"){
            ... on ProjectV2ItemFieldSingleSelectValue {
              name
              field { ... on ProjectV2SingleSelectField { id options { id name } } }
            }
          }
        }
      }
    }
  }
}
"""

_SET_STATUS = """
mutation($project:ID!, $item:ID!, $field:ID!, $option:String!) {
  updateProjectV2ItemFieldValue(input:{
    projectId:$project, itemId:$item, fieldId:$field,
    value:{singleSelectOptionId:$option}
  }){ projectV2Item { id } }
}
"""


class BoardError(RuntimeError):
    """A board operation that must stop rather than guess."""


@dataclass(frozen=True)
class Card:
    """One issue's board state, as one query returned it."""

    issue: int
    title: str
    open_state: bool
    status: str
    labels: tuple[str, ...]
    item_id: str
    project_id: str
    field_id: str
    options: dict[str, str]

    @property
    def risk_class(self) -> str | None:
        for label in self.labels:
            if label.startswith("risk:"):
                return label.removeprefix("risk:")
        return None


#: The only identities that may move a card. The contract assigns each transition to one of them
#: (or to "any"); a caller must say which one it is, because the incident this guards against was
#: real: a specify session pulled a card backwards out of a build that owned it.
ACTORS = frozenset({"claude", "codex", "orchestrator"})


@dataclass(frozen=True)
class Contract:
    """The board half of the workflow contract."""

    statuses: tuple[str, ...]
    automated: frozenset[str]
    transitions: dict[tuple[str, str], str]

    def permits(self, source: str, target: str) -> bool:
        return (source, target) in self.transitions

    def owner(self, source: str, target: str) -> str:
        return self.transitions[(source, target)]


def load_contract(path: Path = CONTRACT_PATH) -> Contract:
    board = tomllib.loads(path.read_text(encoding="utf-8"))["board"]
    return Contract(
        statuses=tuple(str(s) for s in board["statuses"]),
        automated=frozenset(str(s) for s in board["automated_statuses"]),
        transitions={
            (str(t["from"]), str(t["to"])): str(t["actor"])
            for t in board.get("transitions", [])
        },
    )


def _graphql(query: str, **variables: object) -> dict[str, Any]:
    """Run one GraphQL request through `gh`, which supplies the authenticated token."""

    args = ["gh", "api", "graphql", "-f", f"query={query}"]
    for name, value in variables.items():
        flag = "-F" if isinstance(value, int) else "-f"
        args += [flag, f"{name}={value}"]
    completed = subprocess.run(args, capture_output=True, text=True, check=False, cwd=REPO_ROOT)
    if completed.returncode != 0:
        raise BoardError("GitHub rejected the board request; inspect the local gh error.")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise BoardError("GitHub returned a non-JSON board response") from error
    if payload.get("errors"):
        raise BoardError("GitHub returned an error for the board request.")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise BoardError("GitHub returned no data for the board request")
    return data


def read_card(issue: int) -> Card:
    """The whole board state for one issue, in one request."""

    data = _graphql(_CARD_QUERY, owner=_OWNER, repo=_REPO, number=issue)
    node = ((data.get("repository") or {}).get("issue")) or None
    if node is None:
        raise BoardError(f"issue #{issue} does not exist in {_OWNER}/{_REPO}")
    items = (node.get("projectItems") or {}).get("nodes") or []
    if len(items) != 1:
        raise BoardError(
            f"issue #{issue} is on {len(items)} project boards; exactly one is required"
        )
    item = items[0]
    value = item.get("fieldValueByName")
    if not value:
        raise BoardError(f"issue #{issue} has no {_STATUS_FIELD} value on its card")
    field = value.get("field") or {}
    options = {str(o["name"]): str(o["id"]) for o in field.get("options", [])}
    if not options:
        raise BoardError(f"the project has no {_STATUS_FIELD} options")
    return Card(
        issue=int(node["number"]),
        title=str(node.get("title") or ""),
        open_state=str(node.get("state")) == "OPEN",
        status=str(value["name"]),
        labels=tuple(str(label["name"]) for label in (node.get("labels") or {}).get("nodes", [])),
        item_id=str(item["id"]),
        project_id=str(item["project"]["id"]),
        field_id=str(field["id"]),
        options=options,
    )


def move(
    issue: int,
    target: str,
    *,
    actor: str,
    reason: str | None = None,
    contract: Contract | None = None,
) -> Card:
    """Apply one permitted transition as one named actor, and verify it took effect.

    The contract assigns every transition to an actor; a move by anyone else is refused, whatever
    the transition. The hand-back to `Specifying` additionally requires a reason, which lands on
    the issue as a comment — without it the card walks backwards and the record says nothing,
    which is exactly what happened on the first real hand-back.
    """

    contract = contract or load_contract()
    if actor not in ACTORS:
        raise BoardError(f"{actor!r} is not an actor the contract knows: {sorted(ACTORS)}")
    if target not in contract.statuses:
        raise BoardError(f"{target!r} is not a status this project defines")
    if target in contract.automated:
        raise BoardError(f"{target!r} is set by project automation, never by an agent")

    card = read_card(issue)
    if card.status == target:
        return card
    if not contract.permits(card.status, target):
        raise BoardError(
            f"the contract does not permit {card.status!r} -> {target!r} "
            f"(issue #{issue} is in {card.status!r})"
        )
    owner = contract.owner(card.status, target)
    if owner != "any" and actor != owner:
        raise BoardError(
            f"the contract assigns {card.status!r} -> {target!r} to {owner!r}; "
            f"{actor!r} does not move this card"
        )
    if target == "Specifying" and not (reason or "").strip():
        raise BoardError(
            "the hand-back to 'Specifying' requires a reason; it is posted on the issue so the "
            "record shows why the card walked backwards"
        )
    option = card.options.get(target)
    if option is None:
        raise BoardError(f"the project has no {_STATUS_FIELD} option named {target!r}")

    _graphql(
        _SET_STATUS,
        project=card.project_id,
        item=card.item_id,
        field=card.field_id,
        option=option,
    )
    confirmed = read_card(issue)
    if confirmed.status != target:
        raise BoardError(
            f"the status update did not take effect: issue #{issue} still reads "
            f"{confirmed.status!r}"
        )
    if reason and reason.strip():
        _comment(issue, f"{card.status} -> {target} by {actor}: {reason.strip()}")
    return confirmed


def _comment(issue: int, body: str) -> None:
    """Post the transition's reason on the issue; a lost reason is an error, not a shrug."""

    completed = subprocess.run(
        ["gh", "issue", "comment", str(issue), "--body", body],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    if completed.returncode != 0:
        raise BoardError(
            f"the move took effect but its reason did not reach issue #{issue}; "
            "post it by hand so the record stays complete"
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    read = sub.add_parser("status", help="read one issue's board status and labels")
    read.add_argument("issue", type=int)
    write = sub.add_parser("move", help="apply one permitted status transition")
    write.add_argument("issue", type=int)
    write.add_argument("target")
    write.add_argument("--actor", required=True, choices=sorted(ACTORS))
    write.add_argument("--reason", default=None, help="posted on the issue with the move")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        card = (
            read_card(args.issue)
            if args.command == "status"
            else move(args.issue, args.target, actor=args.actor, reason=args.reason)
        )
    except BoardError as error:
        print(f"REFUSED: {error}")
        return 1
    risk = card.risk_class or "none"
    print(f"#{card.issue} {card.title}")
    print(f"  status: {card.status}")
    print(f"  risk:   {risk}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
