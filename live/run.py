"""Entry point to run the live trader against a running MT5 terminal.

Safety-first defaults: it attaches to an **already-logged-in** terminal (no credentials in
code) and runs in **SIGNAL_ONLY** mode -- it logs signals + sizing but places NO orders.
Switch to real orders only with an explicit ``--mode execute``.

Two accounts run in parallel, each attached to its OWN MT5 terminal and with fully isolated
state under ``reports/live/<account>/`` -- pick one with ``--account`` (see
:mod:`live.accounts`). The runner refuses to trade unless the connected account's login
and currency match the chosen profile.

Usage (from the repo root, with that account's MT5 terminal open + logged in, Algo Trading
enabled, and all symbols in Market Watch):

    uv run python -m live.run --account mex                 # demo, SIGNAL_ONLY dry-run
    uv run python -m live.run --account ttp --once          # TTP, a single cycle
    uv run python -m live.run --account ttp --mode execute  # TTP, place REAL orders

The risk layer uses the account's starting balance as the reference for the daily / trailing
floors. Logs go to the console and to ``reports/live/<account>/live.log``.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from core.paths import REPO_ROOT

from live.accounts import ACCOUNTS, get_account, guard_account
from live.mt5_bridge import SYMBOL_MAP, Mt5Bridge
from live.notify import Notifier
from live.risk_control import RiskController, RiskLimits
from live.runner import (
    LiveRunner,
    Mode,
    long_only_from_live_config,
    markets_from_live_config,
    risk_per_trade_from_live_config,
    signal_params_from_live_config,
)

log = logging.getLogger("live")

# Anchor all state/log paths to the REPO ROOT, not the current working directory: a relative
# risk_state.json would silently start with FRESH risk references (losing the K1 protection)
# whenever the runner is launched from a different directory. Each account gets its own subdir
# so two runners (mex, ttp) never share state.
_REPO_ROOT = REPO_ROOT
_LIVE_ROOT = _REPO_ROOT / "reports" / "live"


def _setup_logging(live_dir: Path) -> None:
    live_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(live_dir / "live.log")],
    )


def main(argv: list[str] | None = None) -> None:
    """Connect, build the runner from the frozen live config, and run."""
    parser = argparse.ArgumentParser(description="QPlus live trader (MT5).")
    parser.add_argument(
        "--mode",
        choices=[m.value.lower() for m in Mode],
        default=Mode.SIGNAL_ONLY.value.lower(),
        help="signal_only (default, no orders) or execute (place orders).",
    )
    parser.add_argument(
        "--account",
        default="mex",
        choices=sorted(ACCOUNTS),
        help="which live account to run (its terminal + isolated state). 'ttp' = the real $50k "
        "prop account, 'mex' = the demo. The runner refuses to trade if the connected account's "
        "login/currency does not match the profile.",
    )
    parser.add_argument("--once", action="store_true", help="run a single cycle, then exit.")
    parser.add_argument(
        "--poll",
        type=int,
        default=30,
        help="seconds between cycles (loop mode). Tighter than the H4 bar so the account-level "
        "safety cut-off reacts sooner; each order's server-side SL/TP is the intrabar backstop.",
    )
    parser.add_argument(
        "--start-balance",
        type=float,
        default=None,
        help="the OPENING balance of the current prop loss day (resets 16:15 CT). REQUIRED on a "
        "first run with no saved risk state -- the runner halts rather than guess it, because "
        "guessing can hand out a second daily loss budget. Afterwards the saved state wins.",
    )
    args = parser.parse_args(argv)

    profile = get_account(args.account)
    live_dir = _LIVE_ROOT / profile.name
    _setup_logging(live_dir)
    mode = Mode(args.mode.upper())
    state_path = live_dir / "risk_state.json"

    bridge = Mt5Bridge(symbol_map={**SYMBOL_MAP, **profile.symbol_overrides})
    bridge.connect(path=profile.terminal_path)  # attach to THIS account's terminal (no creds)
    try:
        account = bridge.account()
        # SAFETY: refuse to run unless we are really on the expected account (login + currency).
        guard_account(account, profile, execute=(mode == Mode.EXECUTE))
        log.info(
            "connected: account=***%03d (%s) balance=%.2f equity=%.2f %s | mode=%s",
            account.login % 1000,  # masked: the full login is not written to logs
            profile.name,
            account.balance,
            account.equity,
            account.currency,
            mode.value,
        )
        # Provisional reference for the FIRST run only; if a saved state exists the runner
        # restores it and this is ignored (K1: restarts must not reset the risk references).
        start_balance = (
            args.start_balance if args.start_balance is not None else profile.start_balance
        )
        limits = RiskLimits(risk_per_trade=risk_per_trade_from_live_config())  # M3: from config
        log.info("risk per trade: %.3f%% of equity (compounding)", limits.risk_per_trade * 100)
        notifier = Notifier(live_dir / "signals.log", beep=True)  # +Telegram if env vars set
        runner = LiveRunner(
            bridge,
            markets_from_live_config(),
            signal_params_from_live_config(),
            RiskController(limits, start_balance),
            mode=mode,
            state_path=state_path,
            long_only=long_only_from_live_config(),
            notifier=notifier,
            expected_login=profile.expected_login,
            expected_currency=profile.expected_currency,
            # Only what the operator passed explicitly: the profile's balance is the ACCOUNT
            # reference, not this loss day's opening balance, so it must not stand in for one.
            day_start_balance=args.start_balance,
        )
        if args.once:
            try:  # N3: a single cycle must not crash with a bare traceback on a transient error
                runner.run_once()
            except Exception:
                log.exception("run_once failed")
        else:
            runner.run_forever(poll_seconds=args.poll)
    finally:
        bridge.shutdown()


if __name__ == "__main__":
    main()
