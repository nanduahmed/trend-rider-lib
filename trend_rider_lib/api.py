"""
Public API for external applications to call Trend Rider analysis
without a database dependency.

Callers implement the *IScanResultHandler* interface and receive
results directly through it via composition (no callbacks).
"""
from typing import Callable, Dict, List, Optional, Any

import pandas as pd

from .core.config import TrendRiderConfig
from .core.models import StockContext
from .downloader.yfinance_downloader import YFinanceDownloader
from .engine import TrendRiderEngine
from .indicators.resampler import resample_daily_to_weekly
from .persistence.scan_handler import (
    BridgeProvider,
    IScanResultHandler,
)


def scan_stocks(
    tickers: List[str],
    handler: IScanResultHandler,
    data: Optional[Dict[str, pd.DataFrame]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    debug_callback: Optional[Callable[[str, pd.DataFrame], None]] = None,
) -> Dict[str, StockContext]:
    """
    Run a full historical scan and deliver results to *handler*.

    This is the primary entry point for external applications that want
    to consume Trend Rider analysis results *without* persisting to SQLite.

    Parameters
    ----------
    tickers:
        Stock symbols to analyse.
    handler:
        Application-provided implementation of *IScanResultHandler* that
        receives every context, signal and trade as they are produced.
    data:
        Optional pre-loaded OHLCV data.  If omitted the method will
        download from Yahoo Finance via *yfinance*.
    start_date, end_date:
        Date range for the download (ignored when *data* is provided).
    debug_callback:
        Optional callable ``fn(ticker, pd.DataFrame)`` for raw debug rows.

    Returns
    -------
    dict[str, StockContext]
        Final contexts for all tickers.  The same objects were already
        delivered via *handler.on_context_saved*.
    """
    # 1. Bridge provider — captures data for the handler
    bridge = BridgeProvider(handler)
    config = TrendRiderConfig()
    engine = TrendRiderEngine(config, bridge, bridge, bridge)

    # 2. Data sourcing
    if data is None:
        data = YFinanceDownloader.download_bulk(tickers, start_date, end_date)
        if not data:
            raise RuntimeError("No data returned from Yahoo Finance downloader.")

    # 3. Optional lifecycle hooks
    handler.on_scan_started(tickers)

    # 4. Run the full scan
    results = engine.run_full_scan(
        tickers,
        data,
        debug_callback=debug_callback,
    )

    # 5. Lifecycle completion hooks
    for ticker, ctx in results.items():
        handler.on_ticker_completed(ticker, ctx)
    handler.on_scan_completed(results)

    return results


def update_stocks(
    tickers: Optional[List[str]] = None,
    handler: Optional[IScanResultHandler] = None,
    db_path: Optional[str] = None,
) -> Dict[str, StockContext]:
    """
    Not yet implemented for the handler-based API.

    Incremental updates require previously-saved state, so they
    currently still rely on a SQLite database path.  This method
    will be extended once an in-memory snapshot mechanism is added.
    """
    raise NotImplementedError(
        "Incremental update with IScanResultHandler is not yet available. "
        "Use the CLI ``update`` command with a SQLite database for now."
    )