"""Integration tests: a full LiveRunner.run_once cycle against a stub bridge.

These exercise the real orchestration path (day roll, safety cut-off, bar filtering, signal
replay, sizing, risk gate) without a terminal -- the wiring that must work on Monday.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest
from core.strategies.rsi_wpr_bb_signals import SignalParams
from live.mt5_bridge import (
    MAGIC,
    AccountState,
    Bar,
    Mt5Bridge,
    Mt5Error,
    Position,
    Side,
    SymbolInfo,
)
from live.notify import Notifier
from live.risk_control import RiskController, RiskLimits
from live.runner import _H4_SECONDS, LiveRunner, MarketSpec, Mode, loss_day, size_order

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
        # What the terminal prices entry->stop as; None = it cannot price it (arithmetic fallback).
        self.terminal_risk: float | None = None
        # Broker-priced loss per lot for a candidate order; None = unpriceable (#19).
        self.order_loss_per_lot: float | None = None
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

    def owned_positions(self, name: str | None = None) -> list[Position]:
        return [p for p in self.positions(name) if p.magic == MAGIC]

    def latest_bars(self, name: str, n: int) -> list[Bar]:
        return self.bars[-n:]

    def loss_to_stop(self, position: Position) -> float | None:
        # Default: the terminal cannot price it -> the runner falls back to the arithmetic.
        return self.terminal_risk

    def loss_for_order(
        self, name: str, side: str, entry: float, sl: float, volume: float
    ) -> float | None:
        # None = the terminal cannot price the candidate -> keep the arithmetic volume.
        if self.order_loss_per_lot is None:
            return None
        return volume * self.order_loss_per_lot

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
                magic=MAGIC,  # positions the runner opens carry our magic
            )
        )
        return 99

    def modify_sltp(self, position: Position, *, sl: float, tp: float) -> None:
        if self.modify_error is not None:
            raise self.modify_error
        self.modified.append((position.ticket, sl, tp))
        self.open_positions = [
            Position(p.ticket, p.symbol, p.side, p.volume, p.price_open, sl, tp, p.profit)
            if p.ticket == position.ticket
            else p
            for p in self.open_positions
        ]

    def close_position(self, position: Position, **kw: object) -> None:
        self.closed.append(position.ticket)
        self.open_positions = [p for p in self.open_positions if p.ticket != position.ticket]


class _RecordingNotifier:
    def __init__(self) -> None:
        self.alerts: list[str] = []
        self.signals: list[str] = []

    def alert(self, text: str) -> None:
        self.alerts.append(text)

    def signal(self, text: str) -> None:
        self.signals.append(text)


def _runner(stub: StubBridge, mode: Mode = Mode.SIGNAL_ONLY) -> LiveRunner:
    return LiveRunner(
        cast(Mt5Bridge, stub),
        [MarketSpec(name="XAUUSD", stop_loss_pct=1.0, take_profit_pct=3.0)],
        SignalParams(),
        RiskController(RiskLimits(), stub.balance),
        mode=mode,
        # A first launch without this HALTS by design; these tests exercise the trading path, so
        # they state the loss day's opening balance the way an operator would.
        day_start_balance=stub.balance,
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
    stub.open_positions = [Position(7, "XAUUSD", "BUY", 0.1, 2000.0, 1980.0, 2060.0, -10.0, MAGIC)]
    runner = _runner(stub)
    runner.run_once()
    assert runner._halted  # safety halt engaged
    assert stub.closed == []  # SIGNAL_ONLY never touches the terminal
    stub2 = StubBridge()
    stub2.equity = 94_000.0
    stub2.open_positions = [Position(8, "XAUUSD", "BUY", 0.1, 2000.0, 1980.0, 2060.0, -10.0, MAGIC)]
    runner2 = _runner(stub2, mode=Mode.EXECUTE)
    runner2.run_once()
    assert runner2._halted and stub2.closed == [8]  # EXECUTE flattens for real


def test_runner_halts_loudly_when_the_bridge_rejects_a_position_type() -> None:
    class RejectingPositionBridge(StubBridge):
        def positions(self, name: str | None = None) -> list[Position]:
            raise Mt5Error(
                "invalid MT5 position type; expected POSITION_TYPE_BUY or POSITION_TYPE_SELL"
            )

    stub = RejectingPositionBridge()
    notifier = _RecordingNotifier()
    runner = LiveRunner(
        cast(Mt5Bridge, stub),
        [MarketSpec(name="XAUUSD", stop_loss_pct=1.0, take_profit_pct=3.0)],
        SignalParams(),
        RiskController(RiskLimits(), stub.balance),
        notifier=cast(Notifier, notifier),
        day_start_balance=stub.balance,
    )

    runner.run_once()

    assert runner._halted
    assert runner._halt_reason == (
        "cannot verify open positions: invalid MT5 position type; expected "
        "POSITION_TYPE_BUY or POSITION_TYPE_SELL"
    )
    assert notifier.alerts == [
        "SAFETY HALT: cannot verify open positions: invalid MT5 position type; expected "
        "POSITION_TYPE_BUY or POSITION_TYPE_SELL -- flattening & stopping"
    ]
    assert stub.placed == []
    assert stub.closed == []


def test_daily_safety_cutoff_precedes_unverifiable_open_risk() -> None:
    class RejectingAccountPositionBridge(StubBridge):
        def __init__(self) -> None:
            super().__init__()
            self.account_position_reads = 0

        def positions(self, name: str | None = None) -> list[Position]:
            if name is None:
                self.account_position_reads += 1
                raise Mt5Error(
                    "invalid MT5 position type; expected POSITION_TYPE_BUY or POSITION_TYPE_SELL"
                )
            return [position for position in self.open_positions if position.symbol == name]

    stub = RejectingAccountPositionBridge()
    stub.equity = 90_000.0
    stub.open_positions = [Position(7, "XAUUSD", "BUY", 0.1, 2000.0, 1980.0, 2060.0, -10.0, MAGIC)]
    runner = _runner(stub, mode=Mode.EXECUTE)

    runner.run_once()

    assert runner._halted
    assert stub.closed == [7]
    assert stub.account_position_reads == 0


def test_halt_and_flatten_closes_every_owned_position_when_one_lookup_fails() -> None:
    class PartiallyRejectingBridge(StubBridge):
        def owned_positions(self, name: str | None = None) -> list[Position]:
            if name == "XAUUSD":
                raise Mt5Error(
                    "invalid MT5 position type; expected POSITION_TYPE_BUY or POSITION_TYPE_SELL"
                )
            return [
                position
                for position in self.open_positions
                if position.symbol == name and position.magic == MAGIC
            ]

    stub = PartiallyRejectingBridge()
    stub.open_positions = [
        Position(7, "XAUUSD", "BUY", 0.1, 2000.0, 1980.0, 2060.0, -10.0, MAGIC),
        Position(8, "EURUSD", "BUY", 0.1, 1.2, 1.1, 1.4, -5.0, MAGIC),
        Position(9, "EURUSD", "SELL", 0.1, 1.3, 1.4, 1.1, -4.0, MAGIC),
    ]
    notifier = _RecordingNotifier()
    runner = LiveRunner(
        cast(Mt5Bridge, stub),
        [
            MarketSpec(name="XAUUSD", stop_loss_pct=1.0, take_profit_pct=3.0),
            MarketSpec(name="EURUSD", stop_loss_pct=1.0, take_profit_pct=3.0),
        ],
        SignalParams(),
        RiskController(RiskLimits(), stub.balance),
        mode=Mode.EXECUTE,
        notifier=cast(Notifier, notifier),
        day_start_balance=stub.balance,
    )

    runner._halt_and_flatten("synthetic daily limit")

    assert runner._halted
    assert runner._halt_reason == "synthetic daily limit"
    assert stub.closed == [8, 9]
    assert [position.ticket for position in stub.open_positions] == [7]
    assert notifier.alerts == [
        "SAFETY HALT: synthetic daily limit -- flattening & stopping",
        "SAFETY HALT: could not enumerate owned XAUUSD positions; manual intervention required",
    ]


def test_loss_day_rolls_at_16_15_chicago_dst_aware() -> None:
    from live.runner import loss_day

    # Summer (CDT = UTC-5): 16:15 CT = 21:15 UTC. 16:14 vs 16:16 CT are different loss days.
    before = datetime(2026, 7, 1, 21, 14, tzinfo=UTC)  # 16:14 CDT
    after = datetime(2026, 7, 1, 21, 16, tzinfo=UTC)  # 16:16 CDT
    assert loss_day(after) == loss_day(before) + timedelta(days=1)
    # Winter (CST = UTC-6): the boundary is at 22:15 UTC, not 21:15 -> DST-aware.
    assert loss_day(datetime(2026, 1, 15, 22, 14, tzinfo=UTC)) != loss_day(
        datetime(2026, 1, 15, 22, 16, tzinfo=UTC)
    )
    # 21:15 UTC in January is only 15:15 CST -> still the same (pre-reset) day.
    assert loss_day(datetime(2026, 1, 15, 21, 14, tzinfo=UTC)) == loss_day(
        datetime(2026, 1, 15, 21, 16, tzinfo=UTC)
    )


def test_per_cycle_guard_halts_on_account_mismatch_without_flattening() -> None:
    # If the terminal reconnects to another account mid-run, halt and DON'T touch its positions.
    stub = StubBridge()  # stub.account().login == 1, currency == "EUR"
    stub.open_positions = [Position(3, "XAUUSD", "BUY", 0.1, 2000.0, 1980.0, 2060.0, 5.0, MAGIC)]
    runner = LiveRunner(
        cast(Mt5Bridge, stub),
        [MarketSpec(name="XAUUSD", stop_loss_pct=1.0, take_profit_pct=3.0)],
        SignalParams(),
        RiskController(RiskLimits(), stub.balance),
        mode=Mode.EXECUTE,
        expected_login=999,  # != the connected login (1) -> mismatch
        expected_currency="EUR",
    )
    runner.run_once()
    assert runner._halted
    assert stub.closed == []  # wrong account -> even our-magic positions are left untouched


def test_owned_filter_ignores_manual_and_foreign_positions() -> None:
    # A manual / foreign-EA position (magic != ours) on our symbol must never be acted on.
    foreign = Position(555, "XAUUSD", "BUY", 1.0, 2000.0, 1980.0, 2060.0, 0.0, magic=999)
    stub = StubBridge()
    stub.equity = 94_000.0  # below the trailing floor -> safety halt this cycle
    stub.open_positions = [foreign]
    runner = _runner(stub, mode=Mode.EXECUTE)
    runner.run_once()
    assert runner._halted  # halt engaged
    assert stub.closed == []  # the foreign position is NOT flattened
    # Ownership limits what we act on; account risk still sees all exposure.
    assert stub.owned_positions("XAUUSD") == []
    assert stub.positions("XAUUSD") == [foreign]


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
        day_start_balance=stub.balance,
    )
    r1.run_once()
    handled = r1._last_bar_time["XAUUSD"]
    r2 = LiveRunner(  # fresh process, same state file
        cast(Mt5Bridge, stub),
        [MarketSpec(name="XAUUSD", stop_loss_pct=1.0, take_profit_pct=3.0)],
        SignalParams(),
        RiskController(RiskLimits(), stub.balance),
        state_path=state,
        day_start_balance=stub.balance,
    )
    assert r2._last_bar_time == {"XAUUSD": handled}  # restored -> the bar is already marked


def test_open_risk_prefers_the_terminals_price_and_falls_back_to_arithmetic() -> None:
    # #6: entry->stop risk is priced by the terminal (order_calc_profit) so the broker's own
    # currency conversion applies; our tick arithmetic is only the fallback.
    pos = Position(1, "XAUUSD", "BUY", 1.0, 2000.0, 1980.0, 2060.0, 0.0, MAGIC)
    stub = StubBridge()
    stub.open_positions = [pos]
    runner = _runner(stub)
    # Arithmetic: volume * (distance / tick_size) * tick_value = 1 * (20 / 0.01) * 0.01 = 20.
    assert runner._total_open_risk() == 20.0  # terminal_risk is None -> fallback
    stub.terminal_risk = 33.0  # the broker prices the same stop differently (conversion)
    assert runner._total_open_risk() == 33.0  # the terminal's number wins


def test_rejected_order_leaves_the_bar_unmarked_and_retries_next_cycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # #7: a signal bar is marked handled only AFTER the order is confirmed. If the terminal
    # rejects the order, the bar stays unmarked so the next cycle retries it -- live must not
    # sit flat while the backtest is positioned.
    stub = StubBridge()
    runner = _runner(stub, mode=Mode.EXECUTE)
    # Drive the order path directly (the indicator would need hand-crafted bars); we test the
    # order/idempotency wiring, not the signal maths.
    monkeypatch.setattr(runner, "_replay_signal", lambda closed: (True, False))
    reject = {"n": 1}  # reject exactly the first order, then let it through
    real_place = stub.place_order

    def flaky(name: str, side: str, volume: float, **kw: object) -> int:
        if reject["n"]:
            reject["n"] -= 1
            raise RuntimeError("broker rejected order")
        return real_place(name, side, volume, **kw)

    monkeypatch.setattr(stub, "place_order", flaky)

    runner.run_once()  # order rejected this cycle
    assert stub.open_positions == []  # nothing opened
    assert "XAUUSD" not in runner._last_bar_time  # bar NOT recorded -> eligible for retry

    runner.run_once()  # same bar retried; the order goes through now
    assert stub.placed == [("XAUUSD", "BUY", stub.placed[0][2])]  # placed once, on the retry
    assert stub.open_positions and stub.open_positions[0].side == "BUY"  # position now live
    assert runner._last_bar_time["XAUUSD"] == stub.bars[-2].time  # only NOW marked handled


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
    wall = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)  # real UTC drives the loss day (#18)
    runner.run_once(wall_now=wall)
    first_day = runner._day
    assert first_day is not None
    # Next cycle a day later in REAL time, after the balance grew intraday.
    stub.balance = 101_000.0
    runner.run_once(wall_now=wall + timedelta(days=1))
    assert runner._day != first_day
    assert runner._risk.day_start_balance == 101_000.0  # daily reference rolled
    assert runner._risk.hwm_balance == 101_000.0  # prior day's balance banked into the HWM


def test_the_loss_day_follows_real_utc_not_the_brokers_clock() -> None:
    """#18: MT5 stamps ticks with the SERVER's wall clock, so server_time() is 2-3h ahead of UTC
    on an EET server. Deriving the 16:15-CT boundary from it would move the reset by that offset.
    """
    stub = StubBridge()
    runner = _runner(stub)
    # Server clock claims a moment already past the reset; real UTC is still before it.
    stub.now = datetime(2026, 7, 1, 23, 0, tzinfo=UTC)  # server frame, deliberately misleading
    before = datetime(2026, 7, 1, 21, 14, tzinfo=UTC)  # 16:14 CDT -- still the old loss day
    runner.run_once(wall_now=before)
    assert runner._day == loss_day(before)  # the broker's clock did not move the boundary


def test_broker_pricing_shrinks_a_volume_that_would_over_risk() -> None:
    """#19: trade_tick_value is one generic number per symbol. When the broker really loses more
    per lot than that implies, sizing off the arithmetic alone exceeds the intended risk -- the
    terminal's own pricing must pull the volume back down."""
    stub = StubBridge()
    info = stub.symbol_info("XAUUSD")
    # Arithmetic: loss_per_lot = (20 / 0.01) * 0.01 = 20 -> 400 / 20 = 20 lots.
    plain = size_order("BUY", 2000.0, 1.0, 3.0, info, risk_amount=400.0)
    assert plain is not None and plain.volume == 20.0

    # The broker actually loses twice that per lot (conversion / asymmetric tick value).
    priced = size_order(
        "BUY",
        2000.0,
        1.0,
        3.0,
        info,
        risk_amount=400.0,
        loss_fn=lambda _s, _e, _sl, vol: vol * 40.0,
    )
    assert priced is not None
    assert priced.volume == 10.0  # halved, so the real stop-out still costs 400
    assert priced.risk_amount == 400.0  # and the recorded risk is the BROKER's number


