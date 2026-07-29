"""Live runner -- drive the frozen strategy on MT5, one H4 bar at a time .

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
import math
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from datetime import time as dtime
from enum import StrEnum
from pathlib import Path
from zoneinfo import ZoneInfo

from core.paths import REPO_ROOT
from core.strategies.rsi_wpr_bb_signals import RsiWprBbSignals, SignalParams

from live.mt5_bridge import MAGIC, Bar, Mt5Bridge, Mt5SideError, Position, Side, SymbolInfo
from live.notify import Notifier
from live.risk_control import RiskController, position_volume

log = logging.getLogger("live")

# TTP CFD Prime resets the daily drawdown at 16:15 America/Chicago (DST-aware), on the previous
# day's closing balance -- verified from TTP support. The internal daily stop must follow the same
# loss-day boundary, not UTC/server midnight, or our budget disagrees with the prop firm's.
_CHICAGO = ZoneInfo("America/Chicago")
_DAILY_RESET = dtime(16, 15)


def loss_day(now_utc: datetime) -> date:
    """The prop-firm 'loss day' a UTC instant belongs to (rolls at 16:15 CT).

    An instant at/after 16:15 CT counts toward the NEXT day, so the returned label increments
    exactly at the reset.

    ``now_utc`` must be REAL UTC and tz-aware -- NOT the broker's clock (#18). MT5 encodes tick
    and bar times as the server's wall clock in Unix seconds, so ``Mt5Bridge.server_time()`` is
    the server frame; converting that to America/Chicago would shift this boundary by the server's
    offset (2-3h on an EET server), which is exactly the error this function exists to prevent.
    """
    local = now_utc.astimezone(_CHICAGO)
    return local.date() + timedelta(days=1) if local.time() >= _DAILY_RESET else local.date()


_H4_SECONDS = 4 * 3600  # an H4 bar with open time t is closed once server time >= t + 4h

# Prices a candidate order's entry->stop loss in account currency: (side, entry, sl, volume).
# Returns None when the terminal cannot price it, so the caller falls back to the arithmetic.
LossFn = Callable[[Side, float, float, float], float | None]


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

    Mirrors ``core.strategies.rsi_wpr_bb.exit_prices`` exactly, so live and backtest place their
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
    loss_fn: LossFn | None = None,
) -> SizedOrder | None:
    """Size an entry so a stop-out loses ~``risk_amount``; ``None`` if it can't be sized.

    Pure: computes the SL/TP prices and the lot volume (rounded to the broker's step, capped
    at the max lot, skipped if below the min lot) and the ACTUAL money risked after rounding.

    ``loss_fn`` (#19) prices a candidate volume's entry-to-stop loss with the terminal's own
    ``order_calc_profit``. ``trade_tick_value`` is a single generic number and can differ from the
    loss-side value on converted or asymmetric symbols, so sizing off it alone can overshoot the
    intended risk. Passing the callback keeps this function pure and testable while letting the
    broker have the last word; without it the arithmetic stands.

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
    if loss_fn is not None:
        refined = _refine_volume(side, ref_price, sl, volume, risk_amount, info, loss_fn)
        if refined is None:
            return None
        volume, actual_risk = refined
    return SizedOrder(
        side=side,
        volume=volume,
        sl=round(sl, info.digits),
        tp=round(tp, info.digits),
        risk_amount=actual_risk,
    )


def _refine_volume(
    side: Side,
    entry: float,
    sl: float,
    volume: float,
    risk_amount: float,
    info: SymbolInfo,
    loss_fn: LossFn,
) -> tuple[float, float] | None:
    """Re-solve ``volume`` against the broker's own entry->stop pricing (#19).

    Scales the arithmetic volume by how far the terminal's loss differs from the target, rounds
    DOWN to the lot step, then re-prices and steps down while the rounded volume would still
    over-risk. Returns ``(volume, actual_loss)``, or ``None`` when even the minimum lot over-risks
    -- never silently accepting more than ``risk_amount``.
    """
    priced = loss_fn(side, entry, sl, volume)
    if priced is None or priced <= 0:
        return volume, volume * (abs(entry - sl) / info.tick_size) * info.tick_value
    scaled = volume * (risk_amount / priced)
    vol = math.floor(scaled / info.volume_step) * info.volume_step
    vol = min(vol, info.volume_max)
    for _ in range(3):  # rounding can still leave it a hair over; step down, don't hope
        if vol < info.volume_min:
            return None
        loss = loss_fn(side, entry, sl, vol)
        if loss is None:
            return vol, vol * (abs(entry - sl) / info.tick_size) * info.tick_value
        if loss <= risk_amount:
            return vol, loss
        vol = round(vol - info.volume_step, 8)
    return None


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
        expected_login: int | None = None,
        expected_currency: str | None = None,
        day_start_balance: float | None = None,
    ) -> None:
        self._bridge = bridge
        self._markets = markets
        self._params = signal_params
        self._risk = risk
        self._mode = mode
        self._history = history_bars
        self._long_only = long_only  # N2: a sell signal flattens instead of going short
        # Re-checked every cycle (not just at startup): if the terminal ever reconnects to another
        # account, HALT immediately and do NOT touch positions (they belong to the wrong account).
        self._expected_login = expected_login
        self._expected_currency = expected_currency
        # The loss day's OPENING balance, supplied by the operator for a first launch with no
        # saved state. Without it that path halts rather than guess (see run_once).
        self._day_start_override = day_start_balance
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

    def run_once(self, now: datetime | None = None, wall_now: datetime | None = None) -> None:
        """Process one polling cycle: day roll, safety check, then each market.

        Two clocks, deliberately (#18). ``now`` is the BROKER's frame: MT5 encodes tick and bar
        times as the server's wall clock in Unix seconds, so bar-closure comparisons must happen
        there. ``wall_now`` is real UTC, used for the prop-firm loss day -- that boundary is
        defined in America/Chicago WALL time, and deriving it from the server frame would shift it
        by the server's offset (2-3h on an EET server).
        """
        if self._halted:
            return
        # H3: the daily-limit boundary follows the prop firm's loss day (TTP resets at 16:15 CT on
        # the previous day's closing balance), not UTC/server midnight -- else the daily reference
        # resets at the wrong hour and our budget disagrees with TTP's.
        now = now or self._bridge.server_time()  # BROKER frame -- for bar closure only
        wall = wall_now or datetime.now(tz=UTC)  # real UTC -- for the prop-firm calendar boundary
        account = self._bridge.account()

        # Identity re-check EVERY cycle: if the terminal reconnected to another account, halt and
        # do NOT touch positions (they are the wrong account's). Startup already guarded once.
        if self._expected_login is not None and (
            account.login != self._expected_login or account.currency != self._expected_currency
        ):
            self._halted = True
            self._halt_reason = "account identity mismatch"
            log.critical(
                "SAFETY HALT: connected account is ***%03d/%s, expected ***%03d/%s "
                "-- stopping WITHOUT touching positions.",
                account.login % 1000,
                account.currency,
                self._expected_login % 1000,
                self._expected_currency,
            )
            self._notify.alert("SAFETY HALT: account identity mismatch -- stopped")
            return

        # Day roll: bank the prior day's HWM, reset the daily reference. Persist so a restart keeps
        # the true HWM / day-start rather than resetting to the current balance (K1).
        today = loss_day(wall)  # #18: real UTC, not the server frame
        if self._day is None:
            # First launch (no restored state). The two references pull in OPPOSITE directions,
            # so they are anchored differently and both conservatively:
            #
            # - HWM: banking the current balance can only RAISE the trailing floor. Without it a
            #   50k profile started at a 52k balance would keep a 47.5k floor instead of 49.5k --
            #   looser than the prop firm's own.
            # - Daily: we do NOT know this loss day's opening balance. Taking the current balance
            #   would hand a full fresh 2.5% budget to a runner restarted mid-day after a 2% loss,
            #   allowing 4.5% in one day. Assume instead that the day opened no LOWER than the
            #   account's reference, so the remaining budget can only be under-stated.
            self._risk.on_eod(account.balance)
            if self._day_start_override is None:
                # FAIL CLOSED. Without saved state we do not know this loss day's opening balance,
                # and no heuristic is safe in both directions: max(balance, reference) is only
                # conservative while the account sits BELOW its reference. An account that banked
                # to 55k and is restarted mid-day at 52k would be handed a fresh 2.5% budget from
                # 52k although it is already 5.5% down on the day -- at or past the prop limit.
                # Doing nothing is the safe state; the operator supplies the real day-start.
                self._halted = True
                self._halt_reason = "first launch without a known day-start balance"
                log.critical(
                    "SAFETY HALT: no saved risk state, so this loss day's opening balance is "
                    "unknown (current balance %.2f). Restart with --start-balance <opening "
                    "balance of the current loss day> -- guessing it could hand out a second "
                    "daily loss budget.",
                    account.balance,
                )
                self._notify.alert("SAFETY HALT: first launch needs an explicit --start-balance")
                return
            self._risk.on_new_day(self._day_start_override)
            log.info("first launch: day-start balance set to %.2f", self._day_start_override)
            self._day = today
            self._persist()
        elif today != self._day:
            self._risk.on_eod(account.balance)
            self._risk.on_new_day(account.balance)
            self._day = today
            self._persist()

        if self._apply_cycle_safety(account.equity):
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

    def _apply_cycle_safety(self, equity: float) -> bool:
        """Apply hard stops, then refresh open risk; halt on an invalid position side."""
        flat = self._risk.must_flatten(equity)
        if flat.allowed:
            self._halt_and_flatten(flat.reason)
            return True

        # A bridge-side type rejection is itself a safety halt: proceeding would make the
        # open-risk input unverifiable. Routine terminal read failures remain retryable and must
        # never liquidate a healthy book merely because the bridge uses one general error type.
        try:
            self._risk.open_risk = self._total_open_risk()
        except Mt5SideError as exc:
            self._halt_and_flatten(f"cannot verify open positions: {exc}")
            return True
        return False

    def _position_risk(self, pos: Position, info: SymbolInfo) -> float:
        """Money at risk entry->stop, priced by the TERMINAL when it can (#6).

        ``order_calc_profit`` applies the broker's own currency conversion and contract specifics;
        our tick arithmetic is only the fallback (no stop, or the terminal cannot price it).
        """
        priced = self._bridge.loss_to_stop(pos)
        return priced if priced is not None else position_risk(pos, info)

    def _total_open_risk(self) -> float:
        """Total entry-to-stop risk of every decodable account position.

        A manual or foreign-EA position on an unconfigured symbol contributes its PnL to the
        equity this runner trades against, so its stop-risk must count against the open-risk cap
        too; visiting only ``self._markets`` let check_open admit new trades past the 2% cap.
        The terminal prices any symbol (#6/#19); the tick arithmetic needs our SymbolInfo and is
        only available for configured markets. Any raw record that cannot be decoded, or exposure
        that cannot be priced at all, fails closed: ``inf`` blocks every new entry until the
        operator resolves it. An undecodable owned side remains a semantic safety halt so the
        runner can close every other retrievable owned position.
        """
        snapshot = self._bridge.position_snapshot()
        unverifiable = next(
            (issue for issue in snapshot.issues if issue.magic == MAGIC or issue.magic is None),
            None,
        )
        if unverifiable is not None:
            raise Mt5SideError(unverifiable.reason)
        for issue in snapshot.issues:
            log.critical(
                "cannot decode account position ticket %s on %s -> blocking new entries "
                "until it is resolved",
                issue.ticket,
                issue.symbol,
            )
        if snapshot.issues:
            return math.inf
        infos: dict[str, SymbolInfo] = {}
        for spec in self._markets:
            info = self._bridge.symbol_info(spec.name)
            infos[info.name] = info  # keyed by TERMINAL symbol, which is what positions carry
        total = 0.0
        for pos in snapshot.positions:
            if pos.sl <= 0:  # H5: unbounded downside -> loud warning + worst-case charge below
                log.warning(
                    "open position %s (%s) has NO stop-loss -> charged at worst case",
                    pos.ticket,
                    pos.symbol,
                )
            priced = self._bridge.loss_to_stop(pos)
            if priced is not None:
                total += priced
                continue
            known = infos.get(pos.symbol)
            if known is not None:
                total += position_risk(pos, known)  # arithmetic fallback, worst case if stop-less
                continue
            log.critical(
                "cannot price position %s on unconfigured symbol %s -> blocking new entries "
                "until it is closed or priceable",
                pos.ticket,
                pos.symbol,
            )
            return math.inf
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
        # K1/#7: act on the signal FIRST, then record the bar as handled. A rejected order (or a
        # failed close/reverse) raises out of _act_on_signal, so we never reach the mark below and
        # the SAME bar is retried next cycle -- live can't silently stay flat while the backtest is
        # positioned. The retry is idempotent: owned_positions reflects what actually filled, so a
        # partial reversal (old side already closed) reopens the intended side rather than acting
        # twice. Terminal no-op outcomes (no signal, already positioned, blocked) return normally
        # and DO mark the bar, so we don't reprocess them.
        self._act_on_signal(spec, buy, sell, last, equity)
        self._last_bar_time[spec.name] = last.time
        self._cycle_bars += 1
        self._persist()  # remember the handled bar, so a restart cannot act on it twice

    def _act_on_signal(
        self, spec: MarketSpec, buy: bool, sell: bool, last: Bar, equity: float
    ) -> None:
        """Turn the replayed signal into (at most) one position change for ``spec``.

        Returns normally for every terminal outcome (no signal, already positioned the right way,
        long-only flatten, not sizable, risk-blocked). Raises only if an order it *attempts* fails
        -- the caller relies on that to decide whether the bar may be marked handled (#7).
        """
        if buy == sell:  # no signal (or contradictory) -> hold
            return
        self._cycle_signals += 1
        desired: Side = "BUY" if buy else "SELL"

        current = self._bridge.owned_positions(spec.name)  # never act on manual / foreign-EA trades
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
            # #19: let the terminal price the candidate volume, so lot rounding cannot leave the
            # real stop-out above the intended risk on a converted or asymmetric symbol.
            loss_fn=lambda s, e, stop, vol: self._bridge.loss_for_order(spec.name, s, e, stop, vol),
        )
        if sized is None:
            log.info("[%s] %s signal but not sizable (min-lot/stop) -> skip", spec.name, desired)
            return

        # M2: on a reversal the opposite position is about to be closed, so exclude its stop-risk
        # from the open total -- don't block the replacement trade on risk we're removing.
        exclude = self._position_risk(pos, info) if pos is not None else 0.0
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
            ticket = self._bridge.place_order(
                spec.name, sized.side, sized.volume, sl=sized.sl, tp=sized.tp
            )
            self._reanchor_exits(spec, sized, info, ticket)
        self._notify.signal(
            f"[{spec.name}] {verb} {sized.side} vol={sized.volume} sl={sized.sl} "
            f"tp={sized.tp} risk={sized.risk_amount:.0f} EUR ({self._mode.value})"
        )
        # Account for the new open risk in BOTH modes so a SIGNAL_ONLY dry-run exercises the
        # open-risk cap exactly like EXECUTE would (H4). open_risk is recomputed from live
        # positions each cycle, so this within-cycle increment self-heals next cycle.
        self._risk.on_open(sized.risk_amount)

    def _reanchor_exits(
        self, spec: MarketSpec, sized: SizedOrder, info: SymbolInfo, ticket: int
    ) -> None:
        """Move the just-opened position's SL/TP onto its ACTUAL fill price (backtest parity).

        ``ticket`` is the order ticket ``place_order`` returned; a market order's position carries
        the same ticket, so the position is looked up EXACTLY -- no guessing which one we opened.
        Some terminals (TTP) list the just-opened position a moment after ``order_send`` returns,
        so the lookup polls briefly. Should a broker ever assign a different position ticket, a
        UNIQUE position on the side we just traded is still unambiguous and used as fallback.

        A failure here is not fatal: the order already carries a valid stop, so the worst case is
        the pre-fix behaviour (exits anchored to the signal price), never a naked position.
        """
        try:
            position: Position | None = None
            for attempt in range(5):
                if attempt:
                    time.sleep(0.5)
                mine = self._bridge.owned_positions(spec.name)
                exact = [p for p in mine if p.ticket == ticket]
                same_side = [p for p in mine if p.side == sized.side]
                if exact:
                    position = exact[0]
                    break
                if len(same_side) == 1:
                    position = same_side[0]
                    break
            if position is None:
                log.warning(
                    "[%s] cannot re-anchor exits: position (ticket %d) not listed -> keeping"
                    " signal-anchored SL/TP",
                    spec.name,
                    ticket,
                )
                return
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
                positions = self._owned_positions_for_flatten(spec.name)
                if positions is None:
                    continue
                for pos in positions:  # never flatten manual trades
                    try:
                        self._bridge.close_position(pos)
                    except Exception:
                        log.exception("failed to flatten %s ticket %s", spec.name, pos.ticket)

    def _owned_positions_for_flatten(self, name: str) -> list[Position] | None:
        """Return retrievable owned positions and alert for each undecodable raw record."""
        try:
            snapshot = self._bridge.owned_position_snapshot(name)
        except Exception:
            log.exception("failed to enumerate owned %s positions during safety halt", name)
            self._notify.alert(
                f"SAFETY HALT: could not enumerate owned {name} positions; "
                "manual intervention required"
            )
            return None
        for issue in snapshot.issues:
            log.error(
                "could not decode owned %s position ticket %s during safety halt",
                name,
                issue.ticket,
            )
            self._notify.alert(
                f"SAFETY HALT: could not decode owned {name} position ticket {issue.ticket}; "
                "manual intervention required"
            )
        return list(snapshot.positions)

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


