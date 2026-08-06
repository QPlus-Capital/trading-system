"""Follow one ticket: print a snapshot of its run whenever the state changes.

The ticket's Claude chat runs this in the background and narrates each change for the operator —
the pull that replaced the push: the orchestrator only appends events to the per-ticket log
(``workflow.orchestrate.events_path``), and whoever wants to tell the operator about them watches
here, wakes on a change, reads the log *and* the real artifacts, and writes the update in the
window the operator is actually looking at.

Everything here is read-only. A field that cannot be read right now is reported as ``"?"`` —
visible uncertainty, never a guessed value and never a crash that silently ends the watch.

CLI::

    uv run python -m workflow.watch 104                    # one snapshot, exit
    uv run python -m workflow.watch 104 --until-change     # block until the state moves
    uv run python -m workflow.watch 104 --until-change --max-minutes 45
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from collections.abc import Callable, Sequence

from workflow import board
from workflow.classify import REPO_ROOT
from workflow.orchestrate import events_path, issue_branch_matches

_POLL_SECONDS = 60


def _gh(args: Sequence[str]) -> str:
    completed = subprocess.run(
        ["gh", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or "gh failed").strip())
    return (completed.stdout or "").strip()


def snapshot(issue: int) -> dict[str, object]:
    """The ticket's observable state, one field per evidence source."""

    state: dict[str, object] = {"issue": issue}

    try:
        card = board.read_card(issue)
        state["karte"] = card.status
        state["risiko"] = card.risk_class or "keins"
        state["offen"] = card.open_state
    except Exception:  # noqa: BLE001 - a transient board error must show, not end the watch
        state["karte"] = "?"

    try:
        raw = _gh(
            [
                "pr",
                "list",
                "--state",
                "all",
                "--limit",
                "30",
                "--json",
                "number,state,headRefName,headRefOid",
            ]
        )
        matching = [
            entry
            for entry in json.loads(raw or "[]")
            if issue_branch_matches(issue, str(entry.get("headRefName", "")))
        ]
        if matching:
            entry = matching[0]
            state["pr"] = int(entry["number"])
            state["pr_status"] = str(entry["state"])
            state["head"] = str(entry["headRefOid"])[:12]
            try:
                checks = json.loads(
                    _gh(["pr", "checks", str(entry["number"]), "--json", "state"]) or "[]"
                )
                state["checks"] = "/".join(
                    sorted({str(check.get("state", "?")) for check in checks})
                )
            except (RuntimeError, json.JSONDecodeError):
                state["checks"] = "?"
            try:
                reviews = json.loads(
                    _gh(["pr", "view", str(entry["number"]), "--json", "reviews"]) or "{}"
                )
                state["reviews"] = len(reviews.get("reviews", []))
            except (RuntimeError, json.JSONDecodeError):
                state["reviews"] = "?"
        else:
            state["pr"] = None
    except (RuntimeError, json.JSONDecodeError):
        state["pr"] = "?"

    log = events_path(issue)
    if log.is_file():
        lines = [line for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
        state["ereignisse"] = len(lines)
        if lines:
            state["letztes_ereignis"] = lines[-1]
    else:
        state["ereignisse"] = 0

    return state


def _comparable(state: dict[str, object]) -> str:
    return json.dumps(state, ensure_ascii=False, sort_keys=True)


def wait_for_change(
    issue: int,
    *,
    max_minutes: float,
    poll_seconds: float = _POLL_SECONDS,
    take: Callable[[int], dict[str, object]] = snapshot,
) -> tuple[dict[str, object], bool]:
    """Block until the ticket's state differs from the first snapshot, or the time runs out.

    Returns the last snapshot and whether it differs from the baseline. One change per
    invocation: the caller narrates it and re-arms, so every wake-up corresponds to exactly one
    thing worth telling the operator about.
    """

    baseline = _comparable(take(issue))
    deadline = time.monotonic() + max_minutes * 60
    while time.monotonic() < deadline:
        time.sleep(poll_seconds)
        current = take(issue)
        if _comparable(current) != baseline:
            return current, True
    return json.loads(baseline), False


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Follow one ticket's run, read-only.")
    parser.add_argument("issue", type=int)
    parser.add_argument(
        "--until-change",
        action="store_true",
        help="block until the state moves, then print the new snapshot",
    )
    parser.add_argument("--max-minutes", type=float, default=45.0)
    args = parser.parse_args(argv)

    if not args.until_change:
        print(_comparable(snapshot(args.issue)))
        return 0
    state, changed = wait_for_change(args.issue, max_minutes=args.max_minutes)
    print(_comparable(state))
    if changed:
        return 0
    print(f"unveraendert nach {args.max_minutes:g} Minuten")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
