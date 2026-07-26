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
import json
import math
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

import pandas as pd

from research.engine.config import load_config_module
from research.portfolio import factsheet, html_report
from research.portfolio.curves import DAY_NS, load_daily_close, load_h4_prices
from research.portfolio.resample import DEFAULT_SEED
from research.portfolio.risk import (
    AccountProfile,
    FlatRisk,
    ThrottleRisk,
    evaluate_policy,
)
from research.portfolio.scenarios import (
    read_loss_day_scenarios,
    summarize_scenario_bootstrap,
)
from research.portfolio.stats import edge_stats, risk_stats
from research.stages import _runbook as rb
from research.stages import lineage
from research.stages.edge import PBO_MAX

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


def selection_is_gated(selection: Mapping[str, Any]) -> bool:
    """Re-check every cumulative selection gate before a deployable verdict."""
    gates = selection.get("gates")
    return bool(
        isinstance(gates, Mapping)
        and gates.get("automatic_eligible")
        and gates.get("spa_ok")
        and gates.get("romano_wolf_ok")
        and gates.get("mcs_ok")
        and gates.get("complete")
        and gates.get("positive_market_ok")
        and gates.get("return_drawdown_ok")
        and not selection.get("forced")
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Stage 4 (VERDICT): accept/reject + full report.")
    parser.add_argument("--run", type=Path, required=True, help="the framework run directory")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="study config (default: the one Stage 1 recorded in the run)",
    )
    parser.add_argument(
        "--allow-legacy-unverified",
        action="store_true",
        help="read a run that predates artifact hashing. Such a run can be inspected but can "
        "NEVER produce a deployable PASS -- its inputs cannot be confirmed.",
    )
    args = parser.parse_args(argv)

    run = rb.RunDir.open(args.run, allow_legacy=bool(args.allow_legacy_unverified))
    rb.banner(4, "VERDICT - Urteil & Report", run)
    # #31: verify the WHOLE upstream chain before computing anything. A lineage failure is a
    # property of the run, not of the work this stage is about to do, so it must surface in the
    # first second rather than after a fact sheet has been built on artifacts that do not belong
    # together.
    run.require("run_manifest.json", "edge")  # the config anchor
    sel_path = run.require("selection.json", "select")
    has_pbo = run.file("overfitting.json").exists()
    of_path = run.require("overfitting.json", "edge") if has_pbo else None
    spec = json.loads(run.require("portfolio.json", "portfolio").read_text(encoding="utf-8"))
    trades = pd.read_csv(run.require("portfolio_trades.csv", "portfolio"))
    scenario_path = (
        run.file("loss_day_scenarios.csv")
        if run.allow_legacy
        else run.require("loss_day_scenarios.csv", "portfolio")
    )
    # A run predating this artifact must stay inspectable: legacy mode exists to READ old runs,
    # and demanding a file they never had would lock out the very workflow it is for. It stays
    # mandatory for a real run, where its absence means the stage did not finish.
    fh_path = (
        run.file("full_history_trades.csv")
        if run.allow_legacy
        else run.require("full_history_trades.csv", "portfolio")
    )
    full_trades = pd.read_csv(fh_path) if fh_path.is_file() else None
    cfg = load_config_module(run.study_config(args.config))  # #3: the run's own config
    # Snapshot the external inputs BEFORE the market data is loaded and the verdict computed, so
    # the manifest records the content these numbers came from. Evaluating this at publication
    # time would let a file edited mid-stage be recorded as the input to results produced from
    # its predecessor, and the writer's drift check would see a perfectly stable snapshot.
    inputs = lineage.external_inputs(run.study_config(args.config), cfg)
    account: AccountProfile = getattr(cfg, "ACCOUNT", AccountProfile())
    specs = {str(f().raw_symbol): (f, csv, lev) for f, csv, lev in cfg.INSTRUMENTS}
    universe = [m for m in spec["instruments"] if m in specs]
    daily_close = {m: load_daily_close(str(specs[m][1])) for m in universe}
    h4_prices = {m: load_h4_prices(str(specs[m][1])) for m in universe}

    # Re-run the chosen sizing (cheap: a daily sim, not backtests) to recover each trade's PnL AT
    # the size it was given -- so the metrics are honest under a dynamic policy too. Reconstruct it
    # from the stored result, not the CLI string: flat and Kelly were both sized FLAT at the chosen
    # ceiling (Kelly derived that ceiling upstream), throttle ran from its floor up to it.
    cap = float(spec["tail_cap_pct"]) / 100.0
    if str(spec["risk_policy"]).startswith("throttle"):
        policy: FlatRisk | ThrottleRisk = ThrottleRisk(floor_pct=float(spec["floor_pct"]))
    else:
        policy = FlatRisk(float(spec["ceiling_pct"]))
    result = evaluate_policy(trades, daily_close, account, policy, cap, h4_prices=h4_prices)
    sized_pnl = result.trade_pnl  # NET -- what the edge stats and Monte-Carlo should see
    diagnostics = result.daily_diagnostics
    equity = pd.Series(
        diagnostics.close_equity,
        index=pd.to_datetime(diagnostics.days * DAY_NS),
    )
    stats = {**edge_stats(sized_pnl), **risk_stats(equity, start_balance=account.start_balance)}
    # The drawdown the GATE judged, not one recomputed from daily closes: with intraday marks a
    # day can dip below the floor and recover by the close, so a close-based figure would be
    # published beside a breach it does not show. One number, one path.
    stats["max_drawdown"] = result.max_drawdown_pct / 100.0

    if not scenario_path.is_file():
        raise SystemExit(
            "loss_day_scenarios.csv fehlt: Stage 3 mit dem aktuellen Code erneut ausfuehren."
        )
    scenarios = read_loss_day_scenarios(scenario_path)
    bootstrap = summarize_scenario_bootstrap(scenarios)
    prob_profit = float(bootstrap.prob_profit)
    # #11: a deployable verdict must describe the stops we actually TRADE. Without --fixed the
    # portfolio stage re-optimises stops inside every window, which passes on adaptive stops the
    # live account does not have -- such a run is exploratory, never a go-live decision.
    fixed_config = spec.get("fixed_config")
    # #2: the verdict must TEST the selection gates, not assume selection applied them. A forced
    # (--variation) pick bypassed them by definition and can never be a deployable PASS.
    sel_manifest = json.loads(sel_path.read_text(encoding="utf-8"))
    gates = sel_manifest.get("gates", {})
    gated_pick = selection_is_gated(sel_manifest)
    dsr_txt = "n/a" if gates.get("dsr") is None else f"{gates['dsr']:.2f}"
    pbo: float | None = None
    if of_path is not None:
        try:
            overfitting = json.loads(of_path.read_text(encoding="utf-8"))
            raw_pbo = overfitting.get("pbo") if isinstance(overfitting, Mapping) else None
            if not isinstance(raw_pbo, bool) and raw_pbo is not None:
                parsed_pbo = float(raw_pbo)
                pbo = parsed_pbo if math.isfinite(parsed_pbo) else None
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
            pass
    pbo_txt = "n/a" if pbo is None else f"{pbo:.2f}"
    # A contaminated holdout is IN-SAMPLE for the deployed config, so its numbers cannot support a
    # deployable verdict. Printing that warning next to "PASS - handelbar" contradicted itself.
    contaminated = bool(getattr(cfg, "HOLDOUT_CONTAMINATED", False))
    # #31: a PASS is a live-money decision, so it may only rest on numbers whose whole chain of
    # production is content-verified. A legacy run stays readable and can never clear this.
    try:
        run.assert_deployable(ignore="verdict")
        lineage_ok, lineage_txt = True, "Herkunft aller Stufen inhaltlich verifiziert"
    except SystemExit as exc:
        lineage_ok = False
        lineage_txt = f"Herkunft NICHT verifiziert ({str(exc).splitlines()[0]})"
    checks = [
        (lineage_ok, lineage_txt),
        (not contaminated, "Holdout ist echtes Out-of-Sample (nicht kontaminiert)"),
        (
            gated_pick,
            "Auswahl gegated (SPA + Romano-Wolf + MCS + Struktur, nicht erzwungen)",
        ),
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
    dsr_diag = "ok" if gates.get("dsr_diagnostic_ok") else "nicht bestanden/nicht verfuegbar"
    pbo_diag = "ok" if gates.get("pbo_diagnostic_ok") else "nicht bestanden/nicht verfuegbar"
    print(f"    DIAGNOSTIK: DSR {dsr_txt} gegen 0.90: {dsr_diag} (kein Gate)")
    print(f"    DIAGNOSTIK: PBO {pbo_txt} gegen {PBO_MAX:.2f}: {pbo_diag} (kein Gate)")
    if fixed_config is None:
        print(
            "\n  EXPLORATIV: ohne --fixed wurden die Stops pro Fenster neu optimiert. Diese Zahlen"
            "\n  beschreiben NICHT die Live-Config und taugen nicht als Go-Live-Entscheidung."
        )
    # #12: never let a contaminated holdout be read as clean out-of-sample evidence.
    if contaminated:
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

    # #31: the verdict and the report describe the same evaluation and are published together --
    # a report.html left beside a verdict.json from a different run is exactly the mix-up the
    # staged write prevents.
    with run.stage(
        "verdict",
        argv={"run": str(run.path), "config": str(args.config or "")},
        seeds={"loss_day_bootstrap": DEFAULT_SEED},
        inputs=inputs,
        semantics={"passed": passed, "variation": spec["variation"], "deployable": lineage_ok},
    ) as st:
        st.save_json("path_bootstrap.json", bootstrap.to_json())
        st.save_json(
            "verdict.json",
            {
                "passed": passed,
                "reasons": [f"{'PASS' if ok else 'FAIL'}: {m}" for ok, m in checks],
                "mc_prob_profit": prob_profit,
                "stats": {k: stats[k] for k, _, _ in _STAT_ROWS},
                "path": {
                    "max_drawdown_pct": result.max_drawdown_pct,
                    "max_daily_loss_pct": result.max_daily_loss_pct,
                    "daily_breach_days": int(diagnostics.daily_breach.sum()),
                    "trailing_breach_days": int(diagnostics.trailing_breach.sum()),
                    "assumption": diagnostics.h4_upper_bound,
                },
            },
        )
        # Fact sheet: full history vs holdout, flat vs compound -- the consistent end-of-run
        # report. Sized at the chosen ceiling; the stream was cached by the portfolio stage.
        if full_trades is not None:
            fs_account = replace(account, base_risk_frac=float(spec["ceiling_pct"]) / 100.0)
            fs = factsheet.compute_factsheet(
                full_trades,
                trades,
                daily_close,
                h4_prices,
                fs_account,
                holdout_flat=result,
            )
            print(factsheet.render_terminal(fs))
            html_report.render(fs, str(spec["variation"]), run.path.name, st.file("report.html"))
    if full_trades is None:
        print("\n  (full_history_trades.csv fehlt - Legacy-Lauf, kein Faktsheet)")
    else:
        print(f"\n  Faktsheet-Report (im Browser oeffnen): {run.file('report.html')}")
    rb.finished()


if __name__ == "__main__":
    main()
