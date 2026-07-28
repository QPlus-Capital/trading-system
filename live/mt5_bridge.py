"""MT5 bridge -- data + orders against a running MetaTrader 5 terminal.

Windows-only. Wraps the official ``MetaTrader5`` package into a small, typed surface the
live runner uses: attach to an **already-logged-in** terminal, pull H4 bars, read the
account/positions, place and close orders. No strategy logic here (that is the signal
engine) and no risk logic (that is ``risk_control``) -- this is purely the broker I/O.

Security: prefer attaching to a terminal the user already logged into (``connect()`` with
no credentials). Passwords, if ever passed, come from the environment / password manager,
never from code or the repo.

Symbol map: our research names -> the broker's terminal symbol. Only USTEC differs
(broker: UT100); the FX / metal / index names match but may carry a broker suffix, so each
is resolved against the live terminal's symbol list at connect time.
"""

from __future__ import annotations

import logging
import operator
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal, SupportsIndex

try:  # pragma: no cover - Windows-only dependency; pure helpers stay importable without it
    import MetaTrader5 as mt5
except ImportError:  # pragma: no cover
    mt5 = None

log = logging.getLogger("live")

# Orders placed by this bot carry this magic number, so we can tell them apart from any
# manual trades in the same terminal.
MAGIC = 770077

# Bit flags of ``symbol_info.filling_mode`` (ENUM_SYMBOL_FILLING_FLAGS). The MetaTrader5 Python
# module does not expose these ``SYMBOL_FILLING_*`` names, so the bit values are hard-coded.
_SYMBOL_FILLING_FOK = 1
_SYMBOL_FILLING_IOC = 2
_DEFAULT_ORDER_DEVIATION = 20
_DEFAULT_ORDER_COMMENT = "qplus"

# Our research name -> the broker's base symbol name (before any account suffix).
SYMBOL_MAP: dict[str, str] = {
    "XAUUSD": "XAUUSD",
    "XAGUSD": "XAGUSD",  # silver; the broker carries it (base name matches, suffix resolved live)
    "EURUSD": "EURUSD",
    "GBPUSD": "GBPUSD",
    "AUDUSD": "AUDUSD",
    "USDJPY": "USDJPY",
    "US30": "US30",
    "DE40": "DE40",
    "US500": "US500",
    "USTEC": "UT100",  # broker (MEX Atlantic) calls the Nasdaq-100 cash index UT100
}

Side = Literal["BUY", "SELL"]


class Mt5Error(RuntimeError):
    """Raised when a MetaTrader 5 call fails (init, login, data, or order)."""


class Mt5SideError(Mt5Error):
    """Raised when a runtime side cannot be converted without ambiguity."""


def _runtime_side(
    value: object,
    *,
    position_types: tuple[int, int] | None = None,
) -> Side:
    """Return the canonical side, rejecting every unsupported runtime value."""
    if position_types is not None:
        buy_type, sell_type = position_types
        if isinstance(value, bool):
            raise Mt5SideError(
                "invalid MT5 position type; expected POSITION_TYPE_BUY or POSITION_TYPE_SELL"
            )
        if not isinstance(value, SupportsIndex):
            raise Mt5SideError(
                "invalid MT5 position type; expected POSITION_TYPE_BUY or POSITION_TYPE_SELL"
            )
        try:
            position_type = operator.index(value)
        except TypeError as exc:
            raise Mt5SideError(
                "invalid MT5 position type; expected POSITION_TYPE_BUY or POSITION_TYPE_SELL"
            ) from exc
        if position_type == buy_type:
            return "BUY"
        if position_type == sell_type:
            return "SELL"
        raise Mt5SideError(
            "invalid MT5 position type; expected POSITION_TYPE_BUY or POSITION_TYPE_SELL"
        )
    if isinstance(value, str) and value == "BUY":
        return "BUY"
    if isinstance(value, str) and value == "SELL":
        return "SELL"
    raise Mt5SideError("invalid order side; expected BUY or SELL")


def _order_type(m: Any, value: object, *, opposite: bool) -> int:
    """Return the MT5 order type for a validated side, optionally opposing it."""
    side = _runtime_side(value)
    buy_order = (side == "BUY") != opposite
    return int(m.ORDER_TYPE_BUY if buy_order else m.ORDER_TYPE_SELL)


