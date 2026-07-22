# P-15: German dashboard operator copy

## Problem

`monitoring/dashboard.py` still renders English operator guidance even though constitution section
1 requires German runtime copy for the dashboard.

## Goal

Translate the issue #40 build contract's bounded dashboard strings to German and add a behavioral
rendering guard that prevents the key risk and history captions from returning to English.

## Non-goals

- No changes to `AGENTS.md`, `CLAUDE.md`, `docs/engineering/constitution.md`, or other governance.
- No changes to `research/stages/**`, dashboard logic, monitoring calculations, data flow, charts,
  configuration, dependencies, or live code.
- No translation of source identifiers, comments, docstrings, documentation, or log messages.
- No attempt to translate every dashboard control, chart heading, metric, or table column beyond
  the operator guidance explicitly named by the pinned build contract.

## Behavioural requirements

- Preserve every Streamlit call, branch, interpolated value, and formatting instruction; replace
  only the human-readable literals named by the build contract.
- Render the risk state, history integrity/window guidance, empty states, warnings, and explanatory
  captions in idiomatic German suitable for the sole operator.
- Keep diagnostic logs and non-runtime source artifacts in English.

## Acceptance criteria

- AC-01: The open-risk metric label, indeterminate value, both help texts, and unpriceable-risk
  error render in German without changing the determinate/indeterminate decision.
- AC-02: The incomplete-history and hidden-history-window captions render in German and preserve
  every interpolated value.
- AC-03: Existing `st.info`, `st.warning`, and `st.caption` runtime guidance in the dashboard is
  German, including live/research empty states and comparison guidance.
- AC-04: A behavioral test invokes the live dashboard view with faked data and asserts the rendered
  risk, history, empty-trade, and empty-position output is German; it fails before translation.
- AC-05: The classifier reports R2, impact remains confined to the dashboard and its test, and all
  cumulative R2 gates pass.

## Invariants

- INV-01: Only operator-facing string literals change in production; control flow, calculations,
  function signatures, and data structures remain byte-for-byte equivalent.
- INV-02: Log messages stay English, and committed source, comments, docstrings, tests, task
  artifacts, and commit messages stay English apart from asserted/runtime German literals.
- INV-03: `research/stages/**`, `AGENTS.md`, `CLAUDE.md`, and the constitution remain untouched.
- INV-04: Tests never connect to MetaTrader 5 or interact with a live runner or account.

## Scope

- `monitoring/dashboard.py`
- One focused behavioral test under `tests/`
- `.ai/tasks/P-15/`

## Assumptions

- Streamlit does not parse these literals into control state; they are display-only arguments.
- German umlauts and punctuation are valid UTF-8 source literals under the repository toolchain.

## Expected artifacts

- One literal-only production diff in `monitoring/dashboard.py`.
- One focused behavioral rendering test.
- The five validated `.ai/tasks/P-15/` files.

## Risk class

R2. `scripts/quality/classify.py monitoring/dashboard.py` reports R2 because the file governs
live-vs-backtest monitoring semantics. The string-only scope does not warrant a manual upgrade.

## Human decisions required

None. Constitution section 1 and the pinned issue #40 build contract already decide language,
placement, scope, and exclusions. Jan retains merge authority; Claude reviews the ready PR.

## Open questions

None.
