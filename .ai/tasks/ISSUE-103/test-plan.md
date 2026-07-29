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
| AC-08, INV-04 | source audit, F-037/F-040/F-041 registry tests, mutation policy test | Catch-all branches plus 38 survivors, two selected `no tests`, and uncovered safety consumers | GREEN: one converter, five bridge boundaries, safety consumers, generalized findings, and every selected boundary executes |
| AC-09, INV-07 | Linux Critical mutation, cumulative R3 gates, and task validation | Old report: 38 branch survivors, two selected `no tests` | Final measured result and exact baseline recorded in `evidence.md`; PR remains draft pending full independent review |
| AC-10, INV-02 | runtime integer/string subtype tests and four loose-equality boundary tests | RED: four subtype cases raised instead of reaching the documented BUY/SELL action | GREEN: runtime subtypes preserve the exact legal action; loose-equality impostors raise their boundary's full error with zero terminal calls |
| AC-11, INV-03 | flat-account test and extended owned-position completeness test | RED against review mutants: empty sequence raised; two owned positions were truncated to one | GREEN: both empty surfaces return `[]`; the exact two owned positions survive in terminal order and the foreign position is excluded |
| AC-12, INV-02 | `test_loss_to_stop_rejects_invalid_side_even_without_a_stop` | RED against review mutant: no-stop early return bypassed validation | GREEN: the full side error is raised before any pricing call |
| AC-13, INV-08 | execute-mode conversion halt, transient `symbol_info`/`positions_get`, subsequent healthy-cycle, and safety-cutoff-order tests | RED: three transient-read tests did not raise because the broad catch halted and liquidated the two-position fixture; conversion coverage was signal-only and vacuous | GREEN: only `Mt5SideError` halts, alerts, and flattens the exact two owned positions; routine reads close nothing and remain retryable; a subsequent real breach still flattens |
| AC-14, INV-08 | `test_halt_and_flatten_closes_every_owned_position_when_one_lookup_fails` | RED: first market lookup exception aborted the entire flatten method | GREEN: failure is alerted and the exact two retrievable later-market positions close |
| AC-10, INV-02 | `test_position_types_accept_the_integral_index_protocol`; existing boolean complement cases | RED: two index-protocol integral values raised `Mt5SideError` | GREEN: BUY/SELL index values map exactly while `True` and `False` still raise |
| AC-15, INV-09 | `test_foreign_unknown_type_cannot_poison_account_or_owned_positions`; `test_foreign_unknown_position_type_never_halts_or_flattens_owned_book` | RED: bridge conversion raised; execute mode halted and entered the flatten path | GREEN: the foreign record is omitted before it can poison owned conversion, the runner remains active, and tickets 11/12 remain open |
| AC-16, INV-05 | `test_foreign_unknown_position_type_blocks_new_risk_without_halting`; `test_load_live_surfaces_an_undecodable_position_as_unpriceable` | RED: both stop variants placed a BUY and charged only 110.1 open risk; dashboard reported no unpriceable market | GREEN: both variants set infinite risk, place and close nothing, stay unhalted, and make GBPJPY unpriceable in the dashboard |
| AC-17, INV-08 | `test_runner_halts_loudly_and_flattens_retrievable_positions_from_real_bridge`; `test_trailing_breach_flattens_each_retrievable_owned_raw_position` | RED: the real bridge raised the whole owned batch, closed no ticket, and emitted only a generic enumeration alert | GREEN: both semantic and trailing-limit halts close ticket 11 and alert specifically for undecodable ticket 13 |
| AC-18, INV-02 | `test_position_type_value_error_is_classified_as_a_side_error`; `test_position_magic_value_error_is_classified_before_direction` | RED: both failures escaped as bare `ValueError` | GREEN: both raise the complete boundary-specific `Mt5SideError` before any order call |
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

The independent review supplied the next RED state. With tests only applied, six cases failed:
two integer-subtype cases, two string-subtype cases, the runner conversion-failure case, and the
partial-lookup flatten case. The exact three hand-built mutants for `if not raw`, validation after
the no-stop return, and `owned_positions()[:1]` were then applied together; their dedicated tests
failed independently. Restoring the intended code makes all nine guards green. The loose-equality
object tests satisfy the previously overclaimed adversarial case and pass only because unsupported
comparison semantics never enter side selection.

Linux run `30354605318` then selected the two extracted runner helpers and exposed seven survivors:
three missing halt-reason/immediate-return assertions and four missing exact error-log assertions.
All seven were reconstructed from their exact Mutmut bodies and killed by the focused runner
tests. Final run `30355260718` reports 4,923 total, 4,514 killed, 409 survived, and zero unhealthy
outcomes. It adds no survivor or classification and kills the formerly allowed
`live.risk_control.xǁRiskControllerǁmust_flatten__mutmut_3`.

The complete independent re-review supplied a further RED state for F-042. With two owned positions
in execute mode, three focused tests failed: a transient `symbol_info` error and a transient
account-wide `positions_get` error were swallowed by `_apply_cycle_safety`, both liquidated the
book and halted permanently, and the intended next-cycle `must_flatten` check could not execute.
The conversion-halt fixture itself passed only after being made non-vacuous with execute mode and
two owned opposite-side positions. A dedicated `Mt5SideError` separates ambiguous side conversion
from routine `Mt5Error` reads; the same four-test command is green after the fix.

The next complete re-review supplied the F-047 RED state. Two non-`int` objects implementing
`__index__` were rejected despite carrying legal MT5 values. A foreign GBPJPY record with magic 999
and type 7 caused a healthy execute-mode runner to halt and enter flattening against its two owned
XAUUSD positions. The three focused tests failed four cases before the fix. After raw ownership is
read before conversion and `operator.index` defines integral semantics, all four pass; the existing
`True`/`False` complement tests keep the boolean alias closed.

The fourth complete re-review supplied the F-048/F-049 RED state. The focused fake-only command
exited 1 with nine failures: the bridge exposed no completeness snapshot; `operator.index`
`ValueError` failures escaped unclassified for side and magic; the real-bridge owned batch closed
no retrievable ticket; both stopped and stop-less foreign invalid records let a BUY through with
only 110.1 risk charged; and monitoring reported no unpriceable market. The same 114-test command
passes after the shared snapshot and per-record flatten implementation.

## Adversarial cases

- Unknown positive and negative integer position types.
- Boolean input, which must not alias MT5's integer `0`/`1` constants.
- Lowercase, whitespace-padded, empty, and arbitrary side strings.
- A custom object that compares loosely but is not a supported runtime representation.
- BUY and SELL at all five call sites, checking exact legal request parity.
- Invalid values when no symbol/tick/filling information is available, proving validation occurs
  before those dependencies.
- A conversion failure and two routine read failures against the same non-empty execute-mode book,
  proving only the semantic conversion failure liquidates.
- An unsupported foreign/manual position before two valid owned positions, proving independent
  magic ownership prevents a malformed unowned record from halting or flattening the owned book.
- The same unsupported foreign position with and without a stop, proving non-actionability cannot
  erase it from account-wide risk or the operator display.
- One valid and one invalid owned raw record through the real bridge, proving batch decoding cannot
  erase a retrievable safety close.
- A transient failure followed by a healthy breached cycle, proving retryability does not disable
  the later hard stop.
