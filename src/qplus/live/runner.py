"""Live runner -- drive the frozen strategy on MT5, one H4 bar at a time (Phase 4).

Ties the pieces together: the pure signal engine (identical to the backtest), the MT5
bridge (data + orders), and the risk-control layer (daily / trailing stops + open-risk cap).

Two modes:
- ``SIGNAL_ONLY`` -- compute signals + sizing and log them; place NO orders (dry run).
- ``EXECUTE``     -- additionally place / close orders on the terminal.

Design choices that keep it safe and restart-proof:
- The signal is recomputed by **replaying** the recent closed bars into a fresh engine each
  cycle, so it is stateless and survives restarts/disconnects.
- ``open_risk`` is **recomputed from the live positions** every cycle (from each position's
  entry-to-stop distance), not tracked incrementally -- it always reflects reality.
- Any ``must_flatten`` trigger flattens everything and HALTS the session; it does not
  auto-resume. Doing nothing is the safe state.
- The forming (last) bar is dropped; we act only on the most recently CLOSED H4 bar, once.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path

from qplus.live.mt5_bridge import Bar, Mt5Bridge, Position, Side, SymbolInfo
from qplus.live.risk_control import RiskController, position_volume
from qplus.strategies.rsi_wpr_bb_signals import RsiWprBbSignals, SignalParams

log = logging.getLogger("qplus.live")


class Mode(StrEnum):
    """Runner mode: dry-run (log only) or place real orders."""

    SIGNAL_ONLY = "SIGNAL_ONLY"
    EXECUTE = "EXECUTE"


@dataclass(frozen=True)
class MarketSpec:
    """One market to trade: our research name + its fixed SL/TP (percent of entry)."""

    name: str
    stop_loss_pct: float
    take_profit_pct: float


@dataclass(frozen=True)
class SizedOrder:
    """A fully-sized order proposal for one entry."""

    side: Side
    volume: float
    sl: float
    tp: float
    risk_amount: float  # actual money at risk after lot rounding


def size_order(
    side: Side,
    ref_price: float,
    stop_loss_pct: float,
    take_profit_pct: float,
    info: SymbolInfo,
    risk_amount: float,
) -> SizedOrder | None:
    """Size an entry so a stop-out loses ~``risk_amount``; ``None`` if it can't be sized.

    Pure: computes the SL/TP prices and the lot volume (rounded to the broker's step, capped
    at the max lot, skipped if below the min lot) and the ACTUAL money risked after rounding.
    """
    stop_distance = ref_price * stop_loss_pct / 100.0
    if stop_distance <= 0:
        return None
    if side == "BUY":
        sl = ref_price * (1 - stop_loss_pct / 100.0)
        tp = ref_price * (1 + take_profit_pct / 100.0)
    else:
        sl = ref_price * (1 + stop_loss_pct / 100.0)
        tp = ref_price * (1 - take_profit_pct / 100.0)
    volume = position_volume(
        risk_amount,
        stop_distance,
        info.tick_size,
        info.tick_value,
        min_lot=info.volume_min,
        lot_step=info.volume_step,
        max_lot=info.volume_max,
    )
    if volume <= 0:
        return None
    loss_per_lot = (stop_distance / info.tick_size) * info.tick_value
    actual_risk = volume * loss_per_lot
    return SizedOrder(
        side=side,
        volume=volume,
        sl=round(sl, info.digits),
        tp=round(tp, info.digits),
        risk_amount=actual_risk,
    )


def position_risk(pos: Position, info: SymbolInfo) -> float:
    """Money at risk for an open position from its entry-to-stop distance.

    H5: a position with NO stop-loss has unbounded downside, so it must never count as zero
    risk (that would understate ``open_risk`` and loosen the cap). We charge the worst case --
    the loss if price ran to zero -- so any stop-less position saturates the open-risk cap and
    blocks new entries around it. The runner also logs a warning when it sees one.
    """
    if pos.sl <= 0:
        return pos.volume * (pos.price_open / info.tick_size) * info.tick_value
    distance = abs(pos.price_open - pos.sl)
    return pos.volume * (distance / info.tick_size) * info.tick_value


class LiveRunner:
    """Orchestrates one H4 cycle across all markets; loops until stopped or halted."""

    def __init__(
        self,
        bridge: Mt5Bridge,
        markets: list[MarketSpec],
        signal_params: SignalParams,
        risk: RiskController,
        *,
        mode: Mode = Mode.SIGNAL_ONLY,
        history_bars: int = 300,
        state_path: Path | None = None,
    ) -> None:
        self._bridge = bridge
        self._markets = markets
        self._params = signal_params
        self._risk = risk
        self._mode = mode
        self._history = history_bars
        self._last_bar_time: dict[str, int] = {}  # our name -> epoch of last acted bar
        self._day: date | None = None
        self._halted = False
        self._halt_reason = ""
        self._state_path = state_path
        self._load_state()

    # -- risk-state persistence (K1: a restart must NOT reset the risk references) --

    def _load_state(self) -> None:
        """Restore the risk references + trading day from disk, or persist the initial set.

        Without this, restarting the runner would reset the trailing HWM and the daily
        reference to the current balance -- silently discarding the drawdown protection.
        """
        if self._state_path is None:
            return
        if self._state_path.exists():
            blob = json.loads(self._state_path.read_text())
            self._risk.restore(blob)
            day = blob.get("day")
            self._day = date.fromisoformat(day) if day else None
            log.info(
                "restored risk state: start=%.2f hwm=%.2f day_start=%.2f day=%s",
                self._risk.start_balance,
                self._risk.hwm_balance,
                self._risk.day_start_balance,
                self._day,
            )
        else:
            self._persist()  # capture the initial references so the next restart finds them

    def _persist(self) -> None:
        """Atomically write the risk references + current trading day to disk."""
        if self._state_path is None:
            return
        blob = {**self._risk.snapshot(), "day": self._day.isoformat() if self._day else None}
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._state_path.with_suffix(self._state_path.suffix + ".tmp")
        tmp.write_text(json.dumps(blob, indent=2))
        os.replace(tmp, self._state_path)  # atomic on POSIX and Windows

    # -- per-cycle orchestration --

    def run_once(self, now: datetime | None = None) -> None:
        """Process one polling cycle: day roll, safety check, then each market."""
        if self._halted:
            return
        # H3: the daily-limit boundary must follow the BROKER's server day (TTP resets at
        # server midnight), not the client's UTC date -- otherwise the daily reference resets
        # at the wrong hour and our budget can disagree with TTP's.
        now = now or self._bridge.server_time()
        account = self._bridge.account()

        # Day roll: bank the prior day's HWM, reset the daily reference. Persist so a restart
        # keeps the true HWM / day-start rather than resetting to the current balance (K1).
        today = now.date()
        if self._day is None:
            self._day = today
            self._persist()
        elif today != self._day:
            self._risk.on_eod(account.balance)
            self._risk.on_new_day(account.balance)
            self._day = today
            self._persist()

        # Recompute total open risk from the live positions (source of truth).
        self._risk.open_risk = self._total_open_risk()

        # Safety cut-off first.
        flat = self._risk.must_flatten(account.equity)
        if flat.allowed:
            self._halt_and_flatten(flat.reason)
            return

        for spec in self._markets:
            try:
                self._process_market(spec, account.equity)
            except Exception:  # one market's failure must not abort the others
                log.exception("market %s failed this cycle", spec.name)

    def _total_open_risk(self) -> float:
        total = 0.0
        for spec in self._markets:
            info = self._bridge.symbol_info(spec.name)
            for pos in self._bridge.positions(spec.name):
                if pos.sl <= 0:  # H5: unbounded downside -> loud warning + worst-case charge
                    log.warning(
                        "[%s] open position %s has NO stop-loss -> charged at worst case",
                        spec.name,
                        pos.ticket,
                    )
                total += position_risk(pos, info)
        return total

    def _process_market(self, spec: MarketSpec, equity: float) -> None:
        bars = self._bridge.latest_bars(spec.name, self._history)
        closed = bars[:-1]  # drop the still-forming bar
        if len(closed) < 2:
            return
        last = closed[-1]
        if self._last_bar_time.get(spec.name) == last.time:
            return  # already handled this bar

        buy, sell = self._replay_signal(closed)
        self._last_bar_time[spec.name] = last.time
        if buy == sell:  # no signal (or contradictory) -> hold
            return
        desired: Side = "BUY" if buy else "SELL"

        current = self._bridge.positions(spec.name)
        pos = current[0] if current else None
        if pos is not None and pos.side == desired:
            return  # already positioned the way the signal wants

        info = self._bridge.symbol_info(spec.name)
        sized = size_order(
            desired,
            last.close,
            spec.stop_loss_pct,
            spec.take_profit_pct,
            info,
            self._risk_amount(),
        )
        if sized is None:
            log.info("[%s] %s signal but not sizable (min-lot/stop) -> skip", spec.name, desired)
            return

        check = self._risk.check_open(sized.risk_amount, equity)
        if not check.allowed:
            log.warning("[%s] %s BLOCKED by risk: %s", spec.name, desired, check.reason)
            return

        self._act(spec, pos, sized)

    def _replay_signal(self, closed: list[Bar]) -> tuple[bool, bool]:
        engine = RsiWprBbSignals(self._params)
        buy = sell = False
        for b in closed:
            buy, sell = engine.update(b.open, b.high, b.low, b.close)
        return buy, sell

    def _risk_amount(self) -> float:
        """Money risked per trade -- FLAT off the fixed initial reference (H2).

        The study validated the drawdown feasibility under *flat* sizing (a fixed fraction of
        the starting balance). Sizing off live equity would compound after gains and drift
        outside that validated envelope, so we size off ``start_balance`` instead.
        """
        return self._risk.start_balance * self._risk.limits.risk_per_trade

    def _act(self, spec: MarketSpec, pos: Position | None, sized: SizedOrder) -> None:
        """Log the decision and, in EXECUTE mode, (reverse and) open the position."""
        verb = "REVERSE" if pos is not None else "OPEN"
        log.info(
            "[%s] %s %s vol=%s sl=%s tp=%s risk=%.2f (%s)",
            spec.name,
            verb,
            sized.side,
            sized.volume,
            sized.sl,
            sized.tp,
            sized.risk_amount,
            self._mode.value,
        )
        if self._mode is Mode.EXECUTE:
            if pos is not None:
                self._bridge.close_position(pos)
            self._bridge.place_order(spec.name, sized.side, sized.volume, sl=sized.sl, tp=sized.tp)
        # Account for the new open risk in BOTH modes so a SIGNAL_ONLY dry-run exercises the
        # open-risk cap exactly like EXECUTE would (H4). open_risk is recomputed from live
        # positions each cycle, so this within-cycle increment self-heals next cycle.
        self._risk.on_open(sized.risk_amount)

    def _halt_and_flatten(self, reason: str) -> None:
        self._halted = True
        self._halt_reason = reason
        log.critical("SAFETY HALT: %s -- flattening all positions and stopping.", reason)
        if self._mode is Mode.EXECUTE:
            for spec in self._markets:
                for pos in self._bridge.positions(spec.name):
                    try:
                        self._bridge.close_position(pos)
                    except Exception:
                        log.exception("failed to flatten %s ticket %s", spec.name, pos.ticket)

    # -- loop --

    def run_forever(self, poll_seconds: int = 60) -> None:
        """Poll every ``poll_seconds`` and process; ``run_once`` skips already-handled bars."""
        log.info(
            "live runner started in %s mode (%d markets)", self._mode.value, len(self._markets)
        )
        while not self._halted:
            try:
                self.run_once()
            except Exception:
                log.exception("run_once failed; retrying next poll")
            time.sleep(poll_seconds)
        log.warning("live runner stopped (halted: %s)", self._halt_reason)


def _paper_config() -> object:
    """Load ``config/live/paper_rsi_wpr_bb.py`` by path (config/ is not an import package)."""
    from pathlib import Path

    from qplus.backtest.config import load_config_module

    repo_root = Path(__file__).resolve().parents[3]
    return load_config_module(repo_root / "config" / "live" / "paper_rsi_wpr_bb.py")


def markets_from_paper_config() -> list[MarketSpec]:
    """Build the market list from ``config/live/paper_rsi_wpr_bb.py`` (name + fixed SL/TP)."""
    module = _paper_config()
    specs: list[MarketSpec] = []
    for factory, _csv, _lev, sl, tp in module.MARKETS:  # type: ignore[attr-defined]
        raw_symbol = factory().raw_symbol.value
        specs.append(MarketSpec(name=raw_symbol, stop_loss_pct=sl, take_profit_pct=tp))
    return specs


def signal_params_from_paper_config() -> SignalParams:
    """Build the signal params (default knobs + the frozen no_bb_wpr switches)."""
    module = _paper_config()
    switches = {
        k: v
        for k, v in module.STRATEGY_SWITCHES.items()  # type: ignore[attr-defined]
        if k != "long_only"
    }
    return SignalParams(**switches)
