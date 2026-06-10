"""
Trend Rider V0.3 - Stock Trend Analysis and Trading Library

A sophisticated stock trend analysis system using EMA indicators, state machine
architecture, and trailing stop-loss mechanics for automated trade management.
"""

from .core import (
    State,
    Classification,
    SignalType,
    TrendEventType,
    UptrendStrength,
    TradeStatus,
    ExitReason,
    DEFAULT_SLIPPAGE,
    TrendRiderConfig,
    UptrendRecord,
    StockContext,
    SignalEvent,
    TrendEventRecord,
    TradeRecord,
)

from .engine import TrendRiderEngine
from .indicators import (
    resample_daily_to_weekly,
    compute_zone_flags,
    mark_warmup_complete,
)
from .state_machine import StockFSM, classify_stock, update_classification
from .trading import TradeManager, TSLEngine
from .persistence import SQLiteProvider, IStateStore, ISignalStore, ITradeStore
from .persistence.scan_handler import IScanResultHandler, BridgeProvider
from .downloader import YFinanceDownloader
from .api import scan_stocks

__version__ = "0.81"

__all__ = [
    # Core
    "State",
    "Classification",
    "SignalType",
    "TrendEventType",
    "UptrendStrength",
    "TradeStatus",
    "ExitReason",
    "DEFAULT_SLIPPAGE",
    "TrendRiderConfig",
    "UptrendRecord",
    "StockContext",
    "SignalEvent",
    "TrendEventRecord",
    "TradeRecord",
    # Engine
    "TrendRiderEngine",
    # Indicators
    "resample_daily_to_weekly",
    "compute_zone_flags",
    "mark_warmup_complete",
    # State Machine
    "StockFSM",
    "classify_stock",
    "update_classification",
    # Trading
    "TradeManager",
    "TSLEngine",
    # Persistence
    "SQLiteProvider",
    "IStateStore",
    "ISignalStore",
    "ITradeStore",
    # Handler / Bridge
    "IScanResultHandler",
    "BridgeProvider",
    # Public API
    "scan_stocks",
    # Downloader
    "YFinanceDownloader",
]
