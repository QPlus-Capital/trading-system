# Adversarial review

## Findings

| ID | Severity | Finding | Disposition | Status |
|---|---|---|---|---|
| R-01 | P2 | `python -m mutmut` reloaded `mutmut.__main__` through its trampoline and failed before executing a mutant | Resolve the overlay console script and guard the exact command path | resolved |
| R-02 | P2 | Mutmut 3.5 requires `results --all true`; treating `--all` as a flag exited after mutation without producing evidence | Centralize and test the exact results command | resolved |
| R-03 | P2 | `uvx rust-just` addressed a package, not its `just` executable, so CI never entered the recipe | Use `uvx --from rust-just just` and guard the workflow command | resolved |
| R-04 | P2 | Mutmut's covered-line prepass followed by stats reloaded NumPy's native extension under Python 3.13, aborting before mutation | Disable the prepass while retaining explicit module and test scopes; guard the setting | resolved |
| R-05 | P2 | The mutant tree omitted `.ai/quality/risk-classes.toml`, so the reused classifier failed during Mutmut's clean-test stats pass | Copy `.ai/` into the isolated tree and guard the resource dependency | resolved |
| R-06 | P2 | The artifact uploader excluded hidden paths by default, so a completed `.ai/mutation/critical.toml` report would not be retained | Enable hidden-file upload and guard the workflow option | resolved |

## Dispositions

The implementation-level review attempted dropped/duplicated reconciliation records, lost
non-default configuration, boundary misownership, threshold equality, reversed limit monotonicity,
native-Windows mutation execution, a new survivor from weakened evidence, and drift between the
Mutmut path list and the TOML policy. Linux execution exposed and resolved R-01 through R-06 rather than
accepting a locally correct but non-executing integration. Claude's independent PR review remains
a post-open human step.
