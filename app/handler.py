import logging
from pathlib import Path
from typing import List, Optional

from trend_rider_lib.persistence.scan_handler import IScanResultHandler
from trend_rider_lib.core.models import StockContext, SignalEvent, TradeRecord

from app.database import Database

logger = logging.getLogger(__name__)

class ScanResultHandler(IScanResultHandler):
    """Concrete implementation of IScanResultHandler that persists results to a local SQLite DB.

    The UI layer (Tkinter) will instantiate this handler and pass it to ``scan_stocks``.
    All heavy‑weight business logic remains in the library; this class merely stores
    and logs the events.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db = Database(db_path)
        # Simple in‑memory queues could be added later for UI notifications.

    # ----- Primary hooks ---------------------------------------------------
    def on_context_saved(self, ticker: str, context: StockContext) -> None:
        """Persist the final StockContext for a ticker.

        ``StockContext`` provides a ``to_dict`` method via the library's
        ``__dict__``; the Database wrapper expects a model instance.
        """
        try:
            self.db.save_context(context)
            logger.debug("Context saved for %s", ticker)
        except Exception as exc:  # pragma: no cover – defensive
            logger.exception("Failed to save context for %s: %s", ticker, exc)

    def on_signal_detected(self, ticker: str, signal: SignalEvent) -> None:
        """Persist a detected signal.

        The library may emit many signals per ticker; each is stored as a JSON blob.
        """
        try:
            self.db.save_signal(ticker, signal)
            logger.debug("Signal saved for %s", ticker)
        except Exception as exc:  # pragma: no cover
            logger.exception("Failed to save signal for %s: %s", ticker, exc)

    def on_trade_saved(self, trade: TradeRecord) -> None:
        """Persist a newly created trade."""
        try:
            self.db.save_trade(trade)
            logger.debug("Trade saved: %s", trade.id)
        except Exception as exc:  # pragma: no cover
            logger.exception("Failed to save trade %s: %s", getattr(trade, "id", None), exc)

    def on_trade_updated(self, trade: TradeRecord) -> None:
        """Persist an updated trade. For simplicity we treat it like a write.

        ``Database.save_trade`` performs an INSERT; updates will create a new row.
        This mirrors the library's incremental update behaviour where trade history
        is append‑only.
        """
        self.on_trade_saved(trade)

    # ----- Optional lifecycle hooks (no‑op) -------------------------------
    def on_scan_started(self, tickers: List[str]) -> None:
        logger.info("Scan started for %d tickers", len(tickers))

    def on_ticker_started(self, ticker: str) -> None:
        logger.info("Ticker scan started: %s", ticker)

    def on_ticker_completed(self, ticker: str, context: StockContext) -> None:
        logger.info("Ticker scan completed: %s", ticker)

    def on_scan_completed(self, results: dict) -> None:
        logger.info("Full scan completed – %d results", len(results))
