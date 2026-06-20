"""
Core data models for the Trend Rider library.

All model classes are now @dataclass with a shared generic serializer
(see ``.dataclass_serializer``) that handles datetime, Enum, nested objects,
and property-backed fields automatically.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .dataclass_serializer import from_dict as _from_dict, to_dict as _to_dict
from .enums import (
    Classification,
    ExitReason,
    SignalType,
    TradeStatus,
    TrendEventType,
    UptrendStrength,
)


# ---------------------------------------------------------------------------
# UptrendRecord
# ---------------------------------------------------------------------------


@dataclass(kw_only=True)
class UptrendRecord:
    """Record of an uptrend cycle."""

    start_date: datetime = datetime.min
    end_date: Optional[datetime] = None
    cycle_id: Optional[int] = None
    start_state: Optional[str] = None
    end_state: Optional[str] = None
    start_price: Optional[float] = None
    end_price: Optional[float] = None
    first_buy_zone_date: Optional[datetime] = None
    first_buy_zone_price: Optional[float] = None
    daily_ema21_cross_date: Optional[datetime] = None
    daily_ema21_cross_price: Optional[float] = None
    daily_downtrend_trigger_date: Optional[datetime] = None
    daily_downtrend_trigger_price: Optional[float] = None
    num_weeks: int = 0
    closes_above_ema: int = 0
    closes_below_ema: int = 0
    pct_closes_above: float = 0.0
    strength: Optional[UptrendStrength] = None
    highest_price: Optional[float] = None
    highest_price_date: Optional[datetime] = None
    lowest_price: Optional[float] = None
    lowest_price_date: Optional[datetime] = None
    roc_1w_pct: Optional[float] = None
    roc_3w_pct: Optional[float] = None
    roc_6m_pct: Optional[float] = None
    roc_9m_pct: Optional[float] = None
    max_profit_pct: Optional[float] = None
    trend_roc_pct: Optional[float] = None
    ema21_slope: Optional[float] = None
    ema34_55_spread: Optional[float] = None
    ema34_55_spread_pct: Optional[float] = None
    efficiency_ratio: Optional[float] = None
    ath_price: Optional[float] = None
    ath_date: Optional[datetime] = None
    distance_from_ath_abs: Optional[float] = None
    distance_from_ath_pct: Optional[float] = None
    weekly_close_history: List = field(default_factory=list)
    daily_close_history: List = field(default_factory=list)
    daily_ema21_history: List = field(default_factory=list)
    daily_ema34_history: List = field(default_factory=list)
    daily_ema55_history: List = field(default_factory=list)

    def calculate_strength(self) -> UptrendStrength:
        """Determine uptrend strength based on pct_closes_above ratio."""
        pct = self.pct_closes_above
        if pct is None:
            return UptrendStrength.WEAK
        if pct >= 1.0:
            return UptrendStrength.SUPER_STRONG
        elif pct >= 0.90:
            return UptrendStrength.STRONG
        elif pct >= 0.80:
            return UptrendStrength.MODERATE
        elif pct >= 0.70:
            return UptrendStrength.DEVELOPING
        else:
            return UptrendStrength.WEAK

    # ------------------------------------------------------------------
    # Serialization (thin wrappers around the generic serializer)
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return _to_dict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "UptrendRecord":
        """Reconstruct from a dict (deserialization)."""
        return _from_dict(cls, d)


# ---------------------------------------------------------------------------
# SignalEvent
# ---------------------------------------------------------------------------


@dataclass(kw_only=True)
class SignalEvent:
    """Event representing a trading signal."""

    ticker: str
    signal_type: SignalType
    date: Optional[datetime] = None
    close_price: Optional[float] = None
    ema21: Optional[float] = None
    ema34: Optional[float] = None
    ema55: Optional[float] = None
    timeframe: Optional[str] = None
    state: Optional[str] = None
    trend_cycle_id: Optional[int] = None
    trend_start_date: Optional[datetime] = None
    trend_end_date: Optional[datetime] = None
    metadata: Optional[dict] = None

    def __post_init__(self):
        """Ensure metadata is never None."""
        if self.metadata is None:
            self.metadata = {}

    # ------------------------------------------------------------------
    # Serialization (thin wrappers around the generic serializer)
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return _to_dict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SignalEvent":
        """Reconstruct from a dict (deserialization)."""
        return _from_dict(cls, d)


# ---------------------------------------------------------------------------
# TrendEventRecord
# ---------------------------------------------------------------------------


@dataclass(kw_only=True)
class TrendEventRecord:
    """Record of a trend lifecycle event."""

    ticker: str
    trend_cycle_id: Optional[int] = None
    event_type: Optional[TrendEventType] = None
    date: Optional[datetime] = None
    timeframe: Optional[str] = None
    state: Optional[str] = None
    close_price: Optional[float] = None
    ema21: Optional[float] = None
    ema34: Optional[float] = None
    ema55: Optional[float] = None
    metadata: Optional[dict] = None

    def __post_init__(self):
        """Ensure metadata is never None."""
        if self.metadata is None:
            self.metadata = {}

    # ------------------------------------------------------------------
    # Serialization (thin wrappers around the generic serializer)
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return _to_dict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TrendEventRecord":
        """Reconstruct from a dict (deserialization)."""
        return _from_dict(cls, d)


# ---------------------------------------------------------------------------
# TradeRecord
# ---------------------------------------------------------------------------


@dataclass(kw_only=True)
class TradeRecord:
    """Record of a trade with trailing stop loss."""

    id: Optional[int] = None
    ticker: Optional[str] = None
    entry_date: Optional[datetime] = None
    entry_price: Optional[float] = None
    exit_date: Optional[datetime] = None
    exit_price: Optional[float] = None
    target_price: Optional[float] = None
    initial_sl: Optional[float] = None
    current_sl: Optional[float] = None
    highest_price_seen: Optional[float] = None
    tsl_step_pct: Optional[float] = None
    status: Optional[TradeStatus] = None
    exit_reason: Optional[ExitReason] = None
    profit_loss_pct: Optional[float] = None

    # ------------------------------------------------------------------
    # Serialization (thin wrappers around the generic serializer)
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return _to_dict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TradeRecord":
        """Reconstruct from a dict (deserialization)."""
        return _from_dict(cls, d)


# ---------------------------------------------------------------------------
# StockContext
# ---------------------------------------------------------------------------


@dataclass(kw_only=True)
class StockContext:
    """Central context object holding all analysis state for a stock.

    Notes
    -----
    * ``current_state`` is stored as a **string** (not a ``State`` enum)
      so that the FSM can pass it directly to ``fsm.machine.set_state()``.
    * ``tr_qualified`` is a **one-way latch** – once set to ``True`` it can
      never be reset to ``False``.  This is enforced by ``__setattr__``.
    """

    # -- Constructor fields (all unified – no more "extra attrs" split) -----

    ticker: str

    # State / qualification
    current_state: Optional[str] = None
    tr_qualified: bool = False
    is_buyzone: bool = False
    is_crossover_detected: bool = False
    classification: Optional[Classification] = None

    # EMA values
    last_ema21: Optional[float] = None
    last_ema34: Optional[float] = None
    last_ema55: Optional[float] = None
    last_close: Optional[float] = None

    # Trend dates (most are ``datetime``; serializer handles ISO ↔ datetime)
    trend_start_date: Optional[datetime] = None
    trend_end_date: Optional[datetime] = None
    daily_ema21_cross_date: Optional[datetime] = None
    daily_downtrend_trigger_date: Optional[datetime] = None
    first_buy_zone_date: Optional[datetime] = None
    positive_crossover_date: Optional[datetime] = None
    crossover_date: Optional[datetime] = None
    uptrend_start_date: Optional[datetime] = None
    last_update: Optional[datetime] = None

    # Prices
    crossover_price: Optional[float] = None
    daily_ema21_cross_price: Optional[float] = None
    daily_downtrend_trigger_price: Optional[float] = None
    first_buy_zone_price: Optional[float] = None
    positive_crossover_price: Optional[float] = None

    # Signal tracking
    buy_signal_emitted: bool = False
    last_buy_signal_type: Optional[str] = None
    last_buy_signal_date: Optional[datetime] = None
    last_buy_signal_crossover_date: Optional[datetime] = None

    # Counters
    uptrend_weeks: int = 0
    weekly_candle_count: int = 0
    candle_count: int = 0
    closes_above_ema: int = 0
    closes_below_ema: int = 0

    # Warmup / cycle
    warmup_complete: bool = False
    trend_cycle_id: Optional[int] = None

    # Metadata
    longName: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    marketCap: Optional[float] = None
    website: Optional[str] = None
    nextDividendDate: Optional[str] = None
    isin: Optional[str] = None

    # Nested objects
    current_uptrend: Optional[UptrendRecord] = None
    uptrend_history: List[UptrendRecord] = field(default_factory=list)

    # ------------------------------------------------------------------
    # One-way latch for tr_qualified
    # ------------------------------------------------------------------

    def __setattr__(self, name: str, value: Any) -> None:
        """Enforce the ``tr_qualified`` one-way latch.

        Once ``tr_qualified`` is ``True``, all subsequent attempts to set
        it to ``False`` are silently ignored.
        """
        if name == "tr_qualified" and not value:
            # Only block if the current value is already True
            existing = self.__dict__.get("tr_qualified", False)
            if existing:
                return
        super().__setattr__(name, value)

    # ------------------------------------------------------------------
    # Backward-compat helpers
    # ------------------------------------------------------------------

    def __post_init__(self):
        """Normalise state after construction / deserialisation."""
        # Backward-compat: old data serialised State enum as "State.DOWNTREND"
        if self.current_state and isinstance(self.current_state, str) and self.current_state.startswith("State."):
            self.current_state = self.current_state.replace("State.", "")

    # ------------------------------------------------------------------
    # Serialization (thin wrappers around the generic serializer)
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return _to_dict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StockContext":
        """Reconstruct a StockContext from a dict (deserialization)."""
        return _from_dict(cls, d)


# ---------------------------------------------------------------------------
# Backward-compatible alias
# ---------------------------------------------------------------------------
# ``context_from_dict`` was previously a module-level function.  It is kept
# here so that existing importers (e.g. ``app.database``) continue to work
# without modification.
context_from_dict = StockContext.from_dict