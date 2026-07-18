"""Tests for the real candidate matrix behind PBO/DSR (#13).

The old statistics compared a handful of variations while the trial budget counted the whole
grid, and built their "time" axis by concatenating instrument blocks. These lock in the honest
construction: candidates are (variation x grid-combo), the time axis is the walk-forward windows,
and instruments are averaged into each window rather than laid end to end.
"""

import math

import pytest
from research.engine.characterize import candidate_pbo, candidate_streams
from research.engine.overfitting import cscv_splits
from research.engine.walkforward import combo_key


def _row(
    instrument: str, variation: str, tm: int, combos: dict[str, dict[str, float]]
) -> dict[str, object]:
    """combo_oos is keyed BY WINDOW LABEL, so instruments with different spans still align."""
    return {"instrument": instrument, "variation": variation, "train_months": tm,
            "combo_oos": combos}


def test_candidates_are_variation_times_combo_not_just_variation() -> None:
    good = [
        _row("X", v, 24, {"sl=1.0": {"w1": 0.01, "w2": 0.02}, "sl=2.0": {"w1": 0.03, "w2": 0.04}})
        for v in ("a", "b", "c")
    ]
    streams = candidate_streams(good)
    # 3 variations x 2 combos = 6 candidates for that training length (not 3).
    assert len(streams[24]) == 6
    assert ("a", "sl=1.0") in streams[24]


def test_instruments_are_averaged_into_windows_not_concatenated() -> None:
    # Two instruments, two windows. Concatenating would give a 4-long "time" axis (the old flaw);
    # averaging keeps real time at 2 windows and averages the instruments within each.
    good = [
        _row("X", "a", 24, {"sl=1.0": {"w1": 0.10, "w2": 0.20}}),
        _row("Y", "a", 24, {"sl=1.0": {"w1": 0.30, "w2": 0.40}}),
    ]
    stream = candidate_streams(good)[24][("a", "sl=1.0")]
    assert len(stream) == 2  # real time = 2 windows, not 4 concatenated cells
    assert stream == pytest.approx([0.20, 0.30])  # (0.10+0.30)/2, (0.20+0.40)/2


def test_training_lengths_stay_separate() -> None:
    # Different train lengths have different window boundaries -> not alignable into one matrix.
    good = [
        _row("X", "a", 18, {"sl=1.0": {"w1": 0.01, "w2": 0.02, "w3": 0.03}}),
        _row("X", "a", 36, {"sl=1.0": {"w1": 0.04, "w2": 0.05}}),
    ]
    streams = candidate_streams(good)
    assert set(streams) == {18, 36}
    assert len(streams[18][("a", "sl=1.0")]) == 3
    assert len(streams[36][("a", "sl=1.0")]) == 2


def test_pbo_is_nan_when_no_training_length_has_enough_windows() -> None:
    # Three windows cannot support a CSCV; the study must say "unknown", not invent a number.
    good = [_row("X", v, 24, {"sl=1.0": {"w1": 0.01, "w2": 0.02, "w3": 0.03}}) for v in ("a", "b")]
    assert math.isnan(candidate_pbo(candidate_streams(good)))


def test_cscv_splits_adapts_to_short_studies() -> None:
    assert cscv_splits(20) == 10  # plenty of windows -> the preferred count
    assert cscv_splits(9) == 8  # 9 windows -> largest even count that fits
    assert cscv_splits(3) == 0  # too few to say anything


def test_combo_key_is_order_independent() -> None:
    assert combo_key({"tp": 3.0, "sl": 1.0}) == combo_key({"sl": 1.0, "tp": 3.0})


def test_instruments_with_different_spans_align_on_shared_windows() -> None:
    """Codex P2: averaging by list offset mixed window 0 of a long history with window 0 of a
    later-starting one -- unrelated calendar periods presented as one time slice."""
    good = [
        _row("LONG", "a", 24, {"sl=1.0": {"w1": 0.10, "w2": 0.20, "w3": 0.30}}),
        _row("LATE", "a", 24, {"sl=1.0": {"w2": 0.40, "w3": 0.60}}),  # starts a window later
    ]
    stream = candidate_streams(good)[24][("a", "sl=1.0")]
    # Only w2 and w3 are shared, and they are matched BY LABEL: (0.20+0.40)/2, (0.30+0.60)/2.
    assert stream == pytest.approx([0.30, 0.45])
