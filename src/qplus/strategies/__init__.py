"""Strategy classes -- the single source of truth shared by backtest and live."""

from qplus.strategies.ema_cross import EMACross, EMACrossConfig

__all__ = ["EMACross", "EMACrossConfig"]
