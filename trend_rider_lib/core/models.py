"""
Core data models for the Trend Rider library.
"""
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime
import json
import logging

from .enums import Classification, ExitReason, SignalType, TradeStatus, TrendEventType, UptrendStrength


class UptrendRecord:
    """Record of an uptrend cycle."""

    def __init__(self, start_date: datetime):
        self.start_date: datetime = start_date
        self.end_date: Optional[datetime] = None
        self.cycle_id: Optional[int] = None
        self.start_state: Optional[str] = None
        self.end_state: Optional[str] = None
        self.start_price: Optional[float] = None
        self.end_price: Optional[float] = None
        self.first_buy_zone_date: Optional[datetime] = None
        self.first_buy_zone_price: Optional[float] = None
        self.daily_ema21_cross_date: Optional[datetime] = None
        self.daily_ema21_cross_price: Optional[float] = None
        self.daily_downtrend_trigger_date: Optional[datetime] = None
        self.daily_downtrend_trigger_price: Optional[float] = None
        self.num_weeks: int = 0
        self.closes_above_ema: int = 0
        self.closes_below_ema: int = 0
        self.pct_closes_above: float = 0.0
        self.strength: Optional[UptrendStrength] = None
        self.highest_price: Optional[float] = None
        self.highest_price_date: Optional[datetime] = None
        self.lowest_price: Optional[float] = None
        self.lowest_price_date: Optional[datetime] = None
        self.roc_1w_pct: Optional[float] = None
        self.roc_3w_pct: Optional[float] = None
        self.roc_6m_pct: Optional[float] = None
        self.roc_9m_pct: Optional[float] = None
        self.max_profit_pct: Optional[float] = None
        self.trend_roc_pct: Optional[float] = None
        self.ema21_slope: Optional[float] = None
        self.ema34_55_spread: Optional[float] = None
        self.ema34_55_spread_pct: Optional[float] = None
        self.efficiency_ratio: Optional[float] = None
        self.ath_price: Optional[float] = None
        self.ath_date: Optional[datetime] = None
        self.distance_from_ath_abs: Optional[float] = None
        self.distance_from_ath_pct: Optional[float] = None
        self.weekly_close_history: List = []
        self.daily_close_history: List = []
        self.daily_ema21_history: List = []
        self.daily_ema34_history: List = []
        self.daily_ema55_history: List = []

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

    def to_dict(self) -> Dict[str, Any]:
        """Serialize UptrendRecord to dict for JSON persistence."""
        result = {}
        for attr in (
            "start_date", "end_date", "cycle_id", "start_state", "end_state",
            "start_price", "end_price", "first_buy_zone_date", "first_buy_zone_price",
            "daily_ema21_cross_date", "daily_ema21_cross_price",
            "daily_downtrend_trigger_date", "daily_downtrend_trigger_price",
            "num_weeks", "closes_above_ema", "closes_below_ema", "pct_closes_above",
            "strength",
            "highest_price", "highest_price_date", "lowest_price", "lowest_price_date",
            "roc_1w_pct", "roc_3w_pct", "roc_6m_pct", "roc_9m_pct",
            "max_profit_pct", "trend_roc_pct", "ema21_slope",
            "ema34_55_spread", "ema34_55_spread_pct", "efficiency_ratio",
            "ath_price", "ath_date", "distance_from_ath_abs", "distance_from_ath_pct",
            "weekly_close_history", "daily_close_history",
            "daily_ema21_history", "daily_ema34_history", "daily_ema55_history",
        ):
            val = getattr(self, attr, None)
            if isinstance(val, datetime):
                val = val.isoformat()
            elif isinstance(val, UptrendStrength):
                val = val.name
            result[attr] = val
        return result

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "UptrendRecord":
        """Reconstruct an UptrendRecord from a dict (deserialization)."""
        start_date = d.get("start_date")
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date)
        elif start_date is None:
            start_date = datetime.min
        record = cls(start_date=start_date)
        # Map fields
        for attr in (
            "end_date", "cycle_id", "start_state", "end_state",
            "start_price", "end_price", "first_buy_zone_date", "first_buy_zone_price",
            "daily_ema21_cross_date", "daily_ema21_cross_price",
            "daily_downtrend_trigger_date", "daily_downtrend_trigger_price",
            "num_weeks", "closes_above_ema", "closes_below_ema", "pct_closes_above",
            "strength",
            "highest_price", "highest_price_date", "lowest_price", "lowest_price_date",
            "roc_1w_pct", "roc_3w_pct", "roc_6m_pct", "roc_9m_pct",
            "max_profit_pct", "trend_roc_pct", "ema21_slope",
            "ema34_55_spread", "ema34_55_spread_pct", "efficiency_ratio",
            "ath_price", "ath_date", "distance_from_ath_abs", "distance_from_ath_pct",
            "weekly_close_history", "daily_close_history",
            "daily_ema21_history", "daily_ema34_history", "daily_ema55_history",
        ):
            val = d.get(attr)
            # Convert ISO datetime strings back to datetime
            if attr.endswith("_date") and isinstance(val, str):
                try:
                    val = datetime.fromisoformat(val)
                except (ValueError, TypeError):
                    pass
            if attr == "strength" and isinstance(val, str):
                val = UptrendStrength[val]
            setattr(record, attr, val)
        return record


