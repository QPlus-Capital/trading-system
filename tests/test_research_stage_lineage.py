"""#31: a stage may only build on artifacts it can prove were produced by the run it is in.

The failure this prevents actually happened: a run reported one variation's gate evidence beside
another variation's numbers, because Stage 2 had been re-run after Stage 3 read it. Every file
existed, every stage "succeeded", and the result was meaningless.

These tests drive the REAL stage entrypoints wherever the stage is cheap enough to complete
(Stage 1 ingesting a study, Stage 2), and for the heavy stages assert that the entrypoint refuses
before it starts computing -- which is the property that matters, since a refusal that arrives
after an hour of backtests is not a gate anyone will keep.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from research.stages import _runbook as rb
from research.stages import edge, lineage, portfolio, select, verdict

_CONFIG_SRC = '''
from dataclasses import dataclass


@dataclass
class _Inst:
    raw_symbol: str


def _eurusd() -> _Inst:
    return _Inst("EURUSD")


def _gbpusd() -> _Inst:
    return _Inst("GBPUSD")


INSTRUMENTS = [(_eurusd, "data/eurusd.csv", 1), (_gbpusd, "data/gbpusd.csv", 1)]
VARIATIONS = {"v_alpha": {}, "v_beta": {}}
PARAM_GRID: dict[str, list[float]] = {}
'''


def _write_config(path: Path, marker: str = "original") -> Path:
    path.write_text(f"{_CONFIG_SRC}\nMARKER = {marker!r}\n", encoding="utf-8")
    return path


def _write_study(study_dir: Path) -> Path:
    """A tiny study table: two variations x two training lengths x two instruments, all complete."""
    study_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for variation, ret in (("v_alpha", 30.0), ("v_beta", 20.0)):
        for train in (24, 36):
            for instrument in ("EURUSD", "GBPUSD"):
                rows.append(
                    {
                        "variation": variation,
                        "train_months": train,
                        "instrument": instrument,
                        "mean_oos_pct": ret + (2.0 if train == 36 else 0.0),
                        "return_per_dd": 3.0 if variation == "v_alpha" else 2.8,
                        "pct_profitable": 70.0,
                    }
                )
    pd.DataFrame(rows).to_csv(study_dir / "study.csv", index=False)
    pd.DataFrame({"variation": ["v_alpha", "v_beta"], "dsr": [1.5, 1.2]}).to_csv(
        study_dir / "ranking.csv", index=False
    )
    (study_dir / "overfitting.json").write_text('{"pbo": 0.05, "n_trials": 4}', encoding="utf-8")
    return study_dir


@pytest.fixture
def study(tmp_path: Path) -> tuple[Path, Path, Path]:
    """``(config, study_dir, run_dir)`` -- the inputs of a fresh framework run."""
    cfg = _write_config(tmp_path / "study_cfg.py")
    study_dir = _write_study(tmp_path / "study_src")
    run_dir = tmp_path / "run_test"
    run_dir.mkdir()
    return cfg, study_dir, run_dir


def _run_edge(study: tuple[Path, Path, Path]) -> None:
    cfg, study_dir, run_dir = study
    edge.main([str(cfg), "--from", str(study_dir), "--run", str(run_dir)])


# ------------------------------------------------------------------ the happy path
def test_a_clean_run_completes_stage_1_and_2(study: tuple[Path, Path, Path]) -> None:
    _cfg, _src, run_dir = study
    _run_edge(study)
    select.main(["--run", str(run_dir)])

    assert (run_dir / "selection.json").is_file()
    for stage in ("edge", "select"):
        m = lineage.read_manifest(run_dir, stage)
        assert m is not None, f"stage '{stage}' left no completion marker"
        assert m.verify_outputs(run_dir) == []
        assert m.verify_inputs() == []
    # Both stages belong to ONE run -- a shared run id is what makes "same run" checkable.
    assert lineage.read_manifest(run_dir, "edge").run_id == (  # type: ignore[union-attr]
        lineage.read_manifest(run_dir, "select").run_id  # type: ignore[union-attr]
    )
    # Stage 2 recorded the hash Stage 1's study.csv had when it READ it.
    sel = lineage.read_manifest(run_dir, "select")
    assert sel is not None
    assert sel.upstream["study.csv"] == lineage.sha256_file(run_dir / "study.csv")


# ------------------------------------------------------------------ tampering with artifacts
def test_altering_study_csv_stops_stage_2_and_names_both_hashes(
    study: tuple[Path, Path, Path],
) -> None:
    _cfg, _src, run_dir = study
    _run_edge(study)

    df = pd.read_csv(run_dir / "study.csv")
    df.loc[0, "mean_oos_pct"] = 999.0  # the edit that used to travel silently downstream
    df.to_csv(run_dir / "study.csv", index=False)

    with pytest.raises(SystemExit) as err:
        select.main(["--run", str(run_dir)])
    msg = str(err.value)
    assert "study.csv" in msg
    assert "recorded" in msg and "actual" in msg  # both hashes named, so the operator can see it


def test_altering_the_config_contents_stops_the_next_stage(
    study: tuple[Path, Path, Path],
) -> None:
    """Same path, different content -- the case no output hash can catch."""
    cfg, _src, run_dir = study
    _run_edge(study)
    _write_config(cfg, marker="edited-after-the-study-ran")

    with pytest.raises(SystemExit) as err:
        select.main(["--run", str(run_dir)])
    msg = str(err.value)
    assert "inputs of stage 'edge' changed" in msg
    assert "study_config" in msg


def test_replacing_selection_json_stops_stage_4(study: tuple[Path, Path, Path]) -> None:
    _cfg, _src, run_dir = study
    _run_edge(study)
    select.main(["--run", str(run_dir)])
    _fake_portfolio_stage(run_dir)

    sel = json.loads((run_dir / "selection.json").read_text(encoding="utf-8"))
    sel["variation"] = "v_beta"  # a different structure than the portfolio was built for
    (run_dir / "selection.json").write_text(json.dumps(sel, indent=2), encoding="utf-8")

    with pytest.raises(SystemExit) as err:
        verdict.main(["--run", str(run_dir)])
    assert "selection.json" in str(err.value)


def test_portfolio_json_from_another_run_stops_stage_4(
    study: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """Spec from one evaluation, trades from another -- each file intact, the pair meaningless."""
    _cfg, _src, run_dir = study
    _run_edge(study)
    select.main(["--run", str(run_dir)])
    _fake_portfolio_stage(run_dir)

    other = json.loads((run_dir / "portfolio.json").read_text(encoding="utf-8"))
    other["variation"] = "v_beta"
    (run_dir / "portfolio.json").write_text(json.dumps(other, indent=2), encoding="utf-8")

    with pytest.raises(SystemExit) as err:
        verdict.main(["--run", str(run_dir)])
    assert "portfolio.json" in str(err.value)


def test_stage_3_refuses_a_tampered_upstream_before_doing_any_work(
    study: tuple[Path, Path, Path],
) -> None:
    """The refusal must land immediately -- Stage 3's real work is hours of backtests."""
    cfg, _src, run_dir = study
    _run_edge(study)
    select.main(["--run", str(run_dir)])
    _write_config(cfg, marker="edited")

    with pytest.raises(SystemExit) as err:
        portfolio.main(["--run", str(run_dir), "--risk", "flat:0.15"])
    assert "changed" in str(err.value)
    assert not (run_dir / "portfolio_trades.csv").exists()  # nothing was computed


