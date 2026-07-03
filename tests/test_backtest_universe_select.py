"""Tests for Stage 2 universe selection + global structure."""

import pandas as pd

from qplus.backtest.universe_select import select, select_structure, select_universe


def _df() -> pd.DataFrame:
    rows = []
    # "good" variation beats "bad" on risk-adjusted return per drawdown across instruments.
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


def test_select_structure_picks_best_risk_adjusted() -> None:
    assert select_structure(_df()) == ("good", 24)


def test_select_universe_drops_the_weak_instrument() -> None:
    # Under "good": X and Y clear the thresholds; Z (rpd 0.5, prof 55) is dropped.
    assert select_universe(_df(), "good", 24) == ["X", "Y"]


def test_select_end_to_end() -> None:
    sel = select(_df())
    assert sel.variation == "good"
    assert sel.train_months == 24
    assert sel.instruments == ["X", "Y"]
