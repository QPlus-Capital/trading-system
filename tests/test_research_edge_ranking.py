"""Tests for the gated edge ranking that selection consumes."""

import pandas as pd
from research.stages.edge import ranking


def _rows() -> list[dict[str, object]]:
    """Two configs of the same shape over three markets; Z is the hard one."""
    rows: list[dict[str, object]] = []
    for inst, oos in [("X", 10.0), ("Y", 9.0), ("Z", -5.0)]:
        rows.append({"variation": "complete", "train_months": 24, "instrument": inst,
                     "return_per_dd": 2.0, "mean_oos_pct": oos, "pct_profitable": 70.0})
    for inst, oos in [("X", 10.0), ("Y", 9.0)]:
        rows.append({"variation": "crashed", "train_months": 24, "instrument": inst,
                     "return_per_dd": 2.0, "mean_oos_pct": oos, "pct_profitable": 70.0})
    # Z errored out for 'crashed' -> a row with no result at all.
    rows.append({"variation": "crashed", "train_months": 24, "instrument": "Z",
                 "return_per_dd": None, "mean_oos_pct": None, "pct_profitable": None})
    return rows


def test_a_config_that_crashed_on_its_worst_market_is_not_ranked_on_the_survivors() -> None:
    """#17: a failed task leaves a row without mean_oos_pct, which dropna removes. Averaging the
    remainder rewards a config for having crashed exactly where it was weakest."""
    by_var = ranking(pd.DataFrame(_rows())).set_index("variation")
    # Dropping Z lifts 'crashed' above 'complete' on raw return ...
    assert by_var.loc["crashed", "mean_ret"] > by_var.loc["complete", "mean_ret"]
    # ... but a missing required cell makes it ineligible rather than a smaller sample.
    assert not bool(by_var.loc["crashed", "eligible"])
    assert not bool(by_var.loc["crashed", "complete"])


def test_a_complete_config_is_still_judged_on_its_merits() -> None:
    by_var = ranking(pd.DataFrame(_rows())).set_index("variation")
    assert bool(by_var.loc["complete", "complete"])  # all three cells present