def _live_config() -> object:
    """Load ``config/live/rsi_wpr_bb.py`` by path (config/ is not an import package)."""

    from research.engine.config import load_config_module

    repo_root = REPO_ROOT
    return load_config_module(repo_root / "live" / "config" / "rsi_wpr_bb.py")


def markets_from_live_config() -> list[MarketSpec]:
    """Build the market list from ``config/live/rsi_wpr_bb.py`` (name + fixed SL/TP)."""
    module = _live_config()
    specs: list[MarketSpec] = []
    for factory, _csv, _lev, sl, tp in module.MARKETS:  # type: ignore[attr-defined]
        raw_symbol = factory().raw_symbol.value
        specs.append(MarketSpec(name=raw_symbol, stop_loss_pct=sl, take_profit_pct=tp))
    return specs


def signal_params_from_live_config() -> SignalParams:
    """Build the signal params (default knobs + the frozen no_bb_wpr switches)."""
    module = _live_config()
    switches = {
        k: v
        for k, v in module.STRATEGY_SWITCHES.items()  # type: ignore[attr-defined]
        if k != "long_only"
    }
    return SignalParams(**switches)


def long_only_from_live_config() -> bool:
    """Read the frozen ``long_only`` switch (N2: not a SignalParam; applied by the runner)."""
    module = _live_config()
    return bool(module.STRATEGY_SWITCHES.get("long_only", False))  # type: ignore[attr-defined]


def risk_per_trade_from_live_config() -> float:
    """Per-trade risk FRACTION from the frozen config (M3: the config is the single source)."""
    module = _live_config()
    return float(module.RISK_PER_TRADE_PCT) / 100.0  # type: ignore[attr-defined]
