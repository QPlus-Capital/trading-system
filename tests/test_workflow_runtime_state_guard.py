"""The test suite keeps workflow cycle state out of the shared git directory."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

import pytest
from workflow import orchestrate, watch
from workflow.orchestrate import (
    _lock_path as imported_lock_path,
)
from workflow.orchestrate import (
    events_path as imported_events_path,
)
from workflow.orchestrate import (
    liveness_path as imported_liveness_path,
)


def test_workflow_runtime_paths_are_isolated_per_test(tmp_path: Path) -> None:
    issue = 987_654_321
    resolved = {
        orchestrate.events_path(issue),
        orchestrate.liveness_path(issue),
        orchestrate._lock_path(issue),
    }

    assert resolved == {
        tmp_path / f"qplus-events-{issue}.jsonl",
        tmp_path / f"qplus-cycle-{issue}.json",
        tmp_path / f"qplus-cycle-{issue}.lock",
    }


def test_bound_workflow_path_helpers_share_the_test_redirect(tmp_path: Path) -> None:
    issue = 987_654_321
    resolved = {
        watch.__dict__["events_path"](issue),
        watch.__dict__["liveness_path"](issue),
        imported_events_path(issue),
        imported_liveness_path(issue),
        imported_lock_path(issue),
    }

    assert resolved == {
        tmp_path / f"qplus-events-{issue}.jsonl",
        tmp_path / f"qplus-cycle-{issue}.json",
        tmp_path / f"qplus-cycle-{issue}.lock",
    }


@pytest.mark.parametrize(
    "filename",
    [
        "qplus-events-101.jsonl",
        "qplus-cycle-101.json",
        "qplus-cycle-101.lock",
    ],
)
def test_a_new_shared_runtime_file_is_reported_and_not_deleted(
    filename: str,
    tmp_path: Path,
    assert_no_shared_workflow_state: Callable[[Path, frozenset[Path]], None],
) -> None:
    before = frozenset(tmp_path.iterdir())
    leaked = tmp_path / filename
    leaked.touch()

    with pytest.raises(AssertionError, match=re.escape(filename)):
        assert_no_shared_workflow_state(tmp_path, before)

    assert leaked.exists(), "the guard reports operator state but never removes it"


def test_pre_existing_shared_runtime_state_is_not_claimed_by_a_test(
    tmp_path: Path,
    assert_no_shared_workflow_state: Callable[[Path, frozenset[Path]], None],
) -> None:
    existing = tmp_path / "qplus-cycle-202.json"
    existing.touch()

    assert_no_shared_workflow_state(tmp_path, frozenset({existing}))


def test_local_helper_patches_override_the_autouse_redirect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    override = tmp_path / "explicit.jsonl"
    monkeypatch.setattr(orchestrate, "events_path", lambda issue: override)

    assert orchestrate.events_path(202) == override