@dataclass(frozen=True)
class Bar:
    """One completed OHLC bar (epoch seconds, broker feed)."""

    time: int
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class SymbolInfo:
    """The contract details the sizing / order code needs, from the live terminal."""

    name: str
    digits: int
    point: float
    tick_size: float  # price move of one tick
    tick_value: float  # money one lot gains/loses per tick_size (account currency)
    volume_min: float
    volume_step: float
    volume_max: float


@dataclass(frozen=True)
class Position:
    """An open position in the terminal."""

    ticket: int
    symbol: str
    side: Side
    volume: float
    price_open: float
    sl: float
    tp: float
    profit: float
    magic: int = 0  # the EA magic number; ours is MAGIC. 0 / other = manual or a foreign EA.


@dataclass(frozen=True)
class AccountState:
    """Account snapshot used by the risk layer."""

    balance: float
    equity: float
    currency: str
    login: int  # the broker account number -- used to guard against trading the wrong account


def base_symbol(name: str, symbol_map: dict[str, str] = SYMBOL_MAP) -> str:
    """Map our research name to the broker's base symbol (pure; suffix resolved separately)."""
    return symbol_map.get(name, name)


def prefix_matches(base: str, available: Sequence[str]) -> list[str]:
    """Terminal symbols that equal ``base`` or start with it (broker suffix, e.g. ``EURUSD.r``)."""
    if base in available:
        return [base]
    return sorted((s for s in available if s.startswith(base)), key=len)


def match_terminal_symbol(base: str, available: Sequence[str]) -> str | None:
    """The terminal's symbol for ``base``: exact, else the shortest suffixed match, else ``None``.

    M1: only exact/suffix matches are accepted -- the old "merely contains ``base``" fallback
    could silently pick the WRONG instrument (e.g. ``base`` appearing inside an unrelated name),
    which is unacceptable for order routing. An unresolved symbol fails loudly at connect time.
    """
    matches = prefix_matches(base, available)
    return matches[0] if matches else None


