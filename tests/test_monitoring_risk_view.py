"""#29/#30: what the dashboard is allowed to tell the operator about risk.

Both rules exist because the monitor sits next to a live account: a number that looks precise but
rests on the wrong basis is worse than no number, because it invites action.

The balance behind every R is reconstructed BACKWARDS from the broker's current balance. That is
the one figure stated exactly; every forward reconstruction needs an origin, and each way of
obtaining one double-counts something (see :func:`monitoring.deals.balance_at`).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from monitoring.deals import balance_operations, equity_curve, per_trade_risk, to_ns
from monitoring.risk_view import summarize_open_risk, window_history


def _trades(opens: list[str], closes: list[str], pnl: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open_time": pd.to_datetime(opens, utc=True),
            "close_time": pd.to_datetime(closes, utc=True),
            "net_pnl": pnl,
        }
    )


def _ops(times: list[str], amounts: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"time": pd.to_datetime(times, utc=True), "amount": amounts})


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
_FOUR_WINS = _trades(
    ["2026-01-01", "2026-01-03", "2026-01-05", "2026-01-07"],
    ["2026-01-02", "2026-01-04", "2026-01-06", "2026-01-08"],
    [1_000.0, 1_000.0, 1_000.0, 1_000.0],
)


def test_each_trade_is_charged_the_balance_at_its_own_open() -> None:
    """Four +1000 trades from 100k at 1%: the bases grow 1000, 1010, 1020, 1030."""
    risk = per_trade_risk(_FOUR_WINS, 104_000.0, 0.01)
    assert list(risk) == [1_000.0, 1_010.0, 1_020.0, 1_030.0]


def test_an_overlapping_trade_is_not_credited_with_pnl_that_came_later() -> None:
    """A opens first and closes last; B opens after A and closes before it.

    Crediting B's win to A would attribute money that did not exist when A was sized -- exactly
    the multi-market overlap this monitor exists to diagnose.
    """
    trades = _trades(
        ["2026-01-01", "2026-01-02"], ["2026-01-10", "2026-01-03"], [500.0, 5_000.0]
    )
    risk = per_trade_risk(trades, 105_500.0, 0.01)
    assert list(risk) == [1_000.0, 1_000.0]  # both sized against the untouched 100k


def test_the_window_keeps_each_trades_original_risk_basis() -> None:
    """The defect: walking only the window charges the first shown trade the opening balance."""
    all_risk = per_trade_risk(_FOUR_WINS, 104_000.0, 0.01)
    view = window_history(
        _FOUR_WINS,
        all_risk,
        window_start=pd.Timestamp("2026-01-05", tz="UTC"),
        current_balance=104_000.0,
    )
    assert len(view.trades) == 2
    assert view.hidden == 2
    assert list(view.risk) == [1_020.0, 1_030.0]  # not restarted at 1000


def test_the_window_start_balance_is_what_the_account_actually_held() -> None:
    all_risk = per_trade_risk(_FOUR_WINS, 104_000.0, 0.01)
    view = window_history(
        _FOUR_WINS,
        all_risk,
        window_start=pd.Timestamp("2026-01-05", tz="UTC"),
        current_balance=104_000.0,
    )
    assert view.start_balance == 102_000.0


def test_a_full_window_hides_nothing_and_changes_nothing() -> None:
    trades = _trades(["2026-01-01"], ["2026-01-02"], [500.0])
    all_risk = per_trade_risk(trades, 100_500.0, 0.01)
    view = window_history(
        trades,
        all_risk,
        window_start=pd.Timestamp("2025-01-01", tz="UTC"),
        current_balance=100_500.0,
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
        current_balance=50_000.0,
    )
    assert view.trades.empty
    assert view.start_balance == 50_000.0
    assert view.hidden == 0


# --------------------------------------------------------------------- the balance ledger
def test_a_payout_moves_the_basis_of_every_later_trade() -> None:
    """Prop accounts pay out, and a cashflow moves the balance with no trade attached to it.

    Two +1000 trades on 100k at 1%. Withdraw 50k between them and the second was sized against
    51k, not 101k -- a basis wrong by a factor of two.
    """
    trades = _trades(
        ["2026-01-01", "2026-01-05"], ["2026-01-02", "2026-01-06"], [1_000.0, 1_000.0]
    )
    flows = _ops(["2026-01-03"], [-50_000.0])
    risk = per_trade_risk(trades, 52_000.0, 0.01, cash_flows=flows)
    assert list(risk) == [1_000.0, 510.0]


def test_a_deposit_is_carried_too() -> None:
    trades = _trades(["2026-01-01", "2026-01-05"], ["2026-01-02", "2026-01-06"], [0.0, 0.0])
    flows = _ops(["2026-01-03"], [+25_000.0])
    risk = per_trade_risk(trades, 125_000.0, 0.01, cash_flows=flows)
    assert list(risk) == [1_000.0, 1_250.0]


def test_the_opening_deposit_is_not_double_counted() -> None:
    """The full ledger contains the funding deposit that OPENED the account.

    A forward walk from a saved 50k start balance would replay that deposit onto an already-funded
    figure and size every trade against 100k. Walking backwards from the current balance never
    touches it: the funding sits before every trade, so it is never subtracted.
    """
    trades = _trades(["2026-02-01"], ["2026-02-02"], [1_000.0])
    funding = _ops(["2026-01-01"], [+50_000.0])  # the account being opened
    risk = per_trade_risk(trades, 51_000.0, 0.01, cash_flows=funding)
    assert list(risk) == [500.0]  # sized against the funded 50k, not 100k


def test_no_cashflows_behaves_exactly_as_before() -> None:
    trades = _trades(
        ["2026-01-01", "2026-01-03"], ["2026-01-02", "2026-01-04"], [1_000.0, 1_000.0]
    )
    assert list(per_trade_risk(trades, 102_000.0, 0.01)) == list(
        per_trade_risk(
            trades, 102_000.0, 0.01, cash_flows=pd.DataFrame(columns=["time", "amount"])
        )
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


# --------------------------------------------------------------------- timestamp units
def test_timestamps_become_nanoseconds_whatever_resolution_the_column_has() -> None:
    """Pandas may hold a datetime column in microseconds; ``Timestamp.value`` is always ns.

    Comparing one against the other is off by a factor of a thousand and raises nothing -- the
    window boundary simply lands after every event, so every balance silently becomes today's.
    """
    micro = pd.Series(pd.to_datetime(["2026-01-05"], utc=True)).astype("datetime64[us, UTC]")
    assert to_ns(micro)[0] == pd.Timestamp("2026-01-05", tz="UTC").value


# --------------------------------------------------------------------- the equity path
def test_the_equity_path_steps_at_a_payout() -> None:
    """The curve and the risk ledger describe one account; they may not disagree about it."""
    trades = _trades(
        ["2026-01-01", "2026-01-05"], ["2026-01-02", "2026-01-06"], [1_000.0, 1_000.0]
    )
    flows = _ops(["2026-01-03"], [-50_000.0])
    eq = equity_curve(trades, 100_000.0, cash_flows=flows)
    assert list(eq["equity"]) == [101_000.0, 51_000.0, 52_000.0]


def test_the_equity_path_without_cashflows_is_the_plain_pnl_path() -> None:
    trades = _trades(["2026-01-01", "2026-01-03"], ["2026-01-02", "2026-01-04"], [500.0, 250.0])
    eq = equity_curve(trades, 100_000.0)
    assert list(eq["equity"]) == [100_500.0, 100_750.0]
