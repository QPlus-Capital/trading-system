# ISSUE-121: Move live account identity into the environment

## Problem

`live/accounts.py` commits both broker login numbers and machine-specific terminal paths, while the
account identity guard treats an absent expected login as optional outside execute mode.

## Goal

Resolve both account profiles from required environment variables, reject every missing or malformed
identity before any terminal connection or trading decision, and remove account-identifying values
and operator home paths from the tracked tree.

## Acceptance criteria

- AC-01: No tracked production or documentation file contains a login-shaped account literal or an
  absolute path under a user's home directory; an executable repository-wide guard enforces this.
- AC-02: Correct environment values resolve the selected profile and the identity guard accepts a
  matching synthetic terminal account.
- AC-03: A missing login environment variable raises a refusal before `Mt5Bridge.connect()` and
  direct guard use also refuses; the check is never skipped in signal-only mode.
- AC-04: A configured login that differs from the connected synthetic account is refused exactly as
  a hard-coded mismatch was.
- AC-05: Empty, non-numeric, padded, whitespace-containing, non-positive, and placeholder login
  values are refused without disclosing their content; missing, blank, or placeholder terminal
  paths are also refused before connection.
- AC-06: `.env.example` names all four required account variables with placeholders and contains no
  real login or machine path.
- AC-07: The `just` live, preflight, and monitoring entrypoints load the gitignored `.env` through
  uv's existing `--env-file` mechanism; operator documentation gives the same executable command.
- AC-08: Correctly configured account metadata, currency, starting balance, and symbol overrides
  remain unchanged, and no research, sizing, risk-limit, order, or reported-result behavior moves.
- AC-09: Delivery is a separate draft pull request linked to #121; it is not marked ready, merged,
  or configured for auto-merge.
- AC-10: The documented preflight report masks both connected and expected login values; neither
  full value appears in stdout.
- AC-11: The anti-recommit scan recognizes canonical `*_LOGIN=<digits>` and colon forms, includes
  tests, resolves the real Git top-level from nested mutation copies, and refuses a missing or
  implausibly small scan population. Operator documentation separately rejects every unclassified
  bare 6-to-10-digit value.
- AC-12: Swap snapshot refresh, feed parity, and monitoring verify the connected account through
  `guard_account()` before reading swap rates, bars, deal history, positions, or risk data.
- AC-13: Each profile retains a code-owned non-secret four-digit login suffix; a copied environment
  block from the other profile refuses before connection even when path and login are internally
  consistent.
- AC-14: The documented `.env` layout round-trips both real-form Windows backslash paths and every
  later Telegram value through the repository's actual `uv --env-file` loader without a warning or
  dropped value; both operator guides state the single-quote rule and exported-variable precedence.
- AC-15: Missing or partial Telegram configuration emits a warning that remote safety alerts are
  disabled without disclosing any supplied token or chat value.
- AC-16: The anti-recommit guard detects all 22 committed assignment, quoted, JSON, annotated,
  comment, docstring, shell, and PowerShell login forms; `.ai/**` additionally rejects a
  six-to-ten-digit value ending in either code-owned account suffix without a broad number scan.
- AC-17: A login must contain at least one raw digit before its code-owned suffix; formatting or
  zero-padding a shorter value cannot satisfy the witness.
- AC-18: `guard_account()` exposes no mode/execute parameter. Its accept/refuse decisions match the
  mandatory identity rule across an 80-case profile/login/currency matrix.

## Invariants

- INV-01: The account identity guard is never weaker: missing, malformed, ambiguous, or mismatching
  identity always fails closed.
- INV-02: Required account configuration is resolved before a live terminal connection is attempted.
- INV-03: No account number, terminal path, malformed value, or environment content is logged or
  embedded in a refusal message.
- INV-04: `name`, `expected_currency`, `start_balance`, and `symbol_overrides` remain code-owned
  strategy configuration.
- INV-05: No runner or MT5 terminal is initialized, contacted, stopped, restarted, or sent an order
  during implementation or verification; all behavioral proof uses fakes.
- INV-06: No dependency or second configuration framework is introduced; `os.environ` supplies
  runtime values and uv loads `.env` for repository entrypoints.
- INV-07: Repository history is not rewritten; the change only prevents the values from appearing
  in future tracked revisions.
- INV-08: R3 never merges autonomously and Jan retains the merge and live-restart decision.
- INV-09: Moving identity to the environment cannot expose it through preflight stdout, tracked
  documentation, tests, repr, logs, errors, or URLs.
