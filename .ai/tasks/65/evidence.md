# Evidence

## HEAD

HEAD: 5d590d436d82d284f1c6d28cfdb8e934f240e052

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | initial focused collection | 1 | RED: `tests.support` and `scripts.quality.mutation` absent |
| `red-first` | first property/helper execution | 1 | RED: boundary zip and fixture-lifetime counterexamples found in new tests |
| `red-first` | native Windows Mutmut probe | 1 | RED: Mutmut 3.5.0 refuses native Windows and requires WSL/Linux |
| `red-first` | first Linux Mutmut probe via `python -m` | 1 | RED: trampoline re-imported `mutmut.__main__` and reset multiprocessing context |
| `red-first` | first Mutmut results listing | 2 | RED: `--all` requires the explicit value `true` in 3.5.0 |
| `red-first` | mutation workflow just launcher | 1 | RED: `uvx rust-just` names a package without selecting its `just` executable |
| `red-first` | Mutmut covered-line prepass guard | 1 | RED: coverage then stats reloaded NumPy's native extension under Linux Python 3.13 |
| `red-first` | mutant-tree classifier resource guard | 1 | RED: clean-test stats could not load `.ai/quality/risk-classes.toml` |
| `red-first` | hidden mutation artifact upload guard | 1 | RED: uploader excluded `.ai/mutation/critical.toml` by default |
| `red-first` | named pure-function scope and survivor-classification guards | 1 | RED: module-wide policy included 298 no-test mutants; baseline schema did not require classification |
| `format` | `uv run python -m scripts.quality.impact --base origin/main --check-format` | 0 | All changed Python files formatted |
| `docs-consistency` | `uv run pytest -q tests/test_docs_architecture_map.py tests/test_engineering_docs.py` | 0 | 56 passed |
| `check` | `uvx --from rust-just just --shell powershell.exe --shell-arg -Command check` | 0 | Ruff, mypy (139 files), pytest (657 passed, 1 Linux-only skip), and vulture passed |
| `impacted-tests` | `uvx --from rust-just just --shell powershell.exe --shell-arg -Command check-fast` | 0 | R3; 39 focused tests passed, 1 Linux-only skip |
| `property-tests-where-applicable` | `uv run pytest -q tests/test_quality_properties.py --hypothesis-seed=20260721` twice | 0 | 8 passed, then the same 8 passed |
| `integration-tests` | full pytest within `just check` plus the CI `check` job | 0 | 657 passed locally and in GitHub Actions |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task 65` | 0 | Valid: 4 acceptance criteria and 4 invariants |
| `adversarial-review` | `.ai/tasks/65/review.md` | 0 | 10+ counterexamples attempted; R-01 through R-07 found and resolved |
| `invariants` | focused live/research/mutation-selection test command from `[tool.mutmut]` | 0 | 95 passed |
| `mutation-on-touched-critical` | Linux CI `uvx --from rust-just just mutation-critical` (run 29871690480) | 0 | 774 selected; 585 killed; 189 exact meaningful baseline survivors; zero unhealthy outcomes; weakened-test probe caught |
| `parity-where-applicable` | `git diff --quiet origin/main -- core research live monitoring` | 0 | No production trading package changed |
| `live-money-review` | 95-test invariant suite plus production-package diff check | 0 | Live risk, sizing, drawdown, schedule, attribution, and regression guards passed; no live implementation changed |
| `human-decision-escalation` | issue 65 scope and no-merge rule | 0 | Jan retains scope and merge authority |
| `no-autonomous-merge` | `gh pr view 70 --json isDraft --jq '.isDraft'` | 0 | `true`; PR remains draft and unmerged |

## Coverage and mutation

The eight deterministic properties passed twice with seed `20260721`. The measured critical
mutation baseline is 585/774 killed (75.58%) with 189 exact survivors conservatively classified as
meaningful test-strength gaps. No selected mutant was untested, skipped, suspicious, timed out,
unchecked, interrupted, segfaulted, or merely caught by type checking. GitHub run `29871690480`
also proved that weakening a real boundary test increases survivors and is rejected by the ratchet.

## Deferred checks

- Claude's independent implementation review is intentionally the next post-open workflow step.