def test_sizing_refuses_when_even_the_minimum_lot_over_risks() -> None:
    # Never silently accept more than the intended risk.
    stub = StubBridge()
    info = stub.symbol_info("XAUUSD")
    assert (
        size_order(
            "BUY",
            2000.0,
            1.0,
            3.0,
            info,
            risk_amount=400.0,
            loss_fn=lambda _s, _e, _sl, vol: vol * 1_000_000.0,
        )
        is None
    )


def test_unpriceable_candidates_keep_the_arithmetic_volume() -> None:
    stub = StubBridge()
    info = stub.symbol_info("XAUUSD")
    sized = size_order(
        "BUY",
        2000.0,
        1.0,
        3.0,
        info,
        risk_amount=400.0,
        loss_fn=lambda _s, _e, _sl, _v: None,
    )
    assert sized is not None and sized.volume == 20.0


def test_first_launch_without_a_known_day_start_halts() -> None:
    """Codex P1: with no saved state the loss day's opening balance is unknown, and no heuristic
    is safe both ways -- an account that banked to 55k and restarts mid-day at 52k would be handed
    a fresh budget from 52k while already 5.5% down. Doing nothing is the safe state."""
    stub = StubBridge()
    runner = LiveRunner(
        cast(Mt5Bridge, stub),
        [MarketSpec(name="XAUUSD", stop_loss_pct=1.0, take_profit_pct=3.0)],
        SignalParams(),
        RiskController(RiskLimits(), 100_000.0),
        mode=Mode.EXECUTE,  # no day_start_balance given
    )
    runner.run_once()
    assert runner._halted
    assert stub.placed == [] and stub.closed == []  # halted before touching anything


