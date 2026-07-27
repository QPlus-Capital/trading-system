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
