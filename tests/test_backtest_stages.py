"""Tests for the staged framework CLI skeleton (run-book + the fast, pure stage helpers)."""

import importlib

import pandas as pd
import pytest

from qplus.backtest.portfolio.risk import FlatRisk, ThrottleRisk
from qplus.backtest.stages import _runbook as rb
from qplus.backtest.stages.portfolio import parse_risk


def test_all_stage_modules_import() -> None:
    # Importing every stage catches wiring/typo errors without running the slow compute.
    for mod in ("edge", "select", "portfolio", "verdict"):
        assert importlib.import_module(f"qplus.backtest.stages.{mod}")


def test_parse_risk_flat_and_throttle() -> None:
    assert parse_risk("flat:0.15") == FlatRisk(0.15)
    assert parse_risk("throttle:0.2") == ThrottleRisk(floor_pct=0.2)
    with pytest.raises(SystemExit):
        parse_risk("martingale:9")


def test_live_fixed_stops_reads_per_market_sltp() -> None:
    from pathlib import Path

    from qplus.backtest.stages.portfolio import live_fixed_stops

    repo_root = Path(__file__).resolve().parents[1]
    stops = live_fixed_stops(repo_root / "config" / "live" / "paper_rsi_wpr_bb.py")
    assert stops  # non-empty
    for market, sltp in stops.items():
        assert isinstance(market, str)
        assert sltp["stop_loss_pct"] > 0 and sltp["take_profit_pct"] > 0


def test_rundir_roundtrip_and_missing_artifact(tmp_path) -> None:
    run = rb.RunDir.open(tmp_path)
    run.save_json("selection.json", {"variation": "x", "instruments": ["EURUSD"]})
    assert run.load_json("selection.json")["variation"] == "x"
    assert run.require("selection.json", "select").name == "selection.json"
    with pytest.raises(SystemExit):  # a missing prior-stage artifact fails with a hint
        run.require("portfolio.json", "portfolio")


def test_edge_ranking_is_return_sorted_and_gated() -> None:
    from qplus.backtest.stages.edge import ranking

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
    assert list(top["variation"]) == ["a", "b"]  # best row per variation, sorted by return
    assert int(top.iloc[0]["train_months"]) == 36  # a's best train is the higher-return one
