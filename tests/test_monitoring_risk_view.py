"""#29/#30: what the dashboard is allowed to tell the operator about risk.

Both rules exist because the monitor sits next to a live account: a number that looks precise but
rests on the wrong basis is worse than no number, because it invites action.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from monitoring.deals import balance_operations, derive_account_start, per_trade_risk
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


# --------------------------------------------------------------------- the balance ledger
def _ops(times: list[str], amounts: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {"time": pd.to_datetime(times, utc=True), "amount": amounts}
    )


def test_a_payout_moves_the_basis_of_every_later_trade() -> None:
    """Prop accounts pay out. A cashflow moves the balance with no trade attached to it.

    Two trades of +1000 each on 100k at 1%: bases 1000 and 1010. Withdraw 50k between them and
    the second trade was sized against 51k, not 101k -- a basis wrong by a factor of two.
    """
    trades = _trades(["2026-01-01", "2026-01-05"], ["2026-01-02", "2026-01-06"], [1_000.0, 1_000.0])
    flows = _ops(["2026-01-03"], [-50_000.0])

    risk = per_trade_risk(trades, 100_000.0, 0.01, cash_flows=flows)
    assert list(risk) == [1_000.0, 510.0]


def test_a_deposit_is_carried_too() -> None:
    trades = _trades(["2026-01-01", "2026-01-05"], ["2026-01-02", "2026-01-06"], [0.0, 0.0])
    flows = _ops(["2026-01-03"], [+25_000.0])

    risk = per_trade_risk(trades, 100_000.0, 0.01, cash_flows=flows)
    assert list(risk) == [1_000.0, 1_250.0]


def test_no_cashflows_behaves_exactly_as_before() -> None:
    trades = _trades(["2026-01-01", "2026-01-03"], ["2026-01-02", "2026-01-04"], [1_000.0, 1_000.0])
    assert list(per_trade_risk(trades, 100_000.0, 0.01)) == list(
        per_trade_risk(trades, 100_000.0, 0.01, cash_flows=pd.DataFrame(columns=["time", "amount"]))
    )


def test_balance_operations_are_lifted_out_of_the_raw_deals() -> None:
    deals = [
        {"position_id": 1, "symbol": "EURUSD", "type": 0, "entry": 0, "time": 100,
         "volume": 0.1, "profit": 0.0, "swap": 0.0, "commission": 0.0},
        {"position_id": 0, "symbol": "", "type": 2, "entry": 0, "time": 200,
         "volume": 0.0, "profit": -5_000.0, "swap": 0.0, "commission": 0.0},
    ]
    ops = balance_operations(deals)
    assert len(ops) == 1
    assert float(ops.iloc[0]["amount"]) == -5_000.0


def test_the_account_origin_is_reconstructed_when_no_state_is_saved() -> None:
    """Using today's balance as the origin counts the account's lifetime result twice."""
    trades = _trades(["2026-01-01"], ["2026-01-02"], [8_000.0])
    flows = _ops(["2026-01-03"], [-3_000.0])
    # Today's balance is 105k = 100k opening + 8k earned - 3k withdrawn.
    assert derive_account_start(105_000.0, trades, flows) == 100_000.0


def test_the_derived_origin_of_an_untouched_account_is_its_balance() -> None:
    empty = pd.DataFrame(columns=["open_time", "close_time", "net_pnl"])
    no_flows = pd.DataFrame(columns=["time", "amount"])
    assert derive_account_start(50_000.0, empty, no_flows) == 50_000.0


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
