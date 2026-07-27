# Evidence

## HEAD

HEAD: 1b547eeb731d88c02f74d250b1595cb82d5e07c9

The only later commit permitted by readiness is this evidence file itself.

## Commands

### Required gates

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `format` | `uvx --from rust-just just check-fast origin/main` | 0 | The new Python harness is Ruff-formatted; lint, strict mypy over 181 files, impact, and both focused tests pass. |
| `docs-consistency` | `uv run pytest -q tests/test_docs_architecture_map.py tests/test_docs_language.py tests/test_engineering_docs.py tests/test_engineering_workflow_docs.py tests/test_gate_consistency.py` | 0 | 143 documentation, language, engineering-policy, and gate-consistency tests pass. |
| `check` | `uvx --from rust-just just check` | 0 | Ruff, strict mypy, Vulture, and 1,193 tests pass; the one Linux-only mutation self-test is skipped on Windows. |
| `impacted-tests` | `uvx --from rust-just just check-fast origin/main` | 0 | Impact selected the new harness and both parity tests pass. |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | 0 | 21 deterministic properties pass twice at Hypothesis seed `20260721`. |
| `integration-tests` | `uv run pytest -q tests/test_signal_adapter_parity.py tests/test_import_boundaries.py tests/test_live_parity_check.py tests/test_live_runner.py tests/test_live_runner_cycle.py tests/test_strategies_rsi_wpr_bb.py` | 0 | 110 adapter, structural, live-cycle, feed-parity, and Nautilus end-to-end tests pass. |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task --task-id ISSUE-62 --base origin/main` | 0 | Task schema and traceability are valid with six acceptance criteria and six invariants. |
| `adversarial-review` | `uv run python -m scripts.quality.validate_task --task-id ISSUE-62 --base origin/main` | 0 | Twelve counterexamples are recorded with no unresolved finding; independent Claude review remains external. |
| `invariants` | `uvx --from rust-just just check-invariants` | 0 | 315 critical-invariant tests pass and the new adapter harness is in the recipe. |
| `mutation-on-touched-critical` | GitHub Actions `Critical mutation` | 1 | **blocked by infrastructure — Actions quota exhausted until 2026-08-01**. No workflow can start under the configured $0 budget; no mutation result is claimed. |
| `parity-where-applicable` | `uv run pytest -q tests/test_signal_adapter_parity.py tests/test_import_boundaries.py tests/test_live_parity_check.py` | 0 | Both real adapters agree on all 199 bars; structural construction and feed/data parity remain green. |
| `live-money-review` | `.ai/tasks/ISSUE-62/review.md` plus production/live diff audit | 0 | No production or live byte changes; the fake bridge refuses every terminal access and no runner process was invoked. |
| `human-decision-escalation` | `.ai/tasks/ISSUE-62/spec.md` build-only decision audit | 0 | Jan's quota/build-only decision is preserved: draft only until mutation and independent review complete. |
| `no-autonomous-merge` | `git branch --show-current` and draft-only instruction audit | 0 | Branch `codex/issue-62-behavioural-signal-parity`; no merge, ready transition, or auto-merge action was taken. |

### Additional evidence

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | `uv run python -m scripts.quality.classify $(git diff --name-only origin/main...HEAD)` | 0 | R3 with all fourteen cumulative required gates. |
| `red-first` | `uv run pytest -q tests/test_signal_adapter_parity.py` with the divergent live stub uncaught | 1 | One normal-path test passed; the divergent adapter failed at bar 29: backtest `(True, False)`, live `(False, True)`. |
| `focused-parity` | `uv run pytest -q tests/test_signal_adapter_parity.py` | 0 | Both permanent tests pass, including the deliberately divergent counterexample. |
| `impact` | `uvx --from rust-just just impact origin/main` | 0 | R3; no production file, one direct test, and no transitive, unknown, or dynamic edge. |
| `security` | `uvx --from rust-just just check-security` | 0 | Secret scan clean, no known dependency vulnerabilities, and Ruff security checks pass. |
| `no-production-drift` | `git diff --exit-code origin/main...HEAD -- core live research monitoring pyproject.toml uv.lock` | 0 | Production, dependency, signal, runner, research, and monitoring bytes are identical to main. |
| `baseline-artifacts` | `Get-FileHash -Algorithm SHA256 reports/research/run_20260727_issue91/{portfolio_trades.csv,full_history_trades.csv}` | 0 | Stored baseline hashes remain `b5a0a9bb...45129` and `27592d20...90dc`; no producer changed and no stage rerun is required. |
| `pr-ready` | `uv run python -m scripts.quality.pr_ready ISSUE-62 --base origin/main` | 1 | NOT READY solely because the required Linux mutation gate has non-zero infrastructure-blocked evidence. |

## Red-first proof

Before the permanent divergent-stub expectation was added:

```text
uv run pytest -q tests/test_signal_adapter_parity.py
```

Exit `1`: the real-path parity test passed, and the intentionally buy/sell-swapped live adapter
failed at the first actual signal:

```text
signal adapter mismatch at bar 29:
backtest=(True, False), live=(False, True)
```

The final counterexample test expects that precise assertion, so removing or weakening the
bar-for-bar oracle makes the test fail.

## No-drift audit

This package changes only a test, task artifacts, the critical dependency map, and the invariant
recipe. `core/**`, `live/**`, `research/**`, `monitoring/**`, `pyproject.toml`, and `uv.lock` are
byte-identical to `origin/main`. No Stage 1-4 producer changed, so a research rerun would add no
evidence and was not performed.

The stored current-baseline artifacts remain:

- `portfolio_trades.csv`:
  `b5a0a9bb6d19ccee85c35aa6570a3bd67ea8fd885665d92901e5f14113f45129`
- `full_history_trades.csv`:
  `27592d20dda0fb3b31eb06de69d4d760d0f16cd961f2872e4f6376acb3dd90dc`

No reported number, signal parameter, trade, cost, risk value, or live action changes.

## Coverage and mutation

The fixture contains 199 H4 bars, a 29-bar false prefix spanning indicator warm-up, five buy
signals, five sell signals, and a sell on final index 198. The backtest side invokes the real
`RsiWprBb.on_bar` with native Nautilus bars. The live side invokes the real
`LiveRunner._replay_signal` on every native-live-bar prefix, matching its restart-safe semantics.
The fake bridge raises on every attribute access.

The critical dependency map binds the harness to the signal engine and both adapters, while
`check-invariants` runs it on every critical suite. No production mutation target changed.
Windows cannot execute Mutmut's fork-based Linux gate, and GitHub Actions cannot start it under the
exhausted quota. No survivor count, score, or baseline disposition is invented.

## Deferred checks

The Linux Critical mutation gate is **blocked by infrastructure — Actions quota exhausted until
2026-08-01**. On quota reset, push an empty commit to retrigger CI and mutation, reconcile the
mutation baseline only if the measured run requires it, update evidence, rerun `pr-ready`, obtain
independent Claude review, and only then consider marking the pull request ready. The draft pull
request must not merge or enable auto-merge.
