import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from trend_rider_lib.api import update_stocks
from trend_rider_lib.core.models import StockContext, TradeRecord

from app.database import Database
from app.handler import ScanResultHandler

logger = logging.getLogger(__name__)


def run_update(
    tickers: List[str],
    db_path: Optional[Path] = None,
    end_date: Optional[str] = None,
) -> Tuple[Dict[str, StockContext], List[str]]:
    """Run incremental update for saved tickers via the library API.

    Parameters
    ----------
    tickers:
        Stock symbols to update.
    db_path:
        Path to the local SQLite file.  Defaults to ``app/trend_rider_app.sqlite``.
    end_date:
        Optional cutoff date (YYYY-MM-DD).

    Returns
    -------
    (results, skipped)
        *results* maps ticker → updated StockContext for successfully updated
        tickers.  *skipped* is a list of tickers that were skipped (no context
        found or no new data).
    """
    db = Database(db_path)
    handler = ScanResultHandler(db_path)

    existing_contexts: Dict[str, StockContext] = {}
    existing_trades: Dict[str, List[TradeRecord]] = {}
    skipped: List[str] = []

    for ticker in tickers:
        ctx = db.get_context(ticker)
        if ctx is None:
            skipped.append(ticker)
            continue
        existing_contexts[ticker] = ctx
        existing_trades[ticker] = db.get_trades(ticker)

    if not existing_contexts:
        return {}, skipped

    results = update_stocks(
        tickers=list(existing_contexts.keys()),
        handler=handler,
        existing_contexts=existing_contexts,
        existing_trades=existing_trades,
        end_date=end_date,
    )

    return results, skipped
