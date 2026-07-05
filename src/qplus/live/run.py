"""Entry point to run the live/paper trader against a running MT5 terminal (Phase 5).

Safety-first defaults: it attaches to an **already-logged-in** terminal (no credentials in
code) and runs in **SIGNAL_ONLY** mode -- it logs signals + sizing but places NO orders.
Switch to real orders only with an explicit ``--mode execute``.

Usage (from the repo root, with the MT5 terminal open + logged into the demo, Algo Trading
enabled, and all 9 symbols incl. UT100 in Market Watch):

    uv run python -m qplus.live.run                 # SIGNAL_ONLY dry-run, loops
    uv run python -m qplus.live.run --once          # a single cycle, then exit
    uv run python -m qplus.live.run --mode execute  # place real (paper) orders

The risk layer uses the account's starting balance as the reference for the daily / trailing
floors. Logs go to the console and to ``reports/live/live.log``.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from qplus.live.mt5_bridge import Mt5Bridge
from qplus.live.risk_control import RiskController, RiskLimits
from qplus.live.runner import (
    LiveRunner,
    Mode,
    long_only_from_paper_config,
    markets_from_paper_config,
    risk_per_trade_from_paper_config,
    signal_params_from_paper_config,
)

log = logging.getLogger("qplus.live")

# Anchor all state/log paths to the REPO ROOT, not the current working directory: a relative
# risk_state.json would silently start with FRESH risk references (losing the K1 protection)
# whenever the runner is launched from a different directory.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_LIVE_DIR = _REPO_ROOT / "reports" / "live"


def _setup_logging() -> None:
    _LIVE_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(_LIVE_DIR / "live.log")],
    )


def main(argv: list[str] | None = None) -> None:
    """Connect, build the runner from the frozen paper config, and run."""
    parser = argparse.ArgumentParser(description="QPlus live/paper trader (MT5).")
    parser.add_argument(
        "--mode",
        choices=[m.value.lower() for m in Mode],
        default=Mode.SIGNAL_ONLY.value.lower(),
        help="signal_only (default, no orders) or execute (place orders).",
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
        help="pin the account's INITIAL balance (the trailing/daily reference). Only used on the "
        "first run; afterwards the saved risk state wins. Default: the balance at first launch.",
    )
    args = parser.parse_args(argv)

    _setup_logging()
    mode = Mode(args.mode.upper())
    state_path = _LIVE_DIR / "risk_state.json"

    bridge = Mt5Bridge()
    bridge.connect()  # attach to the already-logged-in terminal (no credentials in code)
    try:
        account = bridge.account()
        log.info(
            "connected: balance=%.2f equity=%.2f %s | mode=%s",
            account.balance,
            account.equity,
            account.currency,
            mode.value,
        )
        # Provisional reference for the FIRST run only; if a saved state exists the runner
        # restores it and this is ignored (K1: restarts must not reset the risk references).
        start_balance = args.start_balance if args.start_balance is not None else account.balance
        limits = RiskLimits(risk_per_trade=risk_per_trade_from_paper_config())  # M3: from config
        log.info("risk per trade: %.3f%% of the initial balance", limits.risk_per_trade * 100)
        runner = LiveRunner(
            bridge,
            markets_from_paper_config(),
            signal_params_from_paper_config(),
            RiskController(limits, start_balance),
            mode=mode,
            state_path=state_path,
            long_only=long_only_from_paper_config(),
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