# ------------------------------------------------------------------ atomicity & invalidation
def test_a_stage_that_raises_publishes_nothing(tmp_path: Path) -> None:
    run = rb.RunDir.open(tmp_path)
    with pytest.raises(RuntimeError), run.stage("edge", argv={}) as st:
        st.save_json("run_manifest.json", {"config": "x"})
        raise RuntimeError("died after the first output")

    assert not (tmp_path / "run_manifest.json").exists()
    assert lineage.read_manifest(tmp_path, "edge") is None  # no completion marker -> invisible
    assert not list(tmp_path.glob(".staging_*"))  # and no debris left behind


def test_rerunning_stage_2_invalidates_stage_3_and_4(study: tuple[Path, Path, Path]) -> None:
    _cfg, _src, run_dir = study
    _run_edge(study)
    select.main(["--run", str(run_dir)])
    _fake_portfolio_stage(run_dir)
    _fake_verdict_stage(run_dir)
    assert lineage.read_manifest(run_dir, "portfolio") is not None

    select.main(["--run", str(run_dir)])  # the exact sequence that corrupted the real run

    assert lineage.read_manifest(run_dir, "select") is not None
    assert lineage.read_manifest(run_dir, "portfolio") is None
    assert lineage.read_manifest(run_dir, "verdict") is None
    # The stale FILES may still sit there; what matters is that nothing will accept them again.
    with pytest.raises(SystemExit):
        verdict.main(["--run", str(run_dir)])


# ------------------------------------------------------------------ legacy runs
def test_a_legacy_run_needs_the_flag_and_is_never_deployable(tmp_path: Path) -> None:
    (tmp_path / "study.csv").write_text("variation\nv_alpha\n", encoding="utf-8")
    (tmp_path / "selection.json").write_text('{"variation": "v_alpha"}', encoding="utf-8")

    strict = rb.RunDir.open(tmp_path)
    with pytest.raises(SystemExit) as err:
        strict.require("study.csv", "edge")
    assert "legacy" in str(err.value).lower()

    legacy = rb.RunDir.open(tmp_path, allow_legacy=True)
    assert legacy.require("study.csv", "edge").is_file()  # readable for inspection...
    with pytest.raises(SystemExit):
        legacy.assert_deployable()  # ...but never blessed


# ------------------------------------------------------------------ helpers
def _fake_portfolio_stage(run_dir: Path) -> None:
    """Publish a Stage 3 result through the REAL writer, without running hours of backtests.

    Only the lineage is under test here; the numbers are irrelevant, so this stands in for the
    compute while keeping the publication path identical to production.
    """
    run = rb.RunDir.open(run_dir)
    run.require("selection.json", "select")
    sel = json.loads((run_dir / "selection.json").read_text(encoding="utf-8"))
    with run.stage("portfolio", argv={"risk": "flat:0.15"}) as st:
        frame = pd.DataFrame({"market": ["EURUSD"], "r": [1.0], "swap_r": [0.0]})
        frame.to_csv(st.file("portfolio_trades.csv"), index=False)
        frame.to_csv(st.file("full_history_trades.csv"), index=False)
        st.save_json(
            "portfolio.json",
            {"variation": sel["variation"], "instruments": ["EURUSD"], "tail_cap_pct": 0.2},
        )


def _fake_verdict_stage(run_dir: Path) -> None:
    run = rb.RunDir.open(run_dir)
    with run.stage("verdict", argv={}) as st:
        st.save_json("verdict.json", {"passed": False})
