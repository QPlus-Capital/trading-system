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

    uv run python -m research.stages.portfolio --run reports/research/run_X --risk flat:0.15
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from core.broker import standard_broker, swap_r_per_trade

from research.engine.config import load_config_module
from research.portfolio.curves import load_daily_close, load_daily_low_high
from research.portfolio.risk import (
    AccountProfile,
    FlatRisk,
    KellyRisk,
    RiskPolicy,
    ThrottleRisk,
    evaluate_policy,
    tail_cap,
)
from research.portfolio.stress import worst_day_r
from research.portfolio.tail import full_history_tail_cap, traded_stop_loss_pct
from research.portfolio.trades import make_extract_fn
from research.stages import _runbook as rb


def parse_risk(spec: str) -> RiskPolicy:
    """``flat:0.15`` | ``throttle:0.15`` | ``kelly:0.05`` (risk-constrained Kelly, beta)."""
    kind, _, rest = spec.partition(":")
    kind = kind.strip().lower()
    if kind == "flat":
        return FlatRisk(float(rest or "0.15"))
    if kind == "throttle":
        return ThrottleRisk(floor_pct=float((rest or "0.15").split(",")[0]))
    if kind == "kelly":
        return KellyRisk(beta=float(rest or "0.05"))
    raise SystemExit(f"unknown risk policy '{spec}' (use flat:0.15, throttle:0.15 or kelly:0.05)")


