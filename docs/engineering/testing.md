# Testing critical behaviour

This guide turns the constitution's test obligations into reusable design matrices. A test need
not exercise every cell when a cell cannot occur in that component, but the test plan must mark it
not applicable rather than silently omit it. Examples should use `tests/support/assertions.py` and
`tests/support/strategies.py` where their semantics fit; a helper is not a substitute for a domain
assertion.

## Lifecycle matrix

| Phase | Required question | Typical assertion |
|---|---|---|
| construct | Are defaults validated without side effects? | Invalid construction fails closed; no order, file, or state mutation occurs. |
| start | Is durable state restored before decisions begin? | References and configuration equal the persisted inputs. |
| run | Does each accepted input produce one domain outcome? | Inputs reconcile exactly once to outputs or named rejections. |
| boundary | What owns an event exactly at the transition? | The documented half-open/inclusive rule is asserted. |
| stop | Does stopping create a trade or reported outcome? | Cleanup cannot manufacture a close, fill, or metric. |
| cleanup | Are resources released even after failure? | Disposal runs once and preserves domain state. |
| report | Does the report reconcile to the executed stream? | Aggregates equal their components and costs remain included. |
| restart | Can restart weaken a reference or repeat an action? | Snapshot/restore is idempotent; no duplicate order or reset floor. |
| exceptional | Does malformed or unavailable input fail closed? | The decision is blocked and the failure is visible. |

## Configuration matrix

| Case | Required assertion |
|---|---|
| omitted | The documented default is applied or omission is rejected. |
| default | The explicit default behaves identically to omission. |
| constant non-default | The selected value reaches execution unchanged. |
| varying | Every independently variable value reaches its consumer; no first/last-value shortcut. |
| invalid | NaN, infinity, negative, missing, or inconsistent values fail before execution. |
| serialization | Save/load preserves type, precision, and meaning. |

For selection/execution paths, use `assert_selection_execution_parity`; for ordinary propagation,
use `assert_config_propagates`. Always include a constant non-default because default-only fixtures
cannot reveal a dropped configuration value.

## Temporal matrix

| Case | Required assertion |
|---|---|
| before first | No schedule or window silently supplies defaults. |
| at start | The new interval owns its inclusive start. |
| within | The active interval owns the event exactly once. |
| at end | The documented inclusive/exclusive final-boundary rule is explicit. |
| gap | A carried outcome is attributed once even when new entries are prohibited. |
| final | Open state is managed without an artificial liquidation. |
| straddling | Opening parameters remain attached until the real close. |
| open at stop | Stop/cleanup cannot create a reportable trade. |
| ordering | Same-day events use true timestamp order and a documented tie-break. |
| DST | The loss-day/session boundary uses its named timezone, including both clock changes. |

Use timezone-aware timestamps. Portfolio daily-limit tests use the 16:15 America/Chicago loss day,
not UTC midnight. `assert_temporal_ownership` and `boundary_timestamps` cover the generic boundary
shape; domain tests still name the actual session grid.

## Numeric matrix

| Case | Required assertion |
|---|---|
| zero | A zero reference or quantity has an explicit result; undefined ratios fail closed. |
| empty | Empty streams do not manufacture evidence or crash after partial output. |
| NaN | Non-finite inputs never satisfy comparisons by accident. |
| infinity | An unbounded threshold cannot disable a gate. |
| sign | Profit, loss, long, short, debit, and credit conventions are each exercised. |
| near-zero denominator | The guard applies before division and does not amplify noise. |
| rounding | Quantity rounds down to the venue grid and never over-risks. |
| threshold | Below, exactly equal, and above the limit have explicit outcomes. |

Money and quantities remain `Decimal` or domain types in production. `finite_decimals` generates
fixed-scale finite values; invalid non-finite cases are separate explicit examples because valid
domain strategies must not blur rejected inputs into accepted ones.

## Reconciliation matrix

| Property | Required assertion |
|---|---|
| one bucket | Every accepted record appears once: no drop, duplicate, or unclassified gap. |
| aggregates sum | Reported totals equal the exact sum of their component buckets. |
| selection/execution parity | Every selected parameter is the parameter execution consumes. |
| limit monotonicity | A stronger limit never admits an input that the weaker limit blocks. |

The helpers deliberately accept a real key, owner, evaluator, or decision function. Tests that
assert only token presence or duplicate production logic are not valid reconciliation evidence.

## Property tests

Hypothesis uses the repository-wide `qplus` profile: 75 examples, no example database, no deadline,
and deterministic generation. CI replays `tests/test_quality_properties.py` twice with seed
`20260721`; either run failing or producing a different result fails the job. Strategies cover
finite Decimals, valid and overlapping windows, schedule segments, trade streams, zero/sparse
references, symbol/lot metadata, and boundary timestamps.

Properties are deliberately confined to pure high-value logic: live risk decisions and sizing,
portfolio sizing/drawdown, parameter schedules, continuous window/gap attribution, regression
gates, and the shared change-risk classifier. A discovered production defect keeps the minimized
property and a named regression example, and adds its generalized class to
`.ai/quality/finding-patterns.toml`.

## Mutation tests

`mutation-fast` mutates only configured critical modules changed relative to its base; it obtains
the changed paths and R3 result from `scripts/quality/classify.py`. `mutation-critical` runs every
configured focused scope and checks `.ai/quality/mutation-baseline.toml`. Each scope names its pure functions;
module-wide wildcards and command/orchestration entry points are excluded. The current TOML result is written
under `.ai/mutation/` and uploaded by CI; it is intentionally unversioned. A new survivor, an
unchecked/no-test/timeout/suspicious outcome, a score decrease, or a changed mutant total blocks.
Every accepted survivor must be named, classified as `equivalent`, `irrelevant`, or `meaningful`,
and explained in the baseline, and every baseline update
must explain why the target or result changed.

The selected tool is Mutmut 3.5.0. Its package metadata supports Python 3.13, but the tool exits on
native Windows because it requires `fork` and directs Windows users to WSL. Therefore mutation runs
in the dedicated Ubuntu job with Python 3.13; `just check` and deterministic property replay remain
on Windows CI. The Ubuntu setup omits the Windows-only MetaTrader5 wheel and mutates only pure
modules that do not import it. The tool is a pinned ephemeral `uv --with` dependency, so it does not
add Mutmut's transitive packages (including YAML tooling) to the project dependency lock.
`mutate_only_covered_lines` is disabled: Mutmut's in-process coverage prepass followed by its stats
pass attempts to load NumPy's native extension twice under Python 3.13. Focus remains bounded by
the explicit configured module targets and their dedicated test selection.
The mutant tree copies `.ai/` because the reused classifier loads its authoritative risk model
from `.ai/quality/risk-classes.toml`. CI explicitly includes hidden files when uploading the
unversioned `.ai/mutation/critical.toml` report.

Compatibility evidence collected before adoption:

| Environment | Command | Result |
|---|---|---|
| Windows, Python 3.13 | `uvx --from mutmut==3.5.0 mutmut --version` | Exit 1: native Windows unsupported; use WSL. |
| Windows, Python 3.13 | `uvx --from cosmic-ray cosmic-ray --version` | Exit 0, version 8.4.6; not selected because Mutmut provides focused wildcard reruns and CI result export. |
| Linux CI, Python 3.13 | `just mutation-critical` | Required before readiness; report retained as a CI artifact. |
