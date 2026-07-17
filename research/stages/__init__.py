"""The staged framework CLI.

Each stage is its own command -- ``python -m research.stages.<name>`` -- that reads the
previous stage's artifact from a shared run directory, prints its results, and prints the exact
next command to run. The four stages:

1. ``edge``      -- does the strategy have an edge, where, and is it robust?     (decide: variation)
2. ``select``    -- which structure + market universe?                          (decide: universe)
3. ``portfolio`` -- combine into one account, size under a risk policy.          (decide: risk)
4. ``verdict``   -- trade yes/no + the full report (equity curve, Sharpe, ...).

Nothing strategy- or account-specific is hardcoded here: the study config module carries the
strategy/variations, and the account + risk policy are passed in (see :mod:`portfolio.risk`).
"""
