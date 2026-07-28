# Evidence

## HEAD

HEAD: ef8d06595c1cba17c9ce5b3f2acb581ad975c26d

The only later commit permitted by readiness is this evidence file itself.

## Commands

### Required gates

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `format` | `uvx --from rust-just just --shell powershell.exe --shell-arg -NoProfile --shell-arg -Command check-fast origin/main` | 0 | All four changed Python files are formatted; Ruff, strict mypy, and 152 impacted tests passed. |
| `docs-consistency` | full `just check` plus task validation | 0 | Engineering-document and gate-consistency tests passed inside the 1,267-test suite. |
| `check` | `uvx --from rust-just just --shell powershell.exe --shell-arg -NoProfile --shell-arg -Command check` with `PYTHONUTF8=1` | 0 | Ruff, strict mypy over 181 files, Vulture, and pytest passed: 1,267 passed, 1 Windows-only mutation self-test skipped. |
| `impacted-tests` | `uvx --from rust-just just --shell powershell.exe --shell-arg -NoProfile --shell-arg -Command check-fast origin/main` | 0 | Both changed production files selected all configured bridge, runner, risk, monitoring, sizing, swap, and parity consumers; 152 tests passed. |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | 0 | 21 property tests passed twice at fixed Hypothesis seed `20260721`. |
| `integration-tests` | `uv run pytest -q tests/test_live_mt5_bridge.py tests/test_live_runner_cycle.py` plus `check-fast` | 0 | 91 direct bridge/runner-cycle tests and 152 complete impacted tests passed using synthetic fakes only. |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task --task-id ISSUE-103 --base origin/main` | 0 | Task ISSUE-103 is valid with 15 acceptance criteria and 9 invariants. |
| `adversarial-review` | `.ai/tasks/ISSUE-103/review.md` | 1 | The complete re-review found F1/F2/F3/F5; all are dispositioned with executable evidence, but the material P1 live-path fix requires one further complete independent review. |
| `invariants` | `uvx --from rust-just just --shell powershell.exe --shell-arg -NoProfile --shell-arg -Command check-invariants` | 0 | 416 critical invariant tests passed; the suite directly exercises the MT5 bridge and runner safety cycle. |
| `mutation-on-touched-critical` | Linux Critical mutation run `30377331484` | 0 | 4,978 total, 4,569 killed, 409 survived, 0 no-tests, and every other unhealthy status 0. The refreshed exact baseline passed; 55 measured mutants and 55 kills were added, with no survivor or classification added. |
| `parity-where-applicable` | legal-input fake-broker assertions and baseline trade-artifact hashes | 0 | Valid BUY/SELL position, pricing, entry, and close behavior remains exact; no research producer changed and both trade artifacts remain byte-identical. |
| `live-money-review` | fake-only safety evidence plus `.ai/tasks/ISSUE-103/review.md` | 1 | Builder evidence is green, but the complete independent doubly-rigorous review must rerun after narrowing the destructive safety trigger. |
| `human-decision-escalation` | task validation and spec audit | 0 | Jan's integral index-protocol rule with explicit bool rejection, independent raw-magic ownership filter, dedicated conversion-failure behavior, draft status, and merge authority are explicit; halt persistence remains in #122. |
| `no-autonomous-merge` | PR #105 state audit | 0 | PR #105 remains open and draft; auto-merge is absent and no ready/merge action occurred. |

### Additional evidence

| Check | Command | Exit status | Result |
|---|---|---:|---|
| `red-current-code` | focused review tests before production changes | 1 | Six failures: two integer-subtype cases, two string-subtype cases, runner conversion failure escaped, and one failed market lookup aborted the flatten loop. |
| `red-hand-mutants` | exact temporary `if not raw`, validation-after-no-stop, and `owned_positions()[:1]` mutations; three dedicated tests | 1 | All three tests failed independently: flat account raised, invalid stop-less side returned, and the second owned position disappeared. The intended source was restored immediately. |
| `red-broad-exception` | focused execute-mode conversion/transient-read tests against the reviewed code | 1 | Three failures: transient `symbol_info` and `positions_get` errors were swallowed, liquidated tickets 11/12, and halted permanently; the next healthy `must_flatten` cycle could not run. |
| `red-foreign-integral-ownership` | four focused tests before the final F1 remediation | 1 | Four failures: two index-protocol position values were rejected, a foreign invalid record poisoned both position surfaces, and the execute-mode runner halted and flattened its owned book. |
| `loose-equality` | four `_LooselyEqual` boundary tests | 0 | Raw position, pricing, placement, and close all raise their full distinct error with zero terminal calls. This replaces the former test-plan overclaim with executable proof. |
| `review-focused-green` | `uv run pytest -q tests/test_live_mt5_bridge.py tests/test_live_runner_cycle.py` | 0 | 91 tests passed after all F1-F7 dispositions. |
| `risk-classification` | `uv run python -m scripts.quality.classify $(git diff --name-only origin/main...HEAD)` | 0 | R3 because the live broker bridge, runner safety consumer, mutation policy, and invariant gate change. |
| `finding-registry` | ID audit across fetched origin branches and registry tests | 0 | F-037/F-040/F-041 remain intact; F-042 was free and generalizes a broad transport exception triggering destructive safety action. |
| `impact` | `uvx --from rust-just just --shell powershell.exe --shell-arg -NoProfile --shell-arg -Command impact origin/main` | 0 | `live/mt5_bridge.py` and `live/runner.py` select all configured direct/transitive consumers; no unknown dynamic edge was reported. |
| `security` | `uvx --from rust-just just --shell powershell.exe --shell-arg -NoProfile --shell-arg -Command check-security` | 0 | Secret scan clean, pip-audit reports no known vulnerabilities, and Ruff security checks passed. |
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

The final independent-review remediation added a fourth RED state. Before its implementation:

- two synthetic runtime values implementing `__index__` were rejected despite representing the
  documented BUY and SELL constants;
- an unsupported foreign position raised before either the account-wide or owned position list
  could be reconstructed;
- in `Mode.EXECUTE`, that foreign GBPJPY record caused the healthy runner to halt and flatten its
  two owned XAUUSD positions.

The green oracle proves both directions of the ownership boundary. Legal foreign positions remain
in `positions()` for account-wide risk; `owned_positions()` excludes them before side conversion.
An unsupported foreign record is omitted with an exact warning and cannot halt or flatten the
owned book. An unsupported owned record still raises `Mt5SideError`. `True` and `False` remain in
the invalid fixture, so removal or weakening of the explicit bool exclusion fails.

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
   then-current exact baseline, proving the dedicated side exception and narrow catch add no
   survivor or classification. The earlier PR summary was nevertheless wrong to describe the
   baseline itself as unchanged: the preceding refresh had tightened 410 survivors to 409, killed
   one inherited survivor, added none, and added one target.
5. The first complete measurement of this final review fix, run
   [30373748950](https://github.com/QPlus-Capital/trading-system/actions/runs/30373748950),
   measured 4,972 mutants with 21 unexplained PR-specific survivors. No survivor was admitted.
6. Exact account-risk visibility, foreign-record warning, halt reason, and failed-close identity
   assertions killed 18 of those 21. Run
   [30374897891](https://github.com/QPlus-Capital/trading-system/actions/runs/30374897891)
   left only three: two provable no-op expressions and one unobservable Mutmut default.
7. The code was made mutation-observable rather than classifying those three. Runtime narrowing
   removes the value-preserving `typing.cast` and unreachable sentinel; the private position
   decoder requires an explicit authoritative owner magic. Run
   [30376536794](https://github.com/QPlus-Capital/trading-system/actions/runs/30376536794)
   measured 4,569/4,978 killed with exactly the inherited 409 survivors and no unhealthy outcome.
8. The baseline was regenerated once from that final report. Final run
   [30377331484](https://github.com/QPlus-Capital/trading-system/actions/runs/30377331484)
   passed independently on implementation HEAD `ef8d065`: 4,569/4,978 killed, 409 exact-name
   survivors, and every unhealthy status zero.

The current refresh adds 55 measured mutants and 55 kills relative to 4,923/4,514, while the
survivor set remains exactly 409. The score improves from 0.9169 to 0.9178. No survivor or
classification was added, `_halt_and_flatten()` is now in the measured runner target, and the
explicit bool-exclusion mutants are killed. The retained report compares with the committed
baseline using `check_baseline(...)=[]`.

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

The final deterministic suite has 1,267 passing tests, the impacted set has 152, the critical
invariant suite has 416, and 21 properties pass twice at the fixed seed. Linux mutation has 4,569
of 4,978 mutants killed, 409 exact-name inherited survivors, and zero unhealthy results. The
baseline adds 55 measured mutants and 55 kills without adding a survivor or classification; no
test, threshold, comparison rule, risk limit, or valid live behavior is weakened.

## Deferred checks

The Linux mutation gate and every builder-controlled gate are complete. The blockers are the fresh
complete independent adversarial and live-money reviews required by the material P1 disposition.
Jan retains the merge decision; PR #105 must remain draft. Halt-state persistence remains out of
scope in issue #122.
