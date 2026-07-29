"""Tests for the live Notifier (file channel; beep/telegram are off by default)."""

import logging
import sys
import urllib.request
from pathlib import Path

import pytest
from live import notify
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


def test_missing_remote_notification_transport_logs_a_warning(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    with caplog.at_level(logging.WARNING, logger="live"):
        Notifier()

    assert [record.getMessage() for record in caplog.records] == [
        "Telegram notifications disabled: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must both be "
        "set; safety alerts will not reach a remote transport"
    ]


@pytest.mark.parametrize(
    ("token", "chat"),
    [
        ("12345:" + "partial-token", None),
        (None, "98765"),
    ],
)
def test_partial_remote_notification_transport_warns_without_disclosure(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    token: str | None,
    chat: str | None,
) -> None:
    for name, value in (
        ("TELEGRAM_BOT_TOKEN", token),
        ("TELEGRAM_CHAT_ID", chat),
    ):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)

    with caplog.at_level(logging.WARNING, logger="live"):
        Notifier()

    assert "safety alerts will not reach a remote transport" in caplog.text
    for value in (token, chat):
        if value is not None:
            assert value not in caplog.text


def test_beep_is_opt_in_and_runs_only_when_requested_on_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[bool] = []
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(Notifier, "_do_beep", lambda _self, urgent: calls.append(urgent))
    monkeypatch.setattr(Notifier, "_send_telegram", lambda _self, _text: None)

    Notifier(telegram=("", "")).signal("default remains silent")
    assert calls == []

    enabled = Notifier(beep=True, telegram=("", ""))
    enabled.signal("requested signal beep")
    enabled.alert("requested alert beep")
    assert calls == [False, True]


def test_beep_request_is_ignored_off_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[bool] = []
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(Notifier, "_do_beep", lambda _self, urgent: calls.append(urgent))
    monkeypatch.setattr(Notifier, "_send_telegram", lambda _self, _text: None)

    Notifier(beep=True, telegram=("", "")).signal("no platform beep")

    assert calls == []


def test_a_failed_telegram_send_never_writes_the_token_to_the_log(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """#21: the Bot API requires the token in the URL, and urllib errors carry that URL. The log
    must not become the place the token leaks to."""
    token = "123456789:AAEEsecretsecretsecret"
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", token)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")

    def boom(*_a: object, **_k: object) -> None:
        # Mirrors urllib: the exception text carries the full request URL.
        raise OSError(f"HTTP 401 for https://api.telegram.org/bot{token}/sendMessage")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    n = notify.Notifier(Path("nul"), beep=False)
    with caplog.at_level(logging.WARNING):
        n.signal("hello")
    logged = caplog.text
    assert "telegram notification failed" in logged  # the failure is still reported
    assert token not in logged  # ...but never with the secret
    assert "123456789" not in logged  # not even the bare bot id
