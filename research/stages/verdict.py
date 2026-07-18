"""Stage 4 — VERDICT: trade yes/no, plus the consistent end-of-run fact sheet.

Reads the cached holdout + full-history trade streams from Stage 3 (no slow re-extraction) and
produces: the accept/reject gate (positive return, within the drawdown ceiling, survives a
stressed tail, Monte-Carlo profit probability), the tradeable portfolio spec, and the fact sheet
(:mod:`research.portfolio.factsheet`) -- the metrics matrix comparing the full history vs
the holdout and flat vs compound sizing, per-market and per-year contributions (flat % lens), and
regime robustness. It is printed as a terminal summary and written as a self-contained
``report.html``.

Everything is measured in R (sizing-invariant); only annual return and max drawdown split into
flat vs compound, so the numbers never mix the two sizings.

Usage::

    uv run python -m research.stages.verdict --run reports/research/run_XXXX
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

import pandas as pd

from research.engine.config import load_config_module
from research.engine.montecarlo import monte_carlo_paths, summarize
from research.portfolio import factsheet, html_report
from research.portfolio.curves import load_daily_close, load_daily_low_high, to_day
from research.portfolio.risk import (
    AccountProfile,
    FlatRisk,
    ThrottleRisk,
    evaluate_policy,
)
from research.portfolio.stats import daily_equity, edge_stats, risk_stats
from research.stages import _runbook as rb

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
        "--config", type=Path, default=Path("research/config/robustness.py"), help="study config"
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
    # #15: day extremes for the intraday daily-limit check
    daily_hl = {m: load_daily_low_high(str(specs[m][1])) for m in universe}

    # Re-run the chosen sizing (cheap: a daily sim, not backtests) to recover each trade's PnL AT
    # the size it was given -- so the metrics are honest under a dynamic policy too. Reconstruct it
    # from the stored result, not the CLI string: flat and Kelly were both sized FLAT at the chosen
    # ceiling (Kelly derived that ceiling upstream), throttle ran from its floor up to it.
    cap = float(spec["tail_cap_pct"]) / 100.0
    if str(spec["risk_policy"]).startswith("throttle"):
        policy: FlatRisk | ThrottleRisk = ThrottleRisk(floor_pct=float(spec["floor_pct"]))
    else:
        policy = FlatRisk(float(spec["ceiling_pct"]))
    result = evaluate_policy(trades, daily_close, account, policy, cap, daily_low_high=daily_hl)
    sized_pnl = result.trade_pnl
    equity = daily_equity(trades, sized_pnl, daily_close, start_balance=account.start_balance)
    stats = {**edge_stats(sized_pnl), **risk_stats(equity, start_balance=account.start_balance)}

    # #16: resample whole trading days, not single trades -- our correlated markets lose together
    # on a macro gap, and breaking those bundles apart understates the tail.
    mc_days = [to_day(x) for x in trades["ts_closed"]]
    paths = monte_carlo_paths(
        sized_pnl.tolist(), n_sims=1000, start_equity=account.start_balance, days=mc_days
    )
    prob_profit = float(summarize(paths, account.start_balance)["prob_profit"])
    # #11: a deployable verdict must describe the stops we actually TRADE. Without --fixed the
    # portfolio stage re-optimises stops inside every window, which passes on adaptive stops the
    # live account does not have -- such a run is exploratory, never a go-live decision.
    fixed_config = spec.get("fixed_config")
    # #2: the verdict must TEST the selection gates, not assume selection applied them. A forced
    # (--variation) pick bypassed them by definition and can never be a deployable PASS.
    sel_manifest = run.load_json("selection.json") if run.file("selection.json").exists() else {}
    gates = sel_manifest.get("gates", {})
    gated_pick = (
        bool(gates.get("eligible")) and bool(gates.get("dsr_ok")) and not sel_manifest.get("forced")
    )
    dsr_txt = "n/a" if gates.get("dsr") is None else f"{gates['dsr']:.2f}"
    checks = [
        (gated_pick, f"Auswahl gegated (eligible + DSR {dsr_txt}, nicht erzwungen)"),
        (fixed_config is not None, "gegen die eingefrorene Live-Config geprueft (--fixed)"),
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
    if fixed_config is None:
        print(
            "\n  EXPLORATIV: ohne --fixed wurden die Stops pro Fenster neu optimiert. Diese Zahlen"
            "\n  beschreiben NICHT die Live-Config und taugen nicht als Go-Live-Entscheidung."
        )
    # #12: never let a contaminated holdout be read as clean out-of-sample evidence.
    if bool(getattr(cfg, "HOLDOUT_CONTAMINATED", False)):
        freeze = getattr(cfg, "DEPLOY_FREEZE_DATE", "?")
        print(
            "\n  HOLDOUT KONTAMINIERT: Deploy-Entscheidungen (Stops, Universum, Risiko) wurden"
            "\n  getroffen, nachdem der Holdout eingesehen wurde -- er ist fuer diese Config"
            "\n  IN-SAMPLE. Die Zahlen oben sind eine optimistische Schaetzung, KEIN Out-of-Sample."
            f"\n  Sauberer OOS-Nachweis ist der Live-Track-Record ab {freeze}."
        )
        for trial in getattr(cfg, "MANUAL_TRIALS", ()):
            print(f"    - manuelle Entscheidung (zaehlt als Trial): {trial}")

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
