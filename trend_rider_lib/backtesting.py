from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, List, Optional

import pandas as pd

from .engine import TrendRiderEngine
from .core.models import TradeRecord
from .reporting.export_utils import SheetFormat, write_excel_workbook


class StrategyBacktestWrapper:
    """Wrapper to run strategy backtests and generate Excel results."""

    def __init__(
        self,
        engine: TrendRiderEngine,
        tickers: List[str],
        daily_data: Dict[str, pd.DataFrame],
        debug_callback: Optional[Callable[[str, pd.DataFrame], None]] = None,
    ):
        self.engine = engine
        self.tickers = tickers
        self.daily_data = daily_data
        self.debug_callback = debug_callback

    def run(self, output_path: Path) -> Path:
        results = self.engine.run_full_scan(
            self.tickers,
            self.daily_data,
            debug_callback=self.debug_callback,
        )
        self._write_report(output_path, results)
        return output_path

    def _write_report(self, output_path: Path, results: Dict[str, object]) -> None:
        trade_store = self.engine.trade_store
        trades = []
        if hasattr(trade_store, "get_all_trades"):
            trades = trade_store.get_all_trades()

        trade_rows = [self._trade_row(trade) for trade in trades]
        result_rows = [self._context_row(context) for context in results.values()]

        sheets = {
            "ScanResults": pd.DataFrame(result_rows),
            "Trades": pd.DataFrame(trade_rows),
        }
        formats = {
            "ScanResults": SheetFormat(date_columns=("Last Update",)),
            "Trades": SheetFormat(date_columns=("Entry Date", "Exit Date")),
        }
        write_excel_workbook(output_path, sheets, formats)

    @staticmethod
    def _trade_row(trade: TradeRecord) -> dict:
        return {
            "ID": trade.id,
            "Ticker": trade.ticker,
            "Status": trade.status.name if trade.status else "UNKNOWN",
            "Entry Date": trade.entry_date,
            "Entry Price": trade.entry_price,
            "Exit Date": trade.exit_date,
            "Exit Price": trade.exit_price,
            "Profit/Loss %": trade.profit_loss_pct,
            "Initial SL": trade.initial_sl,
            "Current SL": trade.current_sl,
            "Highest Price": trade.highest_price_seen,
        }

    @staticmethod
    def _context_row(context: object) -> dict:
        return {
            "Ticker": getattr(context, "ticker", ""),
            "Classification": getattr(context, "classification", "").name if hasattr(getattr(context, "classification", ""), "name") else getattr(context, "classification", ""),
            "State": getattr(context, "current_state", ""),
            "Last Update": getattr(context, "last_update", None),
            "Last Close": getattr(context, "last_close", ""),
        }
