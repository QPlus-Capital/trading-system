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

## Focused green proof

- `uv run pytest -q tests/test_live_accounts.py tests/test_live_run_cli.py`
- configured match, mismatch, missing, malformed, signal-only, and no-connect paths
- repository-wide tracked-content scan
- no refusal output contains a supplied value

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
