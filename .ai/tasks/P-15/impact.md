# Impact analysis

## Direct impact

- Dashboard operators see the issue #40 guidance in German.
- A focused rendering test protects the risk and history copy.
- The existing language guard ignores German only inside direct dashboard Streamlit rendering
  literals while continuing to scan comments, docstrings, logs, identifiers, and indirect strings.

## Transitive impact

None. Literal text is passed directly to Streamlit and is not parsed, persisted, logged, or
consumed by another module. No caller, configuration route, artifact schema, or data calculation
changes.

## Critical dependencies

- Streamlit renders the translated literals.
- The behavioral test replaces dashboard data functions and Streamlit calls with in-memory fakes;
  the repository's autouse MT5 boundary remains active.

## Unknown or dynamic edges

None. The strings are static UI output and have no reflection or dynamic dispatch.

## Scope audit

The final `just impact origin/main` result and forbidden-path diff are recorded in `evidence.md`.
Expected direct production impact is exactly `monitoring/dashboard.py`; `research/stages/**`, logs,
governance, live code, and research calculations are excluded.