class SignalEvent:
    """Event representing a trading signal."""

    def __init__(
        self,
        ticker: str,
        signal_type: SignalType,
        date: Optional[datetime] = None,
        close_price: Optional[float] = None,
        ema21: Optional[float] = None,
        ema34: Optional[float] = None,
        ema55: Optional[float] = None,
        timeframe: Optional[str] = None,
        state: Optional[str] = None,
        trend_cycle_id: Optional[int] = None,
        trend_start_date: Optional[datetime] = None,
        trend_end_date: Optional[datetime] = None,
        metadata: Optional[dict] = None,
    ):
        self.ticker = ticker
        self.signal_type = signal_type
        self.date = date
        self.close_price = close_price
        self.ema21 = ema21
        self.ema34 = ema34
        self.ema55 = ema55
        self.timeframe = timeframe
        self.state = state
        self.trend_cycle_id = trend_cycle_id
        self.trend_start_date = trend_start_date
        self.trend_end_date = trend_end_date
        self.metadata = metadata or {}


class TrendEventRecord:
    """Record of a trend lifecycle event."""

    def __init__(
        self,
        ticker: str,
        trend_cycle_id: Optional[int] = None,
        event_type: Optional[TrendEventType] = None,
        date: Optional[datetime] = None,
        timeframe: Optional[str] = None,
        state: Optional[str] = None,
        close_price: Optional[float] = None,
        ema21: Optional[float] = None,
        ema34: Optional[float] = None,
        ema55: Optional[float] = None,
        metadata: Optional[dict] = None,
    ):
        self.ticker = ticker
        self.trend_cycle_id = trend_cycle_id
        self.event_type = event_type
        self.date = date
        self.timeframe = timeframe
        self.state = state
        self.close_price = close_price
        self.ema21 = ema21
        self.ema34 = ema34
        self.ema55 = ema55
        self.metadata = metadata or {}


class TradeRecord:
    """Record of a trade with trailing stop loss."""

    def __init__(
        self,
        id: Optional[int] = None,
        ticker: Optional[str] = None,
        entry_date: Optional[datetime] = None,
        entry_price: Optional[float] = None,
        exit_date: Optional[datetime] = None,
        exit_price: Optional[float] = None,
        target_price: Optional[float] = None,
        initial_sl: Optional[float] = None,
        current_sl: Optional[float] = None,
        highest_price_seen: Optional[float] = None,
        tsl_step_pct: Optional[float] = None,
        status: Optional[TradeStatus] = None,
        exit_reason: Optional[ExitReason] = None,
        profit_loss_pct: Optional[float] = None,
    ):
        self.id = id
        self.ticker = ticker
        self.entry_date = entry_date
        self.entry_price = entry_price
        self.exit_date = exit_date
        self.exit_price = exit_price
        self.target_price = target_price
        self.initial_sl = initial_sl
        self.current_sl = current_sl
        self.highest_price_seen = highest_price_seen
        self.tsl_step_pct = tsl_step_pct
        self.status = status
        self.exit_reason = exit_reason
        self.profit_loss_pct = profit_loss_pct


