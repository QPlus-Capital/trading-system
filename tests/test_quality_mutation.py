"""Behavioural tests for focused mutation orchestration and its ratchet."""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Sequence
from pathlib import Path

import pytest
from scripts.quality.classify import load_model
from scripts.quality.mutation import (
    MutationBaseline,
    MutationReport,
    Survivor,
    all_results_command,
    check_baseline,
    ensure_supported_platform,
    load_baseline,
    load_policy,
    mutation_executable,
    parse_mutmut_results,
    select_fast_targets,
    summary_lines,
)


def test_policy_names_every_required_critical_scope() -> None:
    policy = load_policy()
    paths = {target.path for target in policy.targets}
    assert {
        "live/risk_control.py",
        "research/portfolio/sizing.py",
        "research/portfolio/drawdown.py",
        "research/portfolio/risk.py",
        "research/portfolio/stats.py",
        "core/strategies/param_schedule.py",
        "research/engine/continuous.py",
        "research/regression.py",
    } <= paths


def test_policy_names_pure_functions_instead_of_whole_modules() -> None:
    policy = load_policy()
    patterns = [pattern for target in policy.targets for pattern in target.mutant_patterns]
    assert patterns
    assert all(not pattern.endswith(".*") for pattern in patterns)
    for required in (
        "position_volume",
        "simulate",
        "trailing_floor",
        "tail_cap",
        "r_multiples",
        "segment_at",
        "window_returns",
        "compare",
    ):
        assert any(required in pattern for pattern in patterns)


def test_fast_scope_reuses_the_classifier_and_selects_changed_r3_targets() -> None:
    policy = load_policy()
    selected = select_fast_targets(["README.md", "live/risk_control.py"], policy, load_model())
    assert [target.path for target in selected] == ["live/risk_control.py"]


def test_native_windows_mutation_fails_with_the_documented_linux_direction() -> None:
    with pytest.raises(RuntimeError, match="Linux CI"):
        ensure_supported_platform("Windows")
    ensure_supported_platform("Linux")


def test_mutmut_results_are_parsed_into_machine_statuses() -> None:
    parsed = parse_mutmut_results(
        "    live.risk_control.x__mutmut_1: killed\n    live.risk_control.x__mutmut_2: survived\n"
    )
    assert parsed == {
        "live.risk_control.x__mutmut_1": "killed",
        "live.risk_control.x__mutmut_2": "survived",
    }


def test_mutation_uses_the_console_script_not_python_module_execution(tmp_path: Path) -> None:
    binary = tmp_path / "bin"
    binary.mkdir()
    python = binary / "python"
    console = binary / "mutmut"
    python.touch()
    console.touch()
    assert mutation_executable("mutmut", str(python), "Linux") == str(console)


def test_mutmut_all_results_passes_the_required_boolean_value() -> None:
    assert all_results_command(["mutmut"]) == ["mutmut", "results", "--all", "true"]


def test_mutation_workflow_invokes_the_just_executable() -> None:
    workflow = (Path(__file__).parents[1] / ".github" / "workflows" / "mutation.yml").read_text(
        encoding="utf-8"
    )
    assert "uvx --from rust-just just mutation-critical" in workflow
    assert "uvx rust-just" not in workflow


def test_mutation_skips_the_in_process_covered_line_prepass() -> None:
    """Avoid reloading native extensions between Mutmut's pytest passes."""
    pyproject = Path(__file__).parents[1] / "pyproject.toml"
    with pyproject.open("rb") as handle:
        config = tomllib.load(handle)
    assert config["tool"]["mutmut"]["mutate_only_covered_lines"] is False


def test_mutation_copies_the_classifier_model_into_the_mutant_tree() -> None:
    pyproject = Path(__file__).parents[1] / "pyproject.toml"
    with pyproject.open("rb") as handle:
        config = tomllib.load(handle)
    assert ".ai" in config["tool"]["mutmut"]["also_copy"]


def test_mutation_workflow_uploads_the_hidden_machine_report() -> None:
    workflow = (Path(__file__).parents[1] / ".github" / "workflows" / "mutation.yml").read_text(
        encoding="utf-8"
    )
    assert "include-hidden-files: true" in workflow


