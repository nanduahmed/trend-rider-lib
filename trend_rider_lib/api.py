"""
Public API for external applications to call Trend Rider analysis
without a database dependency.

Callers implement the *IScanResultHandler* interface and receive
results directly through it via composition (no callbacks).
"""
import logging
import math
from typing import Callable, Dict, List, Optional

import pandas as pd

from .core.config import TrendRiderConfig
from .core.enums import TradeStatus
from .core.models import StockContext, TradeRecord
from .downloader.yfinance_downloader import YFinanceDownloader
from .engine import TrendRiderEngine
from .persistence.scan_handler import (
    BridgeProvider,
    IScanResultHandler,
)


logger = logging.getLogger(__name__)


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


class _UpdateBridge(BridgeProvider):
    """Bridge pre-populated with existing contexts and trades for incremental update."""

    def __init__(
        self,
        handler: IScanResultHandler,
        existing_contexts: Dict[str, StockContext],
        existing_trades: Dict[str, List[TradeRecord]],
    ) -> None:
        super().__init__(handler)
        self._saved_contexts = dict(existing_contexts)
        self._trades_by_ticker: Dict[str, List[TradeRecord]] = {
            t: list(trades) for t, trades in existing_trades.items()
        }

    def get_all_trades(self, ticker: Optional[str] = None) -> List[TradeRecord]:
        if ticker:
            return self._trades_by_ticker.get(ticker, [])
        result: List[TradeRecord] = []
        for trades in self._trades_by_ticker.values():
            result.extend(trades)
        return result

    def get_open_trades(self, ticker: Optional[str] = None) -> List[TradeRecord]:
        all_trades = self.get_all_trades(ticker)
        return [t for t in all_trades if t.status == TradeStatus.OPEN]


def update_stocks(
    tickers: List[str],
    handler: IScanResultHandler,
    existing_contexts: Dict[str, StockContext],
    existing_trades: Dict[str, List[TradeRecord]],
    end_date: Optional[str] = None,
    debug_callback: Optional[Callable[[str, pd.DataFrame], None]] = None,
) -> Dict[str, StockContext]:
    """Run an incremental update for saved tickers.

    If a ticker's saved context has no EMA21 (``last_ema21 is None``) — meaning
    the initial scan had fewer than 21 weekly candles — the ticker is
    automatically re-scanned from scratch so that TA-Lib can compute a proper
    EMA21 before any state transitions occur.

    Parameters
    ----------
    tickers:
        Stock symbols to update.
    handler:
        Application-provided implementation of *IScanResultHandler* that
        receives every context, signal and trade as they are produced.
    existing_contexts:
        Previously-saved StockContext objects, keyed by ticker.
        These are used to restore FSM state before processing new candles.
    existing_trades:
        Previously-saved trades, keyed by ticker.  Restores the trade
        manager so that open trades and trailing stops are maintained.
    end_date:
        Optional cutoff date (YYYY-MM-DD).  Only candles on or before
        this date are processed.  Omit to process all available new data.
    debug_callback:
        Optional callable ``fn(ticker, pd.DataFrame)`` for raw incremental
        debug rows (same format as full scan).

    Returns
    -------
    dict[str, StockContext]
        Final contexts for all updated tickers.
    """
    # ------------------------------------------------------------------
    # 1. Split tickers into two groups:
    #    - fullscan_tickers:  last_ema21 is None  → need full re-scan
    #    - incremental_tickers: last_ema21 exists → normal incremental
    # ------------------------------------------------------------------
    fullscan_tickers: List[str] = []
    incremental_tickers: List[str] = []

    for ticker in tickers:
        ctx = existing_contexts.get(ticker)
        if ctx is None:
            continue
        # Check for both None and NaN — TA-Lib may produce NaN when
        # the initial scan had fewer than 21 weekly candles.
        last_ema21 = ctx.last_ema21
        ema21_missing = (
            last_ema21 is None
            or (isinstance(last_ema21, float) and math.isnan(last_ema21))
        )
        if ema21_missing:
            fullscan_tickers.append(ticker)
        else:
            incremental_tickers.append(ticker)

    results: Dict[str, StockContext] = {}
    handler.on_scan_started(tickers)

    # ------------------------------------------------------------------
    # 2. Full scan fallback — for tickers where EMA21 was never computed
    # ------------------------------------------------------------------
    if fullscan_tickers:
        logger.info(
            "EMA21 not available for %d ticker(s); falling back to full scan: %s",
            len(fullscan_tickers),
            fullscan_tickers,
        )
        full_data = YFinanceDownloader.download_bulk(fullscan_tickers, end_date=end_date)
        if full_data:
            bridge = BridgeProvider(handler)
            config = TrendRiderConfig()
            engine = TrendRiderEngine(config, bridge, bridge, bridge)

            full_results = engine.run_full_scan(fullscan_tickers, full_data)
            for ticker, ctx in full_results.items():
                handler.on_ticker_completed(ticker, ctx)
            results.update(full_results)

    # ------------------------------------------------------------------
    # 3. Incremental update — for tickers with valid EMA21
    # ------------------------------------------------------------------
    if incremental_tickers:
        bridge = _UpdateBridge(handler, existing_contexts, existing_trades)
        config = TrendRiderConfig()
        engine = TrendRiderEngine(config, bridge, bridge, bridge)

        end_dt: Optional[pd.Timestamp] = None
        if end_date is not None:
            end_dt = pd.Timestamp(end_date)
            if end_dt.tz is None:
                end_dt = end_dt.tz_localize("Asia/Kolkata")

        new_candles: Dict[str, pd.DataFrame] = {}
        for ticker in incremental_tickers:
            ctx = existing_contexts.get(ticker)
            if not ctx or not ctx.last_update:
                continue

            last_date = ctx.last_update
            if isinstance(last_date, str):
                last_date = pd.Timestamp(last_date)
            else:
                last_date = pd.Timestamp(last_date)

            daily_df = YFinanceDownloader.download_incremental(ticker, last_date, interval="1d")
            weekly_df = YFinanceDownloader.download_incremental(ticker, last_date, interval="1wk")

            if end_dt is not None:
                if not daily_df.empty:
                    daily_df = daily_df[daily_df.index <= end_dt]
                if not weekly_df.empty:
                    weekly_df = weekly_df[weekly_df.index <= end_dt]

            if daily_df.empty and weekly_df.empty:
                continue

            merged = pd.concat([daily_df, weekly_df]).sort_index()
            new_candles[ticker] = merged

        if new_candles:
            inc_results = engine.run_incremental_update(
                list(new_candles.keys()),
                new_candles,
                debug_callback=debug_callback,
            )
            for ticker, ctx in inc_results.items():
                handler.on_ticker_completed(ticker, ctx)
            results.update(inc_results)

    # ------------------------------------------------------------------
    # 4. Final lifecycle hook
    # ------------------------------------------------------------------
    handler.on_scan_completed(results)

    return results