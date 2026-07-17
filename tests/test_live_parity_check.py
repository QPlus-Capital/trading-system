"""Tests for the pure parity-comparison logic (no terminal needed)."""

from core.strategies.rsi_wpr_bb_signals import SignalParams
from live.mt5_bridge import Bar
from live.parity_check import compare

_H4 = 4 * 3600
_T0 = 1_700_000_000 // _H4 * _H4  # aligned to a 4h boundary


def _bars(n: int, *, offset_sec: int = 0, close_shift: float = 0.0) -> list[Bar]:
    out = []
    for i in range(n):
        base = 100.0 + i * 0.1
        out.append(
            Bar(_T0 + i * _H4 + offset_sec, base, base + 0.6, base - 0.4, base + 0.3 + close_shift)
        )
    return out


def test_identical_bars_are_parity_clean() -> None:
    bars = _bars(200)
    r = compare(bars, list(bars), SignalParams())
    assert r.match_rate == 1.0
    assert r.close_diff_max == 0.0
    assert r.signal_disagree == 0
    assert r.ok


def test_time_offset_is_detected_and_not_ok() -> None:
    # Live bars shifted by +2h (a broker-timezone shift) -> no bar times line up.
    live = _bars(200, offset_sec=2 * 3600)
    csv = _bars(200)
    r = compare(live, csv, SignalParams())
    assert r.match_rate == 0.0
    assert abs(r.modal_offset_hours - 2.0) < 1e-6
    assert not r.ok


def test_ohlc_drift_flags_not_ok() -> None:
    # Same grid, but every close is 0.2% higher -> parity should flag it.
    live = _bars(200, close_shift=0.2)
    csv = _bars(200)
    r = compare(live, csv, SignalParams())
    assert r.match_rate == 1.0
    assert r.close_diff_max > 5e-4
    assert not r.ok
