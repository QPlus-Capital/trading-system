"""Live-vs-backtest parity check -- does the broker's feed give the SAME signals as our data?

The whole thesis rests on live == backtest. The signal engine is shared, so signals can only
diverge if the **bars** differ: the broker's H4 candles could be on a different session grid
(server timezone) or carry slightly different OHLC than the CSVs the study was built on.

For each market this pulls recent H4 bars from the live terminal, loads the study CSV, and on
their overlapping period reports:

- **alignment** -- do the bar open-times line up on the same 4h grid? (a timezone/session shift
  shows up here as a low match rate + a non-zero modal offset),
- **OHLC agreement** -- how close are the close prices on matched bars,
- **signal agreement** -- feed each source's matched bars into a fresh engine and compare the
  buy/sell decisions bar by bar.

Run from the repo root with the MT5 terminal open + logged in::

    uv run python -m live.parity_check
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from core.paths import REPO_ROOT
from core.strategies.rsi_wpr_bb_signals import RsiWprBbSignals, SignalParams

from live.mt5_bridge import Bar, Mt5Bridge

_H4 = 4 * 3600
_EPOCH = pd.Timestamp("1970-01-01", tz="UTC")


def load_csv_bars(csv_path: str | Path) -> list[Bar]:
    """Load H4 OHLC bars from a study MT5 CSV (open time in epoch seconds, parsed as UTC)."""
    df = pd.read_csv(
        csv_path,
        sep="\t",
        usecols=["<DATE>", "<TIME>", "<OPEN>", "<HIGH>", "<LOW>", "<CLOSE>"],
    )
    ts = pd.to_datetime(df["<DATE>"] + " " + df["<TIME>"], format="%Y.%m.%d %H:%M:%S", utc=True)
    epoch = ((ts - _EPOCH) // pd.Timedelta(seconds=1)).to_numpy()
    return [
        Bar(int(e), float(o), float(h), float(low), float(c))
        for e, o, h, low, c in zip(
            epoch, df["<OPEN>"], df["<HIGH>"], df["<LOW>"], df["<CLOSE>"], strict=True
        )
    ]


@dataclass(frozen=True)
class ParityResult:
    """Outcome of comparing one market's live bars against its study CSV."""

    overlap: int  # live bars falling inside the CSV's time range
    matched: int  # of those, how many have an exactly-matching CSV bar time
    match_rate: float
    modal_offset_hours: float  # most common live-vs-nearest-CSV time offset (0 = aligned)
    close_diff_max: float  # worst relative close difference on matched bars
    signal_agree: int
    signal_disagree: int

    @property
    def ok(self) -> bool:
        """Bars line up, prices match to a whisker, and every compared signal agrees."""
        return (
            self.match_rate >= 0.98
            and self.close_diff_max <= 5e-4  # 0.05%
            and self.signal_disagree == 0
            and self.matched > 50
        )


def compare(mt5_bars: list[Bar], csv_bars: list[Bar], params: SignalParams) -> ParityResult:
    """Compare live bars to CSV bars on their overlap: alignment, OHLC, and signal parity (pure)."""
    csv_by_time = {b.time: b for b in csv_bars}
    if not csv_by_time:
        return ParityResult(0, 0, 0.0, 0.0, 0.0, 0, 0)
    lo, hi = min(csv_by_time), max(csv_by_time)
    overlap = sorted((b for b in mt5_bars if lo <= b.time <= hi), key=lambda b: b.time)
    csv_times = sorted(csv_by_time)

    matched = [b for b in overlap if b.time in csv_by_time]
    diffs = [
        abs(b.close - csv_by_time[b.time].close) / csv_by_time[b.time].close
        for b in matched
        if csv_by_time[b.time].close
    ]

    # Modal offset of the UNmatched live bars to the nearest CSV bar (reveals a session shift).
    offsets = [
        min((abs(b.time - t) for t in csv_times), default=0)
        for b in overlap
        if b.time not in csv_by_time
    ]
    modal = pd.Series(offsets).round().mode()
    modal_hours = float(modal.iloc[0]) / 3600 if len(modal) else 0.0

    # Signal parity: feed each source's matched bars (same times, time order) into a fresh engine.
    eng_live, eng_csv = RsiWprBbSignals(params), RsiWprBbSignals(params)
    agree = disagree = 0
    for b in matched:
        c = csv_by_time[b.time]
        s_live = eng_live.update(b.open, b.high, b.low, b.close)
        s_csv = eng_csv.update(c.open, c.high, c.low, c.close)
        if eng_live.warmed_up and eng_csv.warmed_up:
            if s_live == s_csv:
                agree += 1
            else:
                disagree += 1

    return ParityResult(
        overlap=len(overlap),
        matched=len(matched),
        match_rate=len(matched) / len(overlap) if overlap else 0.0,
        modal_offset_hours=modal_hours,
        close_diff_max=max(diffs, default=0.0),
        signal_agree=agree,
        signal_disagree=disagree,
    )


def main() -> None:
    """Connect to the terminal and print a parity report for every configured market."""
    from research.engine.config import load_config_module

    cfg = load_config_module(REPO_ROOT / "live" / "config" / "paper_rsi_wpr_bb.py")
    switches = {k: v for k, v in dict(cfg.STRATEGY_SWITCHES).items() if k != "long_only"}
    params = SignalParams(**switches)

    bridge = Mt5Bridge()
    bridge.connect()
    try:
        header = f"{'market':8s} {'match':>7s} {'offset':>7s} {'close_dmax':>10s} {'sig a/d':>10s}"
        print(f"{header}  verdict")
        all_ok = True
        for factory, csv, _lev, _sl, _tp in cfg.MARKETS:
            name = str(factory().raw_symbol)
            mt5_bars = bridge.latest_bars(name, 5000)  # enough to overlap the CSV's recent end
            r = compare(mt5_bars, load_csv_bars(REPO_ROOT / csv), params)
            verdict = "OK" if r.ok else "CHECK!"
            all_ok = all_ok and r.ok
            sig = f"{r.signal_agree}/{r.signal_disagree}"
            print(
                f"{name:8s} {r.match_rate:>6.1%} {r.modal_offset_hours:>6.1f}h "
                f"{r.close_diff_max:>9.3%} {sig:>10s}  {verdict}"
            )
        if all_ok:
            print("\nAll markets parity-clean -> live feed == backtest data.")
        else:
            print("\nSome markets need a look (CHECK!): different bar grid, stale CSV, or drift.")
    finally:
        bridge.shutdown()


if __name__ == "__main__":
    main()
