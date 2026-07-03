"""Test the pipeline chaining (Stage 2 -> extraction -> Stage 3/4) with a fake extractor."""

from typing import Any

import pandas as pd

from qplus.backtest.pipeline import run_pipeline
from qplus.backtest.portfolio_sim import DAY_NS


def _study_df() -> pd.DataFrame:
    rows = []
    specs = {
        "good": {"X": (3.0, 10.0, 80.0), "Y": (2.0, 8.0, 75.0), "Z": (0.5, 1.0, 55.0)},
        "bad": {"X": (1.0, 5.0, 65.0), "Y": (0.8, 4.0, 62.0), "Z": (0.3, 0.5, 52.0)},
    }
    for variation, insts in specs.items():
        for inst, (rpd, oos, prof) in insts.items():
            rows.append(
                {
                    "variation": variation,
                    "train_months": 24,
                    "instrument": inst,
                    "return_per_dd": rpd,
                    "mean_oos_pct": oos,
                    "pct_profitable": prof,
                }
            )
    return pd.DataFrame(rows)


def test_run_pipeline_selects_then_scores() -> None:
    seen: list[tuple[str, dict[str, Any], int]] = []

    def fake_extract(market: str, overrides: dict[str, Any], train_months: int) -> pd.DataFrame:
        seen.append((market, overrides, train_months))
        # one never-underwater trade per market so scoring is well-defined
        return pd.DataFrame(
            [
                {
                    "market": market,
                    "ts_opened": 0,
                    "ts_closed": 2 * DAY_NS,
                    "pnl_1pct": 100.0,
                    "entry": 10.0,
                    "exit": 11.0,
                }
            ]
        )

    daily = {
        "X": pd.Series({0: 10.0, 1: 10.5, 2: 11.0}),
        "Y": pd.Series({0: 10.0, 1: 10.5, 2: 11.0}),
    }
    res = run_pipeline(
        _study_df(), fake_extract, daily, variations={"good": {"use_bb_confirm": False}, "bad": {}}
    )
    # Stage 2 picked the risk-adjusted winner and dropped the weak instrument Z.
    assert res.selection.variation == "good"
    assert res.selection.instruments == ["X", "Y"]
    # The extractor was called once per selected instrument with the winner's overrides.
    assert [m for m, _, _ in seen] == ["X", "Y"]
    assert all(ov == {"use_bb_confirm": False} and tm == 24 for _, ov, tm in seen)
    # Stage 3/4 scored the combined 2-trade stream.
    assert res.portfolio.n_trades == 2
