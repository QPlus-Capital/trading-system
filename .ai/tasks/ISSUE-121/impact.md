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
| `live/preflight.py::main/_checks` | connects to the selected path and displays the login comparison | required environment before connection; comparison remains authoritative |
| `live/parity_check.py::main` | connects to the TTP path for read-only feed parity | required environment before connection |
| `research/portfolio/swap_analysis.py::pull_snapshot` | connects to the TTP path to refresh the broker snapshot | required environment before connection |
| `monitoring/dashboard.py::_load_live` | indexes `ACCOUNTS`, reads the terminal path and symbol overrides | path must fail closed when absent; monitoring remains read-only |
| `live/run.py::LiveRunner(...)` | receives the resolved login for its repeated per-cycle account guard | a valid integer remains unchanged; no optional `None` from configured profiles |
| CLI choice construction in `live/run.py` and `live/preflight.py` | iterates/sorts account names | `ACCOUNTS` mapping shape and keys remain unchanged |

## Configuration path

- `.env.example` documents `MT5_MEX_LOGIN`, `MT5_MEX_TERMINAL_PATH`, `MT5_TTP_LOGIN`, and
  `MT5_TTP_TERMINAL_PATH` using inert placeholders.
- The real `.env` remains gitignored and is populated from the shared password manager.
- `just live-ttp`, `just live-ttp-execute`, `just live-demo`, `just preflight`, and `just monitor`
  load `.env` with uv's built-in `--env-file` option.
- Direct callers may export the same variables into the process environment; `live/accounts.py`
  reads only `os.environ` and introduces no file parser or dependency.

## Coupled safety quantity

The selected account name, environment key, parsed login, terminal path, currency, runner login
guard, and bridge connection order form one coupled identity boundary. The implementation changes
the producer once, validates both required environment values in `get_account()`, and preserves the
same resolved values for every consumer. A missing identity cannot be represented as an optional
`None` and cannot reach the connection or runner.

## Tracked-content impact

- The current `live/accounts.py` login literals are removed.
- The current operator-specific paths in `live/accounts.py` and `docs/live-runbook.md` are removed.
- The repository-wide guard enumerates tracked files with `git ls-files`, scans production and
  documentation text, and excludes synthetic test fixtures rather than using a hard-coded historic
  secret as its oracle.
- Git history remains untouched by explicit decision.

## Numeric and trading impact

With correct environment values, no signal, price, quantity, risk limit, position, order request,
research artifact, portfolio trade, or reported number changes. With missing/malformed values the
only movement is earlier refusal. No Stage 1-4 rerun is required; both trade CSVs are unaffected
because no research producer or configuration changes.

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
Their correctness is an operator/password-manager responsibility; missing or malformed values fail
closed rather than being guessed.
