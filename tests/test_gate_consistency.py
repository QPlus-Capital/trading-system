"""CI must enforce the same gates as ``just check`` -- neither may silently drift from the other.

A check that runs locally but not in CI (or over a smaller surface) is a gate that does not bind on
a pull request. This asserts the two definitions cover the same packages for the tools where the
surface matters.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[1]
_JUSTFILE = (_ROOT / "justfile").read_text(encoding="utf-8")
_CI = (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
_MUTATION = (_ROOT / ".github" / "workflows" / "mutation.yml").read_text(encoding="utf-8")


def _vulture_packages(text: str) -> set[str]:
    """The package list passed to vulture in a file (the tokens between ``vulture`` and a flag)."""
    match = re.search(r"vulture\s+([\w\s/]+?)\s+--", text)
    assert match, "no vulture invocation found"
    return set(match.group(1).split())


def test_vulture_scans_the_same_packages_locally_and_in_ci() -> None:
    local = _vulture_packages(_JUSTFILE)
    assert local == {"core", "research", "live", "monitoring", "scripts"}
    assert "just check-standard" in _CI


def test_ci_runs_the_core_gates() -> None:
    """CI must run the same four gates as ``just check`` (ruff, mypy, pytest, vulture)."""
    for tool in ("ruff check", "mypy", "pytest", "vulture"):
        assert tool in _JUSTFILE, f"just check must run {tool}"
    assert "just check-standard" in _CI
    assert "just check-tests" in _CI


def test_every_ci_gate_invokes_a_local_just_recipe() -> None:
    for recipe in (
        "check-standard",
        "check-tests",
        "check-properties",
        "check-security",
        "check-invariants",
    ):
        assert re.search(rf"^{re.escape(recipe)}(?:\s+[^:]*)?:", _JUSTFILE, re.MULTILINE)
        assert f"just {recipe}" in _CI
    assert "just mutation-critical" in _MUTATION
    assert "just mutation-self-test" in _MUTATION


def test_ci_exposes_the_complete_consolidated_job_split() -> None:
    for job in ("full-quality", "platform-quality"):
        assert re.search(rf"^  {re.escape(job)}:\s*$", _CI, re.MULTILINE)
    for retired_job in (
        "standard-quality",
        "tests",
        "task-artifact-validation",
        "security",
        "critical-invariants",
        "pr-evidence-validation",
    ):
        assert not re.search(rf"^  {re.escape(retired_job)}:\s*$", _CI, re.MULTILINE)
    assert re.search(r"^  mutation-critical:\s*$", _MUTATION, re.MULTILINE)


def test_workflows_pin_actions_and_cancel_superseded_runs() -> None:
    for workflow in (_CI, _MUTATION):
        assert "cancel-in-progress: true" in workflow
        for use in re.findall(r"uses:\s*([^\s#]+)", workflow):
            assert re.fullmatch(r"[^@]+@[0-9a-f]{40}", use), f"action is not SHA-pinned: {use}"


def test_r3_governance_changes_cannot_be_path_filtered_out() -> None:
    for source in (_CI, _MUTATION):
        workflow = yaml.load(source, Loader=yaml.BaseLoader)
        assert isinstance(workflow, dict)
        triggers = workflow["on"]
        assert isinstance(triggers, dict)
        for event in triggers.values():
            if isinstance(event, dict):
                assert "paths" not in event
                assert "paths-ignore" not in event


def test_pr_body_edits_do_not_rerun_ci() -> None:
    assert "edited" not in _CI
    assert "ready_for_review" in _CI


def test_ci_does_not_hide_gate_logic_outside_just_recipes() -> None:
    mt5_boundary = (
        "uv run pytest -q tests/test_workflow_system_validation.py"
        "::test_pytest_blocks_real_mt5_boundaries"
    )
    assert _CI.count(mt5_boundary) == 1
    gate_source = _CI.replace(mt5_boundary, "")
    for direct_gate in ("uv run ruff", "uv run mypy", "uv run pytest", "pip-audit"):
        assert direct_gate not in gate_source
    assert "uv run --no-sync --with mutmut" not in _MUTATION


def test_the_focused_test_recipe_reuses_the_existing_impact_engine() -> None:
    recipe = _JUSTFILE.split("check-fast", 1)[1].split("\n\n", 1)[0]
    assert "scripts.quality.impact" in recipe
    assert "--run-focused" in recipe
