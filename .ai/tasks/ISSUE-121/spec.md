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

## Scope

- `live/accounts.py`
- `.env.example`
- `justfile`
- `RUN.md`
- `docs/live-runbook.md`
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

- `LiveAccount` stores only the environment-variable names for connection identity.
- Login parsing accepts only a non-zero ASCII decimal string with no surrounding or embedded
  whitespace and no placeholder syntax.
- Terminal paths must be present, non-blank, and not an unchanged placeholder; filesystem existence
  remains the bridge's responsibility so configuration can be tested cross-platform.
- `get_account()` validates both required values before returning the selected profile.
- `guard_account()` resolves the required expected login unconditionally, including signal-only use,
  before comparing it with the connected account.
- Refusal messages name only the variable/profile and failure class, never the secret value.

## Assumptions

- The repository's `uv` version supports the documented `uv run --env-file` option.
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
missing/malformed values fail closed, delivery remains draft, and no running live system is touched.
Jan must populate the real values from the password manager before a future quiet-window restart.

## Open questions

None.
