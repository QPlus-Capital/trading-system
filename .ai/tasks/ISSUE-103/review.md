# Adversarial review

## Findings

No findings; 12 counterexamples attempted

## Dispositions

- Unknown raw types `-1`, `2`, and boolean `True` were rejected before a `Position` was emitted;
  the exact-type check prevents Python's boolean/integer alias from becoming a side.
- Empty, lowercase, padded, and unsupported internal strings were rejected without normalization;
  permissive case-folding or trimming cannot create an executable direction.
- Invalid sides in both pricing methods left `order_calc_profit` at zero calls.
- Invalid entry and close sides left tick lookup, filling-mode lookup, and `order_send` at zero
  calls, proving refusal precedes request construction rather than merely raising afterward.
- Legal BUY and SELL position records, pricing order types, entry bid/ask choices, complete entry
  request dictionaries, opposing close types, close bid/ask choices, and close request dictionaries
  match the former behavior exactly.
- The converter's position-type mode does not accept the internal string `"BUY"` as an MT5 enum,
  and its internal-side mode does not accept integer or boolean aliases.
- Source inspection confirms all five issue-defined boundaries reach the shared converter directly
  or through `_order_type`; none retains the old catch-all mapping.
- No signal, runner, risk limit, sizing, account, monitoring, research, or configuration path
  changed.
- The full suite and explicit live/monitoring integration set use synthetic fakes; no test called
  `connect`, `initialize`, or a real terminal method.
- Baseline research trade artifacts were hashed without rerunning research; neither producer nor
  artifact was modified.
- F-037 generalizes the defect, and mutation policy includes the converter and every affected
  boundary without altering the existing measured baseline.
- Lowercase values were deliberately rejected rather than normalized because accepting anything
  beyond exact BUY/SELL would reintroduce ambiguity at the live boundary.
- Independent Claude live-money review remains required before readiness or merge.

## Rebase review

Rebased onto `origin/main` at `82632060223ab83b3ebaa06154f87b00ed7f8c59` after PR #96.
Main's F-034 was preserved and issue #103's pattern was renumbered to the merge-order-reserved
F-037. The `mt5-deal-export` mutation target is the union: main's `history_deals` pattern remains
and the runtime converter, pricing, positions, placement, and close patterns are added.
`.ai/quality/mutation-baseline.toml` is unchanged. `git range-diff
8fff632..2a558ba 8263206..HEAD` shows no live implementation or test patch change beyond the
registry ID and unioned policy context. Legal/invalid side behaviour is unchanged by the rebase,
so the earlier review still covers the implementation.

Rebased again onto `origin/main` at `8851b91fbf20469d75cd9c2ee2900ccc05183f20` after PR #97.
The sole textual conflict was the append-only registry: merged F-035 and issue #103's existing
F-037 are retained in ID order. A structural TOML comparison proves every mutation target and
pattern from both main and the pre-rebase branch remains present; the mutation baseline is
unchanged. Range-diff shows the live implementation and tests remain patch-equivalent. This rebase
changes no behavior, so the earlier review continues to cover the implementation.

Rebased again onto `origin/main` at `494eafc5404bb9148c1df0887f7260b189cc36d6` after PR #98.
Merged F-035/F-036 and issue #103's F-037 are retained unchanged in ID order. Structural comparison
again proves the mutation policy is the union of main and the pre-rebase branch, while the mutation
baseline remains byte-unchanged. PR #98 changes Stage-1 research scoring and has no live bridge
consumer or configuration overlap; range-diff confirms the issue #103 live implementation and tests
remain patch-equivalent. No behavior changed, so the earlier review still covers this implementation.

## Mutation-remediation review status

The post-#100 rebase and mutation remediation are a material change to the reviewed patch. They add
complete fake-broker behavioural coverage, execute the previously uncovered `owned_positions`
boundary, and replace untestable literal defaults with behavior-identical explicit/module-constant
forms. The earlier independent review does not cover this combined implementation. A new full
independent live-money review is required; the builder does not resolve or waive that requirement.

