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
from qplus.live.notify import Notifier
from qplus.live.risk_control import RiskController, position_volume
from qplus.strategies.rsi_wpr_bb_signals import RsiWprBbSignals, SignalParams

log = logging.getLogger("qplus.live")

_H4_SECONDS = 4 * 3600  # an H4 bar with open time t is closed once server time >= t + 4h


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


def exit_prices(
    side: Side, price: float, stop_loss_pct: float, take_profit_pct: float
) -> tuple[float, float]:
    """``(stop_loss, take_profit)`` a fixed percentage away from ``price``.

    Mirrors ``qplus.strategies.rsi_wpr_bb.exit_prices`` exactly, so live and backtest place their
    exits by the same rule. Anchor it to the price that ACTUALLY filled, not to the signal bar's
    close: sizing assumes a stop-out costs the risked amount, and with a 0.5% stop even 0.1% of
    slippage between signal and fill moves the real risk by 20%.
    """
    sl_frac, tp_frac = stop_loss_pct / 100.0, take_profit_pct / 100.0
    if side == "BUY":
        return price * (1 - sl_frac), price * (1 + tp_frac)
    return price * (1 + sl_frac), price * (1 - tp_frac)


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

    The SL/TP here are anchored to ``ref_price`` and are PROVISIONAL: they ride along with the
    market order so the position is never naked for a single tick. Once it fills, the runner
    re-anchors them to the real fill price (see :meth:`LiveRunner._reanchor_exits`). The volume is
    sized off ``ref_price`` and stays as computed -- the backtest sizes off the signal bar too.
    """
    stop_distance = ref_price * stop_loss_pct / 100.0
    if stop_distance <= 0:
        return None
    sl, tp = exit_prices(side, ref_price, stop_loss_pct, take_profit_pct)
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
        long_only: bool = False,
        notifier: Notifier | None = None,
    ) -> None:
        self._bridge = bridge
        self._markets = markets
        self._params = signal_params
        self._risk = risk
        self._mode = mode
        self._history = history_bars
        self._long_only = long_only  # N2: a sell signal flattens instead of going short
        self._notify = notifier or Notifier()  # default: log-only (no beep / telegram)
        self._last_bar_time: dict[str, int] = {}  # our name -> epoch of last acted bar
        self._day: date | None = None
        self._halted = False
        self._halt_reason = ""
        self._state_path = state_path
        self._cycle_bars = 0  # new closed bars processed this cycle
        self._cycle_signals = 0  # signals fired this cycle
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
            # Restore which bar was last acted on per market, so a restart does not re-process
            # (and potentially re-enter on) a signal bar that was already handled.
            self._last_bar_time = {str(k): int(v) for k, v in blob.get("last_bars", {}).items()}
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
        blob = {
            **self._risk.snapshot(),
            "day": self._day.isoformat() if self._day else None,
            "last_bars": self._last_bar_time,
        }
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

        now_epoch = now.timestamp()  # server epoch, for deciding which bars have closed (M5)
        self._cycle_bars = self._cycle_signals = 0
        for spec in self._markets:
            try:
                self._process_market(spec, account.equity, now_epoch)
            except Exception:  # one market's failure must not abort the others
                log.exception("market %s failed this cycle", spec.name)
        if self._cycle_bars:  # a new H4 bar closed -> log a summary even when nothing traded
            log.info(
                "H4 cycle: %d new bar(s) processed, %d signal(s), equity=%.0f %s",
                self._cycle_bars,
                self._cycle_signals,
                account.equity,
                self._day,
            )

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

    def _process_market(self, spec: MarketSpec, equity: float, now_epoch: float) -> None:
        bars = self._bridge.latest_bars(spec.name, self._history)
        # M5: keep only bars that have actually CLOSED by the server clock, rather than assuming
        # the last element is the forming bar (wrong at market close / weekends / boundaries).
        closed = [b for b in bars if b.time + _H4_SECONDS <= now_epoch]
        if len(closed) < 2:
            return
        last = closed[-1]
        if self._last_bar_time.get(spec.name) == last.time:
            return  # already handled this bar

        buy, sell = self._replay_signal(closed)
        self._last_bar_time[spec.name] = last.time
        self._cycle_bars += 1
        self._persist()  # remember the handled bar, so a restart cannot act on it twice
        if buy == sell:  # no signal (or contradictory) -> hold
            return
        self._cycle_signals += 1
        desired: Side = "BUY" if buy else "SELL"

        current = self._bridge.positions(spec.name)
        pos = current[0] if current else None

        if self._long_only and desired == "SELL":
            # N2: long_only mirrors the backtest -- a sell signal flattens a long, never shorts.
            if pos is not None and pos.side == "BUY":
                self._flatten(spec, pos)
            return
        if pos is not None and pos.side == desired:
            return  # already positioned the way the signal wants

        info = self._bridge.symbol_info(spec.name)
        sized = size_order(
            desired,
            last.close,
            spec.stop_loss_pct,
            spec.take_profit_pct,
            info,
            self._risk_amount(equity),
        )
        if sized is None:
            log.info("[%s] %s signal but not sizable (min-lot/stop) -> skip", spec.name, desired)
            return

        # M2: on a reversal the opposite position is about to be closed, so exclude its stop-risk
        # from the open total -- don't block the replacement trade on risk we're removing.
        exclude = position_risk(pos, info) if pos is not None else 0.0
        check = self._risk.check_open(sized.risk_amount, equity, exclude_risk=exclude)
        if not check.allowed:
            log.warning("[%s] %s BLOCKED by risk: %s", spec.name, desired, check.reason)
            return

        self._act(spec, pos, sized, info)

    def _replay_signal(self, closed: list[Bar]) -> tuple[bool, bool]:
        engine = RsiWprBbSignals(self._params)
        buy = sell = False
        for b in closed:
            buy, sell = engine.update(b.open, b.high, b.low, b.close)
        return buy, sell

    def _risk_amount(self, equity: float) -> float:
        """Money risked per trade -- fixed-fractional off the CURRENT equity (compounding).

        Risk tracks live equity, so as the account grows the money risked grows with it and the
        returns compound -- the natural way to run a fixed edge. This is safe under the prop-firm
        limits precisely because the risk fraction is the gap tail cap: a percentage guarantee
        (a stressed worst-day gap fits the 3% daily limit) holds at *every* equity level, so
        staying at that fraction of current equity never widens the drawdown profile. The
        backtest sizes the same way (``simulate(..., compound=True)`` scales by equity/start),
        keeping live == backtest.
        """
        return equity * self._risk.limits.risk_per_trade

    def _act(
        self, spec: MarketSpec, pos: Position | None, sized: SizedOrder, info: SymbolInfo
    ) -> None:
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
            # The order carries the provisional (signal-anchored) SL/TP, so the position is
            # protected from its first tick; then we re-anchor them to the real fill price.
            self._bridge.place_order(spec.name, sized.side, sized.volume, sl=sized.sl, tp=sized.tp)
            self._reanchor_exits(spec, sized, info)
        self._notify.signal(
            f"[{spec.name}] {verb} {sized.side} vol={sized.volume} sl={sized.sl} "
            f"tp={sized.tp} risk={sized.risk_amount:.0f} EUR ({self._mode.value})"
        )
        # Account for the new open risk in BOTH modes so a SIGNAL_ONLY dry-run exercises the
        # open-risk cap exactly like EXECUTE would (H4). open_risk is recomputed from live
        # positions each cycle, so this within-cycle increment self-heals next cycle.
        self._risk.on_open(sized.risk_amount)

    def _reanchor_exits(self, spec: MarketSpec, sized: SizedOrder, info: SymbolInfo) -> None:
        """Move the just-opened position's SL/TP onto its ACTUAL fill price (backtest parity).

        Deliberately conservative. It only ever touches a position that (a) is on this market,
        (b) points the way we just traded, and (c) is the ONLY such position -- if anything is
        ambiguous we leave the provisional exits alone rather than risk modifying the wrong
        ticket. A failure here is not fatal either: the order already carries a valid stop, so the
        worst case is the pre-fix behaviour (exits anchored to the signal price), never a naked
        position. Everything is logged.

        Some terminals (TTP) list the just-opened position a moment AFTER ``order_send`` returns,
        so an empty result is polled briefly before giving up. Ambiguity (>1 match) is immediate:
        waiting cannot resolve it.
        """
        try:
            candidates: list[Position] = []
            for attempt in range(5):
                if attempt:
                    time.sleep(0.5)
                candidates = [p for p in self._bridge.positions(spec.name) if p.side == sized.side]
                if candidates:
                    break
            if len(candidates) != 1:
                log.warning(
                    "[%s] cannot re-anchor exits: %d matching positions -> keeping signal-anchored"
                    " SL/TP",
                    spec.name,
                    len(candidates),
                )
                return
            position = candidates[0]
            sl, tp = exit_prices(
                sized.side, position.price_open, spec.stop_loss_pct, spec.take_profit_pct
            )
            sl, tp = round(sl, info.digits), round(tp, info.digits)
            if sl == position.sl and tp == position.tp:
                return  # filled exactly at the signal price -> nothing to move
            self._bridge.modify_sltp(position, sl=sl, tp=tp)
            log.info(
                "[%s] exits re-anchored to fill %.*f: sl %s -> %s, tp %s -> %s",
                spec.name,
                info.digits,
                position.price_open,
                position.sl,
                sl,
                position.tp,
                tp,
            )
        except Exception:
            log.exception(
                "[%s] re-anchoring exits failed; position keeps its signal-anchored SL/TP",
                spec.name,
            )

    def _flatten(self, spec: MarketSpec, pos: Position) -> None:
        """Close an open position without opening a new one (N2: long_only sell signal)."""
        log.info(
            "[%s] FLATTEN %s vol=%s (long_only sell, %s)",
            spec.name,
            pos.side,
            pos.volume,
            self._mode.value,
        )
        if self._mode is Mode.EXECUTE:
            self._bridge.close_position(pos)
        self._notify.signal(
            f"[{spec.name}] FLATTEN {pos.side} vol={pos.volume} ({self._mode.value})"
        )

    def _halt_and_flatten(self, reason: str) -> None:
        self._halted = True
        self._halt_reason = reason
        log.critical("SAFETY HALT: %s -- flattening all positions and stopping.", reason)
        self._notify.alert(f"SAFETY HALT: {reason} -- flattening & stopping")
        if self._mode is Mode.EXECUTE:
            for spec in self._markets:
                for pos in self._bridge.positions(spec.name):
                    try:
                        self._bridge.close_position(pos)
                    except Exception:
                        log.exception("failed to flatten %s ticket %s", spec.name, pos.ticket)

    # -- loop --

    def run_forever(self, poll_seconds: int = 60) -> None:
        """Poll every ``poll_seconds`` and process; ``run_once`` skips already-handled bars.

        The only routine log line is the per-H4-close cycle summary (from ``run_once``); there is
        no periodic heartbeat, to keep the log to connection info, cycle summaries and trades.
        """
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


def long_only_from_paper_config() -> bool:
    """Read the frozen ``long_only`` switch (N2: not a SignalParam; applied by the runner)."""
    module = _paper_config()
    return bool(module.STRATEGY_SWITCHES.get("long_only", False))  # type: ignore[attr-defined]


def risk_per_trade_from_paper_config() -> float:
    """Per-trade risk FRACTION from the frozen config (M3: the config is the single source)."""
    module = _paper_config()
    return float(module.RISK_PER_TRADE_PCT) / 100.0  # type: ignore[attr-defined]
