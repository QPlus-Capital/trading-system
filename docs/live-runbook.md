# Live runbook — two accounts in parallel (MEX demo + TTP real)

Two independent runners, each attached to its **own** MT5 terminal, with fully isolated state.
The demo (MEX Atlantic, EUR) is the parity shadow; the TTP CFD Prime $50k (USD) is the real prop
account. All code tooling (dashboard) defaults to TTP.

## One-time setup for the TTP account

1. **Buy** the TTP CFD Prime $50k (1-phase) account. Rules the code already targets: daily DD 3%
   ($1,500), max DD 6% ($3,000), profit target +10% ($5,000). No config-value change needed —
   `RiskLimits`/`AccountProfile` already use 3% / 6%.
2. **Install a second MT5 terminal** in its own folder (do NOT reuse the demo's install — two
   accounts need two terminal instances). Log it into the TTP account, enable Algo Trading, and
   add all 10 symbols to Market Watch.
3. **Fill the TTP profile** in `src/qplus/live/accounts.py`:
   - `expected_login` = the TTP account number (the guard refuses real orders until this is set),
   - `terminal_path` = the full path to that terminal's `terminal64.exe`.
   Also set `MEX.terminal_path` to the demo terminal's `terminal64.exe` so each runner is pinned to
   the right instance (once two terminals run, "the default terminal" is ambiguous).
4. **Verify symbols on first connect:** run `--account ttp` once in the default SIGNAL_ONLY mode and
   check the `symbol resolved: … -> …` log lines. If TTP names differ (like `USTEC -> UT100` on
   MEX), add a per-account symbol map. Do this before `--mode execute`.

## Running

Each runner needs *its* terminal open + logged in.

```bash
# Demo (unchanged strategy; watched only in MT5). State migrates to reports/live/mex/ on first run.
uv run python -m qplus.live.run --account mex --mode execute

# TTP real money — SIGNAL_ONLY first (a few cycles, verify), THEN execute.
uv run python -m qplus.live.run --account ttp                 # dry-run, no orders
uv run python -m qplus.live.run --account ttp --mode execute  # REAL orders
```

- State/logs are isolated per account: `reports/live/mex/` vs `reports/live/ttp/`.
- **The guard:** each runner refuses to trade unless the connected account's login + currency match
  its profile — a runner can never place orders on the wrong account.

## Monitoring

```bash
uv run streamlit run src/qplus/monitoring/dashboard.py
```
Pick the account in the sidebar (defaults to TTP). The demo you watch directly in MT5.

## When the TTP account gets funded

Same 3% / 6% rules apply funded, and the account resets to the $50k start balance. Just restart the
TTP runner with a fresh risk state so the references reset (the absolute risk shrinks back
automatically because sizing is 0.18% of the current equity):

```bash
rm reports/live/ttp/risk_state.json    # reset the trailing/daily reference to the new start
uv run python -m qplus.live.run --account ttp --mode execute
```

## Emergency

To stop a runner: Ctrl+C in its terminal. Its server-side SL/TP stay active on the broker as the
intrabar backstop. To flatten manually, close the positions in that account's MT5 terminal.
