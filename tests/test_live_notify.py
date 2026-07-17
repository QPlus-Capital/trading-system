"""Tests for the live Notifier (file channel; beep/telegram are off by default)."""

from pathlib import Path

from live.notify import Notifier


def test_signal_and_alert_append_to_the_signals_file(tmp_path: Path) -> None:
    path = tmp_path / "signals.log"
    n = Notifier(path)  # beep off, no telegram
    n.signal("[XAUUSD] OPEN BUY vol=0.1")
    n.alert("SAFETY HALT: daily stop")
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert "SIGNAL" in lines[0] and "OPEN BUY" in lines[0]
    assert "ALERT" in lines[1] and "SAFETY HALT" in lines[1]


def test_no_file_channel_is_a_no_op() -> None:
    # Without a signals path (and no telegram/beep), notifying must not raise.
    Notifier().signal("nothing configured -> silent, no error")
