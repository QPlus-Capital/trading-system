"""#29/#30: what the dashboard is allowed to tell the operator about risk.

Both rules exist because the monitor sits next to a live account: a number that looks precise but
rests on the wrong basis is worse than no number, because it invites action.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from monitoring.deals import per_trade_risk
from monitoring.risk_view import summarize_open_risk, window_history


# --------------------------------------------------------------------- #30: open risk
def test_open_risk_is_the_sum_when_every_position_can_be_priced() -> None:
    risk = summarize_open_risk([("EURUSD", 120.0), ("DE40", 80.0)])
    assert risk.determinate
    assert risk.total == 200.0


def test_an_unpriceable_position_makes_the_headroom_indeterminate() -> None:
    """The runner charges this as infinite risk and blocks new entries; the UI must not disagree.

    Reporting 120 here -- the sum of what COULD be priced -- would show headroom under the 2% cap
    while the account is in fact blocked from opening anything.
    """
    risk = summarize_open_risk([("EURUSD", 120.0), ("XAGUSD", None)])
    assert not risk.determinate
    assert risk.unpriceable == ["XAGUSD"]


def test_every_unpriceable_market_is_named() -> None:
    risk = summarize_open_risk([("USTEC", None), ("EURUSD", 10.0), ("DE40", None)])
    assert risk.unpriceable == ["DE40", "USTEC"]  # sorted, so the message is stable


# --------------------------------------------------------------------- #29: the risk basis
def _trades(opens: list[str], closes: list[str], pnl: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open_time": pd.to_datetime(opens, utc=True),
            "close_time": pd.to_datetime(closes, utc=True),
            "net_pnl": pnl,
        }
    )


def test_the_window_keeps_each_trades_original_risk_basis() -> None:
    """The defect: walking only the window charges the first shown trade the opening balance.

    Four sequential trades, each +1000 on a 100k account at 1% risk, so the bases are 1000, 1010,
    1020, 1030. Showing only the last two must keep 1020 and 1030 -- not restart at 1000.
    """
    all_trades = _trades(
        ["2026-01-01", "2026-01-03", "2026-01-05", "2026-01-07"],
        ["2026-01-02", "2026-01-04", "2026-01-06", "2026-01-08"],
        [1_000.0, 1_000.0, 1_000.0, 1_000.0],
    )
    all_risk = per_trade_risk(all_trades, start_balance=100_000.0, risk_frac=0.01)

    view = window_history(
        all_trades,
        all_risk,
        window_start=pd.Timestamp("2026-01-05", tz="UTC"),
        account_start=100_000.0,
    )
    assert len(view.trades) == 2
    assert view.hidden == 2
    assert list(view.risk) == [1_020.0, 1_030.0]


def test_the_window_start_balance_includes_what_happened_before_it() -> None:
    """The equity curve drawn beside the window must start where the account actually was."""
    all_trades = _trades(
        ["2026-01-01", "2026-01-05"], ["2026-01-02", "2026-01-06"], [2_500.0, 1_000.0]
    )
    all_risk = per_trade_risk(all_trades, start_balance=100_000.0, risk_frac=0.01)

    view = window_history(
        all_trades,
        all_risk,
        window_start=pd.Timestamp("2026-01-04", tz="UTC"),
        account_start=100_000.0,
    )
    assert view.start_balance == 102_500.0


def test_a_full_window_hides_nothing_and_changes_nothing() -> None:
    all_trades = _trades(["2026-01-01"], ["2026-01-02"], [500.0])
    all_risk = per_trade_risk(all_trades, start_balance=100_000.0, risk_frac=0.01)

    view = window_history(
        all_trades,
        all_risk,
        window_start=pd.Timestamp("2025-01-01", tz="UTC"),
        account_start=100_000.0,
    )
    assert view.hidden == 0
    assert view.start_balance == 100_000.0
    assert list(view.risk) == list(all_risk)


def test_an_empty_history_is_handled() -> None:
    empty = pd.DataFrame(columns=["open_time", "close_time", "net_pnl"])
    view = window_history(
        empty,
        np.array([]),
        window_start=pd.Timestamp("2026-01-01", tz="UTC"),
        account_start=50_000.0,
    )
    assert view.trades.empty
    assert view.start_balance == 50_000.0
    assert view.hidden == 0
