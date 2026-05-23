"""
Abstract interfaces for persistence layers.
"""
from abc import ABC, abstractmethod
from typing import List, Optional

from ..core.models import StockContext, SignalEvent, TradeRecord


class IStateStore(ABC):
    """Interface for stock state persistence."""

    @abstractmethod
    def save_context(self, context: StockContext) -> None:
        """
        Save or update stock context.

        Args:
            context: StockContext to save
        """
        pass

    @abstractmethod
    def load_context(self, ticker: str) -> Optional[StockContext]:
        """
        Load stock context by ticker.

        Args:
            ticker: Stock symbol

        Returns:
            StockContext if found, None otherwise
        """
        pass

    @abstractmethod
    def load_all_contexts(self) -> List[StockContext]:
        """
        Load all stock contexts.

        Returns:
            List of all StockContext objects
        """
        pass

    @abstractmethod
    def delete_context(self, ticker: str) -> None:
        """
        Delete stock context.

        Args:
            ticker: Stock symbol to delete
        """
        pass


class ISignalStore(ABC):
    """Interface for signal event persistence."""

    @abstractmethod
    def save_signal(self, signal: SignalEvent) -> None:
        """
        Save signal event.

        Args:
            signal: SignalEvent to save
        """
        pass

    @abstractmethod
    def get_signals(
        self,
        ticker: str,
        signal_type: Optional[str] = None,
        from_date: Optional[str] = None
    ) -> List[SignalEvent]:
        """
        Get signals for ticker with optional filters.

        Args:
            ticker: Stock symbol
            signal_type: Optional signal type filter
            from_date: Optional start date filter

        Returns:
            List of matching signals
        """
        pass

    @abstractmethod
    def get_latest_signal(
        self,
        ticker: str,
        signal_type: Optional[str] = None
    ) -> Optional[SignalEvent]:
        """
        Get most recent signal for ticker.

        Args:
            ticker: Stock symbol
            signal_type: Optional signal type filter

        Returns:
            Most recent matching signal, or None
        """
        pass


class ITradeStore(ABC):
    """Interface for trade persistence."""

    @abstractmethod
    def save_trade(self, trade: TradeRecord) -> None:
        """
        Save new trade.

        Args:
            trade: TradeRecord to save
        """
        pass

    @abstractmethod
    def update_trade(self, trade: TradeRecord) -> None:
        """
        Update existing trade.

        Args:
            trade: TradeRecord to update
        """
        pass

    @abstractmethod
    def get_open_trades(self, ticker: Optional[str] = None) -> List[TradeRecord]:
        """
        Get open trades.

        Args:
            ticker: Optional stock symbol filter

        Returns:
            List of open trades
        """
        pass

    @abstractmethod
    def get_all_trades(self, ticker: Optional[str] = None) -> List[TradeRecord]:
        """
        Get all trades (open and closed).

        Args:
            ticker: Optional stock symbol filter

        Returns:
            List of all trades
        """
        pass

    @abstractmethod
    def get_trade_by_id(self, trade_id: int) -> Optional[TradeRecord]:
        """
        Get specific trade by ID.

        Args:
            trade_id: Trade ID

        Returns:
            TradeRecord if found, None otherwise
        """
        pass
