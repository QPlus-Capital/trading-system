"""Behavioural parity between the real Nautilus and live signal adapters.

No terminal is constructed or contacted. The backtest path consumes native Nautilus bars through
``RsiWprBb.on_bar``; the live path consumes native bridge bars through the runner's restart-safe
``_replay_signal`` method.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, fields
from decimal import Decimal
from typing import cast

import pytest
from core.strategies.rsi_wpr_bb import RsiWprBb, RsiWprBbConfig
from core.strategies.rsi_wpr_bb_signals import RsiWprBbSignals, SignalParams
from live import runner as live_runner
from live.mt5_bridge import Bar as LiveBar
from live.mt5_bridge import Mt5Bridge
from live.risk_control import RiskController, RiskLimits
from live.runner import LiveRunner
from nautilus_trader.model.data import Bar as NautilusBar
from nautilus_trader.model.data import BarType
from nautilus_trader.test_kit.providers import TestInstrumentProvider

_H4_SECONDS = 4 * 60 * 60
_H4_NS = _H4_SECONDS * 1_000_000_000
_BAR_COUNT = 199
_FIRST_SIGNAL_INDEX = 29
_EXPECTED_SIGNAL_INDICES = (29, 50, 66, 87, 103, 124, 140, 161, 177, 198)
_INSTRUMENT = TestInstrumentProvider.audusd_cfd()
_BAR_TYPE = BarType.from_str(f"{_INSTRUMENT.id}-4-HOUR-LAST-EXTERNAL")


@dataclass(frozen=True)
class _FixtureBar:
    """One adapter-neutral OHLC bar."""

    time: int
    open: float
    high: float
    low: float
    close: float


class _NoTerminalBridge:
    """Fail if a supposedly pure parity test reaches any terminal-facing boundary."""

    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"signal parity attempted terminal access: {name}")


class _BacktestSignalProbe(RsiWprBb):
    """Observe the real wrapper's mutually-exclusive raw decision without placing orders."""

    def __init__(self, config: RsiWprBbConfig) -> None:
        super().__init__(config)
        self.emitted: list[tuple[bool, bool]] = []
        self._current = (False, False)

    def on_bar(self, bar: NautilusBar) -> None:
        self._current = (False, False)
        super().on_bar(bar)
        self.emitted.append(self._current)

    def _go_long(self, ref_price: float, ts_ns: int, *, may_enter: bool = True) -> None:
        del ref_price, ts_ns, may_enter
        self._current = (True, False)

    def _go_short(self, ref_price: float, ts_ns: int, *, may_enter: bool = True) -> None:
        del ref_price, ts_ns, may_enter
        self._current = (False, True)

    def _go_flat(self) -> None:
        raise AssertionError("long_only is disabled in the parity fixture")


class _BuySellSwappedSignals(RsiWprBbSignals):
    """A deliberate one-adapter divergence used to prove the oracle binds."""

    def update(self, o: float, h: float, low_: float, c: float) -> tuple[bool, bool]:
        buy, sell = super().update(o, h, low_, c)
        return sell, buy


@pytest.fixture
def shared_bars() -> tuple[_FixtureBar, ...]:
    """Oscillating H4 bars with warm-up, both signal sides, and a final-bar signal."""

    bars: list[_FixtureBar] = []
    for index in range(_BAR_COUNT):
        drift = 0.35 * math.sin(2 * math.pi * index / (37 * 11))
        open_ = 100 + 4 * math.sin(2 * math.pi * index / 37) + drift
        close = 100 + 4 * math.sin(2 * math.pi * (index + 1) / 37) + drift
        high = max(open_, close) + 0.15
        low = min(open_, close) - 0.15
        bars.append(
            _FixtureBar(
                time=index * _H4_SECONDS,
                open=round(open_, 5),
                high=round(high, 5),
                low=round(low, 5),
                close=round(close, 5),
            )
        )
    return tuple(bars)


@pytest.fixture
def shared_params() -> SignalParams:
    """One parameter value supplied unchanged to both adapter constructors."""

    return SignalParams(
        bb_mult=1.0,
        use_bb_confirm=False,
        use_wpr_confirm=False,
        use_rsi_filter=False,
    )


def _backtest_config(params: SignalParams) -> RsiWprBbConfig:
    signal_values = {field.name: getattr(params, field.name) for field in fields(SignalParams)}
    return RsiWprBbConfig(
        instrument_id=_INSTRUMENT.id,
        bar_type=_BAR_TYPE,
        trade_size=Decimal("1"),
        **signal_values,
    )


def _nautilus_bar(bar: _FixtureBar, index: int) -> NautilusBar:
    price = _INSTRUMENT.make_price
    timestamp = (index + 1) * _H4_NS
    return NautilusBar(
        _BAR_TYPE,
        price(bar.open),
        price(bar.high),
        price(bar.low),
        price(bar.close),
        _INSTRUMENT.make_qty(1),
        timestamp,
        timestamp,
    )


def _backtest_sequence(
    bars: tuple[_FixtureBar, ...], params: SignalParams
) -> tuple[tuple[bool, bool], ...]:
    strategy = _BacktestSignalProbe(_backtest_config(params))
    for index, bar in enumerate(bars):
        strategy.on_bar(_nautilus_bar(bar, index))
    return tuple(strategy.emitted)


def _live_sequence(
    bars: tuple[_FixtureBar, ...], params: SignalParams
) -> tuple[tuple[bool, bool], ...]:
    native = [LiveBar(bar.time, bar.open, bar.high, bar.low, bar.close) for bar in bars]
    runner = LiveRunner(
        cast(Mt5Bridge, _NoTerminalBridge()),
        [],
        params,
        RiskController(RiskLimits(), 100_000.0),
    )
    return tuple(runner._replay_signal(native[: index + 1]) for index in range(len(native)))


def _assert_adapter_parity(
    bars: tuple[_FixtureBar, ...], params: SignalParams
) -> tuple[tuple[bool, bool], ...]:
    backtest = _backtest_sequence(bars, params)
    live = _live_sequence(bars, params)
    assert len(backtest) == len(live) == len(bars)
    for index, (backtest_signal, live_signal) in enumerate(zip(backtest, live, strict=True)):
        assert backtest_signal == live_signal, (
            f"signal adapter mismatch at bar {index}: "
            f"backtest={backtest_signal}, live={live_signal}"
        )
    return backtest


def test_real_adapters_emit_identical_signal_sequence(
    shared_bars: tuple[_FixtureBar, ...], shared_params: SignalParams
) -> None:
    emitted = _assert_adapter_parity(shared_bars, shared_params)
    assert all(signal == (False, False) for signal in emitted[:_FIRST_SIGNAL_INDEX])
    assert tuple(index for index, signal in enumerate(emitted) if any(signal)) == (
        _EXPECTED_SIGNAL_INDICES
    )
    assert {signal for signal in emitted if any(signal)} == {(True, False), (False, True)}
    assert emitted[-1] == (False, True)


def test_parity_harness_rejects_a_divergent_live_adapter(
    monkeypatch: pytest.MonkeyPatch,
    shared_bars: tuple[_FixtureBar, ...],
    shared_params: SignalParams,
) -> None:
    monkeypatch.setattr(live_runner, "RsiWprBbSignals", _BuySellSwappedSignals)
    with pytest.raises(
        AssertionError,
        match=(
            r"signal adapter mismatch at bar 29: "
            r"backtest=\(True, False\), live=\(False, True\)"
        ),
    ):
        _assert_adapter_parity(shared_bars, shared_params)
