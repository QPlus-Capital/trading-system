# Adversarial review

## Findings

No findings; 28 counterexamples attempted

## Dispositions

The builder's pre-PR adversarial review exercised: each endpoint condition separately; exact
calendar/trade equality; pass/fail bound equality; an overlapping interval; each futility
condition separately; a zero 99% upper bound; a positive interim winner and loser; future
observations beyond the as-of cutoff; an as-of date before cohort start; a `datetime` passed where
a date is required; naive and indeterminate timezones; January month-end and leap-day
anniversaries; empty, duplicate, wrong-cohort, wrong-source, pre-start, NaN, and infinite daily
series; zero, fractional, negative, NaN, infinite, and non-Decimal counts; invalid confidence,
replication, seed, and block inputs; non-integral/out-of-range resample indices; changed seeds;
selected versus 5/10/20/60 sensitivity disagreement; stopped versus active cohort status; registry
bytes before/after evaluation; dashboard imports; and accidental P-12/P-04 changes.

The first Linux measurement exposed 93 decision-target survivors. Exact arithmetic, quantile,
calendar, forwarding, suppression, and metadata guards reduced that to one equivalent survivor:
removing `Decimal("0")` as the `sum` start is identical because empty input is rejected and every
element is already a validated `Decimal`. The final target kills 368/369 mutations. No unresolved
P0-P3 finding remains. Claude's independent R3 methodology review is still required; no live,
stage, registry, resampler, or historical-result path changed.