## Independent review after mutation remediation

The independent reviewer reported no P0/P1 and five blocking P2 findings. The builder dispositions
below record remediation evidence, not a replacement review:

1. **P2 — exact built-in runtime types reject valid extension representations. Resolved.**
   `_runtime_side` now accepts integer/string subclasses with `isinstance`, explicitly excludes
   `bool`, and still rejects the existing invalid complement. Two integer-subtype and two
   string-subtype cases were RED before the fix. Loose-equality impostors are rejected at raw
   position, pricing, placement, and close boundaries with the full distinct error and zero
   terminal calls.
2. **P2 — flat-account `positions_get()` behavior was mutation-unpinned. Resolved.** Both
   `positions()` and `owned_positions()` now have a direct empty-sequence oracle. Replacing
   `raw is None` with `not raw` makes that test RED.
3. **P2 — no-stop early return could move ahead of side validation. Resolved.** An invalid side
   with `sl=0` must raise before pricing. Moving validation below the early return makes the test
   RED; the fail-closed ordering remains unchanged.
4. **P2 — bridge rejection was not covered through runner safety consumers. Resolved in the
   builder patch, pending fresh review.** The daily/trailing cut-off now precedes open-risk
   reconstruction. A later `Mt5Error` from position reconstruction halts and alerts. During an
   execute-mode halt, a failed per-market ownership lookup is alerted and isolated so retrievable
   positions in later markets still close. The former code failed both consumer tests.
5. **P2 — owned-position completeness was not pinned. Resolved.** The fixture now contains two
   owned opposite-side positions and one foreign position and asserts the exact ordered pair.
   Appending `[:1]` makes the test RED.

The test-plan overclaim is also resolved: a custom object whose equality always returns `True` is
now passed independently to `positions`, `loss_for_order`, `place_order`, and `close_position`.
Every boundary rejects it before terminal interaction.

F-041 generalizes the review defect across external runtime representation and safety-consumer
failure handling. Mutation policy includes the extracted `_apply_cycle_safety()` and
`_owned_positions_for_flatten()` consumers in addition to every bridge boundary. A first broad
runner measurement exposed 84 survivors in the surrounding legacy orchestration; none was
classified. The changed logic was isolated into those two targetable helpers instead of admitting
unrelated legacy survivors to the baseline. Because these dispositions materially change
`live/runner.py` and the live bridge, the complete independent doubly-rigorous review must run
again; this file does not mark the findings independently verified or the PR ready.

## Post-disposition mutation status

Linux run `30355260718` is the final builder measurement: 4,514 of 4,923 mutants killed, 409
survived, zero no-tests and zero other unhealthy outcomes. All four reviewer-supplied bridge
mutants and all seven extracted runner-helper survivors are killed. No PR-specific survivor is
classified. The survivor set tightens by one because the added consumer tests kill the previously
allowed `live.risk_control.xǁRiskControllerǁmust_flatten__mutmut_3`.

This is builder evidence only. The dispositions remain pending the newly requested complete
independent review, so `adversarial-review` and `live-money-review` remain non-zero in readiness.

## Complete independent re-review dispositions

The complete independent re-review verified the five earlier P2 dispositions with 11 of 11
hand-built mutants killed, 181 legal-input scenarios identical to `origin/main`, and no invalid
input producing an order that main would not have produced. It then found one P1, two blocking P2s,
and one optional P3:

1. **F1 P1 — a general bridge error liquidated healthy positions. Resolved, pending re-review.**
   `_apply_cycle_safety()` caught the bridge's general `Mt5Error`, which also represents transient
   `symbol_info` and `positions_get` failures. The converter now raises a dedicated
   `Mt5SideError`; only that semantic ambiguity triggers halt-and-flatten. Routine read errors
   propagate to `run_forever()`'s existing logged retry without changing halt state or touching the
   book. F-042 permanently records the defect class.