- INV-10: An empty, partial, or wrong-root tracked-tree scan is a test failure, never evidence of no
  leak.
- INV-11: Read-only terminal consumers are not exempt from identity verification because their
  output can affect monitoring and net-of-swap research selection.
- INV-12: Terminal path and expected login are not the only witnesses from one operator-controlled
  file; the four-digit code pin remains independent.
- INV-13: Operator configuration examples must be executable on the Windows live platform; a
  parser warning, a silently dropped trailing variable, or an unreported disabled remote alert is
  a safety failure.
- INV-14: The mandatory identity guard has one strictness in every run mode and exposes no inert
  parameter suggesting otherwise.

## Scope

- `live/accounts.py`
- `.env.example`
- `justfile`
- `RUN.md`
- `docs/live-runbook.md`
- `live/preflight.py`
- `live/notify.py`
- `live/parity_check.py`
- `research/portfolio/swap_analysis.py`
- `monitoring/dashboard.py`
- focused tests and the R3 task artifact
- critical mutation registration for the changed identity boundary

`justfile`, `RUN.md`, and the live runbook are included because a committed `.env` template without
an entrypoint that actually loads it would leave the guard apparently configured but inactive. uv's
documented `--env-file` option is the repository's existing dependency-free mechanism.

## Non-goals

- Rewriting Git history or claiming the historic values are erased.
- Adding credentials, passwords, or account numbers to tracked files, logs, URLs, or evidence.
- Changing risk limits, sizing, signals, order placement, account currency, starting balances, or
  symbol overrides.
- Introducing `python-dotenv` or a new configuration framework.
- Initializing or querying MT5, or touching either running live runner.

## Behavioural requirements

- `LiveAccount` stores environment-variable names plus one non-secret code-owned four-digit login
  suffix for each profile.
- Login parsing accepts only a non-zero ASCII decimal string with no surrounding or embedded
  whitespace and no placeholder syntax.
- Terminal paths must be present, non-blank, and not an unchanged placeholder; filesystem existence
  remains the bridge's responsibility so configuration can be tested cross-platform.
- `get_account()` validates both required values before returning the selected profile.
- `guard_account()` resolves the required expected login unconditionally, including signal-only use,
  before comparing it with the connected account.
- The raw login is longer than the code-owned suffix and ends with it; no formatting step may
  manufacture the independent prefix.
- `guard_connected_account()` is the common boundary for read-only terminal consumers and delegates
  to `guard_account()` before any account-specific data read.
- Refusal messages name only the variable/profile and failure class, never the secret value.
- Preflight output shows only the final three digits in the repository's established `***NNN` form.
- Windows `.env` values use single quotes; an already-exported process variable takes precedence
  and must be cleared or verified before a live-facing command.
- Missing Telegram transport is best-effort for trading continuity but never silent.

## Assumptions

- The repository's `uv` version supports the documented `uv run --env-file` option.
- `uv run --env-file .env` does not override an already-exported shell variable; the evidence and
  handoff must warn operators to clear or verify stale PowerShell variables before preflight.
- MT5 login identifiers are positive integers at the Python boundary and therefore have a
  canonical ASCII decimal environment representation.
- Terminal path existence and executable validity remain `Mt5Bridge.connect()` responsibilities;
  the identity configuration boundary only requires a non-placeholder value.

## Expected artifacts

- Environment-backed account profiles and a fail-closed identity guard in `live/accounts.py`.
- Four inert placeholders in `.env.example`.
- Explicit `.env` loading in the live-facing `just` recipes and matching operator documentation.
- Focused account/CLI tests, tracked-content protection, mutation registration, and this R3 task
  artifact.
- A real-uv Windows dotenv round-trip and mutation coverage for the alert-transport decision.
- A separate draft pull request linked to #121.

## Expected effects

- With valid environment configuration: no live behavior or number changes.
- With missing or malformed configuration: startup becomes stricter and refuses before connecting.
- Tracked source loses two login literals and two machine paths; `.env.example` gains four inert
  placeholders.

## Risk class

R3. `scripts/quality/classify.py` assigns R3 because `live/accounts.py` is the live-money account
identity guard; a weak configuration boundary could trade the wrong real account.

## Human decisions required

Jan decided the repository remains public, history is not rewritten, configuration moves to `.env`,
missing/malformed values fail closed, each profile keeps a four-digit code-owned login pin, delivery
remains draft, `guard_account` loses the dead `execute` parameter, and no running live system is
touched. Jan must populate the real values from the password manager, verify no stale exported
variables override `.env`, and choose a future quiet-window restart.

## Open questions

None.
