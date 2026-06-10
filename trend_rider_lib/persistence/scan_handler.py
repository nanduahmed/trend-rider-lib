"""
Interface and bridge for external applications to consume Trend Rider scan results
without a database dependency.

Usage:
    class MyHandler(IScanResultHandler):
        def on_context_saved(self, ticker: str, context: StockContext) -> None:
            ...  # send to Postgres, API, etc.

    result = scan_stocks(["AAPL", "MSFT"], handler=MyHandler())
    # result.on_context_saved was called for each ticker
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from ..core.models import StockContext, SignalEvent, TradeRecord
from .interfaces import IStateStore, ISignalStore, ITradeStore


class IScanResultHandler(ABC):
    """Interface that calling applications implement to consume scan results."""

    @abstractmethod
    def on_context_saved(self, ticker: str, context: StockContext) -> None:
        """
        Called when a stock's analysis context has been finalised.

        This is the primary hook for consuming scan results. The application
        can inspect *context.classification*, *context.current_state*,
        *context.tr_qualified*, *context.is_buyzone*, uptrend records, etc.
        """
        ...

    @abstractmethod
    def on_signal_detected(self, ticker: str, signal: SignalEvent) -> None:
        """Called when a signal event is emitted during the scan."""
        ...

    @abstractmethod
    def on_trade_saved(self, trade: TradeRecord) -> None:
        """Called when a trade is created during the scan."""
        ...

    @abstractmethod
    def on_trade_updated(self, trade: TradeRecord) -> None:
        """Called when an existing trade is updated (e.g. SL, exit)."""
        ...

    def on_scan_started(self, tickers: List[str]) -> None:
        """Optional hook — called once before any ticker is processed."""
        ...

    def on_ticker_started(self, ticker: str) -> None:
        """Optional hook — called before a single ticker's data is processed."""
        ...

    def on_ticker_completed(self, ticker: str, context: StockContext) -> None:
        """Optional hook — called after a single ticker's analysis finishes."""
        ...

    def on_scan_completed(self, results: Dict[str, StockContext]) -> None:
        """Optional hook — called when the entire batch scan is finished."""
        ...


class BridgeProvider(IStateStore, ISignalStore, ITradeStore):
    """
    Adapter that implements the three persistence interfaces required by
    *TrendRiderEngine* but forwards every meaningful event to a
    caller-provided *IScanResultHandler* instead of persisting to SQLite.

    Load operations (used only by incremental update, not full scan) return
    empty / None so that a full scan always starts from a blank slate.
    """

    def __init__(self, handler: IScanResultHandler) -> None:
        self._handler = handler
        self._saved_contexts: Dict[str, StockContext] = {}

    # ── IStateStore ──────────────────────────────────────────────────────────

    def save_context(self, context: StockContext) -> None:
        self._saved_contexts[context.ticker] = context
        self._handler.on_context_saved(context.ticker, context)

    def load_context(self, ticker: str) -> Optional[StockContext]:
        return self._saved_contexts.get(ticker)

    def load_all_contexts(self) -> List[StockContext]:
        return list(self._saved_contexts.values())

    def delete_context(self, ticker: str) -> None:
        self._saved_contexts.pop(ticker, None)

    # ── ISignalStore ─────────────────────────────────────────────────────────

    def save_signal(self, signal: SignalEvent) -> None:
        self._handler.on_signal_detected(signal.ticker, signal)

    def get_signals(
        self,
        ticker: str,
        signal_type: Optional[str] = None,
        from_date: Optional[str] = None,
    ) -> List[SignalEvent]:
        return []

    def get_latest_signal(
        self,
        ticker: str,
        signal_type: Optional[str] = None,
    ) -> Optional[SignalEvent]:
        return None

    def delete_signals(self, ticker: str) -> None:
        pass

    # ── ITradeStore ─────────────────────────────────────────────────────────

    def save_trade(self, trade: TradeRecord) -> None:
        self._handler.on_trade_saved(trade)

    def update_trade(self, trade: TradeRecord) -> None:
        self._handler.on_trade_updated(trade)

    def get_open_trades(
        self, ticker: Optional[str] = None
    ) -> List[TradeRecord]:
        return []

    def get_all_trades(
        self, ticker: Optional[str] = None
    ) -> List[TradeRecord]:
        return []

    def get_trade_by_id(self, trade_id: int) -> Optional[TradeRecord]:
        return None

    def delete_trades(self, ticker: str) -> None:
        pass