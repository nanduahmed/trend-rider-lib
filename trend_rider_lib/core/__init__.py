"""
Core module containing models, configuration, and enumerations.
"""
from .enums import State, Classification, SignalType, TrendEventType, UptrendStrength, TradeStatus, ExitReason
from .config import TrendRiderConfig
from .models import UptrendRecord, StockContext, SignalEvent, TrendEventRecord, TradeRecord

__all__ = [
    "State",
    "Classification",
    "SignalType",
    "TrendEventType",
    "UptrendStrength",
    "TradeStatus",
    "ExitReason",
    "TrendRiderConfig",
    "UptrendRecord",
    "StockContext",
    "SignalEvent",
    "TrendEventRecord",
    "TradeRecord",
]
