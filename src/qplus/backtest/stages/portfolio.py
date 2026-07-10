"""Stage 3 — PORTFOLIO: combine the universe into one account and size it under a risk policy.

Extracts the reserved out-of-sample (holdout) trade stream for the selected structure across the
chosen markets, combines it into one account, and reports the HONEST flat return / drawdown at the
chosen risk. The risk policy is passed in (``--risk``), never hardcoded:

* ``flat:0.15``     -- a constant 0.15% of the start balance per trade;
* ``throttle:0.15`` -- dynamic between a 0.15% floor and the tail-cap ceiling.

Both are always evaluated side by side (same floor) so the cost of staying flat -- or the gain of
going dynamic -- is read straight off the table. The tail cap (the crisis-derived ceiling no policy
may cross) is computed from the stream's own worst day; the return is booked from R-multiples, so
nothing compounds.

Saves the trade stream + the feasibility so Stage 4 can build the full report without re-running
the slow extraction. This stage is the heavy one (walk-forward backtests over the holdout).

Usage::

    uv run python -m qplus.backtest.stages.portfolio --run reports/framework/run_X --risk flat:0.15
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from qplus.backtest.broker import TTP_MARKETS
from qplus.backtest.config import load_config_module
from qplus.backtest.pipeline import make_extract_fn
from qplus.backtest.portfolio.curves import load_daily_close
from qplus.backtest.portfolio.risk import (
    AccountProfile,
    FlatRisk,
    RiskPolicy,
    ThrottleRisk,
    evaluate_policy,
    tail_cap,
)
from qplus.backtest.portfolio.stress import worst_day_r
from qplus.backtest.portfolio.tail import full_history_tail_cap, traded_stop_loss_pct
from qplus.backtest.stages import _runbook as rb


def parse_risk(spec: str) -> RiskPolicy:
    """``flat:0.15`` -> FlatRisk(0.15); ``throttle:0.15`` -> ThrottleRisk(floor 0.15%)."""
    kind, _, rest = spec.partition(":")
    kind = kind.strip().lower()
    if kind == "flat":
        return FlatRisk(float(rest or "0.15"))
    if kind == "throttle":
        return ThrottleRisk(floor_pct=float((rest or "0.15").split(",")[0]))
    raise SystemExit(f"unknown risk policy '{spec}' (use flat:0.15 or throttle:0.15)")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Stage 3 (PORTFOLIO): combine + size.")
    parser.add_argument("--run", type=Path, required=True, help="the framework run directory")
    parser.add_argument(
        "--config", type=Path, default=Path("config/study/robustness.py"), help="study config"
    )
    parser.add_argument("--risk", default="flat:0.15", help="policy: flat:PCT or throttle:FLOORPCT")
    parser.add_argument(
        "--stress-mult", type=float, default=1.5, help="tail headroom over the worst day (def 1.5)"
    )
    parser.add_argument(
        "--tail", choices=("full", "holdout"), default="full",
        help="measure the risk ceiling on the FULL history (all crises) or just the holdout",
    )
    args = parser.parse_args(argv)

    run = rb.RunDir.open(args.run)
    rb.banner(3, "PORTFOLIO - Groesse & Risiko", run)
    run.require("selection.json", "select")
    sel = run.load_json("selection.json")
    policy = parse_risk(args.risk)
    cfg = load_config_module(args.config)
    # The account/prop-firm rules come from config; the code never assumes a balance or a limit.
    account: AccountProfile = getattr(cfg, "ACCOUNT", AccountProfile())
    specs = {str(f().raw_symbol): (f, csv, lev) for f, csv, lev in cfg.INSTRUMENTS}
    universe = [m for m in sel["instruments"] if m in specs]
    extract_fn = make_extract_fn(
        specs,
        test_months=int(getattr(cfg, "TEST_MONTHS", 6)),
        param_grid=cfg.PARAM_GRID,
        holdout_months=int(getattr(cfg, "HOLDOUT_MONTHS", 0)),
        phase="holdout",
        embargo_days=int(getattr(cfg, "EMBARGO_DAYS", 0)),
    )
    overrides = cfg.VARIATIONS[sel["variation"]]

    print(
        f"\n  Extrahiere Holdout-Trades: {sel['variation']} @ {sel['train_months']}m "
        f"ueber {len(universe)} Maerkte ..."
    )
    frames = [extract_fn(m, overrides, int(sel["train_months"])) for m in universe]
    trades = pd.concat(frames, ignore_index=True)
    trades.to_csv(run.file("portfolio_trades.csv"), index=False)

    daily_close = {m: load_daily_close(str(specs[m][1])) for m in universe}

    # The crisis sets only the CEILING: the largest risk whose stressed worst-day gap still fits
    # the hard daily limit. Every policy is capped by it; within it a policy may size freely.
    # Measured on the FULL history by default -- a ceiling fit to a benign holdout is the trap.
    if args.tail == "full":
        # Measure the ceiling at the stop the walk-forward really traded: R = move/stop, so a tail
        # measured at a different stop distance is simply the wrong number.
        traded_sl = traded_stop_loss_pct(trades)
        print(f"\n  Messe Tail-Decke auf der VOLLEN Historie (SL {traded_sl}%, wie gehandelt) ...")
        worst_day, cap = full_history_tail_cap(
            specs, universe, overrides, cfg.PARAM_GRID, account,
            broker=TTP_MARKETS, stress_mult=args.stress_mult, stop_loss_pct=traded_sl,
        )
        source = f"volle Historie @ SL {traded_sl}%"
    else:
        worst_day = worst_day_r(trades)
        cap = tail_cap(trades, account, stress_mult=args.stress_mult)
        source = "nur Holdout - eine schlimmere Krise wuerde die Decke senken"
    print(f"\n  Tail-Decke: schlechtester Tag {worst_day:.2f}R x {args.stress_mult} Stress "
          f"-> {cap * 100:.3f}% pro Trade  [{source}]")

    # Same floor for both policies -> apples to apples: what does going dynamic actually buy?
    base_pct = policy.pct if isinstance(policy, FlatRisk) else policy.floor_pct
    results = {
        "flat": evaluate_policy(trades, daily_close, account, FlatRisk(base_pct), cap),
        "throttle": evaluate_policy(trades, daily_close, account, ThrottleRisk(base_pct), cap),
    }
    chosen_label = "flat" if isinstance(policy, FlatRisk) else "throttle"
    chosen = results[chosen_label]

    print(f"\n  {results['flat'].n_trades} Trades / {chosen.years}J (Holdout, netto)\n")
    print(f"  {'Police':10s} {'Risiko/Trade':>18s} {'Rendite p.a.':>13s} {'EUR/Jahr':>11s} "
          f"{'maxDD':>7s}  Limit")
    for label, res in results.items():
        risk_txt = (f"{res.ceiling_pct:.3f}%" if label == "flat"
                    else f"{res.floor_pct:.2f}% -> {res.ceiling_pct:.3f}%")
        mark = "  <- gewaehlt" if label == chosen_label else ""
        limit = "BREACH" if res.breached else "ok"
        print(f"  {label:10s} {risk_txt:>18s} {res.ann_return_pct:>+12.1f}% "
              f"{res.ann_return_eur:>11,.0f} {res.max_drawdown_pct:>6.2f}% {limit:>6s}{mark}")

    run.save_json(
        "portfolio.json",
        {
            "variation": sel["variation"],
            "train_months": sel["train_months"],
            "instruments": universe,
            "risk_policy": args.risk,
            "stress_mult": args.stress_mult,
            "tail_source": args.tail,
            "tail_cap_pct": round(cap * 100, 4),
            "worst_day_r": round(worst_day, 2),
            "ceiling_pct": chosen.ceiling_pct,
            "floor_pct": chosen.floor_pct,
            "n_trades": chosen.n_trades,
            "years": chosen.years,
            "ann_return_pct": chosen.ann_return_pct,
            "ann_return_eur": chosen.ann_return_eur,
            "total_return_pct": chosen.total_return_pct,
            "max_drawdown_pct": chosen.max_drawdown_pct,
            "breached": chosen.breached,
        },
    )

    nxt = rb.cmd("verdict", "--run", str(run.path))
    rb.next_step(nxt, "Urteil & vollstaendiger Report (Equity-Kurve, Sharpe, Diagramme)")


if __name__ == "__main__":
    main()
