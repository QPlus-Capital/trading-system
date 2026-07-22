"""Hypothesis strategies for the framework's recurring financial and temporal domains."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pandas as pd
from core.strategies.param_schedule import ParamSegment
from hypothesis import strategies as st
from hypothesis.strategies import DrawFn, SearchStrategy
from research.engine.walkforward import WalkForwardWindow


@dataclass(frozen=True)
class TradeSample:
    """A valid single-market trade lifecycle used to build pure sizing streams."""

    market: str
    open_day: int
    close_day: int
    pnl_base: Decimal
    swap_base: Decimal
    entry: Decimal
    exit: Decimal
    is_long: bool


@dataclass(frozen=True)
class SymbolLotMetadata:
    """Positive, lot-step-aligned metadata accepted by position sizing."""

    tick_size: Decimal
    tick_value: Decimal
    min_lot: Decimal
    lot_step: Decimal
    max_lot: Decimal


@dataclass(frozen=True)
class BoundaryTimestamps:
    """Strictly ordered instants around a half-open temporal interval."""

    before: datetime
    start: datetime
    within: datetime
    end: datetime
    after: datetime


def finite_decimals(
    *, min_value: Decimal, max_value: Decimal, places: int
) -> SearchStrategy[Decimal]:
    """Finite fixed-scale Decimals; never NaN, infinity, or a float round-trip."""
    return st.decimals(
        min_value=min_value,
        max_value=max_value,
        allow_nan=False,
        allow_infinity=False,
        places=places,
    )


@st.composite
def valid_windows(draw: DrawFn) -> tuple[WalkForwardWindow, ...]:
    """One to four ordered, non-overlapping windows, including possible ownership gaps."""
    count = draw(st.integers(min_value=1, max_value=4))
    offset = draw(st.integers(min_value=0, max_value=3650))
    duration = draw(st.integers(min_value=1, max_value=90))
    gaps = draw(
        st.lists(st.integers(min_value=0, max_value=45), min_size=count - 1, max_size=count - 1)
    )
    start = pd.Timestamp("2010-01-01") + pd.Timedelta(days=offset)
    windows: list[WalkForwardWindow] = []
    for index in range(count):
        end = start + pd.Timedelta(days=duration)
        windows.append(WalkForwardWindow(start - pd.Timedelta(days=180), start, start, end))
        if index < count - 1:
            start = end + pd.Timedelta(days=gaps[index])
    return tuple(windows)


@st.composite
def invalid_windows(draw: DrawFn) -> tuple[WalkForwardWindow, WalkForwardWindow]:
    """Two individually valid windows whose test intervals overlap."""
    offset = draw(st.integers(min_value=0, max_value=3650))
    duration = draw(st.integers(min_value=2, max_value=90))
    overlap = draw(st.integers(min_value=1, max_value=duration - 1))
    first_start = pd.Timestamp("2010-01-01") + pd.Timedelta(days=offset)
    first_end = first_start + pd.Timedelta(days=duration)
    second_start = first_end - pd.Timedelta(days=overlap)
    second_end = second_start + pd.Timedelta(days=duration)
    return (
        WalkForwardWindow(
            first_start - pd.Timedelta(days=180), first_start, first_start, first_end
        ),
        WalkForwardWindow(
            second_start - pd.Timedelta(days=180), second_start, second_start, second_end
        ),
    )


@st.composite
def schedule_segments(draw: DrawFn) -> tuple[ParamSegment, ...]:
    """Strictly ordered parameter segments with finite positive stops and targets."""
    starts = draw(
        st.lists(
            st.integers(min_value=-(10**15), max_value=10**15),
            min_size=1,
            max_size=8,
            unique=True,
        )
    )
    starts.sort()
    stops = draw(
        st.lists(
            finite_decimals(min_value=Decimal("0.01"), max_value=Decimal("10"), places=2),
            min_size=len(starts),
            max_size=len(starts),
        )
    )
    targets = draw(
        st.lists(
            finite_decimals(min_value=Decimal("0.01"), max_value=Decimal("20"), places=2),
            min_size=len(starts),
            max_size=len(starts),
        )
    )
    allowed = draw(st.lists(st.booleans(), min_size=len(starts), max_size=len(starts)))
    return tuple(
        ParamSegment(start, float(stop), float(target), permit)
        for start, stop, target, permit in zip(starts, stops, targets, allowed, strict=True)
    )


@st.composite
def trade_streams(draw: DrawFn) -> tuple[TradeSample, ...]:
    """One to eight valid trade lifecycles with unique symbols and realized costs."""
    raw = draw(
        st.lists(
            st.tuples(
                st.integers(min_value=0, max_value=20),
                st.integers(min_value=0, max_value=5),
                finite_decimals(min_value=Decimal("-5000"), max_value=Decimal("5000"), places=2),
                finite_decimals(min_value=Decimal("-100"), max_value=Decimal("0"), places=2),
                st.booleans(),
            ),
            min_size=1,
            max_size=8,
        )
    )
    trades: list[TradeSample] = []
    for index, (open_day, hold_days, pnl, swap, is_long) in enumerate(raw):
        entry = Decimal(100)
        direction = Decimal(1) if is_long else Decimal(-1)
        price_move = direction * (Decimal(1) if pnl >= 0 else Decimal(-1))
        trades.append(
            TradeSample(
                market=f"M{index}",
                open_day=open_day,
                close_day=open_day + hold_days,
                pnl_base=pnl,
                swap_base=swap,
                entry=entry,
                exit=entry + price_move,
                is_long=is_long,
            )
        )
    return tuple(trades)


def zero_sparse_references() -> SearchStrategy[tuple[int, int]]:
    """Zero and sparse reference/candidate counts for denominator and empty-input guards."""
    return st.tuples(st.integers(min_value=0, max_value=2), st.integers(min_value=0, max_value=20))


@st.composite
def symbol_lot_metadata(draw: DrawFn) -> SymbolLotMetadata:
    """Positive tick and lot metadata whose min/max quantities lie on the lot grid."""
    step = draw(st.sampled_from([Decimal("0.01"), Decimal("0.1"), Decimal("1")]))
    minimum_steps = draw(st.integers(min_value=1, max_value=10))
    maximum_steps = draw(st.integers(min_value=minimum_steps, max_value=1000))
    return SymbolLotMetadata(
        tick_size=draw(
            finite_decimals(min_value=Decimal("0.0001"), max_value=Decimal("10"), places=4)
        ),
        tick_value=draw(
            finite_decimals(min_value=Decimal("0.0001"), max_value=Decimal("100"), places=4)
        ),
        min_lot=step * minimum_steps,
        lot_step=step,
        max_lot=step * maximum_steps,
    )


@st.composite
def boundary_timestamps(draw: DrawFn) -> BoundaryTimestamps:
    """Timezone-aware instants before, on, within, at, and after an interval boundary."""
    offset = draw(st.integers(min_value=0, max_value=3650 * 24 * 60))
    duration = draw(st.integers(min_value=2, max_value=10_000))
    within = draw(st.integers(min_value=1, max_value=duration - 1))
    start = datetime(2010, 1, 1, tzinfo=UTC) + timedelta(minutes=offset)
    return BoundaryTimestamps(
        before=start - timedelta(microseconds=1),
        start=start,
        within=start + timedelta(microseconds=within),
        end=start + timedelta(microseconds=duration),
        after=start + timedelta(microseconds=duration + 1),
    )
