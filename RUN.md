# RUN.md — Getting the project running from scratch

This is the bootstrap guide: from a fresh clone to a runnable setup. It is written so
that you can either follow it by hand, or hand it to Claude Code and have it perform
the steps for you.

**Platform requirement:** Apple Silicon (arm64) or Linux. `nautilus_trader` has no
wheel for Intel macOS (x86_64), so it cannot be installed there.

## 1. Prerequisites

- **Python 3.13** (the version is pinned in `.python-version`).
- **uv** — the package/environment manager. Install it if you don't have it:

  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

  Verify: `uv --version`.

## 2. Clone and enter the repo

```bash
git clone https://github.com/QPlus-Capital/trading-system.git
cd trading-system
```

## 3. Install dependencies

```bash
uv sync
```

This creates `.venv/` and installs all locked dependencies (dev tooling + the local
`qplus` package in editable mode).

## 4. Add NautilusTrader (first time on a new machine)

`nautilus_trader` is intentionally not yet pinned in `pyproject.toml`, because it has
no Intel-macOS wheel. On a supported machine (Apple Silicon / Linux), add it once:

```bash
uv add nautilus_trader
uv sync
```

Commit the resulting `pyproject.toml` and `uv.lock` changes so the dependency is
locked for everyone from then on. After this step, every later `uv sync` installs
NautilusTrader automatically and this step is no longer needed.

## 5. Configure secrets

```bash
cp .env.example .env
```

Fill in the real values in `.env` (IBKR credentials, etc.). `.env` is gitignored and
must never be committed. Also save these credentials in the shared password manager.

## 6. Verify the setup

```bash
uv run ruff check .      # lint
uv run mypy              # type-check
uv run pytest            # tests
```

All three should pass on a clean checkout. Once NautilusTrader is installed (step 4),
you can additionally verify the import:

```bash
uv run python -c "import nautilus_trader; print(nautilus_trader.__version__)"
```

## Everyday commands

| Task                | Command                       |
| ------------------- | ----------------------------- |
| Install / update    | `uv sync`                     |
| Add a dependency    | `uv add <package>`            |
| Add a dev dependency| `uv add --dev <package>`      |
| Run a script        | `uv run python <path>`        |
| Lint                | `uv run ruff check .`         |
| Format              | `uv run ruff format .`        |
| Type-check          | `uv run mypy`                 |
| Tests               | `uv run pytest`               |