def test_committed_critical_baseline_is_complete_and_explained() -> None:
    baseline = load_baseline()
    assert baseline.change_explanation.strip()
    assert baseline.summary.total > 0
    assert baseline.summary.not_checked == 0
    assert all(item.reason.strip() for item in baseline.survivors)


def test_baseline_rejects_an_unclassified_survivor(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.toml"
    baseline.write_text(
        """version = 1
tool = "mutmut"
tool_version = "3.5.0"
change_explanation = "test"
targets = ["one"]
[summary]
total = 1
killed = 0
survived = 1
no_tests = 0
skipped = 0
suspicious = 0
timeout = 0
not_checked = 0
interrupted = 0
segfault = 0
caught_by_type_check = 0
[[survivor_groups]]
names = ["module.x__mutmut_1"]
reason = "not enough"
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="classification"):
        load_baseline(baseline)


def test_baseline_group_classifies_each_exact_survivor(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.toml"
    baseline.write_text(
        """version = 1
tool = "mutmut"
tool_version = "3.5.0"
change_explanation = "test"
targets = ["one"]
[summary]
total = 2
killed = 0
survived = 2
no_tests = 0
skipped = 0
suspicious = 0
timeout = 0
not_checked = 0
interrupted = 0
segfault = 0
caught_by_type_check = 0
[[survivor_groups]]
classification = "meaningful"
reason = "reviewed gap"
names = ["module.x__mutmut_1", "module.x__mutmut_2"]
""",
        encoding="utf-8",
    )
    loaded = load_baseline(baseline)
    assert loaded.survivors == (
        Survivor("module.x__mutmut_1", "meaningful", "reviewed gap"),
        Survivor("module.x__mutmut_2", "meaningful", "reviewed gap"),
    )


def test_a_weakened_test_creates_a_survivor_and_the_ratchet_rejects_it() -> None:
    """Weakening a test moves one mutant from killed to survived and leaves the total alone.

    The earlier fixture dropped every baseline survivor as well, so the report it built could
    only arise from deleted code. That made the second assertion pass on the total difference
    rather than on anything a weakened test actually causes.
    """
    baseline = load_baseline()
    assert baseline.summary.killed > 0
    weakened = MutationReport(
        scope="critical",
        targets=baseline.targets,
        mutants={
            **{f"killed_{i}": "killed" for i in range(baseline.summary.killed - 1)},
            **{item.name: "survived" for item in baseline.survivors},
            "newly_surviving_mutant": "survived",
        },
    )
    assert weakened.summary.total == baseline.summary.total
    issues = check_baseline(weakened, baseline)
    assert any("newly_surviving_mutant" in issue for issue in issues)
    assert any("score regressed" in issue for issue in issues)


def test_an_exact_clean_report_passes_the_ratchet(tmp_path: Path) -> None:
    del tmp_path  # the fixture makes this a separate filesystem-isolated guard case
    baseline = load_baseline()
    survivors = {item.name: "survived" for item in baseline.survivors}
    killed = {
        f"synthetic_killed_{i}": "killed" for i in range(baseline.summary.total - len(survivors))
    }
    report = MutationReport(
        scope="critical", targets=baseline.targets, mutants={**killed, **survivors}
    )
    assert check_baseline(report, baseline) == []


def _synthetic_report(
    *,
    baseline: MutationBaseline,
    killed_delta: int = 0,
    extra_survivors: Sequence[str] = (),
    dropped_survivors: int = 0,
    drop_last_target: bool = False,
    scope: str = "critical",
    unhealthy: bool = False,
) -> MutationReport:
    """Build a report that differs from the baseline along exactly the named axes."""
    survivors = [item.name for item in baseline.survivors][dropped_survivors:]
    mutants: dict[str, str] = {
        f"synthetic_killed_{i}": "killed" for i in range(baseline.summary.killed + killed_delta)
    }
    mutants.update(dict.fromkeys(survivors, "survived"))
    mutants.update(dict.fromkeys(extra_survivors, "survived"))
    if unhealthy:
        mutants["synthetic_unhealthy"] = "no tests"
    targets = baseline.targets[:-1] if drop_last_target else baseline.targets
    return MutationReport(scope=scope, targets=targets, mutants=mutants)


def test_added_production_code_alone_no_longer_fails_the_ratchet() -> None:
    """AC-01. A branch that adds code raises the mutant total and nothing else."""
    baseline = load_baseline()
    report = _synthetic_report(baseline=baseline, killed_delta=128)
    assert report.summary.total > baseline.summary.total
    assert report.summary.score >= baseline.summary.score
    assert check_baseline(report, baseline) == []


@pytest.mark.parametrize("killed_delta", [0, 128, -128])
def test_an_unexplained_survivor_fails_whatever_the_total_is(killed_delta: int) -> None:
    """AC-02, INV-02. The protection this gate exists for is independent of the total."""
    baseline = load_baseline()
    report = _synthetic_report(
        baseline=baseline,
        killed_delta=killed_delta,
        extra_survivors=("live.risk_control.x_position_volume__mutmut_9999",),
    )
    issues = check_baseline(report, baseline)
    assert any("live.risk_control.x_position_volume__mutmut_9999" in issue for issue in issues)


def test_a_score_regression_fails_although_the_total_is_no_longer_compared() -> None:
    """AC-03. Fewer kills against the same reviewed survivor set is a real regression."""
    baseline = load_baseline()
    report = _synthetic_report(baseline=baseline, killed_delta=-500)
    assert report.summary.score < baseline.summary.score
    assert any("score regressed" in issue for issue in check_baseline(report, baseline))


def test_a_changed_target_set_still_fails() -> None:
    """AC-04. Dropping a critical target must never pass silently."""
    baseline = load_baseline()
    report = _synthetic_report(baseline=baseline, drop_last_target=True)
    assert any("targets changed" in issue for issue in check_baseline(report, baseline))


_ISSUE_KINDS = (
    ("ended as", "health"),
    ("applies to critical scope", "scope"),
    ("targets changed", "targets"),
    ("total changed", "total"),
    ("unexplained surviving", "unexpected"),
    ("must be tightened", "missing"),
    ("score regressed", "score"),
)


def _kinds(issues: Sequence[str]) -> set[str]:
    found = set()
    for issue in issues:
        matched = {kind for marker, kind in _ISSUE_KINDS if marker in issue}
        assert matched, f"unclassified gate issue: {issue!r}"
        found |= matched
    return found


def _rule_before_this_change(report: MutationReport, baseline: MutationBaseline) -> set[str]:
    """Independent restatement of the rule #125 replaces, as issue kinds.

    Written from the pre-change source rather than by calling it, so that the differential
    below compares two implementations instead of comparing one with itself.
    """
    summary = report.summary
    kinds: set[str] = set()
    unhealthy = (
        "no_tests",
        "skipped",
        "suspicious",
        "timeout",
        "not_checked",
        "interrupted",
        "segfault",
        "caught_by_type_check",
    )
    if any(getattr(summary, field) for field in unhealthy):
        kinds.add("health")
    if report.scope != "critical":
        kinds.add("scope")
    if report.targets != baseline.targets:
        kinds.add("targets")
    if summary.total != baseline.summary.total:
        kinds.add("total")
    allowed = {item.name for item in baseline.survivors}
    observed = {name for name, status in report.mutants.items() if status == "survived"}
    if observed - allowed:
        kinds.add("unexpected")
    if allowed - observed:
        kinds.add("missing")
    if summary.score + 1e-12 < baseline.summary.score:
        kinds.add("score")
    return kinds


_DIFFERENTIAL_CASES = tuple(
    {
        "killed_delta": killed_delta,
        "extra_survivors": extra_survivors,
        "dropped_survivors": dropped_survivors,
        "drop_last_target": drop_last_target,
        "scope": scope,
        "unhealthy": unhealthy,
    }
    for killed_delta in (0, 64, -64, -700)
    for extra_survivors in ((), ("live.runner.xǁLiveRunnerǁ_total_open_risk__mutmut_9999",))
    for dropped_survivors in (0, 3)
    for drop_last_target in (False, True)
    for scope in ("critical", "fast")
    for unhealthy in (False, True)
)


@pytest.mark.parametrize("case", _DIFFERENTIAL_CASES)
def test_the_rule_changes_only_where_the_total_alone_differed(case: dict[str, object]) -> None:
    """INV-01, INV-02. Across 128 shapes the new rule drops the total verdict and nothing else."""
    baseline = load_baseline()
    report = _synthetic_report(baseline=baseline, **case)  # type: ignore[arg-type]
    before = _rule_before_this_change(report, baseline)
    after = _kinds(check_baseline(report, baseline))
    assert after <= before, f"new verdict invented {after - before}"
    assert before - after <= {"total"}, f"new verdict lost {before - after - {'total'}}"
    if "unexpected" in before:
        assert "unexpected" in after


@pytest.mark.parametrize("extra_survivors", [(), ("live.risk_control.x_flat__mutmut_9999",)])
def test_both_totals_stay_visible_on_a_passing_and_a_failing_run(
    extra_survivors: tuple[str, ...],
) -> None:
    """AC-05. Dropping the comparison must not drop the number needed to refresh the baseline."""
    baseline = load_baseline()
    report = _synthetic_report(
        baseline=baseline, killed_delta=128, extra_survivors=extra_survivors
    )
    assert report.summary.total != baseline.summary.total
    assert bool(check_baseline(report, baseline)) is bool(extra_survivors)
    text = "\n".join(summary_lines("critical", report, baseline, Path("critical.toml")))
    assert str(report.summary.total) in text
    assert str(baseline.summary.total) in text


def test_the_differential_cases_actually_exercise_every_verdict() -> None:
    """A differential proves nothing if the generated cases never trigger the verdicts."""
    baseline = load_baseline()
    seen: set[str] = set()
    for case in _DIFFERENTIAL_CASES:
        seen |= _rule_before_this_change(
            _synthetic_report(baseline=baseline, **case),  # type: ignore[arg-type]
            baseline,
        )
    assert seen == {"health", "scope", "targets", "total", "unexpected", "missing", "score"}


@pytest.mark.skipif(platform.system() != "Linux", reason="Mutmut requires fork/WSL on Windows")
def test_a_real_weakened_test_increases_survivors_and_is_caught(tmp_path: Path) -> None:
    """Exercise the selected tool, not a fake mutator, on a minimal boundary contract."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "sample.py").write_text(
        "def above_limit(value: int) -> bool:\n    return value >= 10\n", encoding="utf-8"
    )
    (tmp_path / "pyproject.toml").write_text(
        '[tool.mutmut]\npaths_to_mutate = ["sample.py"]\ntests_dir = ["tests/"]\n',
        encoding="utf-8",
    )
    test_file = tmp_path / "tests" / "test_sample.py"

    def mutation_report(test_body: str) -> MutationReport:
        test_file.write_text(
            "from sample import above_limit\n\ndef test_boundary():\n" + test_body,
            encoding="utf-8",
        )
        mutants = tmp_path / "mutants"
        if mutants.exists():
            shutil.rmtree(mutants)
        command = [mutation_executable("mutmut", sys.executable, platform.system())]
        mutation = subprocess.run(
            [*command, "run", "sample.*"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )
        assert mutation.returncode == 0, (
            f"Mutmut probe failed:\nSTDOUT:\n{mutation.stdout}\nSTDERR:\n{mutation.stderr}"
        )
        result = subprocess.run(
            all_results_command(command),
            cwd=tmp_path,
            check=True,
            capture_output=True,
            text=True,
        )
        parsed = {
            name: status
            for name, status in parse_mutmut_results(result.stdout).items()
            if name.startswith("sample.")
        }
        return MutationReport("critical", ("probe",), parsed)

    strong = mutation_report("    assert above_limit(10)\n    assert not above_limit(9)\n")
    weak = mutation_report("    assert above_limit(11)\n    assert not above_limit(8)\n")
    assert weak.summary.survived > strong.summary.survived

    baseline = MutationBaseline(
        version=1,
        tool="mutmut",
        tool_version="3.5.0",
        change_explanation="strong probe",
        targets=strong.targets,
        summary=strong.summary,
        survivors=tuple(
            Survivor(name, "meaningful", "reviewed probe survivor")
            for name, status in strong.mutants.items()
            if status == "survived"
        ),
    )
    assert any("surviv" in issue.lower() for issue in check_baseline(weak, baseline))
