"""A synthetic MT5 H4 export, shaped so the mean-reversion strategy actually trades on it.

Integration tests need a market, not a price list: a flat or monotone series produces no signals,
so the test would pass by trading nothing and prove nothing. This oscillates with enough amplitude
to push RSI and the Bollinger bands through their thresholds repeatedly.
"""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

_HEADER = "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>"


def write_mt5_csv(
    path: Path,
    *,
    start: str = "2018-01-01",
    bars: int = 4400,
    base: float = 100.0,
    amplitude: float = 4.0,
    period: int = 37,
) -> Path:
    """Write a deterministic H4 series that oscillates around ``base``.

    ``period`` is deliberately not a divisor of the daily bar count, so the swings do not line up
    with day boundaries and the series never degenerates into one repeating day.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    stamps = pd.date_range(start=start, periods=bars, freq="4h")
    lines = [_HEADER]
    for i, ts in enumerate(stamps):
        mid = base + amplitude * math.sin(2 * math.pi * i / period)
        drift = 0.35 * math.sin(2 * math.pi * i / (period * 11))  # slow regime changes
        o = mid + drift
        c = base + amplitude * math.sin(2 * math.pi * (i + 1) / period) + drift
        high = max(o, c) + 0.15
        low = min(o, c) - 0.15
        lines.append(
            f"{ts:%Y.%m.%d}\t{ts:%H:%M:%S}\t{o:.5f}\t{high:.5f}\t{low:.5f}\t{c:.5f}\t500\t0\t10"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
