"""Integration tests: a full LiveRunner.run_once cycle against a stub bridge.

These exercise the real orchestration path (day roll, safety cut-off, bar filtering, signal
replay, sizing, risk gate) without a terminal -- the wiring that must work on Monday.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from qplus.live.mt5_bridge import AccountState, Bar, Mt5Bridge, Position, SymbolInfo
from qplus.live.risk_control import RiskController, RiskLimits
from qplus.live.runner import _H4_SECONDS, LiveRunner, MarketSpec, Mode
from qplus.strategies.rsi_wpr_bb_signals import SignalParams

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
        # Server time: just after the LAST bar's open -> that bar is still forming.
        self.now = datetime.fromtimestamp(self.bars[-1].time + 60, tz=UTC)

    # -- Mt5Bridge surface used by the runner --
    def server_time(self) -> datetime:
        return self.now

    def account(self) -> AccountState:
        return AccountState(balance=self.balance, equity=self.equity, currency="EUR")

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
        return 1

    def close_position(self, position: Position, **kw: object) -> None:
        self.closed.append(position.ticket)


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
