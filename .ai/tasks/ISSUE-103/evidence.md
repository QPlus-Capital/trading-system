# Evidence

## HEAD

HEAD: e154833a8ed3026888b3c5379907746be631bc6e

The only later commit permitted by readiness is this evidence file itself.

## Commands

### Required gates

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `format` | `uvx --from rust-just just check-fast origin/main` | 0 | Ruff format/check and strict mypy passed; 142 impacted tests passed. |
| `docs-consistency` | full `just check` plus task validation | 0 | Engineering-document and gate-consistency tests passed inside the 1,257-test suite. |
| `check` | `uvx --from rust-just just check` | 0 | Ruff, strict mypy over 181 files, Vulture, and pytest passed: 1,257 passed, 1 Windows-only mutation self-test skipped. |
| `impacted-tests` | `uvx --from rust-just just check-fast origin/main` | 0 | Both changed production files selected the bridge, runner, risk, monitoring, sizing, swap, and parity consumers; 142 tests passed. |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | 0 | 21 property tests passed twice at fixed Hypothesis seed `20260721`. |
| `integration-tests` | focused bridge/runner suite and `check-fast` recommended command | 0 | 77 direct bridge/runner-cycle tests and 142 complete impacted tests passed using synthetic fakes only. |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task --task-id ISSUE-103 --base origin/main` | 0 | Task ISSUE-103 is valid with 14 acceptance criteria and 8 invariants. |
| `adversarial-review` | `.ai/tasks/ISSUE-103/review.md` | 1 | Five P2 findings are dispositioned with executable evidence, but the material live-path remediation requires the complete independent review to run again. |
| `invariants` | `uvx --from rust-just just check-invariants` | 0 | 406 critical invariant tests passed; the suite now directly includes the MT5 bridge and runner cycle. |
| `mutation-on-touched-critical` | Linux run `30355260718`, retained report, then repository `check_baseline` against the regenerated exact baseline | 0 | 4,923 total, 4,514 killed, 409 survived, 0 no-tests, and every other unhealthy status 0. Comparator result is `issues=[]`; no new survivor was added or classified. |
| `parity-where-applicable` | legal-input fake-broker assertions and baseline trade-artifact hashes | 0 | Valid BUY/SELL position, pricing, entry, and close behavior remains exact; no research producer changed and both trade artifacts remain byte-identical. |
| `live-money-review` | fake-only safety evidence plus `.ai/tasks/ISSUE-103/review.md` | 1 | Builder evidence is green, but the complete independent doubly-rigorous review must rerun after the material runner/bridge changes. |
| `human-decision-escalation` | task validation and spec audit | 0 | Jan's runtime-compatible type rule, fail-closed consumer behavior, draft status, and merge authority are explicit. |
| `no-autonomous-merge` | PR #105 state audit | 0 | PR #105 remains open and draft; auto-merge is absent and no ready/merge action occurred. |

### Additional evidence

| Check | Command | Exit status | Result |
|---|---|---:|---|
| `red-current-code` | focused review tests before production changes | 1 | Six failures: two integer-subtype cases, two string-subtype cases, runner conversion failure escaped, and one failed market lookup aborted the flatten loop. |
| `red-hand-mutants` | exact temporary `if not raw`, validation-after-no-stop, and `owned_positions()[:1]` mutations; three dedicated tests | 1 | All three tests failed independently: flat account raised, invalid stop-less side returned, and the second owned position disappeared. The intended source was restored immediately. |
| `loose-equality` | four `_LooselyEqual` boundary tests | 0 | Raw position, pricing, placement, and close all raise their full distinct error with zero terminal calls. This replaces the former test-plan overclaim with executable proof. |
| `review-focused-green` | `uv run pytest -q tests/test_live_mt5_bridge.py tests/test_live_runner_cycle.py` | 0 | 77 tests passed after all five dispositions. |
| `risk-classification` | `uv run python -m scripts.quality.classify $(git diff --name-only origin/main...HEAD)` | 0 | R3 because the live broker bridge, runner safety consumer, mutation policy, and invariant gate change. |
| `finding-registry` | ID audit across main/open branches and registry tests | 0 | F-037/F-040 remain intact; F-041 was free and generalizes external-runtime representations plus consumer read failures disabling safety. |
| `impact` | `uvx --from rust-just just impact origin/main` | 0 | `live/mt5_bridge.py` and `live/runner.py` select all configured direct/transitive consumers; no unknown dynamic edge was reported. |
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

The final survivor set contains no new name and no new classification. It is one name tighter than
main because the new consumer tests kill the formerly allowed
`live.risk_control.xǁRiskControllerǁmust_flatten__mutmut_3`. The exact baseline now has 409 names
and the retained report passes `check_baseline` with `issues=[]`.

## Numerical and artifact parity

No signal, side, price, quantity, risk limit, sizing amount, research stage, or reporting producer
changed. Valid bridge requests remain exact-pinned. The runner changes only failure ordering:
daily/trailing hard stops execute before an unverifiable open-risk read; a later rejected read halts
and alerts; one failed ownership lookup no longer suppresses flattening in later markets.

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

The final deterministic suite has 1,257 passing tests, the impacted set has 142, the critical
invariant suite has 406, and 21 properties pass twice at the fixed seed. Linux mutation has 4,514
of 4,923 mutants killed, 409 exact-name inherited survivors, and zero unhealthy results. The ratchet
tightens by one; no test, target, threshold, comparison rule, risk limit, or valid live behavior is
weakened.

## Deferred checks

The Linux mutation gate and every builder-controlled gate are complete. The sole blocker is the
fresh complete independent live-money review required by the material dispositions. Jan retains the
merge decision; PR #105 must remain draft.
