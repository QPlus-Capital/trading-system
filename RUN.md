# RUN.md — Getting the project running from scratch

This is the bootstrap guide: from a fresh clone to a runnable setup. It is written so
that you can either follow it by hand, or hand it to Claude Code and have it perform
the steps for you.

**Platform requirement:** any platform with a `nautilus_trader` wheel — Windows
(x86_64), Linux, or Apple Silicon macOS (arm64). The only exception is Intel macOS
(x86_64), which has no wheel and cannot run it.

## 1. Prerequisites

- **Python 3.13** (the version is pinned in `.python-version`).
- **uv** — the package/environment manager. Install it if you don't have it:

  ```bash
  # macOS / Linux
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

  ```powershell
  # Windows (PowerShell)
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
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

## 4. NautilusTrader

`nautilus_trader` is already pinned in `pyproject.toml` and `uv.lock` (added
2026-07-01, currently v1.230.0), so the `uv sync` above already installed it — no
extra step is needed.

It was originally added with a one-off `uv add nautilus_trader && uv sync` on a
machine that has a wheel (Windows, Linux, or Apple Silicon). To bump the version
later, run `uv lock --upgrade-package nautilus-trader && uv sync` and commit the
updated `uv.lock`.

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
