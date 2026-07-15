"""GO/NO-GO pre-flight before taking an account live.

Read-only: connects to the account's terminal and checks everything that must be true before
``--mode execute`` -- the right account (login + currency), Algo Trading enabled, every configured
market resolves to a symbol, and every market sizes to a valid lot at 0.18% of the current balance
(so nothing is silently skipped -- e.g. gold on a too-small account). Places no orders.

    uv run python -m qplus.live.preflight --account ttp
"""

from __future__ import annotations

import argparse

from qplus.live.accounts import ACCOUNTS, get_account
from qplus.live.mt5_bridge import Mt5Bridge
from qplus.live.runner import (
    markets_from_paper_config,
    risk_per_trade_from_paper_config,
    size_order,
)

try:
    import MetaTrader5 as mt5
except ImportError:  # pragma: no cover -- Windows-only package
    mt5 = None


def _checks(bridge: Mt5Bridge, account_name: str) -> tuple[list[tuple[str, bool, str]], float]:
    """Run every pre-flight check and return (rows, per-trade risk EUR) -- no side effects."""
    profile = get_account(account_name)
    rows: list[tuple[str, bool, str]] = []
    acct = bridge.account()
    rows.append((
        "Konto-Login",
        profile.expected_login is None or acct.login == profile.expected_login,
        f"verbunden {acct.login}, Profil erwartet {profile.expected_login}",
    ))
    rows.append((
        "Waehrung",
        acct.currency == profile.expected_currency,
        f"{acct.currency} (erwartet {profile.expected_currency})",
    ))
    ti = mt5.terminal_info() if mt5 is not None else None
    rows.append((
        "Algo-Trading aktiv",
        bool(ti and ti.trade_allowed),
        "an" if (ti and ti.trade_allowed) else "AUS -- im Terminal einschalten",
    ))
    risk_amount = acct.balance * risk_per_trade_from_paper_config()
    for spec in markets_from_paper_config():
        try:
            info = bridge.symbol_info(spec.name)
            term = bridge.terminal_symbol(spec.name)
            tick = mt5.symbol_info_tick(term) if mt5 is not None else None
            price = float(tick.ask or tick.bid) if tick else 0.0
            sized = size_order(
                "BUY", price, spec.stop_loss_pct, spec.take_profit_pct, info, risk_amount
            )
            ok = sized is not None and price > 0.0
            detail = f"-> {term}, vol {sized.volume}" if sized else "NICHT sizable (< min-Lot!)"
            rows.append((spec.name, ok, detail))
        except Exception as exc:  # noqa: BLE001 -- report per-market failure, keep checking the rest
            rows.append((spec.name, False, f"Fehler: {exc}"))
    return rows, risk_amount


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="GO/NO-GO pre-flight before going live.")
    parser.add_argument("--account", default="ttp", choices=sorted(ACCOUNTS))
    args = parser.parse_args(argv)
    profile = get_account(args.account)

    bridge = Mt5Bridge()
    bridge.connect(path=profile.terminal_path)
    try:
        rows, risk_amount = _checks(bridge, args.account)
    finally:
        bridge.shutdown()

    print(f"\n  PRE-FLIGHT '{profile.name}'  (Risiko {risk_amount:,.0f} pro Trade)\n")
    for name, ok, detail in rows:
        print(f"    [{'GO' if ok else 'NO'}]  {name:20s} {detail}")
    verdict = all(ok for _, ok, _ in rows)
    msg = (
        "==> GO: alles bereit fuer --mode execute"
        if verdict
        else "==> NO-GO: erst die [NO]-Punkte fixen, dann erneut"
    )
    print(f"\n  {msg}\n")


if __name__ == "__main__":
    main()
