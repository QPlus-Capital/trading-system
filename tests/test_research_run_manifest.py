"""#3: the study config must travel WITH the run, not be re-guessed by each stage.

A run started from config B could otherwise be finished with config A's instruments, account
profile and variation definitions -- silently producing a corrupted result with no error.
"""

from pathlib import Path

from research.stages import _runbook as rb


def test_stages_use_the_config_the_run_was_started_with(tmp_path: Path) -> None:
    run = rb.RunDir(tmp_path)
    run.save_json("run_manifest.json", {"config": "research/config/other_study.py"})
    assert run.study_config() == Path("research/config/other_study.py")


def test_an_explicit_flag_still_wins(tmp_path: Path) -> None:
    run = rb.RunDir(tmp_path)
    run.save_json("run_manifest.json", {"config": "research/config/other_study.py"})
    forced = Path("research/config/forced.py")
    assert run.study_config(forced) == forced


def test_runs_predating_the_manifest_fall_back_to_the_default(tmp_path: Path) -> None:
    # Older run directories have no manifest; they were all produced with the single default.
    assert rb.RunDir(tmp_path).study_config() == rb.DEFAULT_STUDY_CONFIG