2. **F2 P2 — the runner fixture made liquidation assertions vacuous. Resolved, pending
   re-review.** The conversion test now runs in `Mode.EXECUTE` with two owned opposite-side
   positions and requires both exact tickets to close. Separate one-shot `symbol_info` and
   account-wide `positions_get` faults require zero closes and no halt; a subsequent healthy cycle
   at a real trailing breach must still close both tickets.
3. **F3 P2 — scope and parity evidence omitted the destructive behavior change. Resolved.** The
   spec, test plan, and evidence distinguish semantic conversion failure, routine read retry, and
   actual limit-triggered flattening. They no longer describe the runner patch as only failure
   ordering.
4. **F5 P3 — `integer runtime subclasses` was broader than the implementation. Resolved by
   narrowing documentation.** The accepted set is explicitly Python `int` subclasses including
   `IntEnum`, plus `str` subclasses, with `bool` excluded. Other `numbers.Integral`
   implementations remain rejected in the safe direction.
5. **Out of scope — halt persistence.** No code or policy was changed. Issue #122 remains the
   owner because clearing rules differ by halt cause and require Jan's decision.

The fix is material live-runner behavior and therefore invalidates the earlier review for the
changed runner path. A complete independent review must run again before either review gate can
become green; this builder disposition does not mark the PR ready.

## Complete independent re-review after the F-042 fix

The next independent review reproduced the pre-fix broad-exception liquidation, ran ten
consecutive faulting cycles, and compared 3,456 legal-input scenarios against `origin/main` with
zero divergences. Those verified F-042 behaviors are not changed by this remediation. Its seven
review points have these builder dispositions:

| ID | Severity | Review point | Disposition | Status |
|---|---|---|---|---|
| F1 | P2 | A foreign/manual record whose type is not a plain `int` can make account-wide conversion raise and liquidate the owned book. | Accept the full integral index protocol with explicit bool rejection; read magic first and prevent an unsupported unowned record from reaching destructive safety handling. Red-first bridge and execute-cycle tests pin both halves. | resolved |
| F2 | verified | The dedicated `Mt5SideError` fix is identical to main for routine faults across ten cycles. | Preserve `_apply_cycle_safety()` and its narrow catch unchanged; focused and full regression suites rerun. | resolved |
| F3 | verified | Moving daily/trailing cut-offs before open-risk reconstruction fixes main's concurrent-fault outage. | Preserve the safety ordering and the existing cutoff-before-read test unchanged. | resolved |
| F4 | P3 | The summary incorrectly says the mutation gate passed without a baseline change. | Correct evidence and PR summary: survivors tightened 410 to 409, one inherited survivor was killed, none added, and one target was added. | resolved |
| F5 | P3 | Mutation policy omits the changed `_halt_and_flatten()` loop. | Add the exact method pattern to `live-runner-fail-closed`; accept no new unexplained survivor. | resolved |
| F6 | P3 | Two runner tests raise base `Mt5Error` with side-conversion text. | Use `Mt5SideError` for the side-conversion fixture and neutral `positions_get` text for the general enumeration-failure fixture. | resolved |
| F7 | required process | This material boundary fix invalidates the current independent-review coverage. | Keep both review gates non-zero and require another complete independent adversarial/live-money review. | resolved |

F-047 generalizes F1: independent ownership metadata must be applied before an action-bearing enum
can trigger destructive behavior. This section records builder dispositions only; it does not
replace or self-approve the required independent re-review.

## Fourth complete independent re-review dispositions

The fourth review confirmed the integral/ownership change with nine foreign-position variants and
73 legal-input scenarios, then found two P1s, one P2, and two P3s at the position-read consumers:

