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
| AC-06, INV-03 | `test_positions_preserve_every_authoritative_terminal_field`; `test_owned_positions_forward_the_filter_and_exclude_foreign_magic` | RED under fourteen position survivors and two `no tests` mutants | GREEN: full position equality, symbol-filter forwarding, and ownership are independently pinned |
| AC-06, INV-03 | default entry/close request and broker-failure tests | RED under nineteen request/default/failure survivors | GREEN: complete fake-broker requests and full distinct failures are pinned |
| AC-06, INV-03 | zero/one-stop and non-loss pricing tests | RED under four loss-boundary survivors | GREEN: exact stop boundary, pricing tuple, and zero loss are pinned |
| AC-08, INV-04 | source audit, F-037/F-040 registry tests, mutation policy test | Catch-all branches plus 38 survivors and two selected `no tests` | GREEN: one converter, five consumers, generalized mutation finding, and every selected boundary executes |
| AC-09, INV-07 | Linux Critical mutation, cumulative R3 gates, and task validation | Old report: 38 branch survivors, two selected `no tests` | Final measured result and exact baseline recorded in `evidence.md`; PR remains draft pending full independent review |
| INV-01 | autouse MT5 boundary plus synthetic fake assertions | Existing safety fixture | GREEN: no real terminal import, initialization, connection, or order |
| INV-05, INV-06 | production-path diff and baseline artifact SHA-256 comparison | Main baseline | GREEN: no research/report producer diff; both CSV hashes unchanged |

## Red-first command

The five invalid-boundary tests ran against unmodified production code before the converter. The
focused command exited 1 with ten failures: every case reported `DID NOT RAISE Mt5Error`. Inspection
of the pre-change branches confirms those accepted values selected SELL pricing/order types, or an
opposing BUY close. The same command passes after the implementation and every counter remains
zero.

Linux run `30339340183` then supplied the second RED state: 38 unexplained branch survivors and two
selected mutants with `no tests`. Exact trampoline replay against the new behavioural suite kills
33 of the 38 old survivors plus both `owned_positions` no-test mutants. The remaining five were
semantically meaningful default mutations that Mutmut's unchanged wrapper default made
unobservable; they are not classified. The untestable representation is removed while preserving
the API behavior: `_order_type` receives `opposite` explicitly, and `place_order`/`close_position`
defaults reference module constants. Regeneration confirms those five signature mutants no longer
exist.

## Adversarial cases

- Unknown positive and negative integer position types.
- Boolean input, which must not alias MT5's integer `0`/`1` constants.
- Lowercase, whitespace-padded, empty, and arbitrary side strings.
- A custom object that compares loosely but is not a supported runtime representation.
- BUY and SELL at all five call sites, checking exact legal request parity.
- Invalid values when no symbol/tick/filling information is available, proving validation occurs
  before those dependencies.
