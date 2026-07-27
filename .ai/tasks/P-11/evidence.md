# Evidence

## HEAD

HEAD: RED-FIRST-WORKTREE

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | `uv run python -m scripts.quality.classify research/portfolio/scenarios.py research/stages/verdict.py docs/methodology.md` | 0 | R3 with all fourteen cumulative gates |
| `red-first` | `uv run pytest -q tests/test_research_path_risk.py` before `path_risk.py` existed | 2 | RED during collection: `ModuleNotFoundError: research.portfolio.path_risk` |
| `check` | `PYTHONUTF8=1 just check` | 0 | GREEN: Ruff, strict mypy over 180 files, Vulture, and 1,154 pytest tests passed; one Linux-only mutation test skipped on Windows |

## Red-first proof

Before implementation, the focused P-11 file failed during collection because
`research.portfolio.path_risk` did not exist. Therefore none of the Clopper-Pearson, four-limit,
intraday-recovery, dominance, or real-verdict oracles could pass against the P-10 code.

## Numerical regression

Not run yet.
