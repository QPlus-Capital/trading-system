"""Tests for universe selection + global structure (return-first, risk-gated)."""

import pandas as pd
import pytest
from research.stages.universe import (
    NoEligibleConfig,
    select,
    select_structure,
    select_universe,
)


def _df() -> pd.DataFrame:
    """Three structures. ``high_ret`` has the most return at a tolerable risk-adjustment;
    ``high_rpd`` is best risk-adjusted but earns less; ``reckless`` earns most but its
    risk-adjustment is far below the best (excluded by the gate). ``W`` is a weak instrument
    dropped by the universe filter."""
    specs = {
        "high_ret": {"X": (2.3, 12.0, 80.0), "Y": (2.4, 11.0, 78.0), "Z": (2.2, 11.5, 75.0),
                     "W": (0.5, 1.0, 55.0)},
        "high_rpd": {"X": (2.6, 9.0, 80.0), "Y": (2.5, 9.5, 78.0), "Z": (2.5, 9.0, 75.0),
                     "W": (0.5, 1.0, 55.0)},
        "reckless": {"X": (1.0, 15.0, 70.0), "Y": (1.1, 14.0, 68.0), "Z": (0.9, 16.0, 65.0),
                     "W": (0.5, 1.0, 55.0)},
    }
    rows = []
    for variation, insts in specs.items():
        for inst, (rpd, oos, prof) in insts.items():
            rows.append({"variation": variation, "train_months": 24, "instrument": inst,
                         "return_per_dd": rpd, "mean_oos_pct": oos, "pct_profitable": prof})
    return pd.DataFrame(rows)


def test_structure_is_return_first_among_tolerable_risk() -> None:
    # high_ret earns more than high_rpd and both clear the risk gate -> return wins.
    assert select_structure(_df()) == ("high_ret", 24)


def test_structure_gate_excludes_reckless_high_return() -> None:
    # reckless has the highest return but its risk-adjustment is far below the best -> excluded,
    # so it is NOT picked despite the higher return.
    assert select_structure(_df())[0] != "reckless"


def test_structure_gate_excludes_a_negative_market() -> None:
    # A structure with the highest return but a losing market fails the robustness gate.
    df = _df()
    df.loc[(df.variation == "high_ret") & (df.instrument == "Z"), "mean_oos_pct"] = -2.0
    # high_ret now has a negative market (frac_positive 0.75 < 0.9) -> high_rpd wins instead.
    assert select_structure(df) == ("high_rpd", 24)


def test_select_universe_drops_the_weak_instrument() -> None:
    assert select_universe(_df(), "high_ret", 24) == ["X", "Y", "Z"]


def test_select_end_to_end() -> None:
    sel = select(_df())
    assert sel.variation == "high_ret"
    assert sel.train_months == 24
    assert sel.instruments == ["X", "Y", "Z"]


def test_selection_fails_closed_when_nothing_clears_the_gates() -> None:
    """#2: no eligible config must RAISE, not silently return the highest raw return.

    The old fallback widened the pool to everything exactly when the risk gates had rejected
    every candidate -- so 'nothing is good enough' came back as 'trade the most reckless one'.
    """
    df = _df()
    # Make every structure fail the robustness gate: one losing market each.
    df.loc[df.instrument == "Z", "mean_oos_pct"] = -2.0
    df.loc[df.instrument == "Y", "mean_oos_pct"] = -1.0
    with pytest.raises(NoEligibleConfig):
        select_structure(df)
