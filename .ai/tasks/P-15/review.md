# Adversarial review

## Findings

No findings; 11 counterexamples attempted

## Dispositions

- Normalized-string AST comparison proves the production change contains no logic or structural
  difference from post-P-14 `origin/main`; P-14's snapshot, ticket-order, and Decimal paths remain
  exact.
- The language exception was challenged with German in a direct Streamlit literal, a source
  comment, `log.warning`, and a raised exception; only the direct operator literal is excluded
  from scanning.
- Both determinate and indeterminate open-risk branches render German labels and help; the blocked
  state also renders the German error without showing headroom.
- The complete set of direct caption/warning/error/info literals, metric labels, metric help, and
  metric deltas is exact-ratcheted; new or reverted English copy fails the guard.
- The MT5 read failure keeps the English exception payload intact while rendering its operator
  guidance in German.
- Incomplete-history and hidden-window captions preserve the interpolated balances and hidden count.
- The rendering guard replaces MT5 and dashboard inputs before invoking `_live_view`; the autouse
  terminal boundary remains active and no live process is called.
- A call-site audit finds no scoped English caption, warning, error, info, metric label, help, or
  delta left.
- The forbidden-path diff confirms shared configuration and architecture/testing documentation
  equal main exactly; the PR changes no research-stage, core, research, live, or non-dashboard
  monitoring logic.

Claude's independent pull-request review remains the next workflow phase.
