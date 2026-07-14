import logging
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import pandas as pd

from trend_rider_lib.api import update_stocks
from trend_rider_lib.core.models import StockContext, TradeRecord
from trend_rider_lib.reporting.export_utils import safe_filename_part, write_debug_csv

from app.database import Database
from app.handler import ScanResultHandler

logger = logging.getLogger(__name__)

INCREMENTAL_DEBUG_CACHE_DIR = Path("data/cache/output")


def _make_incremental_debug_callback(
    cache_dir: Path,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> Callable[[str, pd.DataFrame], None]:
    """Create a callback that persists incremental analysis debug rows per ticker."""
    from_part = safe_filename_part(from_date) if from_date else "start"
    to_part = safe_filename_part(to_date) if to_date else "end"

    def _write_debug(ticker: str, frame: pd.DataFrame) -> None:
        filename = f"{safe_filename_part(ticker)}_{from_part}-{to_part}_debug.csv"
        debug_path = cache_dir / filename
        write_debug_csv(debug_path, frame)
    return _write_debug


def run_update(
    tickers: List[str],
    db_path: Optional[Path] = None,
    end_date: Optional[str] = None,
    debug_csv: bool = False,
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
    debug_csv:
        If True, persist raw incremental analysis debug CSV files.

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

    # Determine the from_date from the earliest last_update value
    date_strs = []
    for ctx in existing_contexts.values():
        if ctx.last_update:
            if hasattr(ctx.last_update, "strftime"):
                date_strs.append(ctx.last_update.strftime("%Y-%m-%d"))
            else:
                date_strs.append(str(ctx.last_update))
    from_date = min(date_strs) if date_strs else None
    to_date = end_date or datetime.now().strftime("%Y-%m-%d")

    debug_callback = (
        _make_incremental_debug_callback(
            INCREMENTAL_DEBUG_CACHE_DIR,
            from_date=from_date,
            to_date=to_date,
        )
        if debug_csv
        else None
    )

    results = update_stocks(
        tickers=list(existing_contexts.keys()),
        handler=handler,
        existing_contexts=existing_contexts,
        existing_trades=existing_trades,
        end_date=end_date,
        debug_callback=debug_callback,
    )

    return results, skipped
