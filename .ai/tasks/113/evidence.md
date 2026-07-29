# Evidence

## HEAD

HEAD: pre-implementation; replace after the final implementation commit.

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | `uv run python -m scripts.quality.classify ...` | 0 | Expected R3 from the workflow paths; final changed-path run not yet recorded. |

## Coverage and mutation

Windows pre-change collection: `uv run pytest --collect-only -q` exited 0 with 1,286 node IDs.
Sorted-in-command-order SHA-256: `c1c907cdea66a2c66d88eb07a55e27f4544e9555a1b90b9fa53ecacf2a0f6ee0`.

No mutation target, baseline, threshold, or production module is changed. The Linux critical
ratchet is nevertheless an R3 requirement and will be recorded honestly when it can run.

## Deferred checks

- AC-01 Linux collection/diff: blocked locally because `wsl.exe --status` reports WSL is not
  installed and no Linux VM/container runtime is present. It must run on a real Linux runner after
  the Actions allowance resets on 2026-08-01.
- AC-04, AC-05, AC-06: confirm real workflow dispatch after 2026-08-01. Until then the executable
  parsed-YAML event oracles are the only evidence and are not presented as GitHub observations.
- AC-07: compare the first complete post-reset ready run against the last comparable six-job
  Windows run and record both run IDs plus billed minutes.
- External ruleset transition: replace the six legacy CI required contexts with the consolidated
  ready contexts only after their first observed green run.
