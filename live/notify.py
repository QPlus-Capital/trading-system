"""Live notifications -- a signal ping you cannot miss while running live.

The runner calls this on every position change and on a safety halt. Every channel is optional
and best-effort: a notification failure must NEVER disrupt trading, so all of them swallow their
own errors.

- **signals log file** -- a dedicated file you can tail / check "did anything happen",
- **Windows beep** -- zero setup, instantly noticeable at the desk,
- **Telegram** -- remote pings, only if ``TELEGRAM_BOT_TOKEN`` + ``TELEGRAM_CHAT_ID`` are set in
  the environment (from a gitignored ``.env`` / the password manager, never the repo).
"""

from __future__ import annotations

import logging
import os
import sys
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

log = logging.getLogger("live")


def redact_token(text: str, token: str) -> str:
    """Replace ``token`` (and its bare id half) with ``***`` anywhere in ``text``.

    Telegram bot tokens look like ``12345:AA...``; error strings sometimes carry only the numeric
    id, so both halves are scrubbed.
    """
    if not token:
        return text
    out = text.replace(token, "***")
    bot_id = token.split(":", 1)[0]
    return out.replace(bot_id, "***") if bot_id else out


class Notifier:
    """Fan-out for signal / alert pings across the configured channels (all best-effort)."""

    def __init__(
        self,
        signals_path: Path | None = None,
        *,
        beep: bool = False,
        telegram: tuple[str, str] | None = None,
    ) -> None:
        self._signals_path = signals_path
        self._beep = beep and sys.platform == "win32"
        if telegram is None:  # auto-configure from the environment if present
            token = os.environ.get("TELEGRAM_BOT_TOKEN")
            chat = os.environ.get("TELEGRAM_CHAT_ID")
            telegram = (token, chat) if token and chat else None
            if telegram is None:
                log.warning(
                    "Telegram notifications disabled: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID "
                    "must both be set; safety alerts will not reach a remote transport"
                )
        self._telegram = telegram

    def signal(self, text: str) -> None:
        """A normal position change (open / reverse / flatten)."""
        self._emit(text, urgent=False)

    def alert(self, text: str) -> None:
        """An urgent event (safety halt) -- louder ping."""
        self._emit(text, urgent=True)

    # -- channels (each guarded so it can never break the runner) --

    def _emit(self, text: str, *, urgent: bool) -> None:
        kind = "ALERT" if urgent else "SIGNAL"
        line = f"{datetime.now(UTC):%Y-%m-%d %H:%M:%S} {kind} {text}"
        if self._signals_path is not None:
            try:
                self._signals_path.parent.mkdir(parents=True, exist_ok=True)
                with self._signals_path.open("a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
            except OSError:
                log.exception("could not append to the signals log")
        if self._beep:
            self._do_beep(urgent)
        if self._telegram is not None:
            self._send_telegram(f"[{kind}] {text}")

    def _do_beep(self, urgent: bool) -> None:
        try:
            import winsound

            for _ in range(3 if urgent else 1):
                winsound.Beep(1200 if urgent else 800, 250)
        except Exception:  # noqa: BLE001 -- a failed beep must not matter
            pass

    def _send_telegram(self, text: str) -> None:
        assert self._telegram is not None
        token, chat = self._telegram
        try:
            data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
            req = urllib.request.Request(  # noqa: S310 -- fixed https telegram endpoint
                f"https://api.telegram.org/bot{token}/sendMessage", data=data
            )
            urllib.request.urlopen(req, timeout=10)  # noqa: S310
        except Exception as exc:  # noqa: BLE001 -- best-effort remote ping
            # #21: the Bot API puts the token in the URL path and offers no header alternative, so
            # the defence is keeping it out of anything persistent. urllib errors carry the full
            # URL, and log.exception would write that traceback straight into live.log -- so log a
            # redacted one-liner instead of the exception.
            log.warning("telegram notification failed: %s", redact_token(str(exc), token))
