from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import pandas as pd

from .engine import TrendRiderEngine
from .core.models import TradeRecord


class StrategyBacktestWrapper:
    """Wrapper to run strategy backtests and generate Excel results."""

    def __init__(self, engine: TrendRiderEngine, tickers: List[str], daily_data: Dict[str, pd.DataFrame]):
        self.engine = engine
        self.tickers = tickers
        self.daily_data = daily_data

    def run(self, output_path: Path) -> Path:
        results = self.engine.run_full_scan(self.tickers, self.daily_data)
        self._write_report(output_path, results)
        return output_path

    def _write_report(self, output_path: Path, results: Dict[str, object]) -> None:
        trade_store = self.engine.trade_store
        trades = []
        if hasattr(trade_store, "get_all_trades"):
            trades = trade_store.get_all_trades()

        trade_rows = [self._trade_row(trade) for trade in trades]
        result_rows = [self._context_row(context) for context in results.values()]

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            pd.DataFrame(result_rows).to_excel(writer, sheet_name="ScanResults", index=False)
            pd.DataFrame(trade_rows).to_excel(writer, sheet_name="Trades", index=False)

    @staticmethod
    def _trade_row(trade: TradeRecord) -> dict:
        return {
            "ID": trade.id,
            "Ticker": trade.ticker,
            "Status": trade.status.name if trade.status else "UNKNOWN",
            "Entry Date": trade.entry_date.isoformat() if trade.entry_date else "",
            "Entry Price": trade.entry_price,
            "Exit Date": trade.exit_date.isoformat() if trade.exit_date else "",
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
            "Last Update": getattr(context, "last_update", ""),
            "Last Close": getattr(context, "last_close", ""),
        }
