# Impact analysis

## Direct impact

- `.claude/skills/**` contracts from eight skills to five: `specify-change`, `build-change`,
  `review-change`, `resolve-findings`, and `create-issue`.
- `.claude/agents/**` gains the read-only `methodology-reviewer`; all reviewer severities migrate
  to the four descriptive names.
- `scripts/quality/review_selection.py` becomes the executable source for risk/path reviewer
  selection, and `scripts/quality/validate_task.py` plus `scripts/quality/finding_registry.py`
  accept only the migrated severities.
- All 58 `.ai/quality/finding-patterns/*.toml` records migrate their severity field. Legacy numeric
  IDs remain fixed; content-addressed files are renamed to the digest of their migrated content.
- `.ai/quality/workflow-contract.toml` removes both issue-112 activation rows. Its generated
  activation block is refreshed without changing transitions, statuses, rendering policy, or
  skeleton-digest policy.
- `AGENTS.md`, `CLAUDE.md`, the constitution, reviewer guidance, pull-request template, task schema,
  fixtures, and consistency tests move together with the executable contracts.

## Transitive impact

- Claude's specification, exceptional builder, review, finding-resolution, and issue-creation
  paths consume the renamed skills.
- R2 and R3 reviews consume reviewer selection through the new module; the matrix controls which
  read-only agent contracts are invoked.
- Task readiness parses finding rows through `validate_task`; registry loading and all finding
  regression-reference checks parse the migrated pattern files.
- Workflow rendering consumes the reduced activation tuple. When issue #110 removes the last row,
  the same renderer and validator must accept and render an empty activation register.

## Critical dependencies

- Constitution sections 4, 12, 14, and 19 remain authoritative for methodology, severity,
  permanent protections, and handovers.
- The blocking set remains exactly `Blocker`, `Defect`, and `Suspected defect`.
- The classifier remains authoritative for risk. Reviewer selection consumes the already-decided
  effective risk and touched paths; it does not implement a second risk classifier.
- Every review skill and subagent remains read-only, and `build-change` remains available only
  under Jan's explicit highest-stakes builder exception.

## Unknown or dynamic edges

- Claude discovers skills and agents by filesystem name and frontmatter rather than Python imports;
  exact-set runtime tests therefore bind names, required sections, and read-only wording.
- Issue #110 is concurrently removing the remaining activation row and adding board tooling. If it
  lands first, this branch must rebase and preserve both changes; the empty-register test covers
  that combined state.
- GitHub review execution itself is external. This change makes selection deterministic and
  executable locally, while the later independent review remains a fresh-session human handover.
