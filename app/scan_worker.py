import argparse
import logging
from pathlib import Path
# Removed sys.path hack; module imports handled via package structure.
from typing import List, Optional

from trend_rider_lib.api import scan_stocks
from app.handler import ScanResultHandler

logger = logging.getLogger(__name__)

def run_scan(tickers: List[str], start_date: Optional[str] = None, end_date: Optional[str] = None, db_path: Optional[Path] = None) -> None:
    """Execute a full Trend Rider scan using the custom SQLite handler.

    Parameters
    ----------
    tickers: List[str]
        Stock symbols to analyze.
    start_date, end_date: Optional[str]
        Date range for the historical download (YYYY‑MM‑DD). Omit for full history.
    db_path: Optional[Path]
        Path to the local SQLite file used by ``ScanResultHandler``. If omitted, the default
        ``app/trend_rider_app.sqlite`` is used.
    """
    handler = ScanResultHandler(db_path)
    logger.info("Starting scan for tickers: %s", ", ".join(tickers))
    results = scan_stocks(tickers, handler=handler, start_date=start_date, end_date=end_date)
    logger.info("Scan completed. Results: %s", results)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a Trend Rider scan and store results locally.")
    parser.add_argument("tickers", nargs="+", help="Ticker symbols to scan (space separated)")
    parser.add_argument("--start", dest="start_date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", dest="end_date", help="End date (YYYY-MM-DD)")
    parser.add_argument("--db", dest="db_path", type=Path, help="Path to SQLite DB file")
    args = parser.parse_args()
    run_scan(args.tickers, start_date=args.start_date, end_date=args.end_date, db_path=args.db_path)
