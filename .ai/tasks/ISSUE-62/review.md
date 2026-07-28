# Adversarial review

## Findings

No findings; 12 counterexamples attempted

## Dispositions

- A flat/no-signal fixture was rejected: the registered series contains five buys, five sells,
  and a sell on its final bar.
- A final-bar omission was attempted: the expected index tuple includes index 198 of 199.
- A warm-up omission was attempted: every bar before the first possible decision is compared and
  the entire pre-signal prefix is explicitly false.
- A one-sided oracle was attempted by swapping buy/sell only in the live module; the red-first run
  failed at bar 29 with backtest `(True, False)` versus live `(False, True)`.
- A shared-engine-only comparison was rejected. The backtest side calls the real
  `RsiWprBb.on_bar`; the live side calls the real `LiveRunner._replay_signal`.
- A final-signal-only comparison was rejected. The live restart-safe replay is invoked for every
  prefix and the full 199-element sequences are compared.
- A symmetric stub was rejected. Only the live module's engine factory is replaced in the
  counterexample; the Nautilus adapter remains real.
- A terminal-capable fake was rejected. `_NoTerminalBridge` raises on every attribute access and
  the harness never invokes `run_once`.
- An order-path side effect was rejected. The backtest probe overrides only the terminal
  long/short dispatches and never accesses portfolio, order factory, or venue state.
- Adapter parameter drift was checked: one `SignalParams` value supplies the live runner and every
  signal field in the Nautilus config.
- Bar conversion drift was checked: both native bar types receive the same five-decimal OHLC
  values and strict chronological order.
- Registration drift was checked: the invariant recipe executes the harness, and the TOML map
  binds it separately to the engine and both adapters.
- The production diff is empty across `core`, `live`, `research`, and `monitoring`; no live-money
  behaviour or reported result changes.
- Existing AST construction, live-feed parity, live runner, and Nautilus end-to-end tests pass
  beside the new behavioural oracle.

Independent Claude review remains external and is required after the infrastructure block clears.
