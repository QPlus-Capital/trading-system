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
