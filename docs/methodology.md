# QPlus Backtesting Methodology

The authoritative, literature-grounded specification for how a strategy is taken from idea to a
tradeable, prop-firm-compliant configuration — *what* is done, *in which order*, and *by which
pass/fail criterion*. It replaces the earlier design blueprint (removed; see git history).

The goal it serves: a framework that tests every sensible variant in the order that makes sense and
ends with a defensible recommendation plus an explicit **return-vs-risk decision**, not a pile of
ad-hoc runs.

---

## 0. Two questions, two literatures

A backtest answers two independent questions. Conflating them is the root of most self-deception.

| | Question | Literature | Governs |
|---|---|---|---|
| **A** | *Is the edge real, or did we overfit?* | López de Prado, Bailey; Harvey & Liu | Stages 0–4 (find & validate) |
| **B** | *How large do we trade it, given a hard loss limit?* | Kelly; fractional Kelly; risk-constrained Kelly (Busseti–Ryu–Boyd); drawdown control | Stages 5–7 (size & decide) |

Literature **A** is implemented with deflated Sharpe, PBO, Hansen's SPA, purged/embargoed CV, and a
trial-count budget. Literature **B** is where earlier work improvised (a hand-rolled tail cap and
stress multiplier); this document puts it on the theory it approximates.

---

## 1. Non-negotiable principles

1. **Hypothesis before test.** State an economic reason a signal *should* work before backtesting
   it. Harvey & Liu: mining without a prior guarantees false positives at scale.
2. **Validity before optimization.** Prove an edge generalizes out-of-sample before fine-tuning —
   otherwise you optimize noise.
3. **Cheap & universal before expensive & specific.** Per-instrument before portfolio; global
   structure before per-market tailoring (per-market multiplies the trial count and overfitting).
4. **Every choice is a trial.** Count trials across *all* stages; deflate the Sharpe accordingly
   (DSR); reserve a holdout no stage ever selects on.
5. **Deploy = validate.** Validate the *exact* config you will trade. If you trade fixed stops, do
   not report a walk-forward that re-optimizes the stop every window (see §5).
6. **Risk lives on three separate levels — never conflate them:**
   - **Trade-level** (SL/TP) — part of the strategy, chosen inside the walk-forward.
   - **Evaluation lens** — selection always uses a *risk-adjusted* metric, never raw return.
   - **Capital sizing** — a pure scaling transform applied last, against the prop-firm limit
     (Stage 5); it changes trade *size*, not *which* trades happen.
7. **The number is an upper bound until paper-traded.** Leverage, walk-forward-selected params and
   idealized fills all bias the headline upward.

---

## 2. The protocol, front to back

Each stage: the question it answers, the method, the literature, the pass/fail criterion, and the
artifact it hands to the next stage. Stages are separately runnable so a human decides between them.

### Stage 0 — Economic hypothesis *(pre-registration)*
State, before any backtest: what inefficiency is captured, why it should persist, and which knobs
are legitimate to vary. This bounds the trial universe and is the honest denominator for the DSR.
- **Literature:** Harvey & Liu, *Backtesting* (2015) — an economic prior is the first line of defence
  against data mining.
- **Criterion:** a written rationale + a *fixed* list of variations/parameters. Anything tested
  later that is not on this list must be added to the trial count.

### Stage 1 — Frozen signal + realistic execution & cost model *(always on)*
The signal engine is frozen and shared by backtest and live (so live == backtest). Every backtest
runs **net of costs**: bid/ask spread, commission, slippage (fill model), exact overnight swap.
Execution must be modelled correctly — see §6 (implementation risk).
- **Criterion:** costs present in every run; exits fill at their own price (a stop at the trigger,
  a gap at the gap); per-trade **R = pnl / (risk it took)** is honest and scale-invariant.

### Stage 2 — Edge & robustness *(the heavy compute)*
Rolling **purged, embargoed, non-overlapping** walk-forward: parameters chosen on each train window
by a drawdown-adjusted score (Calmar), scored on the unseen test window. Run for the baseline **and**
the component ablation (a 2ⁿ factorial of the confirmation filters) across **many instruments** and
**several train-window lengths**.
- **Metrics:** OOS return per window, OOS max drawdown, **return-per-drawdown** (ranking key),
  % profitable windows, length-normalized WFE, **Deflated Sharpe Ratio (DSR)**, **PBO**, and
  Hansen's one-sided studentized **Superior Predictive Ability (SPA)** family test and
  Romano-Wolf one-sided studentized max-t stepdown.
