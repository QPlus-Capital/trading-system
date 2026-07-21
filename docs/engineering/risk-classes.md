# Change risk classes

Every non-trivial change carries a risk class. The class controls which quality gates are mandatory
before the change can reach a pull request, and whether it may merge autonomously. This is the prose
companion to the machine-readable model in
[`.ai/quality/risk-classes.toml`](../../.ai/quality/risk-classes.toml); the two must agree, which
`tests/test_engineering_docs.py` checks.

## How the class is decided

1. **Path minimum (conservative).** Each changed path is matched against the rules in the TOML; the
   class is the **highest** minimum over all matched paths. A change touching only markdown/docs is
   `R0`; anything unmatched falls back to `R1`.
2. **Semantic upgrade (mandatory).** The author raises the class when the real impact is broader
   than the paths suggest — e.g. an `R1`-looking helper that a sizing function calls, or a config
   value that flows into live. Path matching may never *lower* the class below the matched minimum.

The class and the one-line reason go in the task spec and the PR.

## The classes

| Class | What it is | Mandatory gates (beyond the lower classes) |
|-------|------------|---------------------------------------------|
| **R0** | Documentation or comments only; no behaviour change. | format check, docs consistency |
| **R1** | Local non-financial code (tooling, scripts) with no financial, methodology, or result-integrity impact. | `just check`, impacted tests |
| **R2** | Shared core, research orchestration, artifact schema, configuration, or monitoring semantics — depended on widely, but not on the money or methodology path. | property tests where applicable, integration tests, artifact/schema checks, adversarial review |
| **R3** | The live-money path, position sizing, risk control, account identity, order placement, signal parity, broker/instrument conversion, money calculations, trading methodology, holdout handling, selection logic, or result integrity. | explicit invariants, mutation testing on touched critical functions, parity checks where applicable, adversarial review, **live-money review**, human decision escalation for ambiguous domain choices, and **no autonomous merge** |

Gates are cumulative: R2 includes R1's, R3 includes R2's.

## R3 — the paths that are always at least R3

These are matched automatically (see the YAML for the exact globs and reasons):

- `live/risk_control.py`, `live/runner.py`, `live/accounts.py`, `live/mt5_bridge.py`,
  `live/preflight.py`, `live/config/**`
- `core/strategies/**`, `core/broker.py`, `core/instruments/**`
- `research/regression.py`
- `research/portfolio/{risk,sizing,drawdown,trades,tail,stress}.py`
- `research/engine/{continuous,walkforward,walkforward_runner,characterize}.py`
- `research/stages/**`, `research/config/**`

A change to any of these ranks parameters, sizes a position, moves money, decides selection, or
guards result integrity. It gets the full R3 treatment and a human approves the merge.

## Why the upgrade rule matters

The most expensive defects this repository has seen were **coupled-quantity** changes: a value
(a sizing basis, a risk denominator, a cost) was changed at one call site while other consumers were
left inconsistent. Path matching cannot see that. Before changing such a value, enumerate every
place it enters the pipeline and raise the class to cover all of them. See the finding registry
(`.ai/quality/finding-patterns.yaml`) for the recorded instances.
