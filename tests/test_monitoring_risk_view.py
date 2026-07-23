"""#29/#30: what the dashboard is allowed to tell the operator about risk.

Both rules exist because the monitor sits next to a live account: a number that looks precise but
rests on the wrong basis is worse than no number, because it invites action.

The balance behind every R is reconstructed BACKWARDS from the broker's current balance -- the one
figure stated exactly -- over the COMPLETE deal ledger. Both halves matter: a forward walk needs
an origin, and every way of obtaining one double-counts something; and anything missing from the
ledger is inherited into every reconstructed balance before it.
"""

from __future__ import annotations

from decimal import Decimal

import numpy as np
import pandas as pd
from monitoring.deals import deal_ledger, deals_to_trades, equity_curve, per_trade_risk, to_ns
from monitoring.risk_view import summarize_open_risk, window_history


def _trades(opens: list[str], closes: list[str], pnl: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open_time": pd.to_datetime(opens, utc=True),
            "close_time": pd.to_datetime(closes, utc=True),
            "net_pnl": pnl,
        }
    )


def _ledger(times: list[str], amounts: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"time": pd.to_datetime(times, utc=True), "amount": amounts})


def _deal(time: int, symbol: str, profit: float, commission: float = 0.0) -> dict[str, object]:
    return {
        "position_id": 1,
        "symbol": symbol,
        "type": 0,
        "entry": 0,
        "time": time,
        "volume": 0.1,
        "profit": profit,
        "swap": 0.0,
        "commission": commission,
    }


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
_FOUR_WINS_LEDGER = _ledger(
    ["2026-01-02", "2026-01-04", "2026-01-06", "2026-01-08"],
    [1_000.0, 1_000.0, 1_000.0, 1_000.0],
)


def test_each_trade_is_charged_the_balance_at_its_own_open() -> None:
    """Four +1000 trades from 100k at 1%: the bases grow 1000, 1010, 1020, 1030."""
    risk = per_trade_risk(_FOUR_WINS, 104_000.0, 0.01, ledger=_FOUR_WINS_LEDGER)
    assert list(risk) == [1_000.0, 1_010.0, 1_020.0, 1_030.0]


def test_an_overlapping_trade_is_not_credited_with_pnl_that_came_later() -> None:
    """A opens first and closes last; B opens after A and closes before it.

    Crediting B's win to A would attribute money that did not exist when A was sized -- exactly
    the multi-market overlap this monitor exists to diagnose.
    """
    trades = _trades(
        ["2026-01-01", "2026-01-02"], ["2026-01-10", "2026-01-03"], [500.0, 5_000.0]
    )
    ledger = _ledger(["2026-01-10", "2026-01-03"], [500.0, 5_000.0])
    risk = per_trade_risk(trades, 105_500.0, 0.01, ledger=ledger)
    assert list(risk) == [1_000.0, 1_000.0]  # both sized against the untouched 100k


def test_the_window_keeps_each_trades_original_risk_basis() -> None:
    """The defect: walking only the window charges the first shown trade the opening balance."""
    all_risk = per_trade_risk(_FOUR_WINS, 104_000.0, 0.01, ledger=_FOUR_WINS_LEDGER)
    view = window_history(
        _FOUR_WINS,
        all_risk,
        window_start=pd.Timestamp("2026-01-05", tz="UTC"),
        current_balance=104_000.0,
        ledger=_FOUR_WINS_LEDGER,
    )
    assert len(view.trades) == 2
    assert view.hidden == 2
    assert list(view.risk) == [1_020.0, 1_030.0]  # not restarted at 1000
    assert view.start_balance == 102_000.0


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
    ledger = _ledger(["2026-01-02", "2026-01-03", "2026-01-06"], [1_000.0, -50_000.0, 1_000.0])
    risk = per_trade_risk(trades, 52_000.0, 0.01, ledger=ledger)
    assert list(risk) == [1_000.0, 510.0]


