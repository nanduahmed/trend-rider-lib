import argparse
import logging
from pathlib import Path
from typing import Callable, List, Optional

import pandas as pd

from trend_rider_lib.api import scan_stocks
from trend_rider_lib.reporting.export_utils import safe_filename_part, write_debug_csv
from app.handler import ScanResultHandler

logger = logging.getLogger(__name__)

DEBUG_CACHE_DIR = Path("data/cache/output")

def _make_debug_csv_callback(cache_dir: Path) -> Callable[[str, pd.DataFrame], None]:
    """Create a callback that persists analysis debug rows per ticker."""
    def _write_debug(ticker: str, frame: pd.DataFrame) -> None:
        debug_path = cache_dir / f"{safe_filename_part(ticker)}_analysis_debug.csv"
        write_debug_csv(debug_path, frame)
    return _write_debug

def run_scan(tickers: List[str], start_date: Optional[str] = None,
             end_date: Optional[str] = None, db_path: Optional[Path] = None,
             debug_csv: bool = False) -> dict:
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
    debug_csv: bool
        If True, persist raw analysis debug CSV files in the cache directory.

    Returns
    -------
    dict
        Results dictionary containing the scan results and debug CSV paths (if enabled).
    """
    handler = ScanResultHandler(db_path)
    logger.info("Starting scan for tickers: %s", ", ".join(tickers))

    debug_callback = _make_debug_csv_callback(DEBUG_CACHE_DIR) if debug_csv else None

    results = scan_stocks(tickers, handler=handler, start_date=start_date,
                          end_date=end_date, debug_callback=debug_callback)
    logger.info("Scan completed. Results: %s", results)

    # Collect debug CSV paths if enabled
    debug_paths = []
    if debug_csv:
        for ticker in tickers:
            debug_path = DEBUG_CACHE_DIR / f"{safe_filename_part(ticker)}_analysis_debug.csv"
            if debug_path.exists():
                debug_paths.append(str(debug_path))

    return {
        "results": results,
        "debug_csv_paths": debug_paths,
        "debug_csv_dir": str(DEBUG_CACHE_DIR) if debug_csv else None,
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a Trend Rider scan and store results locally.")
    parser.add_argument("tickers", nargs="+", help="Ticker symbols to scan (space separated)")
    parser.add_argument("--start", dest="start_date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", dest="end_date", help="End date (YYYY-MM-DD)")
    parser.add_argument("--db", dest="db_path", type=Path, help="Path to SQLite DB file")
    args = parser.parse_args()
    run_scan(args.tickers, start_date=args.start_date, end_date=args.end_date, db_path=args.db_path)