class StockContext:
    """Central context object holding all analysis state for a stock."""

    def __init__(
        self,
        ticker: str,
        current_state: str = None,
        last_ema21: Optional[float] = None,
        last_ema34: Optional[float] = None,
        last_ema55: Optional[float] = None,
        trend_start_date: Optional[str] = None,
        trend_end_date: Optional[str] = None,
        daily_ema21_cross_date: Optional[str] = None,
        daily_downtrend_trigger_date: Optional[str] = None,
        first_buy_zone_date: Optional[str] = None,
        positive_crossover_date: Optional[str] = None,
        tr_qualified: bool = False,
        is_buyzone: bool = False,
        uptrend_weeks: int = 0,
        weekly_candle_count: int = 0,
        closes_above_ema: int = 0,
        closes_below_ema: int = 0,
        is_crossover_detected: bool = False,
        crossover_date: Optional[str] = None,
        crossover_price: Optional[float] = None,
        longName: Optional[str] = None,
        sector: Optional[str] = None,
        industry: Optional[str] = None,
        marketCap: Optional[float] = None,
        website: Optional[str] = None,
        nextDividendDate: Optional[str] = None,
        isin: Optional[str] = None,
    ):
        self.ticker = ticker
        self.current_state = current_state
        self.last_ema21 = last_ema21
        self.last_ema34 = last_ema34
        self.last_ema55 = last_ema55
        self.trend_start_date = trend_start_date
        self.trend_end_date = trend_end_date
        self.daily_ema21_cross_date = daily_ema21_cross_date
        self.daily_downtrend_trigger_date = daily_downtrend_trigger_date
        self.first_buy_zone_date = first_buy_zone_date
        self.positive_crossover_date = positive_crossover_date
        self.tr_qualified = tr_qualified
        self.is_buyzone = is_buyzone
        self.uptrend_weeks = uptrend_weeks
        self.weekly_candle_count = weekly_candle_count
        self.closes_above_ema = closes_above_ema
        self.closes_below_ema = closes_below_ema
        self.is_crossover_detected = is_crossover_detected
        self.crossover_date = crossover_date
        self.crossover_price = crossover_price
        self.longName = longName
        self.sector = sector
        self.industry = industry
        self.marketCap = marketCap
        self.website = website
        self.nextDividendDate = nextDividendDate
        self.isin = isin

        # Extra fields used by the FSM
        self.daily_ema21_cross_price: Optional[float] = None
        self.daily_downtrend_trigger_price: Optional[float] = None
        self.first_buy_zone_price: Optional[float] = None
        self.positive_crossover_price: Optional[float] = None
        self.buy_signal_emitted: bool = False
        self.last_buy_signal_date: Optional[datetime] = None
        self.last_buy_signal_type: Optional[str] = None
        self.last_buy_signal_crossover_date: Optional[datetime] = None
        self.uptrend_start_date: Optional[datetime] = None
        self.last_close: Optional[float] = None
        self.last_update: Optional[datetime] = None
        self.warmup_complete: bool = False
        self.candle_count: int = 0
        self.current_uptrend: Optional[UptrendRecord] = None
        self.uptrend_history: List[UptrendRecord] = []
        self.classification: Optional[Classification] = None
        self.trend_cycle_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize StockContext to dict for JSON persistence.

        Includes ALL fields, with proper serialization of nested objects,
        enums, and datetime values.
        """
        result = {}
        # Constructor fields (the ones accepted in __init__)
        for attr in (
            "ticker", "current_state", "last_ema21", "last_ema34", "last_ema55",
            "trend_start_date", "trend_end_date",
            "daily_ema21_cross_date", "daily_downtrend_trigger_date",
            "first_buy_zone_date", "positive_crossover_date",
            "tr_qualified", "is_buyzone", "uptrend_weeks", "weekly_candle_count",
            "closes_above_ema", "closes_below_ema",
            "is_crossover_detected", "crossover_date", "crossover_price",
            "longName", "sector", "industry", "marketCap", "website",
            "nextDividendDate", "isin",
        ):
            val = getattr(self, attr, None)
            # current_state may be a State enum object; store its .name string
            if attr == "current_state":
                from .enums import State
                if isinstance(val, State):
                    val = val.name
            result[attr] = val

        # Extra fields not in constructor
        extra_attrs = (
            "daily_ema21_cross_price", "daily_downtrend_trigger_price",
            "first_buy_zone_price", "positive_crossover_price",
            "buy_signal_emitted", "last_buy_signal_type",
            "uptrend_start_date", "last_close",
            "warmup_complete", "candle_count", "trend_cycle_id",
        )
        for attr in extra_attrs:
            val = getattr(self, attr, None)
            if isinstance(val, datetime):
                val = val.isoformat()
            result[attr] = val

        # last_update and last_buy_signal_date/last_buy_signal_crossover_date
        for attr in ("last_update", "last_buy_signal_date", "last_buy_signal_crossover_date"):
            val = getattr(self, attr, None)
            if isinstance(val, datetime):
                val = val.isoformat()
            result[attr] = val

        # classification (enum -> str)
        cls_val = getattr(self, "classification", None)
        if cls_val is not None and isinstance(cls_val, Classification):
            result["classification"] = cls_val.name
        else:
            result["classification"] = cls_val

        # current_uptrend (UptrendRecord -> dict)
        cu = getattr(self, "current_uptrend", None)
        result["current_uptrend"] = cu.to_dict() if cu else None

        # uptrend_history (list of UptrendRecord -> list of dict)
        uh = getattr(self, "uptrend_history", [])
        result["uptrend_history"] = [u.to_dict() for u in uh]

        return result

    def __repr__(self) -> str:
        return f"StockContext(ticker={self.ticker}, classification={self.classification})"


def context_from_dict(d: Dict[str, Any]) -> StockContext:
    """Reconstruct a StockContext from a dict (deserialization).

    Handles nested UptrendRecord lists, enum values, and datetime strings.
    """
    # Build with constructor fields only
    current_state = d.get("current_state")
    # Backward-compat: handle old data where State enum was serialized as
    # "State.DOWNTREND" by json.dumps(default=str) instead of just "DOWNTREND".
    if current_state and isinstance(current_state, str) and current_state.startswith("State."):
        current_state = current_state.replace("State.", "")
    ctx = StockContext(
        ticker=d.get("ticker", ""),
        current_state=current_state,
        last_ema21=d.get("last_ema21"),
        last_ema34=d.get("last_ema34"),
        last_ema55=d.get("last_ema55"),
        trend_start_date=d.get("trend_start_date"),
        trend_end_date=d.get("trend_end_date"),
        daily_ema21_cross_date=d.get("daily_ema21_cross_date"),
        daily_downtrend_trigger_date=d.get("daily_downtrend_trigger_date"),
        first_buy_zone_date=d.get("first_buy_zone_date"),
        positive_crossover_date=d.get("positive_crossover_date"),
        tr_qualified=bool(d.get("tr_qualified", False)),
        is_buyzone=bool(d.get("is_buyzone", False)),
        uptrend_weeks=int(d.get("uptrend_weeks", 0)),
        weekly_candle_count=int(d.get("weekly_candle_count", 0)),
        closes_above_ema=int(d.get("closes_above_ema", 0)),
        closes_below_ema=int(d.get("closes_below_ema", 0)),
        is_crossover_detected=bool(d.get("is_crossover_detected", False)),
        crossover_date=d.get("crossover_date"),
        crossover_price=d.get("crossover_price"),
        longName=d.get("longName"),
        sector=d.get("sector"),
        industry=d.get("industry"),
        marketCap=d.get("marketCap"),
        website=d.get("website"),
        nextDividendDate=d.get("nextDividendDate"),
        isin=d.get("isin"),
    )

    # Set extra fields
    for attr in (
        "daily_ema21_cross_price", "daily_downtrend_trigger_price",
        "first_buy_zone_price", "positive_crossover_price",
        "buy_signal_emitted", "last_buy_signal_type",
        "candle_count", "trend_cycle_id",
    ):
        if attr in d:
            setattr(ctx, attr, d[attr])

    # Numeric / datetime fields
    for attr in ("uptrend_start_date", "last_close", "warmup_complete"):
        if attr in d:
            val = d[attr]
            if attr.endswith("_date") and isinstance(val, str):
                try:
                    val = datetime.fromisoformat(val)
                except (ValueError, TypeError):
                    pass
            setattr(ctx, attr, val)

    # Date fields
    for attr in ("last_update", "last_buy_signal_date", "last_buy_signal_crossover_date"):
        if attr in d:
            val = d[attr]
            if isinstance(val, str):
                try:
                    val = datetime.fromisoformat(val)
                except (ValueError, TypeError):
                    pass
            setattr(ctx, attr, val)

    # classification (str -> Classification enum)
    cls_val = d.get("classification")
    if isinstance(cls_val, str):
        try:
            ctx.classification = Classification[cls_val]
        except (KeyError, ValueError):
            ctx.classification = cls_val
    else:
        ctx.classification = cls_val

    # current_uptrend (dict -> UptrendRecord)
    cu = d.get("current_uptrend")
    if isinstance(cu, dict):
        ctx.current_uptrend = UptrendRecord.from_dict(cu)

    # uptrend_history (list of dict -> list of UptrendRecord)
    uh = d.get("uptrend_history", [])
    if isinstance(uh, list):
        ctx.uptrend_history = [
            UptrendRecord.from_dict(u) if isinstance(u, dict) else u
            for u in uh
        ]

    return ctx