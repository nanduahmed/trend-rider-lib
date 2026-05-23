"""
Core module containing models, configuration, and enumerations.
"""
from .enums import State, Classification, SignalType, UptrendStrength, TradeStatus, ExitReason
from .config import TrendRiderConfig
from .models import UptrendRecord, StockContext, SignalEvent, TradeRecord

__all__ = [
    "State",
    "Classification",
    "SignalType",
    "UptrendStrength",
    "TradeStatus",
    "ExitReason",
    "TrendRiderConfig",
    "UptrendRecord",
    "StockContext",
    "SignalEvent",
    "TradeRecord",
]
