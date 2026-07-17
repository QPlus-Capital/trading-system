"""Integration tests: a full LiveRunner.run_once cycle against a stub bridge.

These exercise the real orchestration path (day roll, safety cut-off, bar filtering, signal
replay, sizing, risk gate) without a terminal -- the wiring that must work on Monday.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from core.strategies.rsi_wpr_bb_signals import SignalParams
from live.mt5_bridge import AccountState, Bar, Mt5Bridge, Position, Side, SymbolInfo
from live.risk_control import RiskController, RiskLimits
from live.runner import _H4_SECONDS, LiveRunner, MarketSpec, Mode, size_order

_T0 = 1_750_000_000  # arbitrary aligned epoch used as the first bar's open time


class StubBridge:
    """Duck-typed stand-in for Mt5Bridge: canned bars/account, records orders."""

    def __init__(self, n_bars: int = 100, balance: float = 100_000.0) -> None:
        # Gently rising H4 bars -> warmed-up indicators, no buy/sell signal fires.
        self.bars = [
            Bar(
                time=_T0 + i * _H4_SECONDS,
                open=100.0 + i * 0.1,
                high=100.6 + i * 0.1,
                low=99.4 + i * 0.1,
                close=100.3 + i * 0.1,
            )
            for i in range(n_bars)
        ]
        self.balance = balance
        self.equity = balance
        self.open_positions: list[Position] = []
        self.placed: list[tuple[str, str, float]] = []
        self.closed: list[int] = []
        self.modified: list[tuple[int, float, float]] = []
        # When set, a placed order fills HERE instead of at the requested price (slippage).
        self.fill_price: float | None = None
        self.modify_error: Exception | None = None
        # Server time: just after the LAST bar's open -> that bar is still forming.
        self.now = datetime.fromtimestamp(self.bars[-1].time + 60, tz=UTC)

    # -- Mt5Bridge surface used by the runner --
    def server_time(self) -> datetime:
        return self.now

    def account(self) -> AccountState:
        return AccountState(balance=self.balance, equity=self.equity, currency="EUR", login=1)

    def symbol_info(self, name: str) -> SymbolInfo:
        return SymbolInfo(
            name=name,
            digits=2,
            point=0.01,
            tick_size=0.01,
            tick_value=0.01,
            volume_min=0.01,
            volume_step=0.01,
            volume_max=100.0,
        )

    def positions(self, name: str | None = None) -> list[Position]:
        return list(self.open_positions)

    def latest_bars(self, name: str, n: int) -> list[Bar]:
        return self.bars[-n:]

    def place_order(self, name: str, side: str, volume: float, **kw: object) -> int:
        self.placed.append((name, side, volume))
        # A real terminal opens a position; its price_open is the price that ACTUALLY filled,
        # which may differ from the price the order asked for. A market order's position carries
        # the SAME ticket as the order, which place_order returns.
        sl, tp = float(cast(float, kw["sl"])), float(cast(float, kw["tp"]))
        requested = sl / (1 - 0.01) if side == "BUY" else sl / (1 + 0.01)
        self.open_positions.append(
            Position(
                ticket=99,
                symbol=name,
                side=cast("Side", side),
                volume=volume,
                price_open=self.fill_price if self.fill_price is not None else requested,
                sl=sl,
                tp=tp,
                profit=0.0,
            )
        )
        return 99

    def modify_sltp(self, position: Position, *, sl: float, tp: float) -> None:
        if self.modify_error is not None:
            raise self.modify_error
        self.modified.append((position.ticket, sl, tp))
        self.open_positions = [
            Position(
                p.ticket, p.symbol, p.side, p.volume, p.price_open, sl, tp, p.profit
            )
            if p.ticket == position.ticket
            else p
            for p in self.open_positions
        ]

    def close_position(self, position: Position, **kw: object) -> None:
        self.closed.append(position.ticket)
        self.open_positions = [p for p in self.open_positions if p.ticket != position.ticket]


def _runner(stub: StubBridge, mode: Mode = Mode.SIGNAL_ONLY) -> LiveRunner:
    return LiveRunner(
        cast(Mt5Bridge, stub),
        [MarketSpec(name="XAUUSD", stop_loss_pct=1.0, take_profit_pct=3.0)],
        SignalParams(),
        RiskController(RiskLimits(), stub.balance),
        mode=mode,
    )


def test_run_once_full_cycle_no_signal_no_orders() -> None:
    stub = StubBridge()
    runner = _runner(stub)
    runner.run_once()
    assert stub.placed == [] and stub.closed == []  # no signal on trending bars, no orders
    # M5: the forming last bar was excluded -> the acted-on bar is the second-to-last.
    assert runner._last_bar_time["XAUUSD"] == stub.bars[-2].time
    runner.run_once()  # same bar again -> deduped, still no action
    assert stub.placed == []


def test_run_once_halts_below_trailing_floor() -> None:
    stub = StubBridge()
    stub.equity = 94_000.0  # below the 95k trailing floor (100k - 5%)
    stub.open_positions = [Position(7, "XAUUSD", "BUY", 0.1, 2000.0, 1980.0, 2060.0, -10.0)]
    runner = _runner(stub)
    runner.run_once()
    assert runner._halted  # safety halt engaged
    assert stub.closed == []  # SIGNAL_ONLY never touches the terminal
    stub2 = StubBridge()
    stub2.equity = 94_000.0
    stub2.open_positions = [Position(8, "XAUUSD", "BUY", 0.1, 2000.0, 1980.0, 2060.0, -10.0)]
    runner2 = _runner(stub2, mode=Mode.EXECUTE)
    runner2.run_once()
    assert runner2._halted and stub2.closed == [8]  # EXECUTE flattens for real


def test_restart_does_not_reprocess_the_handled_bar(tmp_path: Path) -> None:
    # The handled-bar marker is persisted: a restarted runner must not re-act on the same
    # signal bar (it could re-enter a position that was already stopped out in between).
    state = tmp_path / "risk_state.json"
    stub = StubBridge()
    r1 = LiveRunner(
        cast(Mt5Bridge, stub),
        [MarketSpec(name="XAUUSD", stop_loss_pct=1.0, take_profit_pct=3.0)],
        SignalParams(),
        RiskController(RiskLimits(), stub.balance),
        state_path=state,
    )
    r1.run_once()
    handled = r1._last_bar_time["XAUUSD"]
    r2 = LiveRunner(  # fresh process, same state file
        cast(Mt5Bridge, stub),
        [MarketSpec(name="XAUUSD", stop_loss_pct=1.0, take_profit_pct=3.0)],
        SignalParams(),
        RiskController(RiskLimits(), stub.balance),
        state_path=state,
    )
    assert r2._last_bar_time == {"XAUUSD": handled}  # restored -> the bar is already marked


# -- re-anchoring the exits onto the real fill price (live == backtest) ---------------------------

_SPEC = MarketSpec(name="XAUUSD", stop_loss_pct=1.0, take_profit_pct=3.0)


def _open_at(fill: float | None, mode: Mode = Mode.EXECUTE) -> StubBridge:
    """Run one OPEN through ``_act`` with the terminal filling at ``fill`` (None = no slippage)."""
    stub = StubBridge()
    stub.fill_price = fill
    runner = _runner(stub, mode=mode)
    info = stub.symbol_info("XAUUSD")
    sized = size_order("BUY", 2000.0, 1.0, 3.0, info, risk_amount=400.0)
    assert sized is not None and (sized.sl, sized.tp) == (1980.0, 2060.0)
    runner._act(_SPEC, None, sized, info)
    return stub


def test_exits_are_reanchored_to_the_actual_fill_price() -> None:
    # Order asked for 2000 (SL 1980) but filled at 2002. Anchored to the fill, a stop-out costs
    # exactly the 1% that sizing assumed -- anchored to the signal it would cost ~1.1%.
    stub = _open_at(2002.0)
    assert stub.placed == [("XAUUSD", "BUY", 20.0)]
    assert stub.modified == [(99, 1981.98, 2062.06)]  # 2002 * (1 -/+ 1%/3%)
    assert stub.open_positions[0].sl == 1981.98


def test_reanchor_polls_until_the_terminal_lists_the_position(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Some terminals (TTP) list the just-opened position a moment after order_send returns; the
    # first queries come back empty. The re-anchor must poll briefly instead of giving up.
    class LaggyBridge(StubBridge):
        def __init__(self) -> None:
            super().__init__()
            self.lag = 2  # the first two positions() calls miss the new position

        def positions(self, name: str | None = None) -> list[Position]:
            if self.lag:
                self.lag -= 1
                return []
            return super().positions(name)

    naps: list[float] = []
    monkeypatch.setattr("time.sleep", lambda s: naps.append(s))
    stub = LaggyBridge()
    stub.fill_price = 2002.0
    runner = _runner(stub, mode=Mode.EXECUTE)
    info = stub.symbol_info("XAUUSD")
    sized = size_order("BUY", 2000.0, 1.0, 3.0, info, risk_amount=400.0)
    assert sized is not None
    runner._act(_SPEC, None, sized, info)
    assert naps == [0.5, 0.5]  # polled twice, then the position showed up
    assert stub.modified == [(99, 1981.98, 2062.06)]  # and was re-anchored normally


def test_no_modify_when_the_fill_matches_the_signal_price() -> None:
    # No slippage -> the provisional exits are already right; don't send a pointless order.
    stub = _open_at(2000.0)
    assert stub.placed and stub.modified == []


def test_signal_only_mode_never_touches_the_terminal() -> None:
    stub = _open_at(2002.0, mode=Mode.SIGNAL_ONLY)
    assert stub.placed == [] and stub.modified == [] and stub.open_positions == []


def test_ticket_match_reanchors_only_the_position_we_just_opened() -> None:
    # Another same-side position already exists. The order ticket identifies OUR position
    # exactly, so it is re-anchored and the pre-existing one is left untouched.
    stub = StubBridge()
    stub.open_positions = [Position(1, "XAUUSD", "BUY", 1.0, 1990.0, 1970.0, 2050.0, 0.0)]
    stub.fill_price = 2002.0
    runner = _runner(stub, mode=Mode.EXECUTE)
    info = stub.symbol_info("XAUUSD")
    sized = size_order("BUY", 2000.0, 1.0, 3.0, info, risk_amount=400.0)
    assert sized is not None
    runner._act(_SPEC, None, sized, info)
    assert stub.modified == [(99, 1981.98, 2062.06)]  # only ticket 99 (ours)
    assert stub.open_positions[0].sl == 1970.0  # the pre-existing position is untouched


def test_side_fallback_when_the_broker_assigns_a_different_position_ticket() -> None:
    # Broker quirk: the position's ticket differs from the order ticket. A UNIQUE position on
    # the side we just traded is still unambiguous, so it is re-anchored via the fallback.
    class OddTicketBridge(StubBridge):
        def place_order(self, name: str, side: str, volume: float, **kw: object) -> int:
            super().place_order(name, side, volume, **kw)
            return 12345  # order ticket != position ticket (99)

    stub = OddTicketBridge()
    stub.fill_price = 2002.0
    runner = _runner(stub, mode=Mode.EXECUTE)
    info = stub.symbol_info("XAUUSD")
    sized = size_order("BUY", 2000.0, 1.0, 3.0, info, risk_amount=400.0)
    assert sized is not None
    runner._act(_SPEC, None, sized, info)
    assert stub.modified == [(99, 1981.98, 2062.06)]  # found via the unique-side fallback


def test_a_failed_modify_leaves_the_protective_stop_in_place() -> None:
    # The order already carries a valid stop, so a rejected modify must never be fatal and must
    # never leave the position naked -- the worst case is the old signal-anchored stop.
    stub = StubBridge()
    stub.fill_price = 2002.0
    stub.modify_error = RuntimeError("broker rejected SLTP")
    runner = _runner(stub, mode=Mode.EXECUTE)
    info = stub.symbol_info("XAUUSD")
    sized = size_order("BUY", 2000.0, 1.0, 3.0, info, risk_amount=400.0)
    assert sized is not None
    runner._act(_SPEC, None, sized, info)  # must not raise
    assert stub.modified == []
    assert stub.open_positions[0].sl == 1980.0  # still protected, at the provisional level


def test_run_once_rolls_the_trading_day() -> None:
    stub = StubBridge()
    runner = _runner(stub)
    runner.run_once()
    first_day = runner._day
    assert first_day is not None
    # Next cycle a (server) day later, after the balance grew intraday.
    stub.balance = 101_000.0
    stub.now = datetime.fromtimestamp(stub.now.timestamp() + 86_400, tz=UTC)
    runner.run_once()
    assert runner._day != first_day
    assert runner._risk.day_start_balance == 101_000.0  # daily reference rolled
    assert runner._risk.hwm_balance == 101_000.0  # prior day's balance banked into the HWM