def live_fixed_stops(config: Path) -> dict[str, dict[str, float]]:
    """Per-market fixed SL/TP from a live config -- the stops we actually deploy and hold constant.

    ``config`` is a live config module with ``MARKETS = [(factory, csv, leverage, sl, tp), ...]``.
    """
    module = load_config_module(config)
    stops: dict[str, dict[str, float]] = {}
    for factory, _csv, _lev, sl, tp in module.MARKETS:
        name = str(factory().raw_symbol)
        stops[name] = {"stop_loss_pct": float(sl), "take_profit_pct": float(tp)}
    return stops


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Stage 3 (PORTFOLIO): combine + size.")
    parser.add_argument("--run", type=Path, required=True, help="the framework run directory")
    parser.add_argument(
        "--config", type=Path, default=None,
        help="study config (default: the one Stage 1 recorded in the run)"
    )
    parser.add_argument("--risk", default="flat:0.15", help="policy: flat:PCT or throttle:FLOORPCT")
    parser.add_argument(
        "--stress-mult", type=float, default=1.5, help="tail headroom over the worst day (def 1.5)"
    )
    parser.add_argument(
        "--tail", choices=("full", "holdout"), default="full",
        help="measure the risk ceiling on the FULL history (all crises) or just the holdout",
    )
    parser.add_argument(
        "--fixed", type=Path, default=None,
        help="trade the FIXED per-market SL/TP from this live config every window (no per-window "
        "stop re-optimisation) -- validates the config we deploy, whose gentle tail is tradeable",
    )
    args = parser.parse_args(argv)

    run = rb.RunDir.open(args.run)
    rb.banner(3, "PORTFOLIO - Groesse & Risiko", run)
    run.require("selection.json", "select")
    sel = run.load_json("selection.json")
    policy = parse_risk(args.risk)
    cfg = load_config_module(run.study_config(args.config))  # #3: the run's own config
    # The account/prop-firm rules come from config; the code never assumes a balance or a limit.
    account: AccountProfile = getattr(cfg, "ACCOUNT", AccountProfile())
    specs = {str(f().raw_symbol): (f, csv, lev) for f, csv, lev in cfg.INSTRUMENTS}

    # Fixed mode: trade the deployed per-market stops, restricted to the markets that have them.
    fixed_stops = live_fixed_stops(args.fixed) if args.fixed else None
    universe = [m for m in sel["instruments"] if m in specs]
    if fixed_stops is not None:
        dropped = [m for m in universe if m not in fixed_stops]
        universe = [m for m in universe if m in fixed_stops]
        if dropped:
            print(f"\n  [fixed] ohne feste Stops im Live-Config, ausgelassen: {', '.join(dropped)}")

    extract_fn = make_extract_fn(
        specs,
        test_months=int(getattr(cfg, "TEST_MONTHS", 6)),
        param_grid=cfg.PARAM_GRID,
        holdout_months=int(getattr(cfg, "HOLDOUT_MONTHS", 0)),
        phase="holdout",
        embargo_days=int(getattr(cfg, "EMBARGO_DAYS", 0)),
        start_balance=account.start_balance,  # size the backtests against the REAL account
        risk_per_trade_pct=account.base_risk_frac * 100.0,
        fixed_stops=fixed_stops,
    )
    overrides = cfg.VARIATIONS[sel["variation"]]

    mode_txt = "FESTE Live-Stops" if fixed_stops is not None else "re-optimiert pro Fenster"
    print(
        f"\n  Extrahiere Holdout-Trades ({mode_txt}): {sel['variation']} @ "
        f"{sel['train_months']}m ueber {len(universe)} Maerkte ..."
    )
    # #22: an empty universe or an empty stream is a RESULT (nothing survived selection), not a
    # crash. Fail closed with the reason instead of letting concat/mode/min raise deep inside.
    if not universe:
        raise SystemExit(
            "\n  ABBRUCH: kein Markt hat die Auswahl ueberlebt.\n"
            "  Das ist ein Ergebnis, kein Fehler: es gibt nichts zu handeln."
        )
    frames = [extract_fn(m, overrides, int(sel["train_months"])) for m in universe]
    trades = pd.concat(frames, ignore_index=True)
    if trades.empty:
        raise SystemExit(
            f"\n  ABBRUCH: {len(universe)} Maerkte ausgewaehlt, aber im Holdout kein einziger"
            "\n  Trade. Ohne Trades gibt es keine belastbare Aussage - nichts zu handeln."
        )
    # Carry the real TTP swap as a SEPARATE column (not netted into r): a realized cost booked at
    # close, so downstream returns/drawdown net it while the mark-to-market stays on gross price R.
    broker = standard_broker()
    trades["swap_r"] = 0.0
    for market, grp in trades.groupby("market"):
        if (spec := broker.swap_spec(str(market))) is not None:
            trades.loc[grp.index, "swap_r"] = swap_r_per_trade(grp, spec)
    trades.to_csv(run.file("portfolio_trades.csv"), index=False)

    daily_close = {m: load_daily_close(str(specs[m][1])) for m in universe}
    # #15: day extremes for the intraday daily-limit check
    daily_hl = {m: load_daily_low_high(str(specs[m][1])) for m in universe}

    # The crisis sets only the CEILING: the largest risk whose stressed worst-day gap still fits
    # the hard daily limit. Every policy is capped by it; within it a policy may size freely.
    # Measured on the FULL history by default -- a ceiling fit to a benign holdout is the trap.
    if args.tail == "full":
        # Measure the ceiling at the stop actually traded: R = move/stop, so a tail at a different
        # stop distance is simply the wrong number. In fixed mode that is each market's own
        # fixed stop; otherwise it is the stop the walk-forward optimiser landed on most often.
        traded_sl = traded_stop_loss_pct(trades)
        sl_note = "feste Live-Stops je Markt" if fixed_stops is not None else f"SL {traded_sl}%"
        print(f"\n  Messe Tail-Decke auf der VOLLEN Historie ({sl_note}, wie gehandelt) ...")
        worst_day, cap, rck_stream = full_history_tail_cap(
            specs, universe, overrides, cfg.PARAM_GRID, account,
            broker=broker, stress_mult=args.stress_mult,
            stop_loss_pct=traded_sl, fixed_stops=fixed_stops,
        )
        source = f"volle Historie @ {sl_note}"
    else:
        worst_day = worst_day_r(trades)
        cap = tail_cap(trades, account, stress_mult=args.stress_mult)
        rck_stream = trades  # holdout mode: no full-history stream, fall back to the holdout
        source = "nur Holdout - eine schlimmere Krise wuerde die Decke senken"
    print(f"\n  Tail-Decke: schlechtester Tag {worst_day:.2f}R x {args.stress_mult} Stress "
          f"-> {cap * 100:.3f}% pro Trade  [{source}]")

    # Persist the full-history stream (already computed for the tail) so the verdict fact sheet can
    # report full-history vs holdout side by side without re-running the backtests.
    rck_stream.to_csv(run.file("full_history_trades.csv"), index=False)

    # Risk-constrained Kelly derives the growth-optimal flat fraction from the trade distribution
    # under the "P(ever hit the 6% trailing wall) <= beta" bound; the single-day gap tail still caps
    # it. Flat/Throttle instead start from the requested percent. All are then compared at one base.
    kelly_info: dict[str, float | str] = {}
    if isinstance(policy, KellyRisk):
        phi = policy.fraction(rck_stream, account)  # drawdown bound on the ALL-crises stream
        bound = "RCK" if phi <= cap else "Tail-Cap"
        base_pct = min(phi, cap) * 100.0
        kelly_info = {"kelly_beta": policy.beta, "rck_pct": round(phi * 100, 4), "bound": bound}
        alpha = 1 - account.trailing_hard
        print(
            f"\n  Risk-constrained Kelly (beta={policy.beta}, Wand alpha={alpha}): "
            f"phi={phi * 100:.3f}% -> gebunden durch {bound} -> {base_pct:.3f}% pro Trade"
        )
    else:
        base_pct = policy.pct if isinstance(policy, FlatRisk) else policy.floor_pct

    # Same base for both policies -> apples to apples: what does going dynamic actually buy?
    results = {
        "flat": evaluate_policy(
            trades, daily_close, account, FlatRisk(base_pct), cap, daily_low_high=daily_hl
        ),
        "throttle": evaluate_policy(
            trades, daily_close, account, ThrottleRisk(base_pct), cap, daily_low_high=daily_hl
        ),
    }
    chosen_label = "throttle" if isinstance(policy, ThrottleRisk) else "flat"  # Kelly sizes flat
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
            # Provenance (#11): which per-market stops these numbers were produced with. Without a
            # frozen config the stops were re-optimised per window, so the result is EXPLORATORY --
            # the verdict refuses to call such a run deployable.
            "fixed_config": str(args.fixed) if args.fixed else None,
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
            **kelly_info,
        },
    )

    nxt = rb.cmd("verdict", "--run", str(run.path))
    rb.next_step(nxt, "Urteil & vollstaendiger Report (Equity-Kurve, Sharpe, Diagramme)")


if __name__ == "__main__":
    main()
