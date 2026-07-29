# Test plan

## Traceability

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | tracked-tree scan against the current source | RED: tracked login literals and user-home paths are found | GREEN: no production/docs login literal or user-home path |
| AC-02 | matching fake environment and `AccountState` | RED: profile API cannot consume environment keys | GREEN: profile resolves and guard returns normally |
| AC-03 | delete the selected login variable, invoke guard and fake CLI | RED: guard returns and old profile ignores the missing variable | GREEN: `SystemExit`; fake bridge records no connect |
| AC-04 | configured login differs from fake `AccountState` | RED: configured value does not feed the guard | GREEN: mismatch refusal with no value disclosure |
| AC-05 | parameterized malformed login/path values | RED: no environment parser exists | GREEN: every value refuses; raw values absent from message |
| AC-06 | parse `.env.example` | RED: four keys are absent | GREEN: exact four keys, inert placeholder values, no real path/login |
| AC-07 | inspect `justfile` and documented command | RED: commands omit `--env-file` | GREEN: every live-facing recipe loads `.env` explicitly |
| AC-08 | existing live account/CLI tests plus diff audit | RED: no environment-backed parity proof | GREEN: metadata and valid fake wiring unchanged |
| AC-09 | PR state inspection | RED: no delivery exists | GREEN: separate draft, no auto-merge, no merge |
| AC-10, INV-09 | execute preflight with distinct fake connected/expected values and capture stdout | RED: both full values printed | GREEN: neither full value appears; both `***NNN` masks appear |
| AC-11, INV-10 | canonical regex fixtures, nested-root scan, tests sentinel, plausible count, and documentation number classification | RED: canonical forms were missed, tests excluded, and nested scans partial | GREEN: exact canonical forms match and scan population is explicit |
| AC-12, INV-11 | wrong-login fakes through swap refresh, parity main, and dashboard `_load_live` | RED: swap pull executes and parity/dashboard return without refusal | GREEN: refusal precedes swap, bar, and history calls |
| AC-13, INV-12 | copy MEX login into the complete TTP environment block | RED: `get_account("ttp")` accepts the self-consistent copy | GREEN: suffix mismatch refuses before bridge construction |
| AC-14, INV-13 | write the documented layout with two Windows paths and Telegram values, then invoke real `uv run --env-file` | RED: uv warns, returns success, and drops the first backslash path plus every later value | GREEN: all six values round-trip exactly with no warning |
| AC-15, INV-13 | construct `Notifier` with both Telegram variables absent | RED: no log record | GREEN: one exact warning states that remote safety alerts are disabled |
| AC-16, INV-09 | 22-form login serialization matrix plus synthetic `.ai` suffix evidence | RED: ten representation cases fail and the `.ai` helper is absent | GREEN: every form and either known-suffix task value is detected without a broad `.ai` number scan |
| AC-17, INV-12 | configure MEX login as `97` against suffix `0097` | RED: accepted after zero-padding | GREEN: refused because the raw login has no independent prefix |
| AC-18, INV-14 | signature oracle plus 80 profile/login/currency decisions | RED: `execute` remains in the signature | GREEN: only `(state, profile)` remain and the decision matrix has zero divergences |
| INV-01 | missing/malformed/wrong identity complement | RED: missing identity passes | GREEN: no case reaches an allowed guard result |
| INV-02 | fake bridge connect counter | RED: missing identity is not checked before connection | GREEN: missing configuration leaves counter at zero |
| INV-03 | capture every refusal | RED: old mismatch message contains both full login values | GREEN: no raw environment or login value appears |
| INV-04 | profile metadata assertions and scoped diff | RED: connection and code-owned fields are not separated | GREEN: currency, balance, names, and overrides remain code-owned |
| INV-05 | fake-only import/call audit | RED: no explicit fake-only proof | GREEN: no MT5 initialization or terminal call |
| INV-06 | dependency/lock diff | RED: no executable `.env` path exists | GREEN: no dependency or dotenv parser added |
| INV-07 | git-history/scope audit | RED: no delivery audit exists | GREEN: no rewrite operation; normal feature commit only |
| INV-08 | PR state inspection | RED: no delivery exists | GREEN: draft, no auto-merge, no merge |

## Red-first proof

Add AC-03 first. Against the pre-change implementation, delete `MT5_TTP_LOGIN`, use the profile's
current expected login only as an in-memory fake terminal state, and assert refusal. The old
hard-coded profile ignores the missing environment and the guard returns, so the test must fail.

Then add the remaining environment-backed constructor, malformed-input, repository-scan, and
entrypoint tests before implementation. Record the actual failing command and failure count in
`evidence.md`.

The independent review supplied two further RED executions. The F1-F4 focused command produced nine
failures: three canonical login forms were missed, tests and the repository root were absent from
the scan, both preflight identities leaked, and all three wrong-terminal consumers proceeded. The
separate F5 test showed a complete MEX-to-TTP environment-block copy was accepted. These are the
recorded pre-remediation oracles.

The complete re-review supplied a third RED execution. The focused N1-N4 command exited 1 with 16
failures: ten of 22 plausible login representations escaped the regex, `.ai` suffix evidence had
no detector, the documented Windows path made uv warn and discard trailing values, both operator
guides omitted quoting/precedence, a two-digit login passed the four-digit witness, the dead mode
parameter remained, and missing remote transport emitted no warning. The corrected env-file test
uses a forward-slash fixture filename so its failure is the dotenv content rather than uv's command
argument parsing.

## Focused green proof

- `uv run pytest -q tests/test_live_accounts.py tests/test_live_notify.py tests/test_live_run_cli.py tests/test_live_parity_check.py tests/test_research_swap_analysis.py tests/test_monitoring_dashboard.py`
- configured match, mismatch, missing, malformed, signal-only, and no-connect paths
- repository-wide tracked-content scan, including nested-root and non-vacuity proof
- no refusal output contains a supplied value
- no wrong-account consumer reaches its first account-specific data read

## R3 gates

- `just check-fast origin/main`
- `just check`
- `just check-properties`
- `just check-invariants`
- `just check-security`
- `just impact origin/main`
- task validation
- Linux Critical mutation workflow for the registered identity boundary
- `pr-ready ISSUE-121` (expected NOT READY until independent adversarial/live-money review)

## Safety

All terminal and runner behavior is synthetic. No real MT5 import, initialization, connection,
account read, order request, runner signal, or process control is permitted.