def test_an_explicit_day_start_is_used_and_the_hwm_banks_the_balance() -> None:
    stub = StubBridge()
    stub.balance = stub.equity = 104_000.0  # grown since the profile reference
    runner = LiveRunner(
        cast(Mt5Bridge, stub),
        [MarketSpec(name="XAUUSD", stop_loss_pct=1.0, take_profit_pct=3.0)],
        SignalParams(),
        RiskController(RiskLimits(), 100_000.0),
        day_start_balance=103_000.0,  # the loss day actually opened here
    )
    runner.run_once()
    assert not runner._halted
    assert runner._risk.day_start_balance == 103_000.0  # the operator's number, not the balance
    assert runner._risk.hwm_balance == 104_000.0  # HWM banks the balance -> raises the floor


def test_an_unpriceable_position_on_a_foreign_symbol_blocks_new_risk() -> None:
    """Codex round-5 P1: open risk only visited configured markets, so a manual position on any
    OTHER symbol contributed its PnL to equity while its stop-risk never entered the total --
    check_open could admit new trades past the 2% cap. Unpriceable exposure must fail closed."""
    stub = StubBridge()
    stub.open_positions = [
        Position(9, "GBPJPY", "BUY", 1.0, 200.0, 190.0, 220.0, 5.0, magic=777)  # not configured
    ]
    runner = _runner(stub)  # terminal_risk None -> the terminal cannot price it either
    runner.run_once()
    assert runner._risk.open_risk == float("inf")  # fail closed
    assert not runner._risk.check_open(1.0, stub.equity).allowed  # nothing new gets in


def test_a_priceable_foreign_position_is_charged_into_open_risk() -> None:
    # Same situation, but the terminal CAN price it -> its stop-risk joins the total normally.
    stub = StubBridge()
    stub.open_positions = [Position(9, "GBPJPY", "BUY", 1.0, 200.0, 190.0, 220.0, 5.0, magic=777)]
    stub.terminal_risk = 500.0
    runner = _runner(stub)
    runner.run_once()
    assert runner._risk.open_risk == 500.0
