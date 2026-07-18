# Strategy hypothesis — RSI / Williams %R / Bollinger reversal (4H)

Stage 0 of the [methodology](../methodology.md): the economic rationale **stated before testing**,
and the fixed trial universe. This is the honest denominator for the Deflated Sharpe Ratio — any
variation or parameter tested that is not listed here must be added to the trial count.

## Economic hypothesis

**Claim.** On 4-hour bars, liquid FX pairs and equity-index CFDs exhibit **short-term mean
reversion** after stretched moves: a thrust that pushes price to a statistical extreme (a Bollinger
band edge) while momentum is exhausted (Williams %R oversold/overbought) and RSI confirms tends to
*revert* rather than continue, over the next few bars.

**Why it should persist.**
- **Liquidity provision / overreaction.** Short-horizon reversal is one of the most robust,
  longest-documented anomalies (Lehmann 1990; Jegadeesh 1990): liquidity demanders push price past
  fair value; providers are compensated as it snaps back. This is a *structural* compensation for
  absorbing flow, not a fragile calendar/seasonal quirk.
- **The confirmations encode "stretched AND exhausted."** Bollinger = distance from the local mean;
  Williams %R = position in the recent range (momentum exhaustion); RSI = a second momentum filter.
  Requiring several agreeing signals targets the *overreaction* case, not mere noise.
- **4H horizon.** Long enough to avoid microstructure noise and be tradeable net of spread/commission,
  short enough that the reversal has not yet decayed.

**Why it could fail (the honest priors).**
- Reversal edges **shrink in strong trends** and are **regime-dependent** — they pay more in
  high-volatility regimes (more overreaction to fade) and less in calm, trending ones. Expect the
  per-year return to vary with volatility, not to be constant.
- The edge is **crowded**; net-of-cost margins are thin, so realistic costs are non-negotiable.
- **Gap risk is the tail:** a reversal position is short volatility on a gap through its stop. This
  is a real, unhedgeable tail that the sizing/tail-cap step must respect — not a backtest artifact.

**Direction of the bet.** Long on a buy signal, short on a sell signal (reversal), flat between.
`long_only` is a defensive variant (skip shorts) for markets/regimes where shorting the index is
unattractive.

## Fixed trial universe (the DSR denominator)

Anything outside this list is a new trial and must be counted.

**Structural variations** (12 — the confirmation-filter ablation + a few parameter variants):
`baseline`, `no_bb`, `no_wpr`, `no_rsi`, `no_bb_wpr`, `no_bb_rsi`, `no_wpr_rsi`, `no_confirms`,
`long_only`, `ema20`, `bb30`, `wpr21`. The first eight are the full 2³ factorial of the three
confirmation filters — a *pre-registered* ablation, so removing a filter that does not improve the
risk-adjusted OOS result is a legitimate simplification, not a mined variant.

**Per-window parameter grid** (swept inside the walk-forward, not hand-picked):
`stop_loss_pct ∈ {0.2, 0.3, 0.5, 1.0, 1.5, 2.0}`, `take_profit_pct ∈ {1.0, 2.0, 3.0, 4.0}`
→ 24 combinations. (`buy_rsi_threshold` is inert on 4H data and dropped.)

**Training lengths:** {18, 24, 36} months. **Universe:** the 12 configured instruments.

**Trial budget** = variations × train-lengths × param-combos = **12 × 3 × 24 = 864** effective
trials — the number the DSR deflates by (see `foundation/trial_budget.py`).

## What is frozen vs. free

- **Frozen:** the signal logic and its indicator periods (mirror the Pine source), the confirmation
  structure above, the cost model, the walk-forward scheme (purged, embargoed, non-overlapping).
- **Free (chosen inside the walk-forward):** stop/target per window from the grid.
- **Chosen in the portfolio/verdict stages and frozen into the live config:** the
  risk-aversion parameters (α, β) and the per-market deployed stop.
  These do not change *which* entry signals fire — but they are still strategy parameters, not
  free choices: the stop determines every **exit**, hence every R and the entire equity path.
  Fitting them on a window that overlaps the reserved holdout makes that holdout in-sample for the
  deployed config (see `HOLDOUT_CONTAMINATED` in `research/config/robustness.py`). The holdout
  numbers are therefore an optimistic estimate; the clean out-of-sample evidence is the live track
  record from the freeze date onward.
