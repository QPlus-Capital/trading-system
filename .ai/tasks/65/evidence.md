# Evidence

## HEAD

HEAD: 5f8ea724924a4ba547c10349f8a148ba11882eb6

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
| `format` | pending final command | 1 | PENDING |
| `docs-consistency` | pending final command | 1 | PENDING |
| `check` | pending final command | 1 | PENDING |
| `impacted-tests` | pending final command | 1 | PENDING |
| `property-tests-where-applicable` | pending deterministic replay | 1 | PENDING |
| `integration-tests` | pending final command | 1 | PENDING |
| `artifact-schema` | pending task validation | 1 | PENDING |
| `adversarial-review` | pending final review | 1 | PENDING |
| `invariants` | pending focused suite | 1 | PENDING |
| `mutation-on-touched-critical` | pending Linux CI | 1 | PENDING |
| `parity-where-applicable` | pending scope review | 1 | PENDING |
| `live-money-review` | pending live-scope review | 1 | PENDING |
| `human-decision-escalation` | issue 65 scope and no-merge rule | 0 | Jan retains scope and merge authority |
| `no-autonomous-merge` | pending draft PR check | 1 | PENDING |

## Coverage and mutation

Property and mutation results are pending final local/CI runs.

## Deferred checks

- Claude's independent PR review occurs after the draft PR opens.
- Critical mutation execution requires the dedicated Linux CI job.