class Mt5Bridge:
    """Thin, typed wrapper over the ``MetaTrader5`` terminal connection."""

    _H4 = "TIMEFRAME_H4"  # resolved to mt5.TIMEFRAME_H4 at call time (mt5 may be None on import)

    def __init__(self, symbol_map: dict[str, str] | None = None) -> None:
        self._map = symbol_map if symbol_map is not None else SYMBOL_MAP
        self._resolved: dict[str, str] = {}  # our name -> terminal symbol
        self._connected = False

    # -- connection --

    def connect(
        self,
        *,
        path: str | None = None,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
    ) -> None:
        """Attach to a running, logged-in terminal (default) or initialize with credentials.

        Credentials are optional and, when used, must come from the environment / password
        manager -- never hard-coded. Resolves every configured symbol against the terminal.
        """
        if mt5 is None:
            raise Mt5Error("MetaTrader5 package is not available (Windows-only).")
        kwargs: dict[str, Any] = {}
        if path is not None:
            kwargs["path"] = path
        if login is not None:
            kwargs["login"] = login
        if password is not None:
            kwargs["password"] = password
        if server is not None:
            kwargs["server"] = server
        if not mt5.initialize(**kwargs):
            raise Mt5Error(f"mt5.initialize failed: {mt5.last_error()}")
        self._connected = True
        self._resolve_all()

    def shutdown(self) -> None:
        """Disconnect from the terminal (safe to call repeatedly)."""
        if mt5 is not None and self._connected:
            mt5.shutdown()
        self._connected = False

    def _require(self) -> Any:
        if mt5 is None or not self._connected:
            raise Mt5Error("Not connected to a MetaTrader 5 terminal (call connect() first).")
        return mt5

    def _resolve_all(self) -> None:
        m = self._require()
        symbols = m.symbols_get()
        if symbols is None:
            raise Mt5Error(f"mt5.symbols_get failed: {m.last_error()}")
        available = [s.name for s in symbols]
        missing = []
        for name in self._map:
            base = base_symbol(name, self._map)
            candidates = prefix_matches(base, available)
            terminal = candidates[0] if candidates else None
            if terminal is None:
                missing.append(name)
                continue
            if len(candidates) > 1:  # M1: surface an ambiguous match instead of silently guessing
                log.warning(
                    "symbol %s -> %s is AMBIGUOUS (candidates: %s); using the shortest -- verify!",
                    name,
                    terminal,
                    candidates,
                )
            if not m.symbol_select(terminal, True):  # ensure it's in Market Watch
                raise Mt5Error(f"could not select symbol {terminal} in Market Watch")
            self._resolved[name] = terminal
            log.info("symbol resolved: %s -> %s", name, terminal)  # M1: verifiable mapping
        if missing:
            raise Mt5Error(f"symbols not found in the terminal: {missing}")

    def terminal_symbol(self, name: str) -> str:
        """Return the resolved terminal symbol for our research name."""
        if name not in self._resolved:
            raise Mt5Error(f"symbol {name} was not resolved at connect time")
        return self._resolved[name]

    # -- time --

    def server_time(self) -> datetime:
        """Broker server wall-clock time (for the daily-limit day boundary, H3).

        MT5 encodes a symbol tick's ``time`` as the server's wall clock in Unix seconds, so
        ``fromtimestamp(.., UTC)`` recovers the server calendar day (TTP resets at server
        midnight). Falls back to real UTC now if no resolved symbol has a tick yet.
        """
        m = self._require()
        for terminal in self._resolved.values():
            tick = m.symbol_info_tick(terminal)
            if tick is not None and tick.time:
                return datetime.fromtimestamp(int(tick.time), tz=UTC)
        return datetime.now(tz=UTC)

    # -- market data --

    def latest_bars(self, name: str, n: int) -> list[Bar]:
        """Return the most recent ``n`` H4 bars; the LAST element is the still-forming bar.

        The runner acts on closed bars, so it should drop / ignore the final element.
        """
        m = self._require()
        sym = self.terminal_symbol(name)
        rates = m.copy_rates_from_pos(sym, m.TIMEFRAME_H4, 0, n)
        if rates is None or len(rates) == 0:
            raise Mt5Error(f"no H4 bars for {sym}: {m.last_error()}")
        return [
            Bar(
                time=int(r["time"]),
                open=float(r["open"]),
                high=float(r["high"]),
                low=float(r["low"]),
                close=float(r["close"]),
            )
            for r in rates
        ]

    def symbol_info(self, name: str) -> SymbolInfo:
        """Return the contract/tick/volume details for our research name."""
        m = self._require()
        sym = self.terminal_symbol(name)
        info = m.symbol_info(sym)
        if info is None:
            raise Mt5Error(f"symbol_info failed for {sym}: {m.last_error()}")
        return SymbolInfo(
            name=sym,
            digits=int(info.digits),
            point=float(info.point),
            tick_size=float(info.trade_tick_size),
            tick_value=float(info.trade_tick_value),
            volume_min=float(info.volume_min),
            volume_step=float(info.volume_step),
            volume_max=float(info.volume_max),
        )

    # -- account & positions --

    def account(self) -> AccountState:
        """Return the current balance / equity / currency."""
        m = self._require()
        info = m.account_info()
        if info is None:
            raise Mt5Error(f"account_info failed: {m.last_error()}")
        return AccountState(
            balance=float(info.balance),
            equity=float(info.equity),
            currency=str(info.currency),
            login=int(info.login),
        )

    def positions(self, name: str | None = None) -> list[Position]:
        """Return every decodable account position for account-wide risk and monitoring."""
        return self._positions(name, owner_magic=None)

    def _positions(
        self,
        name: str | None,
        *,
        owner_magic: int | None,
    ) -> list[Position]:
        """Return decodable positions, optionally restricted to this runner before conversion.

        Every decodable account position remains visible to account-wide risk. An unsupported
        foreign position is ignored after its independent magic value proves that the runner
        neither owns nor may act on it. An unsupported owned position still fails closed.
        """
        m = self._require()
        if name is not None:
            raw = m.positions_get(symbol=self.terminal_symbol(name))
        else:
            raw = m.positions_get()
        if raw is None:
            raise Mt5Error(f"positions_get failed: {m.last_error()}")
        out: list[Position] = []
        for p in raw:
            magic = int(p.magic)
            if owner_magic is not None and magic != owner_magic:
                continue
            try:
                side = _runtime_side(
                    p.type,
                    position_types=(int(m.POSITION_TYPE_BUY), int(m.POSITION_TYPE_SELL)),
                )
            except Mt5SideError:
                if magic == MAGIC:
                    raise
                log.warning(
                    "ignoring foreign position ticket %s with unsupported MT5 position type",
                    int(p.ticket),
                )
                continue
            out.append(
                Position(
                    ticket=int(p.ticket),
                    symbol=str(p.symbol),
                    side=side,
                    volume=float(p.volume),
                    price_open=float(p.price_open),
                    sl=float(p.sl),
                    tp=float(p.tp),
                    profit=float(p.profit),
                    magic=magic,
                )
            )
        return out

    def owned_positions(self, name: str | None = None) -> list[Position]:
        """Only the positions THIS runner opened (magic == MAGIC).

        Everything the runner opens, closes, modifies or flattens goes through here, so it can
        never touch a manual trade or another EA's position on the same account. Account-level
        risk still counts ALL exposure (see the runner) -- ownership limits what we *act on*,
        not what we *account for*.
        """
        return self._positions(name, owner_magic=MAGIC)

    def loss_for_order(
        self, name: str, side: Side, entry: float, sl: float, volume: float
    ) -> float | None:
        """What ``volume`` lots of ``name`` would lose going from ``entry`` to ``sl``, in account
        currency, priced by the terminal (#19).

        ``trade_tick_value`` is one generic number per symbol and can differ from the loss-side
        value on converted or asymmetric symbols, so sizing off it alone can quietly exceed the
        intended risk. ``order_calc_profit`` applies the broker's own conversion. ``None`` when the
        terminal cannot price it -- the caller then keeps the arithmetic result.

        Measured against the live TTP terminal (2026-07-18): the arithmetic matches the broker to
        1.000 on eight of ten markets, but **DE40 is out by a factor of 1.144** (EUR-quoted index
        on a USD account) and USDJPY by 1.005. Sized off the arithmetic alone, a DE40 stop-out
        cost 0.206% instead of the intended 0.18%. This is not a theoretical correction.
        """
        m = self._require()
        order_type = _order_type(m, side, opposite=False)
        profit = m.order_calc_profit(order_type, self.terminal_symbol(name), volume, entry, sl)
        if profit is None:
            return None
        return max(0.0, -float(profit))

    def loss_to_stop(self, position: Position) -> float | None:
        """Account-currency loss if ``position`` ran from its ENTRY to its stop.

        Priced by the terminal itself (``order_calc_profit``), so the currency conversion and
        contract specifics are the broker's rather than our own tick arithmetic (#6) -- which is
        what goes wrong on cross-currency symbols whose ``tick_value`` is not in account currency.

        Entry->stop (not current->stop) is the measure that matches the risk budgets, which are
        anchored to the DAY-START balance: floating profit is excluded on both sides, so counting
        it here too would charge it twice.

        Returns ``None`` when the position has no stop or the terminal cannot price it; the caller
        then falls back to the arithmetic estimate.
        """
        side = _runtime_side(position.side)
        if position.sl <= 0:
            return None  # unbounded downside -> the caller charges the worst case
        m = self._require()
        order_type = _order_type(m, side, opposite=False)
        profit = m.order_calc_profit(
            order_type, position.symbol, position.volume, position.price_open, position.sl
        )
        if profit is None:
            return None
        return max(0.0, -float(profit))

    def history_deals(self, since: datetime) -> list[dict[str, Any]]:
        """Raw closed deals since ``since`` (for monitoring); empty list if none.

        Returns the fields needed to reconstruct round-trip trades + the realized equity curve:
        ticket, time (epoch s), type (0=buy,1=sell,2=balance), entry (0=in,1=out),
        position_id, symbol, volume, price, and every Decimal money leg: profit, swap, commission,
        and fee.
        """
        m = self._require()
        raw = m.history_deals_get(since, datetime.now(tz=UTC))
        if raw is None:
            return []
        return [
            {
                "ticket": int(d.ticket),
                "time": int(d.time),
                "type": int(d.type),
                "entry": int(d.entry),
                "position_id": int(d.position_id),
                "symbol": str(d.symbol),
                "volume": float(d.volume),
                "price": float(d.price),
                "profit": Decimal(str(d.profit)),
                "swap": Decimal(str(d.swap)),
                "commission": Decimal(str(d.commission)),
                "fee": Decimal(str(getattr(d, "fee", 0))),
            }
            for d in raw
        ]

    # -- orders --

    def _filling_mode(self, sym: str) -> int:
        """Pick an order filling mode the symbol supports (IOC preferred, else FOK).

        ``symbol_info.filling_mode`` is a bitmask of the ALLOWED fill modes. The MetaTrader5
        Python module does NOT export the ``SYMBOL_FILLING_*`` bit names (only the
        ``ORDER_FILLING_*`` order types), so the bit values are hard-coded here.
        """
        m = self._require()
        info = m.symbol_info(sym)
        modes = int(getattr(info, "filling_mode", 0)) if info is not None else 0
        if modes & _SYMBOL_FILLING_IOC:
            return int(m.ORDER_FILLING_IOC)
        if modes & _SYMBOL_FILLING_FOK:
            return int(m.ORDER_FILLING_FOK)
        # N4: brokers typically reject ORDER_FILLING_RETURN for market DEALs; fall back to FOK
        # (fill-or-kill) instead, and warn so the mismatch surfaces on the first order.
        log.warning("%s advertises no IOC/FOK filling mode; falling back to FOK", sym)
        return int(m.ORDER_FILLING_FOK)

    def place_order(
        self,
        name: str,
        side: Side,
        volume: float,
        *,
        sl: float | None = None,
        tp: float | None = None,
        deviation: int = _DEFAULT_ORDER_DEVIATION,
        comment: str = _DEFAULT_ORDER_COMMENT,
    ) -> int:
        """Send a market order; return the resulting deal/order ticket. Raises on rejection."""
        m = self._require()
        order_type = _order_type(m, side, opposite=False)
        sym = self.terminal_symbol(name)
        tick = m.symbol_info_tick(sym)
        if tick is None:
            raise Mt5Error(f"no tick for {sym}: {m.last_error()}")
        price = float(tick.ask) if order_type == m.ORDER_TYPE_BUY else float(tick.bid)
        request = {
            "action": m.TRADE_ACTION_DEAL,
            "symbol": sym,
            "volume": float(volume),
            "type": order_type,
            "price": price,
            "sl": float(sl) if sl is not None else 0.0,
            "tp": float(tp) if tp is not None else 0.0,
            "deviation": int(deviation),
            "magic": MAGIC,
            "comment": comment,
            "type_time": m.ORDER_TIME_GTC,
            "type_filling": self._filling_mode(sym),
        }
        result = m.order_send(request)
        if result is None:
            raise Mt5Error(f"order_send returned None for {sym}: {m.last_error()}")
        if result.retcode != m.TRADE_RETCODE_DONE:
            raise Mt5Error(f"order rejected for {sym}: retcode={result.retcode} ({result.comment})")
        return int(result.order)

    def modify_sltp(self, position: Position, *, sl: float, tp: float) -> None:
        """Re-set an OPEN position's stop-loss / take-profit. Raises on rejection.

        Used to re-anchor the exits to the price that actually filled (the terminal's
        ``price_open``), which is what the backtest anchors to. Sends only the SL/TP, never a
        volume or a price, so it cannot open, close or resize anything.
        """
        m = self._require()
        request = {
            "action": m.TRADE_ACTION_SLTP,
            "symbol": position.symbol,
            "position": position.ticket,
            "sl": float(sl),
            "tp": float(tp),
            "magic": MAGIC,
        }
        result = m.order_send(request)
        if result is None:
            raise Mt5Error(f"modify_sltp returned None for {position.symbol}: {m.last_error()}")
        if result.retcode != m.TRADE_RETCODE_DONE:
            raise Mt5Error(
                f"modify_sltp rejected for {position.symbol}: "
                f"retcode={result.retcode} ({result.comment})"
            )

    def close_position(
        self,
        position: Position,
        *,
        deviation: int = _DEFAULT_ORDER_DEVIATION,
    ) -> None:
        """Close an open position with an opposing market order. Raises on rejection."""
        m = self._require()
        order_type = _order_type(m, position.side, opposite=True)
        sym = position.symbol
        tick = m.symbol_info_tick(sym)
        if tick is None:
            raise Mt5Error(f"no tick for {sym}: {m.last_error()}")
        price = float(tick.ask) if order_type == m.ORDER_TYPE_BUY else float(tick.bid)
        request = {
            "action": m.TRADE_ACTION_DEAL,
            "symbol": sym,
            "volume": position.volume,
            "type": order_type,
            "position": position.ticket,
            "price": price,
            "deviation": int(deviation),
            "magic": MAGIC,
            "comment": "qplus-close",
            "type_time": m.ORDER_TIME_GTC,
            "type_filling": self._filling_mode(sym),
        }
        result = m.order_send(request)
        if result is None:
            raise Mt5Error(f"close order_send returned None for {sym}: {m.last_error()}")
        if result.retcode != m.TRADE_RETCODE_DONE:
            raise Mt5Error(f"close rejected for {sym}: retcode={result.retcode} ({result.comment})")