| ID | Severity | Review point | Disposition | Status |
|---|---|---|---|---|
| F1 | P1 | Omitting an undecodable foreign record also hid its exposure from the 2% cap and dashboard. | One bridge snapshot now carries decoded positions and all decode issues. The runner maps any non-owned/unknown issue to infinite open risk and the dashboard maps it to an unpriceable market; stopped and stop-less real-bridge fixtures place and close nothing. F-048 records the generalized defect. | resolved |
| F2 | P1 | One undecodable owned record discarded the whole batch, so a genuine safety stop closed no retrievable ticket. | Safety flattening consumes a per-record owned snapshot, closes every decoded owned position, and emits a ticket-specific alert for each issue. Both semantic and genuine trailing halts run through real `Mt5Bridge.positions_get`; ticket 11 closes while ticket 13 remains loud. F-049 records the generalized defect. | resolved |
| F3 | P2 | The former runner fixture decoupled account-wide and owned reads and could not reproduce the real bridge failure. | Replace it with a synthetic raw terminal behind the real `Mt5Bridge`; both account and owned surfaces now arise from the same `positions_get` batch. | resolved |
| F4 | P3 | `operator.index` and magic conversion did not classify `ValueError`. | The shared runtime-index boundary catches `TypeError` and `ValueError`, preserves explicit bool rejection, and supplies distinct complete side/magic messages. | resolved |
| F5 | P3 | `_total_open_risk` documented completeness behavior that the code no longer provided. | The docstring now states the two observable cases exactly: undecodable non-owned/unknown exposure blocks at `inf`, while an undecodable owned side triggers the semantic halt and best-effort owned flatten. | resolved |

The scope judgment does not require splitting the PR. F1 explicitly requires the three existing
position-read consumers: bridge decoding, runner account-risk/flattening, and the dashboard's
read-only risk header. The implementation adds one shared snapshot at that boundary and does not
touch signal generation, order placement, order sizing, risk thresholds, or any research path.
No fourth production path was changed. This is nevertheless a material live-risk fix, so the
complete independent adversarial and live-money reviews must run again; these builder dispositions
do not mark either review gate green.

The mutation remediation is also complete without classification. Run `30431184595` first exposed
53 PR-specific survivors. Exact snapshot fields, per-record continuation, account-risk
accumulation, boundary warnings, and flatten alerts reduced that set to two in run `30432148064`.
The remaining boolean-ticket and early-break bodies were applied literally and made RED; run
`30432909044` then exposed a distinct fallback-overwrite survivor that the first position ordering
could not distinguish. The final mixed ordering makes both early termination and replacement of
the running total observable. Run `30433501950` measured 5,106 mutants with 4,697 killed, exactly
the inherited 409 survivors, and zero unhealthy outcomes. The baseline refresh therefore adds 128
measured mutants and 128 kills, adds no survivor or classification, and weakens no gate.

## Fifth complete independent re-review dispositions

The fifth review verified both previous-round P1 fixes and the rollback binding of the partial
flatten behavior. Those paths remain unchanged. It found two P1 defects in the six-line
account-risk issue decision and one non-binding regression fixture:

| ID | Severity | Review point | Disposition | Status |
|---|---|---|---|---|
| F1 | P1 | Returning inside the issue loop made the halt depend on whether an owned undecodable record appeared before a foreign one. | Scan the complete issue tuple for an owned or ownership-unknown record before selecting any outcome. The reviewer-supplied two-order fixture now halts in both orders. | resolved |
| F2 | P1 | `magic=None` was treated as proven foreign ownership and received only the infinite-risk outcome. | Treat `magic is None` as unverifiable ownership and raise the same dedicated semantic side error used for a known-owned record. The reviewer-supplied unreadable-magic fixture now halts. | resolved |
| F3 | P2 | The foreign-undecodable runner test delegated list reads but not either snapshot read, so it never reached the issue consumer. | Delegate both `position_snapshot()` and `owned_position_snapshot()` to the real fake-backed bridge. A temporary halt-on-any-issue mutation now makes the test fail. | resolved |

F-054 generalizes the combined failure: batch safety decisions must be order-invariant, inspect the
complete batch, and place unknown classification metadata on the conservative branch. The focused
pre-fix run was `2 failed, 2 passed`; the corrected focused run is `8 passed`, including the
previously verified owned partial-flatten and foreign-only infinite-risk outcomes. This is builder
disposition evidence only. Because the runner safety decision changed, the independent adversarial
and live-money reviews remain non-zero until Claude completes another full review.
