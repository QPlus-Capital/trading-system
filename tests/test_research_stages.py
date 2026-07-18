"""Tests for the staged framework CLI skeleton (run-book + the fast, pure stage helpers)."""

import importlib
from pathlib import Path

import pandas as pd
import pytest
from research.portfolio.risk import FlatRisk, ThrottleRisk
from research.stages import _runbook as rb
from research.stages.portfolio import parse_risk


def test_all_stage_modules_import() -> None:
    # Importing every stage catches wiring/typo errors without running the slow compute.
    for mod in ("edge", "select", "portfolio", "verdict"):
        assert importlib.import_module(f"research.stages.{mod}")


def test_parse_risk_flat_and_throttle() -> None:
    assert parse_risk("flat:0.15") == FlatRisk(0.15)
    assert parse_risk("throttle:0.2") == ThrottleRisk(floor_pct=0.2)
    with pytest.raises(SystemExit):
        parse_risk("martingale:9")


def test_parse_risk_kelly() -> None:
    from research.portfolio.risk import KellyRisk

    assert parse_risk("kelly:0.05") == KellyRisk(beta=0.05)
    assert parse_risk("kelly") == KellyRisk(beta=0.05)  # default tolerance


def test_live_fixed_stops_reads_per_market_sltp() -> None:
    from pathlib import Path

    from research.stages.portfolio import live_fixed_stops

    repo_root = Path(__file__).resolve().parents[1]
    stops = live_fixed_stops(repo_root / "live" / "config" / "rsi_wpr_bb.py")
    assert stops  # non-empty
    for market, sltp in stops.items():
        assert isinstance(market, str)
        assert sltp["stop_loss_pct"] > 0 and sltp["take_profit_pct"] > 0


def test_rundir_roundtrip_and_missing_artifact(tmp_path: Path) -> None:
    run = rb.RunDir.open(tmp_path)
    run.save_json("selection.json", {"variation": "x", "instruments": ["EURUSD"]})
    assert run.load_json("selection.json")["variation"] == "x"
    assert run.require("selection.json", "select").name == "selection.json"
    with pytest.raises(SystemExit):  # a missing prior-stage artifact fails with a hint
        run.require("portfolio.json", "portfolio")


def test_edge_ranking_is_return_sorted_and_gated() -> None:
    from research.stages.edge import ranking

    df = pd.DataFrame(
        {
            "variation": ["a", "a", "b", "b"],
            "train_months": [24, 36, 24, 36],
            "instrument": ["E", "E", "E", "E"],
            "mean_oos_pct": [10.0, 30.0, 5.0, 8.0],
            "return_per_dd": [2.0, 3.0, 1.0, 1.2],
            "pct_profitable": [70, 70, 65, 65],
        }
    )
    top = ranking(df)
    # EVERY (variation, train_months) row survives, sorted by return: reducing to one row per
    # variation dropped eligible candidates whenever a variation's best length was gated out
    # while a lower-return length passed (Codex round 6).
    assert list(top["variation"]) == ["a", "a", "b", "b"]
    assert [int(t) for t in top["train_months"]] == [36, 24, 36, 24]  # return-sorted


def test_edge_ranking_dsr_gate_excludes_low_dsr() -> None:
    from research.stages.edge import ranking

    df = pd.DataFrame(
        {
            "variation": ["a", "a", "b", "b"],
            "train_months": [24, 36, 24, 36],
            "instrument": ["E", "E", "E", "E"],
            "mean_oos_pct": [30.0, 30.0, 25.0, 25.0],
            "return_per_dd": [3.0, 3.0, 2.9, 2.9],
            "pct_profitable": [100, 100, 100, 100],
        }
    )
    # 'a' has the higher return but an overfit DSR; 'b' clears the DSR gate.
    top = ranking(df, dsr_by_variation={"a": 0.10, "b": 0.99})
    a = top[top["variation"] == "a"].iloc[0]
    b = top[top["variation"] == "b"].iloc[0]
    assert not a["dsr_ok"] and b["dsr_ok"]  # low DSR gated out, high DSR kept


def test_edge_ranking_unknown_dsr_does_not_gate_out() -> None:
    from research.stages.edge import ranking

    df = pd.DataFrame(
        {
            "variation": ["a"],
            "train_months": [36],
            "instrument": ["E"],
            "mean_oos_pct": [20.0],
            "return_per_dd": [2.0],
            "pct_profitable": [100],
        }
    )
    top = ranking(df)  # no DSR supplied
    assert bool(top.iloc[0]["dsr_ok"])  # unknown DSR must not exclude


def test_load_overfitting_reads_ranking_and_pbo(tmp_path: Path) -> None:
    from research.stages.edge import load_overfitting

    pd.DataFrame({"variation": ["a", "b"], "dsr": [1.0, 0.4]}).to_csv(
        tmp_path / "ranking.csv", index=False
    )
    (tmp_path / "overfitting.json").write_text('{"pbo": 0.05, "n_trials": 864}')
    dsr, pbo = load_overfitting(tmp_path)
    assert dsr == {"a": 1.0, "b": 0.4}
    assert pbo == 0.05


def test_load_overfitting_missing_artifacts_returns_empty(tmp_path: Path) -> None:
    from research.stages.edge import load_overfitting

    dsr, pbo = load_overfitting(tmp_path)
    assert dsr == {} and pbo is None
