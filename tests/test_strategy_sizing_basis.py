"""The sizing basis a continuous run measures every window from.

The property: with ``sizing_equity`` set, the position a trade takes does NOT depend on what the
account is worth. A growing balance inside one continuous run is the same thing as a larger
starting balance here, so varying the balance while pinning the basis is a faithful proxy for the
failure -- an index run whose compounding account is not scale-invariant -- rather than a
restatement of the code. A guard test covers the other half of that isolation: an entry the engine
refuses must not vanish from a scoring run.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest
from core.instruments import us30
from core.strategies.rsi_wpr_bb import RsiWprBb, RsiWprBbConfig
from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
from nautilus_trader.backtest.models import FillModel
from nautilus_trader.config import LoggingConfig
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.enums import AccountType, OmsType
from nautilus_trader.model.identifiers import TraderId, Venue
from nautilus_trader.model.objects import Money

_INSTR = us30()
_BAR_TYPE = BarType.from_str(f"{_INSTR.id}-1-HOUR-LAST-EXTERNAL")
_H = 3_600_000_000_000


class _ForcedEntry(RsiWprBb):
    """Real strategy and real sizing; only the entry TRIGGER is forced."""

    def __init__(self, config: RsiWprBbConfig) -> None:
        super().__init__(config)
        self._done = False

    def on_bar(self, bar: Bar) -> None:
        if self._done or bar.ts_event != 3 * _H:
            return
        self._done = True
        self._go_long(bar.close.as_double(), bar.ts_event)


def _bar(price: float, ts: int) -> Bar:
    p = _INSTR.make_price
    return Bar(_BAR_TYPE, p(price), p(price), p(price), p(price), _INSTR.make_qty(1), ts, ts)


def _entry_qty(*, balance: float, sizing_equity: Decimal) -> float:
    """The quantity the strategy actually sized, at a given account balance."""
    engine = BacktestEngine(
        BacktestEngineConfig(
            trader_id=TraderId("T-001"), logging=LoggingConfig(bypass_logging=True)
        )
    )
    engine.add_venue(
        venue=Venue("TTP"),
        oms_type=OmsType.NETTING,
        account_type=AccountType.MARGIN,
        base_currency=USD,
        starting_balances=[Money(balance, USD)],
        fill_model=FillModel(),
    )
    engine.add_instrument(_INSTR)
    engine.add_data([_bar(100.0, i * _H) for i in range(1, 8)])
    engine.add_strategy(
        _ForcedEntry(
            RsiWprBbConfig(
                instrument_id=_INSTR.id,
                bar_type=_BAR_TYPE,
                trade_size=Decimal(1),
                stop_loss_pct=1.0,
                take_profit_pct=2.0,
                risk_per_trade_pct=1.0,
                sizing_equity=sizing_equity,
                flatten_on_stop=False,
            )
        )
    )
    try:
        engine.run()
        orders = engine.trader.generate_orders_report()
        entries = orders[(orders["type"] == "MARKET") & (orders["side"] == "BUY")]
        assert len(entries) == 1, "the fixture must place exactly one entry, or it proves nothing"
        return float(entries["quantity"].iloc[0])
    finally:
        engine.dispose()


def test_without_a_fixed_basis_the_position_grows_with_the_account() -> None:
    """The control. Without this the test below could pass on a strategy that never sizes at all.

    Four times the equity buys four times the position, because ``risk_per_trade_pct`` is a
    percentage OF the account. That is correct for live trading -- and it is exactly what a
    continuous run turns into an artefact, since a late window then trades an account earlier
    windows grew.
    """
    small = _entry_qty(balance=100_000.0, sizing_equity=Decimal(0))
    large = _entry_qty(balance=400_000.0, sizing_equity=Decimal(0))
    assert large == pytest.approx(4 * small), "sizing must track the account when no basis is set"


def test_a_fixed_basis_makes_the_position_independent_of_the_account() -> None:
    """The property a continuous walk-forward needs.

    Same basis, four times the balance, identical position. Every window in a span is then measured
    on the conditions of one account size, so the mean over windows is an equal-weighted measure of
    edge rather than a curve weighted towards whatever the account has become.
    """
    small = _entry_qty(balance=100_000.0, sizing_equity=Decimal(100_000))
    large = _entry_qty(balance=400_000.0, sizing_equity=Decimal(100_000))
    assert small == large, "a fixed basis must ignore the account balance entirely"


def test_the_fixed_basis_is_the_size_it_claims_to_be() -> None:
    """A basis that is merely CONSTANT would satisfy the test above while sizing anything at all.

    At a 1% stop on a price of 100 the stop distance is 1.0, so risking 1% of a 100k basis is
    1,000 units. Pinning the number keeps the basis meaningful rather than merely stable.
    """
    assert _entry_qty(balance=400_000.0, sizing_equity=Decimal(100_000)) == pytest.approx(1_000.0)


def test_a_negative_or_zero_basis_falls_back_to_the_account() -> None:
    """Zero is the documented default and every live path uses it.

    A basis guarded with ``> 0`` rather than ``is not None`` means an unset value can never be
    mistaken for "size nothing", which would silently stop a live strategy from trading.
    """
    assert _entry_qty(balance=250_000.0, sizing_equity=Decimal(0)) == pytest.approx(2_500.0)


def _config(sizing_equity: Decimal) -> RsiWprBbConfig:
    return RsiWprBbConfig(
        instrument_id=_INSTR.id,
        bar_type=_BAR_TYPE,
        trade_size=Decimal(1),
        stop_loss_pct=1.0,
        take_profit_pct=2.0,
        risk_per_trade_pct=1.0,
        sizing_equity=sizing_equity,
    )


class _Denial(SimpleNamespace):
    """The one field the refusal reads off an OrderDenied / OrderRejected event."""


def test_a_scoring_run_refuses_a_denied_or_rejected_entry() -> None:
    """The margin channel constant sizing does not close on its own.

    Percent-risk sizing scales the position DOWN with the account, so a small account never denies
    an entry by itself -- but a scoring run sizes off a fixed basis, not the account, and the
    engine still enforces margin against the real (drawn-down) balance. A denied entry then
    vanishes from the report and the window scores as a harmless zero-trade window. Both the
    engine's denial callback and its rejection callback must turn that into a hard stop.

    The guard's own logic is tested directly rather than through a bespoke margin scenario: the
    property is "a scoring run raises on a dropped order", independent of which engine condition
    dropped it.
    """
    scoring = RsiWprBb(_config(Decimal(1_000_000)))
    with pytest.raises(RuntimeError, match="lost an entry"):
        scoring.on_order_denied(_Denial(reason="MARGIN"))
    with pytest.raises(RuntimeError, match="lost an entry"):
        scoring.on_order_rejected(_Denial(reason="REJECTED_BY_VENUE"))


def test_a_live_run_swallows_a_denied_or_rejected_entry() -> None:
    """The same events, with no basis set, must NOT raise -- live has to survive rejections.

    A real rejection is routine live (a re-quote, a closed session), and the runner must keep
    trading. The guard is scoped to scoring runs by the ``sizing_equity > 0`` check alone, so this
    pins that it stays silent on the live default.
    """
    live = RsiWprBb(_config(Decimal(0)))
    live.on_order_denied(_Denial(reason="MARGIN"))  # must not raise
    live.on_order_rejected(_Denial(reason="REJECTED_BY_VENUE"))  # must not raise
