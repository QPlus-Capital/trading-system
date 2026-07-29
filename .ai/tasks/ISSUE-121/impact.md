# Impact analysis

## Direct impact

- `live/accounts.py::LiveAccount` currently carries the committed login and terminal path.
- `live/accounts.py::ACCOUNTS` defines the two profiles.
- `live/accounts.py::get_account` selects a profile.
- `live/accounts.py::guard_account` compares the expected login and currency with `AccountState`.

## Transitive impact

| Consumer | Identity/path use | Required behavior |
|---|---|---|
| `live/run.py::main` | selects the profile, connects to `terminal_path`, calls `guard_account`, and passes `expected_login` into `LiveRunner` | complete environment validation before bridge construction/connection; matching identity unchanged |
| `live/notify.py::Notifier` | resolves optional Telegram transport from the same environment tail | missing or partial remote transport is warned without leaking values; notification failure remains non-disruptive |
| `live/preflight.py::main/_checks` | connects to the selected path and displays the login comparison | required environment before connection; both identities masked in stdout |
| `live/parity_check.py::main` | connects to the TTP path for read-only feed parity | shared identity guard before any live bar read |
| `research/portfolio/swap_analysis.py::main` | connects to the TTP path to refresh the broker snapshot | shared identity guard before any swap-rate read |
| `monitoring/dashboard.py::_load_live` | resolves the profile, connects, then reads deals, account, positions, and risk | shared identity guard before any account-specific history or position read |
| `live/run.py::LiveRunner(...)` | receives the resolved login for its repeated per-cycle account guard | a valid integer remains unchanged; no optional `None` from configured profiles |
| CLI choice construction in `live/run.py` and `live/preflight.py` | iterates/sorts account names | `ACCOUNTS` mapping shape and keys remain unchanged |

## Configuration path

- `.env.example` documents `MT5_MEX_LOGIN`, `MT5_MEX_TERMINAL_PATH`, `MT5_TTP_LOGIN`, and
  `MT5_TTP_TERMINAL_PATH` using single-quoted inert placeholders. The real-uv regression replaces
  them with Windows backslash paths and proves that all six account/Telegram values survive.
- The real `.env` remains gitignored and is populated from the shared password manager.
- `just live-ttp`, `just live-ttp-execute`, `just live-demo`, `just preflight`, and `just monitor`
  load `.env` with uv's built-in `--env-file` option.
- Direct callers may export the same variables into the process environment; `live/accounts.py`
  reads only `os.environ` and introduces no file parser or dependency.
- An already-exported shell value wins over `.env`. `RUN.md` and the live runbook therefore put the
  precedence warning and clearing instruction at the operator start boundary.

## Coupled safety quantity

The selected account name, environment key, parsed login, code-owned suffix, terminal path,
currency, runner login guard, read-only consumer guards, and bridge connection order form one
coupled identity boundary. The implementation validates both required environment values and the
independent suffix in `get_account()`, then routes every connected account through the same guard.
A missing, malformed, copied, or mismatching identity cannot reach account-specific consumption.

## Tracked-content impact

- The current `live/accounts.py` login literals are removed.
- The current operator-specific paths in `live/accounts.py` and `docs/live-runbook.md` are removed.
- The repository-wide guard resolves `git rev-parse --show-toplevel`, enumerates tracked files with
  `git ls-files`, includes tests, asserts sentinel paths and a plausible count, matches the
  22 realistic environment/code/JSON/shell forms, and scans operator documentation for
  unclassified bare long numbers. `.ai/**` uses the two code-owned account suffixes as a narrow
  witness instead of applying the broad numeric scan to thousands of legitimate task numbers.
- Git history remains untouched by explicit decision.

## Numeric and trading impact

With correct environment values and matching suffixes, no signal, price, quantity, risk limit,
position, order request, research artifact, portfolio trade, or reported number changes. Wrong
terminal selection now refuses parity, monitoring, and swap refresh before data consumption; this
prevents a wrong swap snapshot from moving later net-of-swap selection. No Stage 1-4 rerun is
required and both trade CSVs remain unaffected.

## Documentation impact

`RUN.md` currently says `.env` is optional and Telegram-only. `docs/live-runbook.md` currently tells
the operator to edit code and embeds a user-home path. Both statements become false under #121 and
must be corrected in the same bounded change.

## Test and mutation impact

- `tests/test_live_accounts.py` owns environment parsing, guard, pre-connection refusal, and
  configured parity.
- A tracked-tree scan test owns the non-regression guarantee for login literals and user-home paths.
- The identity resolver and guard enter the exact Linux critical mutation surface; no threshold is
  relaxed and any non-equivalent survivor blocks.
- `Notifier.__init__` enters a separate exact Linux mutation target, and `test_live_notify.py` is a
  critical dependency and invariant because a silent missing phone transport is live-money risk.
- Existing CLI, preflight, dashboard, runner, security, docs, and gate-consistency tests are
  transitive consumers.

## Critical dependencies

- `live/run.py` must call `get_account()` before constructing and connecting the bridge.
- `live/runner.py` receives the resolved login for its repeated account guard.
- `justfile` supplies `.env` to every supported live-facing entrypoint.
- `.gitignore` excludes `.env`.
- `tests/test_live_accounts.py` and `tests/test_live_run_cli.py` provide the direct behavioral
  boundary.
- `.ai/quality/mutation.toml`, `pyproject.toml`, and
  `.ai/quality/critical-dependencies.toml` bind the live identity functions to Linux mutation.

## Safety boundary

No command imports or calls MetaTrader5, creates a real `Mt5Bridge`, reads an account, or touches a
runner. CLI tests replace bridge and runner classes with in-memory fakes before entrypoint use.

## Unknown or dynamic edges

The real environment values and terminal locations are intentionally unavailable to the codebase.
Four-digit code pins reject cross-profile copies; full correctness remains an operator/password-
manager responsibility.

uv gives an already-exported shell variable precedence over `.env`. A stale PowerShell
`MT5_*_LOGIN` can therefore override the file silently; both operator guides and evidence call this
out. The `uv` subprocess regression removes those keys from its own environment so it actually
tests file loading rather than inheriting a green value.
