"""Honest multiple-testing budget: how many configurations were effectively searched?

The more configurations tried, the better the best one looks by luck alone. The deflated Sharpe
ratio corrects for this -- but only if it is told the TRUE number of trials. The study searches
three independent dimensions, so the effective breadth is their product::

    variations  x  training-window lengths  x  parameter-grid combinations

Deflating by only one dimension (just the param grid, or just the variations) understates the
selection bias. This computes the honest product from a study config, so the burden grows
automatically as variants / train-lengths / grid points are added -- exactly when the risk of an
overfit pick rises. (It counts one study's breadth; if several independent studies were run, the
true budget is larger still -- multiply by the number of independent searches.)

Caveat -- read the resulting DSR as conservative: the product assumes *independent* trials, but
grid combos within a variation (and overlapping train-lengths) are highly correlated, so the
effective number of independent looks is somewhere between the structural count
(variations x train-lengths) and this product. Using the full product makes the deflation bar
harder, which is the safe direction when guarding against an overfit pick. NOTE the DSR is also
only as honest as the ``sharpe_variance`` fed alongside this count -- that must be the variance of
the *trial* Sharpes (as the study computes it), not a cross-sectional proxy, or the bar is wrong.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from research.engine.grid import expand_grid


@dataclass(frozen=True)
class TrialBudget:
    """The effective number of configurations searched, broken down by dimension."""

    variations: int
    train_lengths: int
    param_combos: int

    @property
    def total(self) -> int:
        """Effective trial count = the product of the independent search dimensions."""
        return self.variations * self.train_lengths * self.param_combos

    def summary(self) -> str:
        """One-line human breakdown for the report."""
        return (
            f"{self.total} effective trials = "
            f"{self.variations} variations x {self.train_lengths} train-lengths "
            f"x {self.param_combos} param-combos"
        )


def study_trial_budget(cfg: Any) -> TrialBudget:
    """Derive the multiple-testing budget from a study config's search dimensions."""
    variations = len(getattr(cfg, "VARIATIONS", {"baseline": {}}))
    train_cfg = getattr(cfg, "TRAIN_MONTHS", 24)
    train_lengths = len(train_cfg) if isinstance(train_cfg, list | tuple) else 1
    param_combos = len(expand_grid(getattr(cfg, "PARAM_GRID", {})))
    return TrialBudget(max(variations, 1), max(train_lengths, 1), max(param_combos, 1))
