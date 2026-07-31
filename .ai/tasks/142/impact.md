# Impact analysis

## Direct impact

- `.ai/quality/mutation.toml` gains one `board-build-permit` target bounded to the BoardService
  methods that validate statuses, permits, risk labels, write ordering, and read-back verification.
- `pyproject.toml` mirrors the new mutation path and adds `tests/test_quality_board.py` to Mutmut's
  selected test suite.
- `.ai/quality/mutation-baseline.toml` will append the target, recompute the policy fingerprint and
  totals, and record every native Linux board survivor by exact name and reason.
- `tests/test_quality_mutation.py` and `tests/test_ci_cost_workflows.py` bind target selection,
  workflow applicability, policy/config parity, survivor explanations, and unexpected-survivor
  rejection.

## Transitive impact

- A pull request changing only `scripts/quality/board.py` now starts `mutation-critical`.
- The critical Linux mutation run executes the existing Board behavioral suite against the new
  target alongside every previously configured target.
- Future changes to BoardService permit guards cannot silently add an unnamed survivor.

## Critical dependencies

- `scripts/quality/mutation.py` remains the unchanged selector, fingerprint, report, and exact-set
  ratchet implementation.
- `.github/workflows/mutation.yml` remains configuration-driven and reads the production policy.
- `scripts/quality/board.py` is the immutable production subject; its focused fake-gateway tests
  exercise status, label, boundary, interleaving, and write/read-back behavior.
- Native Mutmut 3.5.0 execution requires Linux and Python 3.13.

## Unknown or dynamic edges

- Production impact analysis reports no unknown or dynamic import edge for the changed paths.
- Mutmut's generated exact names were resolved from native Linux reports rather than inferred:
  runs `30616591967` and `30617552213` exposed the complete before-test and after-test Board sets,
  and run `30618204290` proved the committed exact ratchet.
- Windows continues to refuse native Mutmut execution rather than claim a result.
- Generated-source inspection reduced the Board survivor set to three equivalent comparisons whose
  exact names and observability reason are recorded in the baseline; aggregate counts were not used
  as a tolerance.
