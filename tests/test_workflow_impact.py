"""Impact analysis must find real repository dependencies without claiming completeness."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from workflow.classify import REPO_ROOT
from workflow.impact import (
    analyze_impact,
    changed_tests_exercise_targets,
    format_check_command,
    targets_exercised_by_changed_tests,
    write_test_map,
)


def test_target_attribution_returns_exactly_the_reached_targets(tmp_path: Path) -> None:
    """The scoped mutation run needs to know *which* targets a changed test reaches, not merely
    whether any is reached; measuring the others would spend minutes proving nothing."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "pkg" / "reached.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "pkg" / "middle.py").write_text("import pkg.reached\n", encoding="utf-8")
    (tmp_path / "pkg" / "unrelated.py").write_text("VALUE = 2\n", encoding="utf-8")
    (tmp_path / "tests" / "test_middle.py").write_text("import pkg.middle\n", encoding="utf-8")

    exercised = targets_exercised_by_changed_tests(
        ["tests/test_middle.py"],
        ["pkg/reached.py", "pkg/unrelated.py"],
        root=tmp_path,
    )
    assert exercised == ("pkg/reached.py",)


def test_target_attribution_fails_closed_to_every_target(tmp_path: Path) -> None:
    """When the reach cannot be attributed, narrowing would silently drop evidence."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "pkg" / "a.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "pkg" / "b.py").write_text("VALUE = 2\n", encoding="utf-8")
    (tmp_path / "tests" / "test_broken.py").write_text("def broken(:\n", encoding="utf-8")

    assert targets_exercised_by_changed_tests(
        ["tests/test_broken.py"],
        ["pkg/a.py", "pkg/b.py"],
        root=tmp_path,
    ) == ("pkg/a.py", "pkg/b.py")


def test_continuous_change_surfaces_known_dependent_tests() -> None:
    report = analyze_impact(["research/engine/continuous.py"])
    found = set(report.direct_tests) | set(report.transitive_tests)
    assert "tests/test_research_continuous_windows.py" in found
    assert "tests/test_research_continuous_integration.py" in found
    assert report.risk_class == "R3"


def test_live_risk_control_surfaces_direct_and_transitive_tests() -> None:
    report = analyze_impact(["live/risk_control.py"])
    found = set(report.direct_tests) | set(report.transitive_tests)
    assert "tests/test_live_risk_control.py" in found
    assert "tests/test_live_runner.py" in found
    assert "tests/test_live_runner_cycle.py" in found
    assert report.critical_escalations


def test_changed_test_files_are_always_recommended() -> None:
    report = analyze_impact(["tests/test_workflow_classify.py"])
    assert "tests/test_workflow_classify.py" in report.direct_tests


def test_changed_tests_are_mapped_to_mutation_targets_transitively() -> None:
    assert changed_tests_exercise_targets(
        ["tests/test_strategy_sizing_basis.py"],
        ["core/strategies/param_schedule.py"],
    )


def test_changed_tests_fail_closed_when_their_imports_cannot_be_resolved(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "pkg" / "target.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "tests" / "test_broken.py").write_text("def broken(:\n", encoding="utf-8")
    (tmp_path / "tests" / "test_dynamic.py").write_text(
        "import importlib\n"
        "def load(name: str) -> object:\n"
        "    return importlib.import_module(name)\n",
        encoding="utf-8",
    )

    assert changed_tests_exercise_targets(
        ["tests/test_broken.py"],
        ["pkg/target.py"],
        root=tmp_path,
    )
    assert changed_tests_exercise_targets(
        ["tests/test_dynamic.py"],
        ["pkg/target.py"],
        root=tmp_path,
    )


def test_changed_tests_fail_closed_on_an_unknown_dynamic_production_edge(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "pkg" / "target.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "pkg" / "loader.py").write_text(
        'import importlib\nimportlib.import_module("pkg.target")\n',
        encoding="utf-8",
    )
    (tmp_path / "tests" / "test_other.py").write_text("VALUE = 2\n", encoding="utf-8")

    assert changed_tests_exercise_targets(
        ["tests/test_other.py"],
        ["pkg/target.py"],
        root=tmp_path,
    )


def test_changed_noncritical_tests_and_docs_do_not_select_mutation(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "pkg" / "target.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "tests" / "test_other.py").write_text(
        "from pathlib import Path\n\n"
        "def test_path() -> None:\n"
        "    assert Path('README.md').suffix == '.md'\n",
        encoding="utf-8",
    )

    assert not changed_tests_exercise_targets(
        ["tests/test_other.py", "README.md"],
        ["pkg/target.py"],
        root=tmp_path,
    )
    assert not changed_tests_exercise_targets(
        ["README.md"],
        ["pkg/target.py"],
        root=tmp_path,
    )


def test_format_check_is_limited_to_changed_python_files() -> None:
    report = analyze_impact(["workflow/impact.py", "justfile", "docs/architecture.md"])
    assert format_check_command(report) == (
        "uv",
        "run",
        "ruff",
        "format",
        "--check",
        "workflow/impact.py",
    )


def test_format_check_skips_deleted_python_files(tmp_path: Path) -> None:
    report = analyze_impact(["pkg/deleted.py"], root=tmp_path, critical_map=None)
    assert format_check_command(report, root=tmp_path) == ()


def test_inheritance_names_surface_a_dependent_test(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "pkg" / "changed.py").write_text("class Guard:\n    pass\n", encoding="utf-8")
    (tmp_path / "tests" / "test_guard.py").write_text(
        "class TestGuard(Guard):\n    pass\n", encoding="utf-8"
    )
    report = analyze_impact(["pkg/changed.py"], root=tmp_path, critical_map=None)
    assert "tests/test_guard.py" in report.direct_tests


def test_unknown_dynamic_edges_are_reported_conservatively(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "pkg" / "changed.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "pkg" / "loader.py").write_text(
        'import importlib\nimportlib.import_module("pkg.changed")\n', encoding="utf-8"
    )
    (tmp_path / "tests" / "test_loader.py").write_text("from pkg import loader\n", encoding="utf-8")
    report = analyze_impact(["pkg/changed.py"], root=tmp_path, critical_map=None)
    assert "pkg/loader.py" in report.unknown_dynamic_edges
    assert "tests/test_loader.py" in report.possibly_affected_tests


def test_impact_artifact_is_machine_readable(tmp_path: Path) -> None:
    report = analyze_impact(["research/engine/continuous.py"])
    output = tmp_path / "test-map.json"
    write_test_map(report, output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["full_suite_mandatory"] is True
    assert payload["recommended_pytest_command"].startswith("uv run pytest -q")


def test_impact_artifact_is_independent_of_input_path_order() -> None:
    paths = ["workflow/impact.py", "docs/architecture.md", "justfile"]
    forward = analyze_impact(paths)
    reverse = analyze_impact(list(reversed(paths)))
    assert forward == reverse


def test_default_impact_artifact_is_gitignored() -> None:
    completed = subprocess.run(
        ["git", "check-ignore", "workflow/impact/test-map.json"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0


def test_report_never_claims_complete_coverage() -> None:
    report = analyze_impact(["research/engine/continuous.py"], root=REPO_ROOT)
    assert "not complete" in report.completeness_note.lower()


def test_every_configured_critical_dependency_names_an_existing_path() -> None:
    report = analyze_impact(
        [
            "research/engine/continuous.py",
            "live/risk_control.py",
            "core/strategies/rsi_wpr_bb_signals.py",
        ]
    )
    configured = set(report.direct_tests) | set(report.possibly_affected_tests)
    assert configured
    assert all((REPO_ROOT / path).is_file() for path in configured)
