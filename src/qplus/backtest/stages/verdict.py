"""Stage 4 — VERDICT: trade yes/no, plus the consistent end-of-run fact sheet.

Reads the cached holdout + full-history trade streams from Stage 3 (no slow re-extraction) and
produces: the accept/reject gate (positive return, within the drawdown ceiling, survives a
stressed tail, Monte-Carlo profit probability), the tradeable portfolio spec, and the fact sheet
(:mod:`qplus.backtest.portfolio.factsheet`) -- the metrics matrix comparing the full history vs
the holdout and flat vs compound sizing, per-market and per-year contributions (flat % lens), and
regime robustness. It is printed as a terminal summary and written as a self-contained
``report.html``.

Everything is measured in R (sizing-invariant); only annual return and max drawdown split into
flat vs compound, so the numbers never mix the two sizings.

Usage::

    uv run python -m qplus.backtest.stages.verdict --run reports/framework/run_XXXX
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

import pandas as pd

from qplus.backtest.config import load_config_module
from qplus.backtest.foundation.montecarlo import monte_carlo_paths, summarize
from qplus.backtest.portfolio import factsheet, html_report
from qplus.backtest.portfolio.curves import load_daily_close
from qplus.backtest.portfolio.equity_report import daily_equity, edge_stats, risk_stats
from qplus.backtest.portfolio.risk import (
    AccountProfile,
    FlatRisk,
    ThrottleRisk,
    evaluate_policy,
)
from qplus.backtest.stages import _runbook as rb

_STAT_ROWS = [
    ("trades", "Trades", "{:,.0f}"),
    ("hit_rate", "Trefferquote", "{:.1%}"),
    ("profit_factor", "Profit-Faktor", "{:.2f}"),
    ("payoff", "Payoff (Chance/Risiko)", "{:.2f} : 1"),
    ("expectancy", "Erwartung / Trade", "{:,.0f} EUR"),
    ("total_return", "Gesamtrendite (Holdout)", "{:+.1%}"),
    ("annual_return", "Rendite p.a.", "{:+.1%}"),
    ("sharpe", "Sharpe (annualisiert)", "{:.2f}"),
    ("max_drawdown", "Max Drawdown", "{:.1%}"),
]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Stage 4 (VERDICT): accept/reject + full report.")
    parser.add_argument("--run", type=Path, required=True, help="the framework run directory")
    parser.add_argument(
        "--config", type=Path, default=Path("config/study/robustness.py"), help="study config"
    )
    args = parser.parse_args(argv)

    run = rb.RunDir.open(args.run)
    rb.banner(4, "VERDICT - Urteil & Report", run)
    run.require("portfolio.json", "portfolio")
    spec = run.load_json("portfolio.json")
    trades = pd.read_csv(run.require("portfolio_trades.csv", "portfolio"))
    cfg = load_config_module(args.config)
    account: AccountProfile = getattr(cfg, "ACCOUNT", AccountProfile())
    specs = {str(f().raw_symbol): (f, csv, lev) for f, csv, lev in cfg.INSTRUMENTS}
    universe = [m for m in spec["instruments"] if m in specs]
    daily_close = {m: load_daily_close(str(specs[m][1])) for m in universe}

    # Re-run the chosen sizing (cheap: a daily sim, not backtests) to recover each trade's PnL AT
    # the size it was given -- so the metrics are honest under a dynamic policy too. Reconstruct it
    # from the stored result, not the CLI string: flat and Kelly were both sized FLAT at the chosen
    # ceiling (Kelly derived that ceiling upstream), throttle ran from its floor up to it.
    cap = float(spec["tail_cap_pct"]) / 100.0
    if str(spec["risk_policy"]).startswith("throttle"):
        policy: FlatRisk | ThrottleRisk = ThrottleRisk(floor_pct=float(spec["floor_pct"]))
    else:
        policy = FlatRisk(float(spec["ceiling_pct"]))
    result = evaluate_policy(trades, daily_close, account, policy, cap)
    sized_pnl = result.trade_pnl
    equity = daily_equity(trades, sized_pnl, daily_close, start_balance=account.start_balance)
    stats = {**edge_stats(sized_pnl), **risk_stats(equity, start_balance=account.start_balance)}

    paths = monte_carlo_paths(sized_pnl.tolist(), n_sims=1000, start_equity=account.start_balance)
    prob_profit = float(summarize(paths, account.start_balance)["prob_profit"])
    checks = [
        (result.n_trades >= 30, f"genug Trades ({result.n_trades} >= 30)"),
        (not result.breached, "haelt die harten Konto-Limits (3%/Tag, 6% trailing)"),
        (result.ann_return_pct > 0, f"Rendite positiv ({result.ann_return_pct:+.1f}%/Jahr)"),
        (result.ceiling_pct <= float(spec["tail_cap_pct"]) + 1e-9, "Risiko unter der Tail-Decke"),
        (prob_profit >= 0.6, f"Monte-Carlo Gewinnwahrsch. {prob_profit:.0%} >= 60%"),
    ]
    passed = all(ok for ok, _ in checks)

    print(f"\n  URTEIL: {'PASS - handelbar' if passed else 'FAIL - nicht handelbar'}")
    for ok, msg in checks:
        print(f"    {'PASS' if ok else 'FAIL'}: {msg}")

    risk_txt = (
        f"{result.ceiling_pct:.3f}%/Trade"
        if result.label == "flat"
        else f"{result.floor_pct:.2f}% -> {result.ceiling_pct:.3f}%/Trade (dynamisch)"
    )
    print("\n  PORTFOLIO-SPEC")
    print(f"    Strategie-Variante : {spec['variation']} @ {spec['train_months']}m Training")
    print(f"    Risiko-Police      : {spec['risk_policy']}  ({risk_txt})")
    print(
        f"    Tail-Decke         : {spec['tail_cap_pct']:.3f}%  "
        f"(schlechtester Tag {spec['worst_day_r']:.2f}R x {spec['stress_mult']})"
    )
    print(f"    Maerkte ({len(universe)})       : {', '.join(universe)}")

    run.save_json(
        "verdict.json",
        {
            "passed": passed,
            "reasons": [f"{'PASS' if ok else 'FAIL'}: {m}" for ok, m in checks],
            "mc_prob_profit": prob_profit,
            "stats": {k: stats[k] for k, _, _ in _STAT_ROWS},
        },
    )

    # Fact sheet: full history vs holdout, flat vs compound -- the consistent end-of-run report.
    # Sized at the chosen ceiling; the full-history stream was cached by the portfolio stage.
    fh_path = run.file("full_history_trades.csv")
    if fh_path.exists():
        full_trades = pd.read_csv(fh_path)
        fs_account = replace(account, base_risk_frac=float(spec["ceiling_pct"]) / 100.0)
        fs = factsheet.compute_factsheet(full_trades, trades, daily_close, fs_account)
        print(factsheet.render_terminal(fs))
        html = html_report.render(
            fs, str(spec["variation"]), run.path.name, run.file("report.html")
        )
        print(f"\n  Faktsheet-Report (im Browser oeffnen): {html}")
    else:
        print("\n  (full_history_trades.csv fehlt - Portfolio-Stufe neu laufen fuer den Faktsheet)")
    rb.finished()


if __name__ == "__main__":
    main()
