# Evidence

## HEAD

HEAD: 8856c26

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | planned-path `uv run python -m scripts.quality.classify ...` | 0 | R3: Stage-1 selection, parameter search, continuous OOS attribution, and trade-return paths |
| `impact-pre-code` | `just impact origin/main` | 0 | R0 for task-document-only diff; no production file existed yet, so the explicit coupled-quantity inventory governs implementation |
| `red-first` | `uv run pytest -q tests/test_research_stage1_swap.py` before implementation | 1 | RED: 5 failed, 1 passed; missing net APIs, unchanged real CLI output under -0.50R swap, and absent direct-study provenance |

## Coverage and mutation

Red-first, focused coverage, mutation, and full-gate evidence will be recorded against the final
code HEAD. No numerical validation result is asserted here.

## Deferred checks

The approximately nine-hour Stage-1 validation and regression comparison against
`run_20260723_1540` are deliberately deferred until Claude and Jan agree thresholds before the
run. This code-only pull request must remain draft and must not merge before that later step.
