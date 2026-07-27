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
