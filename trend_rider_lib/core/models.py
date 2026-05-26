"""
Data models for Trend Rider library.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any

from .enums import (
    State,
    Classification,
    SignalType,
    TrendEventType,
    UptrendStrength,
    TradeStatus,
    ExitReason,
)


@dataclass
class UptrendRecord:
    """Record of an uptrend period with statistics."""

    start_date: datetime
    cycle_id: Optional[int] = None
    start_state: Optional[str] = None
    end_state: Optional[str] = None
    start_price: Optional[float] = None
    end_price: Optional[float] = None
    end_date: Optional[datetime] = None
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
    weekly_close_history: List[tuple[datetime, float]] = field(default_factory=list)
    daily_close_history: List[tuple[datetime, float]] = field(default_factory=list)
    daily_ema21_history: List[tuple[datetime, float]] = field(default_factory=list)
    daily_ema34_history: List[tuple[datetime, float]] = field(default_factory=list)
    daily_ema55_history: List[tuple[datetime, float]] = field(default_factory=list)

    def calculate_strength(self) -> UptrendStrength:
        """Calculate uptrend strength based on close percentages."""
        if self.num_weeks == 0:
            return UptrendStrength.WEAK

        pct = self.pct_closes_above
        if pct < 0.70:
            return UptrendStrength.WEAK
        elif pct < 0.80:
            return UptrendStrength.DEVELOPING
        elif pct < 0.90:
            return UptrendStrength.MODERATE
        elif pct < 1.00:
            return UptrendStrength.STRONG
        else:
            return UptrendStrength.SUPER_STRONG


@dataclass
class StockContext:
    """Runtime state for a single stock being tracked."""

    ticker: str
    current_state: State = State.WARMUP
    tr_qualified: bool = False

    # Official trend lifecycle tracking
    trend_start_date: Optional[datetime] = None
    trend_end_date: Optional[datetime] = None
    daily_ema21_cross_date: Optional[datetime] = None
    daily_ema21_cross_price: Optional[float] = None
    daily_downtrend_trigger_date: Optional[datetime] = None
    daily_downtrend_trigger_price: Optional[float] = None
    first_buy_zone_date: Optional[datetime] = None
    first_buy_zone_price: Optional[float] = None
    trend_cycle_id: Optional[int] = None

    # Buy signal / crossover tracking
    positive_crossover_date: Optional[datetime] = None
    positive_crossover_price: Optional[float] = None
    buy_signal_emitted: bool = False
    last_buy_signal_date: Optional[datetime] = None
    last_buy_signal_type: Optional[SignalType] = None
    last_buy_signal_crossover_date: Optional[datetime] = None

    # Uptrend tracking
    uptrend_start_date: Optional[datetime] = None
    uptrend_weeks: int = 0
    closes_above_ema: int = 0
    closes_below_ema: int = 0
    current_uptrend: Optional[UptrendRecord] = None
    uptrend_history: List[UptrendRecord] = field(default_factory=list)

    # Buy zone flags
    is_buyzone: bool = False

    # Recovery tracking
    is_crossover_detected: bool = False
    crossover_date: Optional[datetime] = None
    crossover_price: Optional[float] = None

    # Classification
    classification: Classification = Classification.UNQUALIFIED

    # Latest indicator values
    last_ema21: Optional[float] = None
    last_ema34: Optional[float] = None
    last_ema55: Optional[float] = None
    last_close: Optional[float] = None
    last_update: Optional[datetime] = None

    # Metadata
    warmup_complete: bool = False
    candle_count: int = 0
    weekly_candle_count: int = 0


@dataclass
class SignalEvent:
    """A signal event emitted during analysis."""

    ticker: str
    signal_type: SignalType
    date: datetime
    close_price: float
    ema21: Optional[float] = None
    ema34: Optional[float] = None
    ema55: Optional[float] = None
    timeframe: Optional[str] = None
    state: Optional[str] = None
    trend_cycle_id: Optional[int] = None
    trend_start_date: Optional[datetime] = None
    trend_end_date: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TrendEventRecord:
    """Lifecycle event separate from the signal stream."""

    ticker: str
    event_type: TrendEventType
    date: datetime
    close_price: Optional[float] = None
    ema21: Optional[float] = None
    ema34: Optional[float] = None
    ema55: Optional[float] = None
    timeframe: Optional[str] = None
    state: Optional[str] = None
    trend_cycle_id: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TradeRecord:
    """Record of a trade lifecycle."""

    id: Optional[int] = None
    ticker: str = ""
    entry_date: Optional[datetime] = None
    entry_price: float = 0.0
    exit_date: Optional[datetime] = None
    exit_price: Optional[float] = None
    target_price: float = 0.0
    initial_sl: float = 0.0
    current_sl: float = 0.0
    highest_price_seen: float = 0.0
    tsl_step_pct: float = 0.10
    status: TradeStatus = TradeStatus.OPEN
    exit_reason: Optional[ExitReason] = None
    profit_loss_pct: float = 0.0
