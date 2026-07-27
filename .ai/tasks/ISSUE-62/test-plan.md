# Test plan

| Requirement | Test | Before | After |
|---|---|---|---|
| AC-01 | `test_real_adapters_emit_identical_signal_sequence` | No behavioural adapter comparison | All 199 decisions equal bar-for-bar |
| AC-02 | `test_parity_harness_rejects_a_divergent_live_adapter` | RED: swapped live adapter produces a first-signal mismatch | GREEN: harness raises with the mismatch index |
| AC-03 | `test_real_adapters_emit_identical_signal_sequence` warm-up assertions | AST construction only | Both adapters emit only `(False, False)` before warm-up |
| AC-04 | Same fixture final-index assertion | Final boundary not compared | Both paths process index 198 and emit `(False, True)` |
| AC-05 | `test_gate_consistency` plus critical dependency impact | Harness absent from invariant/dependency maps | Harness runs in invariants and maps to all three modules |
| AC-06 | Cumulative commands in `evidence.md` | Package absent | All local gates green; Linux mutation explicitly blocked |
| INV-01 | `git diff --exit-code origin/main -- core live research monitoring` | No package diff | Production trees remain byte-identical |
| INV-02 | Shared fixture/parameter identity assertions and adapter harness | No cross-adapter fixture | One tuple and one `SignalParams`; no direct-engine parity result |
| INV-03 | `_NoTerminalBridge` fail-fast fake and live replay test | No adapter harness | No bridge attribute is read |
| INV-04 | Existing import-boundary and live-parity suites | Structural-only parity | Existing guards stay green beside behavioural harness |
| INV-05 | Production diff plus current baseline SHA-256 audit | No package | Both trade artifact hashes unchanged |
| INV-06 | `pr-ready ISSUE-62 origin/main` and draft PR state | No package | NOT READY only for blocked mutation; PR remains draft |

## Red-first procedure

Implement the parity oracle and initially invoke it against a deliberately buy/sell-swapped live
adapter without catching the assertion. The focused test must fail at the first non-zero signal.
Then express the permanent guard as an expected `AssertionError` and rerun both focused tests.

## Integration and parity

- Drive the real Nautilus `on_bar` method with native Nautilus bars.
- Drive the real live `_replay_signal` method for every prefix with native live bars.
- Keep the bridge fake terminal-hostile and do not invoke `run_once`.
- Run the existing structural and feed-parity tests together with the new adapter harness.

## Mutation focus

The Linux Critical mutation job is unavailable until quota reset. The critical dependency map
ensures future changes to the signal engine or either adapter select this harness. No production
mutation target changes in this test-only package.
