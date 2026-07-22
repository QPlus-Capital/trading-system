# Impact analysis

## Direct impact

- `.github/**`, `justfile`, and `pyproject.toml` change the repository-wide R3 gate surface.
- `scripts/quality/pr_body.py` and `scripts/quality/security.py` add evidence and security decisions.
- Existing task validation/readiness tooling gains only the discovery surface needed by local/CI
  recipes; classification and readiness semantics stay authoritative in their existing modules.

## Transitive impact

- Every pull request and push to `main` runs the split workflows.
- Branch protection will consume the documented stable workflow/job names after Jan applies it.
- Contributor task artifacts and PR bodies become machine-validated inputs to readiness.

## Critical dependencies

- The risk classifier determines R3 and cumulative gates.
- Task validation, readiness, impact, and mutation retain their existing implementations.
- Python 3.13 and Windows compatibility are required for the security tools; mutation remains Linux.

## Unknown or dynamic edges

- GitHub branch-protection settings live outside Git and require Jan's manual application.
- GitHub Actions evaluates workflow expressions and action pins only on the hosted runners.
- Vulnerability-audit results depend on the advisory database at gate execution time.
