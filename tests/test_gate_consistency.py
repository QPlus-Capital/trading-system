"""CI must enforce the same gates as ``just check`` -- neither may silently drift from the other.

A check that runs locally but not in CI (or over a smaller surface) is a gate that does not bind on
a pull request. This asserts the two definitions cover the same packages for the tools where the
surface matters.
"""

from __future__ import annotations

import re
from pathlib import Path

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
        "check-task-artifact",
        "check-security",
        "check-invariants",
        "check-pr-evidence",
    ):
        assert re.search(rf"^{re.escape(recipe)}(?:\s+[^:]*)?:", _JUSTFILE, re.MULTILINE)
        assert f"just {recipe}" in _CI
    assert "just mutation-critical" in _MUTATION
    assert "just mutation-self-test" in _MUTATION


def test_ci_exposes_the_complete_stable_job_split() -> None:
    for job in (
        "standard-quality",
        "tests",
        "task-artifact-validation",
        "security",
        "critical-invariants",
        "pr-evidence-validation",
    ):
        assert re.search(rf"^  {re.escape(job)}:\s*$", _CI, re.MULTILINE)
    assert re.search(r"^  mutation-critical:\s*$", _MUTATION, re.MULTILINE)


def test_workflows_pin_actions_and_cancel_superseded_runs() -> None:
    for workflow in (_CI, _MUTATION):
        assert "cancel-in-progress: true" in workflow
        for use in re.findall(r"uses:\s*([^\s#]+)", workflow):
            assert re.fullmatch(r"[^@]+@[0-9a-f]{40}", use), f"action is not SHA-pinned: {use}"


def test_r3_governance_changes_cannot_be_path_filtered_out() -> None:
    assert "paths:" not in _CI
    assert "paths-ignore:" not in _CI
    assert "paths:" not in _MUTATION
    assert "paths-ignore:" not in _MUTATION


def test_pr_body_edits_rerun_evidence_validation() -> None:
    assert "types: [opened, reopened, synchronize, edited]" in _CI


def test_ci_does_not_hide_gate_logic_outside_just_recipes() -> None:
    for direct_gate in ("uv run ruff", "uv run mypy", "uv run pytest", "pip-audit"):
        assert direct_gate not in _CI
    assert "uv run --no-sync --with mutmut" not in _MUTATION


def test_task_artifact_recipe_reuses_the_existing_impact_engine() -> None:
    recipe = _JUSTFILE.split("check-task-artifact", 1)[1].split("\n\n", 1)[0]
    assert "scripts.quality.impact" in recipe
    assert "scripts.quality.validate_task" in recipe
