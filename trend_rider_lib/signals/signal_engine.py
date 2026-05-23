"""
Signal engine for signal event management.
"""
from typing import List, Optional, TYPE_CHECKING
from datetime import datetime

from ..core.models import SignalEvent
from ..core.enums import SignalType

if TYPE_CHECKING:
    from ..persistence.interfaces import ISignalStore


class SignalEngine:
    """
    Signal engine for processing and storing signal events.
    Minimal implementation with basic storage.
    """

    def __init__(self, store: Optional['ISignalStore'] = None):
        """
        Initialize signal engine.

        Args:
            store: Optional signal store implementation
        """
        self.store = store
        self.in_memory_signals: List[SignalEvent] = []

    def process_signal(self, signal: SignalEvent) -> None:
        """
        Process a signal event.

        Args:
            signal: Signal event to process
        """
        # Store in memory
        self.in_memory_signals.append(signal)

        # Store persistently if store available
        if self.store:
            self.store.save_signal(signal)

    def get_recent_signals(self, ticker: str, count: int = 10) -> List[SignalEvent]:
        """
        Get most recent signals for a ticker.

        Args:
            ticker: Stock symbol
            count: Number of recent signals to return

        Returns:
            List of recent signals
        """
        ticker_signals = [s for s in self.in_memory_signals if s.ticker == ticker]
        return ticker_signals[-count:]

    def get_signals_by_type(
        self,
        ticker: str,
        signal_type: SignalType
    ) -> List[SignalEvent]:
        """
        Get signals of specific type for a ticker.

        Args:
            ticker: Stock symbol
            signal_type: Type of signal to filter

        Returns:
            List of matching signals
        """
        return [
            s for s in self.in_memory_signals
            if s.ticker == ticker and s.signal_type == signal_type
        ]