- **Literature:**
  - Purged & embargoed CV: López de Prado, *Advances in Financial Machine Learning* (2018) — prevents
    train/test leakage across the boundary.
  - DSR: Bailey & López de Prado (2014) — deflate the Sharpe by the number of trials, skew, kurtosis,
    sample length. A high raw Sharpe is only lightly penalized; a marginal one heavily.
  - PBO via CSCV: Bailey, Borwein, López de Prado, Zhu (2015) — probability the in-sample winner
    underperforms the median out-of-sample.
  - SPA: Hansen (2005) — tests whether any formal candidate has positive expected daily net R
    against zero while accounting for the correlated search family. Consistent recentering keeps
    clearly inferior candidates from diluting a genuine winner.
  - Romano-Wolf (2005) — controls familywise error while identifying which individual candidates
    have positive mean daily net R. Ordered hypotheses are stepped down against the bootstrap
    maximum over only the not-yet-rejected family.
  - Multiple-testing haircut: Harvey & Liu (2015).
- **Criterion:** a positive, generalizing edge — normalized WFE ≳ 0.5, **DSR significant after
  deflation by the full trial budget** (variations × train-lengths × per-window param-combos), PBO
  low, and the consistent SPA p-value at most 0.05. SPA uses the 36 formal
  `(variation, train_months)` daily net-R streams, a zero benchmark, P-04's selected stationary
  bootstrap length, 10,000 replications, and seed 20260719. The selected length and every fixed
  5/10/20/60-day sensitivity must pass; missing or unreadable evidence fails closed. Rank variants
  by return-per-drawdown across instruments; a component that lifts return but wrecks drawdown does
  not win. Stage 1 also persists Romano-Wolf adjusted p-values and the exact `p <= 0.05`
  per-candidate eligibility label using SPA's selected block length, seed, replications, paired
  stationary-bootstrap draw, long-run variance, and studentization. P-06 only publishes this
  evidence; P-08 owns its use in selection.

### Stage 3 — Selection: global structure + universe
Pick the single **global** structure (variation + train length) that is most robust across markets
(return-first, but only among the risk-tolerable and cross-instrument-consistent), then keep the
instruments whose own risk-adjusted edge clears the thresholds.
- **Criterion:** one structure for all markets; markets kept only on a robust risk-adjusted edge.

### Stage 4 — Holdout *(touched once)*
Score the chosen config on the reserved holdout period no earlier stage ever saw. This is the honest
out-of-sample estimate. Touch it **once**; re-touching turns it into another selection trial.

### Stage 5 — Sizing under the hard limit *(see §3 for the theory)*
Given the OOS trade stream, choose the capital-at-risk per trade. This is **not** a return lever to
be maximized — it is a constrained optimization: **maximize log-growth subject to the prop-firm hard
limits never being breached, even in a worse-than-history crisis.**
- **Literature:** risk-constrained Kelly gambling (Busseti, Ryu, Boyd 2016); fractional Kelly.
- **Criterion:** the chosen risk survives a stressed worst-case single-day gap within the daily hard
  limit, and its full-history max drawdown stays within the trailing hard limit with margin (§3).

### Stage 6 — Robustness of the sized portfolio
- **Regime / per-year:** return every calendar year — a real edge pays in most years; an overfit one
  in a few. Reveals regime dependence (e.g. a reversal strategy earns more in high-vol years).
- **Monte-Carlo:** bootstrap the trade order for a sequence-risk distribution (prob. of profit,
  drawdown percentiles).
- **Stress:** extra slippage, crisis windows, a higher stress multiplier.
- **Criterion:** positive in the large majority of years; MC profit probability high; survives the
  stressed cases.

### Stage 7 — Decision under uncertainty
Present the **return-vs-risk efficient frontier** (§3.3), not a single number. The operator picks a
point on it (more crisis buffer ↔ more return), with the regime range attached (calm / central /
volatile). This is the deliverable: a recommendation *plus* the explicit trade-off.

---

## 3. Sizing, grounded (Stage 5 in depth)

### 3.1 The problem is risk-constrained Kelly

Classical **Kelly** sizing maximizes long-run log-growth but accepts brutal drawdowns (full Kelly can
draw down 50 %+). We cannot: a prop account *dies* at a fixed loss. The correct frame is
**risk-constrained Kelly** (Busseti, Ryu, Boyd 2016):

> maximize  E[log growth]   subject to   P(min Wealth ≤ α·W₀) ≤ β

i.e. maximize growth while holding the probability of *ever* dropping to a fraction α of capital
below a tolerance β. Their key move is a **convex, guaranteed-safe bound** on that drawdown
probability:

> P(min Wealth ≤ α·W₀) ≤ α^λ

so choosing the single **risk-aversion parameter**

> **λ = ln(β) / ln(α)**

makes α^λ = β and enforces the constraint. The bet is then the solution of the convex problem

> maximize  E[ln(bᵀr)]   subject to   **E[(bᵀr)^(−λ)] ≤ 1**,   Σb = 1, b ≥ 0

(bᵀr = the gross return of the sized bet; solvable by bisection on the bet fraction for our
single-strategy case). λ = 0 recovers full Kelly; larger λ shrinks the bet — always to a
**fractional-Kelly** size, but the paper's bets beat plain fractional Kelly at the same drawdown
risk. The value: it **converts subjective risk aversion into one explicit, reproducible parameter**
(α, β) instead of a gut number, and it is stable across regimes.

Fractional Kelly is also *cheap insurance*: **half-Kelly keeps ≈ 75 % of full-Kelly growth for far
less variance and drawdown** — a derived property, not a rule of thumb. Overestimating the edge under
full Kelly is catastrophic (Browne & Whitt 1996); the fractional haircut is the standard defence.

### 3.2 Our two hard constraints, as special cases

The Trading Pit imposes two hard walls (account death on breach):

1. **Daily loss ≤ 3 %.** The binding event is a **single-day gap** through the stops — unhedgeable,
   untaperable (it hits at whatever size you hold). This is the α→(1−0.03), δ→0 corner: the *worst
   single day must not breach*. Our **tail cap** implements exactly this:

   > cap = daily_hard / (stress × |worst-day R|)

   measured on the **full history** (all crises) at the **stop actually traded** (R = move/stop, so
   the stop distance is the dominant lever on the tail). The **stress multiplier** is the fractional
   part: it is our c(α,δ) — how much worse than the worst historical day we size for.

2. **Trailing drawdown ≤ 6 %.** The multi-day path constraint. Checked as the full-history max
   drawdown of the sized, mark-to-market equity; it must stay under 6 % with margin.

A **dynamic throttle** (size down as the drawdown budget is consumed) is the path-dependent tool for
constraint 2 — but it does **nothing** for constraint 1 (a gap hits before you can taper), so the
*ceiling* is always the gap-safe tail cap. On calm data a throttle simply sits at the ceiling, so it
is not a return lever; its only value is auto-braking in a *gradual* drawdown near the wall.

### 3.3 The decision tool: the return-vs-buffer frontier

Because the tail is the binding constraint and a gap cannot be diversified or tapered away, **there
is no free lunch**: every knob trades return for crisis buffer. The single honest control is the
stress multiplier (the Kelly fraction), and it traces the efficient frontier, e.g. (no_bb_rsi, full
history):

| stress | crisis buffer | risk/trade (cap) | return @ cap |
|---|---|---|---|
| 1.25 | 1.25× worst day | 0.261 % | +46.6 %/yr |
| 1.50 | 1.50× worst day | 0.218 % | +38.8 %/yr |
| 2.00 | 2.00× worst day | 0.163 % | +29.1 %/yr |

Stage 7 presents this frontier with the regime range (calm ≈ ⅓, volatile ≈ 1.4× the central figure)
so the operator chooses a point deliberately.

### 3.4 Levers that do *not* work (tested, negative results)

- **Per-market stop re-optimization for return:** picks the tightest grid stop (raw R is maximized
  there), which worsens the gap tail and lowers the cap; the apparent gain is in-sample and does not
  survive. The stop belongs to the strategy and is chosen in-walk-forward, not tuned for size.
- **Tail-aware market weighting:** the markets that drive the worst day (correlated indices) are also
  the return drivers, so down-weighting them cuts return in lockstep. The correlated-gap risk is not
  diversifiable without sacrificing the edge.

---

## 4. Deploy = validate (fixed vs. re-optimized)

The per-window optimizer maximizes **train-window Calmar**, which is *tail-blind* (a train window is
almost always gap-free), so it always grabs the tightest stop on the grid — a stop whose full-history
tail then forces an untradeable size. But we deploy **fixed** per-market stops. Therefore:

- **Validate the fixed config** (each market's deployed SL/TP held constant every window), not the
  re-optimized chase. The framework provides both; the *fixed* run is the one that matches live.
- Report the **fixed-vs-re-optimized gap** explicitly — it is the cost of not re-optimizing, and it
  tells you whether per-window re-optimization is even worth its overfitting risk (usually not).

---

## 5. Implementation risk (the bugs that bite)

A backtest can be methodologically perfect and still lie because of an execution-model error
("implementation risk" is itself a studied source of backtest error). The ones that bit this project,
now guarded by tests — check these first when a number looks too good:

- **Exit fills.** A synthetic "close on the next bar" turns every stop-out into a full-bar overshoot;
  losses reach many R and the sizing built on "1R = the risked amount" is fiction. Exits must be
  resting venue orders that fill at the trigger (and only at the gap price on a genuine gap).
- **Passive-order volume cap.** A bar's volume caps how much a passive (limit / touched) order fills;
  feeding a tick-count as tradeable volume splits a take-profit across both exit legs. Bar volume for
  a CFD at our size must be non-binding.
- **Compounding vs. flat.** Backtest PnL sized at a % of *growing* equity compounds; it must never be
  scaled linearly to another risk. Book from **R-multiples** to size flat or dynamically.
- **Tail at the wrong stop.** R = move/stop, so the tail cap must be measured at the stop actually
  traded, per market — not a grid average.
- **Zero-trade window / empty report.** A trade-free window is a flat window, not a crashed task.

---

## 6. Mapping to the code (status)

| Stage | Module(s) | Status |
|---|---|---|
| 0 Hypothesis | *(doc / config)* | ⚠️ make explicit per strategy |
| 1 Signal + costs | `core/strategies`, `core/broker`, `engine/recipe`, `core/data` | ✅ |
| 2 Edge & robustness | `engine/` walk-forward, `engine/overfitting`, `engine/spa`, `engine/romano_wolf` | ✅ DSR/PBO, SPA, and Romano-Wolf candidate evidence are surfaced in Stage 1 (`stages/edge`) |
| 3 Selection | `stages/universe`, `stages/edge`, `stages/select` | ✅ |
| 4 Holdout | `portfolio/trades` (phase="holdout"), `stages/portfolio` | ✅ |
| 5 Sizing | `portfolio/risk` (tail cap, `rck_fraction`/`KellyRisk`, policies), `portfolio/tail`, `portfolio/stress` | ✅ gap tail cap + risk-constrained Kelly (`kelly:beta`), sized on the full-history stream; the drawdown bound is Monte-Carlo-verified |
| 6 Robustness | `engine/montecarlo`, per-year analysis, `portfolio/stress` | ✅ |
| 7 Decision | *(the stress/return frontier)* | ⚠️ produced ad-hoc; to formalize into Stage-4 report output |

**Done since:** Stage 0 hypothesis written; DSR, PBO, SPA, and Romano-Wolf candidate evidence
surfaced in the staged CLI (Stage 2);
risk-constrained Kelly wired as the `kelly:beta` policy (Stage 5), sized on the full-history stream.
**Nearest gap:** the efficient frontier (return vs risk-aversion β) as the formal Stage-7 report
output -- currently produced ad-hoc; on real data the gap tail cap binds below RCK for every β, so
the sizing decision reduces to the tail cap with RCK confirming the trade-sequence drawdown is safe.

---

## 7. References

- D. H. Bailey & M. López de Prado, *The Deflated Sharpe Ratio: Correcting for Selection Bias,
  Backtest Overfitting and Non-Normality* (2014). SSRN 2460551.
- D. H. Bailey, J. Borwein, M. López de Prado, Q. J. Zhu, *The Probability of Backtest Overfitting*
  (2015). SSRN 2326253.
- P. R. Hansen, *A Test for Superior Predictive Ability*, Journal of Business & Economic
  Statistics 23(4), 365–380 (2005).
- J. P. Romano & M. Wolf, *Stepwise Multiple Testing as Formalized Data Snooping*,
  Econometrica 73(4), 1237–1282 (2005).
- C. R. Harvey & Y. Liu, *Backtesting* (2015) and *Evaluating Trading Strategies* (2014). SSRN
  2345489 / 2474755.
- M. López de Prado, *Advances in Financial Machine Learning* (Wiley, 2018) — the front-to-back
  reference: purged/combinatorial CV, PBO, DSR, backtesting pitfalls.
- E. Busseti, E. Ryu, S. Boyd, *Risk-Constrained Kelly Gambling* (2016). arXiv:1603.06183.
- J. L. Kelly Jr. (1956); E. Thorp on fractional Kelly; S. Browne & W. Whitt (1996) on Kelly
  fragility to estimation error.
- S. Grossman & Z. Zhou, *Optimal Investment Strategies for Controlling Drawdowns* (1993); E. Chan on
  drawdown-limited Kelly (practical).
