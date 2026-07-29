# Impact

## Direct impact

`scripts/quality/mutation.py`

- `check_baseline` loses the total comparison. Its four remaining comparisons and the health checks
  are untouched.
- `summary_lines` is new: the operator-facing summary of one run, extracted from `run` unchanged and
  then extended with the observed and baseline totals for critical scope.
- `run` prints through `summary_lines` instead of an inline f-string. Its verdict, its exit codes and
  its report file are unchanged.

`tests/test_quality_mutation.py`

- Six new behavioural tests plus a 128-case differential oracle.
- `test_a_weakened_test_creates_a_survivor_and_the_ratchet_rejects_it` keeps its subject and gains a
  correct fixture; see `test-plan.md`.

## Transitive impact

- `just mutation-critical` and `just mutation-self-test` invoke `run`; both keep their exit
  semantics. A run that previously failed only on the total now exits 0.
- `.github/workflows/mutation.yml` invokes the recipe verbatim and is unchanged.
- `scripts/quality/pr_ready.py` and `scripts/quality/hooks/decisions.py` consume the mutation gate's
  exit status, not its messages. `baseline_evidence_decision` still requires passing mutation
  evidence when a committed quality baseline changes; this change touches no baseline.
- No consumer parses the summary text. Searching `justfile`, `scripts`, `.github`, `tests`, `core`,
  `research`, `live` and `monitoring` for `mutation total`, `Mutant total` and `Mutation critical:`
  returns exactly one hit, the definition site at `scripts/quality/mutation.py:329`. The tests assert
  on the reported numbers, not on the wording.

## Critical dependencies

`.ai/quality/critical-dependencies.toml` names no edge into `scripts/quality/mutation.py`. The
module's own dependency on `scripts.quality.classify` is unchanged; no classification path is
touched.

## Unknown or dynamic edges

`load_baseline` and `load_policy` read TOML by path at call time. Both keep their signatures and
their validation, including the internal consistency check that a baseline's per-status counts sum to
its recorded total. The mutant names in the report are supplied by Mutmut at run time and are matched
against the baseline by exact name, which this change does not alter.
