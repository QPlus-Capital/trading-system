# Test plan

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01, INV-02 | `test_positions_fail_closed_on_unknown_position_type` | RED: three cases `DID NOT RAISE`; unknown values emitted positions | GREEN: unknown integer and boolean types raise; all order counters remain zero |
| AC-02, INV-02 | `test_loss_for_order_fails_before_pricing_invalid_side` | RED: four cases `DID NOT RAISE`; invalid strings reached SELL pricing | GREEN: all invalid strings raise with zero pricing/order calls |
| AC-03, INV-02 | `test_loss_to_stop_fails_before_pricing_invalid_position_side` | RED: `DID NOT RAISE`; invalid position side reached SELL pricing | GREEN: raises with zero pricing/order calls |
| AC-04, INV-02 | `test_place_order_fails_before_terminal_calls_for_invalid_side` | RED: `DID NOT RAISE`; a SELL request was sent | GREEN: raises before tick, filling, or order calls |
| AC-05, INV-02 | `test_close_position_fails_before_terminal_calls_for_invalid_side` | RED: `DID NOT RAISE`; a BUY close request was sent | GREEN: raises before tick, filling, or order calls |
| AC-06, INV-03 | `test_legal_order_sides_preserve_pricing_and_entry_requests` | Existing behavior newly pinned | GREEN: exact BUY/SELL pricing calls, prices, request fields, and results |
| AC-07, INV-03 | `test_legal_position_sides_preserve_close_requests` | Existing behavior newly pinned | GREEN: exact opposing order types, prices, request fields, and results |
| AC-08, INV-04 | source audit, finding-registry test, mutation policy test | Catch-all branches and history-only mutation target | GREEN locally: one converter, five consumers, F-037, focused patterns; Linux execution blocked |
| AC-09, INV-07 | cumulative local R3 gates and `pr-ready ISSUE-103` | Not applicable | Local gates green; readiness blocked by missing Linux mutation evidence |
| INV-01 | autouse MT5 boundary plus synthetic fake assertions | Existing safety fixture | GREEN: no real terminal import, initialization, connection, or order |
| INV-05, INV-06 | production-path diff and baseline artifact SHA-256 comparison | Main baseline | GREEN: no research/report producer diff; both CSV hashes unchanged |

## Red-first command

The five invalid-boundary tests ran against unmodified production code before the converter. The
focused command exited 1 with ten failures: every case reported `DID NOT RAISE Mt5Error`. Inspection
of the pre-change branches confirms those accepted values selected SELL pricing/order types, or an
opposing BUY close. The same command passes after the implementation and every counter remains
zero.

## Adversarial cases

- Unknown positive and negative integer position types.
- Boolean input, which must not alias MT5's integer `0`/`1` constants.
- Lowercase, whitespace-padded, empty, and arbitrary side strings.
- A custom object that compares loosely but is not a supported runtime representation.
- BUY and SELL at all five call sites, checking exact legal request parity.
- Invalid values when no symbol/tick/filling information is available, proving validation occurs
  before those dependencies.
