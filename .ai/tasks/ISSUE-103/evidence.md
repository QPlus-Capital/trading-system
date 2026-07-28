# Evidence

## HEAD

HEAD: d08091a9d462a68281211e4a78b131ce8184e8a9

The only later commit permitted by readiness is this evidence file itself.

## Commands

### Required gates

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `format` | `uvx --from rust-just just check-fast origin/main` | 0 | Ruff format/check and strict mypy passed; 145 impacted tests passed. |
| `docs-consistency` | full `just check` plus task validation | 0 | Engineering-document and gate-consistency tests passed inside the 1,260-test suite. |
| `check` | `uvx --from rust-just just check` with `PYTHONUTF8=1` on Windows | 0 | Ruff, strict mypy over 181 files, Vulture, and pytest passed: 1,260 passed, 1 Windows-only mutation self-test skipped. |
| `impacted-tests` | `uvx --from rust-just just check-fast origin/main` | 0 | Both changed production files selected the bridge, runner, risk, monitoring, sizing, swap, and parity consumers; 145 tests passed. |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | 0 | 21 property tests passed twice at fixed Hypothesis seed `20260721`. |
| `integration-tests` | focused bridge/runner suite and `check-fast` recommended command | 0 | 84 direct bridge/runner-cycle tests and 145 complete impacted tests passed using synthetic fakes only. |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task --task-id ISSUE-103 --base origin/main` | 0 | Task ISSUE-103 is valid with 14 acceptance criteria and 8 invariants. |
| `adversarial-review` | `.ai/tasks/ISSUE-103/review.md` | 1 | The complete re-review found F1/F2/F3/F5; all are dispositioned with executable evidence, but the material P1 live-path fix requires one further complete independent review. |
| `invariants` | `uvx --from rust-just just check-invariants` | 0 | 409 critical invariant tests passed; the suite directly exercises the MT5 bridge and runner safety cycle. |
| `mutation-on-touched-critical` | Linux run `30362970416` against the existing exact baseline | 0 | 4,923 total, 4,514 killed, 409 survived, 0 no-tests, and every other unhealthy status 0. The gate passed without any baseline change, new survivor, or classification. |
| `parity-where-applicable` | legal-input fake-broker assertions and baseline trade-artifact hashes | 0 | Valid BUY/SELL position, pricing, entry, and close behavior remains exact; no research producer changed and both trade artifacts remain byte-identical. |
| `live-money-review` | fake-only safety evidence plus `.ai/tasks/ISSUE-103/review.md` | 1 | Builder evidence is green, but the complete independent doubly-rigorous review must rerun after narrowing the destructive safety trigger. |
| `human-decision-escalation` | task validation and spec audit | 0 | Jan's Python `int`/`IntEnum` and `str` type rule, dedicated conversion-failure behavior, draft status, and merge authority are explicit; halt persistence remains in #122. |
| `no-autonomous-merge` | PR #105 state audit | 0 | PR #105 remains open and draft; auto-merge is absent and no ready/merge action occurred. |

### Additional evidence

| Check | Command | Exit status | Result |
|---|---|---:|---|
| `red-current-code` | focused review tests before production changes | 1 | Six failures: two integer-subtype cases, two string-subtype cases, runner conversion failure escaped, and one failed market lookup aborted the flatten loop. |
| `red-hand-mutants` | exact temporary `if not raw`, validation-after-no-stop, and `owned_positions()[:1]` mutations; three dedicated tests | 1 | All three tests failed independently: flat account raised, invalid stop-less side returned, and the second owned position disappeared. The intended source was restored immediately. |
| `red-broad-exception` | focused execute-mode conversion/transient-read tests against the reviewed code | 1 | Three failures: transient `symbol_info` and `positions_get` errors were swallowed, liquidated tickets 11/12, and halted permanently; the next healthy `must_flatten` cycle could not run. |
| `loose-equality` | four `_LooselyEqual` boundary tests | 0 | Raw position, pricing, placement, and close all raise their full distinct error with zero terminal calls. This replaces the former test-plan overclaim with executable proof. |
| `review-focused-green` | `uv run pytest -q tests/test_live_mt5_bridge.py tests/test_live_runner_cycle.py` | 0 | 84 tests passed after the P1/P2 dispositions. |
| `risk-classification` | `uv run python -m scripts.quality.classify $(git diff --name-only origin/main...HEAD)` | 0 | R3 because the live broker bridge, runner safety consumer, mutation policy, and invariant gate change. |
| `finding-registry` | ID audit across fetched origin branches and registry tests | 0 | F-037/F-040/F-041 remain intact; F-042 was free and generalizes a broad transport exception triggering destructive safety action. |
| `impact` | `uvx --from rust-just just impact origin/main` | 0 | `live/mt5_bridge.py` and `live/runner.py` select all configured direct/transitive consumers; 145 impacted tests passed and no unknown dynamic edge was reported. |
| `security` | `uvx --from rust-just just check-security` | 0 | Secret scan clean, pip-audit reports no known vulnerabilities, and Ruff security checks passed. |
| `pr-ready` | `uv run python -m scripts.quality.pr_ready ISSUE-103 --base origin/main` | 1 | Correctly reports NOT READY on the pending `adversarial-review` and `live-money-review`; all builder-controlled gates pass and evidence binds the non-evidence HEAD. |

## Red-first proof

The review fixes have two independently recorded RED states.

First, tests-only execution against the reviewed code produced six failures:

- integer subclasses representing `POSITION_TYPE_BUY` and `POSITION_TYPE_SELL` were rejected;
- string subclasses representing `BUY` and `SELL` were rejected;
- a `positions()` `Mt5Error` escaped `run_once()` while `_halted` remained false;
- an `owned_positions()` failure for the first market aborted the entire flatten loop.

Second, the three exact hand-built bridge mutants were applied temporarily:

- `raw is None` to `not raw`;
- side validation moved below the `sl <= 0` return;
- the owned-position result truncated with `[:1]`.

Their three dedicated tests all failed. Restoring the intended source makes them green.

Third, the complete independent re-review's execute-mode transient-fault tests ran against the
reviewed production code with two owned positions. The focused command produced three failures:

- `symbol_info` and account-wide `positions_get` faults did not propagate because the broad
  `except Mt5Error` converted both into a permanent safety halt;
- both transient faults closed tickets 11 and 12 despite healthy 100,000 equity;
- the permanent halt made the next healthy cycle return before `must_flatten` could evaluate a
  real 90,000-equity trailing breach.

The conversion-failure test was also changed from signal-only with an empty book to
`Mode.EXECUTE` with the two owned opposite-side positions. It requires the dedicated semantic
failure to halt, alert exactly once, and close the exact two tickets. A dedicated `Mt5SideError`
makes all four tests green while ordinary `Mt5Error` reads remain loud and retryable.

The invalid complement includes `True`, `False`, `0.0`, `"0"`, `None`, unknown integers, malformed
strings, and an object whose equality always returns `True`. Every rejected value is asserted to
leave pricing, tick, filling, and order-send counters at zero.

## Mutation evidence

The mutation sequence was deliberately fail-closed:

1. Run `30353847656` proved every reviewer-supplied bridge mutant killed. A deliberately broad
   first runner registration measured 4,557/5,051 killed with 494 survivors: main's 410 plus 84
   unrelated survivors from the large legacy `run_once()` / `_halt_and_flatten()` bodies. None was
   classified or admitted to the baseline.
2. The changed runner logic was isolated without behavior change into
   `_apply_cycle_safety()` and `_owned_positions_for_flatten()`. Run `30354605318` measured
   4,506/4,923 killed and exposed seven survivors in those two helpers.
3. Exact halt-reason, immediate-cycle-return, alert, and ERROR-log assertions killed all seven.
   Final run [30355260718](https://github.com/QPlus-Capital/trading-system/actions/runs/30355260718)
   measured 4,514/4,923 killed, 409 survived, and zero unhealthy outcomes.
4. After F-042, final run
   [30362970416](https://github.com/QPlus-Capital/trading-system/actions/runs/30362970416)
   again measured 4,514/4,923 killed, 409 survived, and zero unhealthy outcomes. It passed the
   existing exact baseline unchanged, proving the dedicated side exception and narrow catch add no
   survivor or classification.

The final survivor set contains no new name and no new classification. It is one name tighter than
main because the new consumer tests kill the formerly allowed
`live.risk_control.xǁRiskControllerǁmust_flatten__mutmut_3`. The exact baseline now has 409 names
and the retained report passes `check_baseline` with `issues=[]`.

## Numerical and artifact parity

No signal, side, price, quantity, risk limit, sizing amount, research stage, or reporting producer
changed. Valid bridge requests remain exact-pinned. The runner's failure behavior changes
materially and deliberately: a semantic `Mt5SideError` still halts, alerts, and execute-mode
flattens, while routine `symbol_info` or `positions_get` `Mt5Error` reads close nothing, leave the
runner unhalted, and propagate to the established logged polling retry. Daily/trailing hard stops
still execute before open-risk reconstruction, and one failed ownership lookup during a real halt
still cannot suppress flattening in later markets.

- `portfolio_trades.csv`:
  `b5a0a9bb6d19ccee85c35aa6570a3bd67ea8fd885665d92901e5f14113f45129`;
- `full_history_trades.csv`:
  `27592d20dda0fb3b31eb06de69d4d760d0f16cd961f2872e4f6376acb3dd90dc`.

Both remain byte-identical. No reported number moved.

## Live safety attestation

Every test replaces terminal behavior with in-memory fakes. No command initialized or connected
MT5, inspected an account, restarted a runner, or placed, modified, or closed an order. Neither
running live runner was touched.

## Coverage and mutation

The final deterministic suite has 1,260 passing tests, the impacted set has 145, the critical
invariant suite has 409, and 21 properties pass twice at the fixed seed. Linux mutation has 4,514
of 4,923 mutants killed, 409 exact-name inherited survivors, and zero unhealthy results. No
baseline change was needed; no test, target, threshold, comparison rule, risk limit, or valid live
behavior is weakened.

## Deferred checks

The Linux mutation gate and every builder-controlled gate are complete. The blockers are the fresh
complete independent adversarial and live-money reviews required by the material P1 disposition.
Jan retains the merge decision; PR #105 must remain draft. Halt-state persistence remains out of
scope in issue #122.
