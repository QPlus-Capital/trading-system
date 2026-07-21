"""Impact analysis must find real repository dependencies without claiming completeness."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.quality.classify import REPO_ROOT
from scripts.quality.impact import analyze_impact, format_check_command, write_test_map


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
    report = analyze_impact(["tests/test_quality_classify.py"])
    assert "tests/test_quality_classify.py" in report.direct_tests


def test_format_check_is_limited_to_changed_python_files() -> None:
    report = analyze_impact(["scripts/quality/impact.py", "justfile", "docs/architecture.md"])
    assert format_check_command(report) == (
        "uv",
        "run",
        "ruff",
        "format",
        "--check",
        "scripts/quality/impact.py",
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
    paths = ["scripts/quality/impact.py", "docs/architecture.md", "justfile"]
    forward = analyze_impact(paths)
    reverse = analyze_impact(list(reversed(paths)))
    assert forward == reverse


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
