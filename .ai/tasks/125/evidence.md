# Evidence

## HEAD

HEAD: dd5a3dfe832cd38cc262cf067eb1f5e13fe2a001

Branch `claude/125-mutation-total`, branched from `origin/main` at `8b75ff0`. This tree contains
nothing from the unmerged pull requests #105, #106 and #123 or from the unmerged issue #107 branch.

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | `uv run pytest -q tests/test_quality_mutation.py` before the production change | 1 | RED: **1 failed, 150 passed** — `test_added_production_code_alone_no_longer_fails_the_ratchet` failed with `mutation total changed: expected 4646, observed 4774`. The single failure is the criterion under change; every preservation test and all 128 differential cases were already green. |
| `red-first` | `uv run pytest -q tests/test_quality_mutation.py -k both_totals_stay_visible` after extracting `summary_lines` behaviour-preserving and before adding the baseline total | 1 | RED: **2 failed** — `assert '4646' in 'Mutation critical: 4364/4775 killed, 411 survived; report critical.toml'`, on both the passing-run and the failing-run case. |
| `format` | `uvx --from rust-just just check-standard` | 0 | GREEN: Ruff, format and mypy. Two `C420` findings and one `E501` were fixed before the final commit. |
| `docs-consistency` | `uv run pytest -q tests/test_engineering_docs.py tests/test_claude_runtime_files.py tests/test_docs_language.py tests/test_docs_architecture_map.py` | 0 | GREEN: **136 passed**. No engineering document changed. |
| `check` | `uvx --from rust-just just check` | 0 | GREEN: **1348 passed**, 1 skipped (Mutmut needs fork/WSL on Windows). |
| `impacted-tests` | `uvx --from rust-just just check-fast` | 0 | GREEN: impact selected `tests/test_quality_mutation.py` as the only directly related suite and discovered no transitive, critical-path or dynamic edge; **155 passed**, 1 skipped. |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | 0 | GREEN: **21 properties passed twice** with seed 20260721. |
| `integration-tests` | full pytest within `check` | 0 | GREEN: 1348 passed with no MT5 terminal initialised and no runner contacted. |
| `invariants` | `uvx --from rust-just just check-invariants` | 0 | GREEN: **325 passed**. |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task 125` | 0 | GREEN: valid. |
| `security` | `uvx --from rust-just just check-security` | 0 | GREEN: tracked-secret scan, dependency audit and static security checks. |
| `parity-where-applicable` | `git diff --name-only origin/main...HEAD -- core research live monitoring` | 0 | GREEN: zero production trading paths changed. The change is confined to `scripts/quality/mutation.py` and its tests. |
| `mutation-on-touched-critical` | `git diff --name-only origin/main...HEAD -- core research live monitoring` | 0 | GREEN, vacuous: no critical production file changed, so no target is touched. `scripts/quality/mutation.py` is not itself a mutation target. |
| `live-money-review` | changed-path audit against `live/**`, sizing, risk and broker paths | 0 | GREEN: no live, risk, order or account code changed; no MT5 terminal was initialised and no runner was contacted at any point. |
| `human-decision-escalation` | issue #125 | 0 | GREEN: no open decision. Jan directed the change after being shown the two-run measurement. |
| `no-autonomous-merge` | — | 0 | GREEN: not merged, auto-merge not enabled, not marked ready for review. |
| `adversarial-review` | — | 1 | **OWED and blocking.** Claude built this change, so Claude must not review it. The independent review is owed from Codex before readiness. |

## Coverage and mutation

No production file under `core`, `research`, `live` or `monitoring` changed, so the critical
mutation ratchet is vacuous for this branch and no baseline is touched. The recorded baseline total
of 4646 in `.ai/quality/mutation-baseline.toml` is unchanged; it is now reported rather than
compared.

### Real-data replay of the rule change

The strongest available evidence is not synthetic. The artifact `mutation-critical-result` of the
failing Linux run 30432148064 on PR #105 was downloaded and replayed against the baseline committed
at that run's own commit `a221985`, using the production `check_baseline` from this branch:

```
observed total 5106, baseline total 4978
observed score 0.9195, baseline score 0.9178

OLD rule -> 2 issue(s):
  - unexplained surviving mutants: ['live.mt5_bridge.x__position_ticket__mutmut_1',
    'live.runner.xǁLiveRunnerǁ_total_open_risk__mutmut_46']
  - mutation total changed: expected 4978, observed 5106; update the baseline with an explanation

NEW rule -> 1 issue(s):
  - unexplained surviving mutants: ['live.mt5_bridge.x__position_ticket__mutmut_1',
    'live.runner.xǁLiveRunnerǁ_total_open_risk__mutmut_46']
```

The verdict that survives is the one naming the two genuinely uncovered mutants in PR #105's own new
code, one of which is in `_total_open_risk` — the function an independent review separately found to
carry a defect. The verdict that disappears is the one that carried no information about the branch.

### Why the removed condition could not bind

Two consecutive Linux runs of the same branch, 30431184595 at 07:26 and 30432148064 at 07:42 on
2026-07-29:

| Run | total | unexplained survivors | score |
|---|---|---:|---|
| 30431184595 | 4978 vs 5118 | 53 | regressed, 0.9097 < 0.9178 |
| 30432148064 | 4978 vs 5106 | 2 | passed |

Between the two runs the builder closed 51 real test gaps. Both substantive verdicts moved. The total
verdict did not change state, because the branch still added code. A condition whose state is
independent of test strength cannot detect a test-strength defect.

## Deferred checks

- **Independent adversarial review — owed, and blocking.** Claude built this change under the builder
  exception, so the review must come from Codex in fresh context. This branch must not be marked
  ready for review until that review is clean. Readiness fails today for exactly this reason, and
  that is the correct state.
- **Linux mutation self-test — not run locally.** `just mutation-self-test` requires fork, so it does
  not run on Windows. The Mutmut-backed probe
  `test_a_real_weakened_test_increases_survivors_and_is_caught` is skipped locally for the same
  reason and will run on the Linux CI job. It exercises `check_baseline` end to end against the real
  tool and is unaffected by the total comparison, which it never triggered.
- **Issue #115 encountered.** The first full `just check` reported 54 failures in
  `tests/test_research_stage_lineage.py` because this branch's uncommitted test file contains the
  `ǁ` character used in Mutmut's method-mutant names, which Windows lineage decoding reads through
  cp1252. Committing the identical tree and re-running gave 1346 passed. No production workaround and
  no test relaxation was made here; #115 remains open.
- **Branch protection on `main` — not active.** Unchanged by this task.
