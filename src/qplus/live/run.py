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
    markets_from_paper_config,
    signal_params_from_paper_config,
)

log = logging.getLogger("qplus.live")


def _setup_logging() -> None:
    log_dir = Path("reports/live")
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(log_dir / "live.log")],
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
    parser.add_argument("--poll", type=int, default=60, help="seconds between cycles (loop mode).")
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
    state_path = Path("reports/live/risk_state.json")

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
        runner = LiveRunner(
            bridge,
            markets_from_paper_config(),
            signal_params_from_paper_config(),
            RiskController(RiskLimits(), start_balance),
            mode=mode,
            state_path=state_path,
        )
        if args.once:
            runner.run_once()
        else:
            runner.run_forever(poll_seconds=args.poll)
    finally:
        bridge.shutdown()


if __name__ == "__main__":
    main()
