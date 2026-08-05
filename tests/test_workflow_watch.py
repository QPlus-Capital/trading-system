"""The watch tool is the pull half of the narration: read-only, one change per wake-up."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from workflow import watch


def test_wait_for_change_wakes_exactly_on_the_first_change() -> None:
    states: list[dict[str, object]] = [
        {"issue": 104, "karte": "Reviewing", "ereignisse": 3},
        {"issue": 104, "karte": "Reviewing", "ereignisse": 3},
        {"issue": 104, "karte": "Reviewing", "ereignisse": 4},
        {"issue": 104, "karte": "Blocked", "ereignisse": 5},
    ]
    calls = iter(states)

    state, changed = watch.wait_for_change(
        104, max_minutes=1, poll_seconds=0, take=lambda issue: next(calls)
    )

    assert changed is True
    assert state == {"issue": 104, "karte": "Reviewing", "ereignisse": 4}, (
        "the first change wakes the watcher; later ones belong to the next arm"
    )


def test_wait_for_change_times_out_visibly_when_nothing_moves() -> None:
    constant = {"issue": 104, "karte": "Reviewing"}

    state, changed = watch.wait_for_change(
        104, max_minutes=0.0001, poll_seconds=0, take=lambda issue: dict(constant)
    )

    assert changed is False
    assert state == constant, "the unchanged state is still reported, never swallowed"


def test_snapshot_reads_the_event_log_and_shows_unreadable_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A transient board or gh error must show as '?', not end the watch and not invent state."""

    log = tmp_path / "qplus-events-104.jsonl"
    log.write_text(
        json.dumps({"zeit": "t", "issue": 104, "ereignis": "runde", "runde": 1}) + "\n"
        + json.dumps({"zeit": "t", "issue": 104, "ereignis": "urteil", "blockierend": 0}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(watch, "events_path", lambda issue: log)

    def refuse(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("offline")

    monkeypatch.setattr("workflow.board.read_card", refuse)
    monkeypatch.setattr(watch, "_gh", refuse)

    state = watch.snapshot(104)

    assert state["karte"] == "?" and state["pr"] == "?"
    assert state["ereignisse"] == 2
    assert "urteil" in str(state["letztes_ereignis"])


def test_the_cli_prints_one_machine_readable_snapshot(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(watch, "snapshot", lambda issue: {"issue": issue, "karte": "Done"})

    assert watch.main(["104"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed == {"issue": 104, "karte": "Done"}


def test_the_cli_reports_a_timeout_with_its_own_exit_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        watch,
        "wait_for_change",
        lambda issue, max_minutes: ({"issue": issue}, False),
    )

    assert watch.main(["104", "--until-change", "--max-minutes", "0.01"]) == 3
    assert "unveraendert" in capsys.readouterr().out


def test_the_watch_is_read_only() -> None:
    """It observes a run other actors own; a watcher that writes is an actor in disguise."""

    source = Path(watch.__file__).read_text(encoding="utf-8")
    for forbidden in ("board.move", "gh pr review", "pr merge", "workflow run", "issue comment"):
        assert forbidden not in source
