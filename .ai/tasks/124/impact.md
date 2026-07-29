# Impact

## Direct impact

- `.ai/quality/task-artifacts.toml` and `scripts/quality/validate_task.py` move from one
  five-file schema to cumulative R0/R1/R2/R3 schemas. `spec.md` is no longer required;
  the issue is the specification. R0/R1 require no task files, R2 requires
  `review.md` and `evidence.md`, and R3 additionally requires `impact.md` and
  `test-plan.md`.
- `.ai/quality/pr-body.toml` and `scripts/quality/pr_body.py` select an exact,
  cumulative section set from the declared risk: 5/8/14/20 for R0/R1/R2/R3.
- `scripts/quality/pr_ready.py` validates only the artifacts required by the
  classifier result (or a higher risk declared in the PR body) and preserves the
  existing cumulative gate list for that effective class.
- `scripts/quality/hooks/decisions.py` and
  `scripts/quality/hooks/pre_bash.py` allow `gh pr create --draft`, require draft
  creation, and apply readiness plus the independent-review guard at `gh pr ready`.
  Initial and review-fix pushes are no longer circularly blocked by readiness.
- `.ai/quality/finding-patterns.toml` becomes one immutable migrated file per legacy
  finding plus content-addressed files for new findings. A loader derives IDs and
  validates the migration manifest.
- `.ai/quality/workflow-contract.toml` removes the two issue-124 activation rows and
  the transitional review record. Generated blocks in `AGENTS.md`,
  `docs/engineering/constitution.md`, and `docs/engineering/workflow.md` are
  regenerated from those changed facts.
- `.github/PULL_REQUEST_TEMPLATE.md` remains the superset template; the validator
  selects the required subset. No workflow file under `.github/workflows/**` is
  touched, preserving parallel issue #113's scope.

## Transitive impact

- `scripts/quality/pr_body.py`, `scripts/quality/pr_ready.py`, the Claude pre-Bash
  hook, task-artifact CI validation, and branch protection jointly govern whether a
  change may become ready and later merge.
- Existing task directories remain byte-unchanged. Extra legacy files, including
  `spec.md`, are tolerated; only newly required files are read.
- Finding-registry consumers in tests, engineering docs, architecture docs, and
  Claude reviewer/builder skills move from the retired monolith path to the split
  registry directory and production loader.
- The workflow-contract exact-set tests lose only the two capabilities delivered by
  this issue. The remaining activation records, transition records, status records,
  gate lower bound, and approval ordering are unchanged.

## Critical dependencies

- `scripts/quality/classify.py` and `.ai/quality/risk-classes.toml` remain the
  authoritative lower bound for risk; issue #109 already classifies every workflow
  and agent surface at R3.
- The R3 gate tuple from `.ai/quality/risk-classes.toml` is captured before the
  implementation and compared literally after it.
- Branch protection remains the final enforcement of required CI checks. Scaling
  local artifacts for R0/R1 does not remove or make optional any class gate.
- `scripts/quality/workflow_contract.py --write` is the only permitted way to change
  generated contract blocks.

## Unknown or dynamic edges

- The issue's AC-02 says “R1 ... five required sections”, while the approved
  workflow contract and the build request state the complete mapping
  R0/R1/R2/R3 = 5/8/14/20. The already-ratified contract is retained: the five-section
  acceptance case is R0 and the R1 case has eight. No contract fact is changed to
  accommodate the stale class name.
- Manual risk upgrades above the path classifier are supplied by the PR body's
  declared risk and are enforced by `pr_body`; local `pr_ready` without a PR body
  remains classifier-based. It may never select a class below the classifier.
- Git merge behavior is platform/tool-version dependent, so AC-05 uses a real
  temporary Git repository and executes both merge orders rather than modelling
  conflicts in Python.

