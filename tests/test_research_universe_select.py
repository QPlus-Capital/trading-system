"""Tests for per-candidate aggregation and market-universe filtering."""

import pandas as pd
from research.stages.universe import per_config, select_universe


def _df() -> pd.DataFrame:
    """Three structures. ``high_ret`` has the most return at a tolerable risk-adjustment;
    ``high_rpd`` is best risk-adjusted but earns less; ``reckless`` earns most but its
    risk-adjustment is far below the best (excluded by the gate). ``W`` is a weak instrument
    dropped by the universe filter."""
    specs = {
        "high_ret": {
            "X": (2.3, 12.0, 80.0),
            "Y": (2.4, 11.0, 78.0),
            "Z": (2.2, 11.5, 75.0),
            "W": (0.5, 1.0, 55.0),
        },
        "high_rpd": {
            "X": (2.6, 9.0, 80.0),
            "Y": (2.5, 9.5, 78.0),
            "Z": (2.5, 9.0, 75.0),
            "W": (0.5, 1.0, 55.0),
        },
        "reckless": {
            "X": (1.0, 15.0, 70.0),
            "Y": (1.1, 14.0, 68.0),
            "Z": (0.9, 16.0, 65.0),
            "W": (0.5, 1.0, 55.0),
        },
    }
    rows = []
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


def test_per_config_preserves_all_structure_inputs() -> None:
    summary = per_config(_df())

    assert set(summary.index.get_level_values("variation")) == {
        "high_ret",
        "high_rpd",
        "reckless",
    }
    assert summary.loc[("high_ret", 24), "frac_positive"] == 1.0
    assert summary.loc[("high_rpd", 24), "mean_rpd"] > summary.loc[("high_ret", 24), "mean_rpd"]


def test_select_universe_drops_the_weak_instrument() -> None:
    assert select_universe(_df(), "high_ret", 24) == ["X", "Y", "Z"]