def test_the_opening_deposit_is_not_double_counted() -> None:
    """The full ledger contains the funding deposit that OPENED the account.

    A forward walk from a saved 50k start balance would replay that deposit onto an already-funded
    figure and size every trade against 100k. Walking backwards never touches it: the funding sits
    before every trade, so it is never subtracted.
    """
    trades = _trades(["2026-02-01"], ["2026-02-02"], [1_000.0])
    ledger = _ledger(["2026-01-01", "2026-02-02"], [50_000.0, 1_000.0])
    risk = per_trade_risk(trades, 51_000.0, 0.01, ledger=ledger)
    assert list(risk) == [500.0]  # sized against the funded 50k, not 100k


def test_an_open_positions_commission_is_not_inherited_backwards() -> None:
    """An open position's entry commission is already in the broker's balance.

    It has no OUT deal so it is not a trade, and it has a symbol so it is not a cashflow. Built
    from trades alone, the ledger misses it and the backward walk hands that commission to every
    earlier basis -- flattering historical R for as long as the position stays open.
    """
    trades = _trades(["2026-01-01"], ["2026-01-02"], [1_000.0])
    deals = [
        _deal(int(pd.Timestamp("2026-01-02", tz="UTC").timestamp()), "EURUSD", 1_000.0),
        # ...and a position opened afterwards that is still open, charging commission now:
        _deal(int(pd.Timestamp("2026-01-09", tz="UTC").timestamp()), "GBPUSD", 0.0, -7.0),
    ]
    ledger = deal_ledger(deals)
    risk = per_trade_risk(trades, 100_993.0, 0.01, ledger=ledger)
    assert list(risk) == [1_000.0]  # the -7 belongs after the trade, not inside its basis


def test_the_ledger_carries_every_deal_not_just_completed_trades() -> None:
    deals = [
        _deal(100, "EURUSD", 250.0, -3.0),
        _deal(200, "", -5_000.0),  # a withdrawal
    ]
    ledger = deal_ledger(deals)
    assert list(ledger["amount"]) == [247.0, -5_000.0]


def test_an_empty_ledger_leaves_the_balance_where_it_is() -> None:
    trades = _trades(["2026-01-01"], ["2026-01-02"], [0.0])
    assert list(per_trade_risk(trades, 100_000.0, 0.01)) == [1_000.0]


def test_same_second_opening_cost_is_excluded_from_its_own_basis() -> None:
    """Earlier same-second money is real; the opening deal itself was booked after sizing."""
    opened = int(pd.Timestamp("2026-01-01", tz="UTC").timestamp())
    closed = int(pd.Timestamp("2026-01-02", tz="UTC").timestamp())
    deals = [
        {
            **_deal(opened, "", 50.0),
            "position_id": 0,
            "ticket": 9,
        },
        {
            **_deal(opened, "EURUSD", 0.0, -3.0),
            "position_id": 17,
            "ticket": 10,
            "fee": Decimal("-2.0"),
        },
        {
            **_deal(closed, "EURUSD", 100.0),
            "position_id": 17,
            "ticket": 11,
            "entry": 1,
            "type": 1,
            "fee": Decimal("0"),
        },
    ]
    trades = deals_to_trades(deals)
    ledger = deal_ledger(deals)

    risk = per_trade_risk(
        trades,
        Decimal("100145"),
        Decimal("0.01"),
        ledger=ledger,
    )

    assert list(risk) == [Decimal("1000.50")]
    assert trades.iloc[0]["open_ticket"] == 10
    assert isinstance(risk[0], Decimal)


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
    ledger = _ledger(["2026-01-02", "2026-01-03", "2026-01-06"], [1_000.0, -50_000.0, 1_000.0])
    eq = equity_curve(100_000.0, ledger)
    assert list(eq["equity"]) == [101_000.0, 51_000.0, 52_000.0]


def test_the_equity_path_of_an_empty_ledger_is_empty() -> None:
    assert equity_curve(100_000.0, None).empty
