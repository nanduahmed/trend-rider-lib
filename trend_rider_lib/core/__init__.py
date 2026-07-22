"""
Core module containing models, configuration, and enumerations.
"""
from .enums import State, Classification, SignalType, TrendEventType, UptrendStrength, UptrendSubstate, TradeStatus, ExitReason
from .config import DEFAULT_SLIPPAGE, TrendRiderConfig
from .models import UptrendRecord, StockContext, SignalEvent, TrendEventRecord, TradeRecord

__all__ = [
    "State",
    "Classification",
    "SignalType",
    "TrendEventType",
    "UptrendStrength",
    "UptrendSubstate",
    "TradeStatus",
    "ExitReason",
    "DEFAULT_SLIPPAGE",
    "TrendRiderConfig",
    "UptrendRecord",
    "StockContext",
    "SignalEvent",
    "TrendEventRecord",
    "TradeRecord",
]
