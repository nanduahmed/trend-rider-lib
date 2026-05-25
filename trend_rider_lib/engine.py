"""
Main Trend Rider engine orchestrating all modules.
"""
from typing import Any, Callable, Dict, List, Optional
import json
import logging
import pandas as pd
from datetime import datetime

from .core.config import TrendRiderConfig
from .core.models import StockContext, SignalEvent, TradeRecord
from .core.enums import Classification

from .indicators.resampler import resample_daily_to_weekly
from .indicators.ema_engine import enrich_with_indicators, incremental_ema
from .indicators.flag_computer import compute_zone_flags, mark_warmup_complete

from .state_machine.fsm import StockFSM
from .state_machine.classifier import classify_stock, update_classification
from .state_machine.fsm_serializer import serialize_context, deserialize_context

from .signals.signal_engine import SignalEngine
from .trading.trade_manager import TradeManager

from .persistence.interfaces import IStateStore, ISignalStore, ITradeStore


logger = logging.getLogger(__name__)


class TrendRiderEngine:
    """
    Main library entry point orchestrating all modules.
    Processes stock data through indicators, state machine, trading system.
    """

    def __init__(
        self,
        config: TrendRiderConfig,
        state_store: IStateStore,
        signal_store: ISignalStore,
        trade_store: ITradeStore
    ):
        """
        Initialize Trend Rider engine.

        Args:
            config: TrendRiderConfig with analysis parameters
            state_store: Persistence layer for stock states
            signal_store: Persistence layer for signals
            trade_store: Persistence layer for trades
        """
        self.config = config
        self.state_store = state_store
        self.signal_store = signal_store
        self.trade_store = trade_store

        self.signal_engine = SignalEngine(signal_store)
        self.trade_manager = TradeManager(config)
        self.fsm_instances: Dict[str, StockFSM] = {}

    def run_full_scan(
        self,
        tickers: List[str],
        daily_data: Dict[str, pd.DataFrame],
        debug_callback: Optional[Callable[[str, pd.DataFrame], None]] = None
    ) -> Dict[str, StockContext]:
        """
        Run full historical scan on provided tickers.

        Processes complete daily data through indicators, FSM, trading system.

        Args:
            tickers: List of stock symbols
            daily_data: Dictionary of ticker → daily OHLC DataFrame
                       DataFrame must have columns: Open, High, Low, Close, Volume
                       Index must be DatetimeIndex

        Returns:
            Dictionary of ticker → final StockContext
        """
        results = {}
        self.trade_manager.reset()
        self.trade_manager.seed_trade_id_counter(self.trade_store.get_all_trades())

        for ticker in tickers:
            if ticker not in daily_data:
                logger.warning("No data provided for %s", ticker)
                continue

            daily_df = daily_data[ticker].copy()
            context = self._process_full_history(
                ticker,
                daily_df,
                debug_callback=debug_callback
            )

            # Save final state
            self.state_store.save_context(context)

            results[ticker] = context

        return results

    def run_incremental_update(
        self,
        tickers: List[str],
        new_candles: Dict[str, pd.DataFrame]
    ) -> Dict[str, StockContext]:
        """
        Run incremental update with new candles.

        Args:
            tickers: List of stock symbols
            new_candles: Dictionary of ticker → new candle DataFrame
                        Can contain daily and/or weekly candles

        Returns:
            Dictionary of ticker → updated StockContext
        """
        results = {}
        persisted_trades = self.trade_store.get_all_trades()
        self.trade_manager.restore_from_trades(persisted_trades)

        for ticker in tickers:
            # Load existing context
            context = self.state_store.load_context(ticker)
            if not context:
                logger.warning("No existing context for %s. Run full scan first.", ticker)
                continue

            # Restore FSM with loaded context
            fsm = self._restore_fsm(ticker, context)

            if ticker in new_candles:
                raw_df = new_candles[ticker].copy()

                # Enforce daily-before-weekly ordering on the same date
                if 'timeframe' in raw_df.columns:
                    raw_df['_order'] = raw_df['timeframe'].map({'daily': 0, 'weekly': 1}).fillna(0)
                    raw_df = raw_df.reset_index()
                    date_col = 'Date' if 'Date' in raw_df.columns else raw_df.columns[0]
                    raw_df = (
                        raw_df
                        .sort_values(by=[date_col, '_order'], kind='stable')
                        .set_index(date_col)
                        .drop(columns=['_order'])
                    )

                new_df = raw_df

                # Process new candles in order
                for idx, row in new_df.iterrows():
                    if row.get('timeframe') == 'weekly':
                        # Work on an explicit copy so mutation intent is clear
                        row = row.copy()
                        if context.last_ema21 is not None and 'Close' in row:
                            row['EMA21'] = incremental_ema(
                                context.last_ema21,
                                row['Close'],
                                self.config.ema_weekly_period
                            )

                        # Compute zone flags for this single row
                        row_df = pd.DataFrame([row])
                        row_df = compute_zone_flags(
                            row_df,
                            self.config.buy_zone_upper_pct,
                            self.config.downtrend_trigger_pct
                        )
                        fsm.process_weekly_candle(row_df.iloc[0])

                    elif row.get('timeframe') == 'daily':
                        row = row.copy()
                        if context.last_ema34 is not None and 'Close' in row:
                            row['EMA34'] = incremental_ema(
                                context.last_ema34,
                                row['Close'],
                                self.config.ema_daily_fast
                            )
                        if context.last_ema55 is not None and 'Close' in row:
                            row['EMA55'] = incremental_ema(
                                context.last_ema55,
                                row['Close'],
                                self.config.ema_daily_slow
                            )
                        fsm.process_daily_candle(row)

                    # Update trades
                    closed_trades = self.trade_manager.update_trades(
                        ticker, idx, row['Close']
                    )
                    for trade in closed_trades:
                        self.trade_store.update_trade(trade)

            # Update classification
            update_classification(fsm.context)

            # Save updated state
            self.state_store.save_context(fsm.context)
            results[ticker] = fsm.context

        return results

    def get_classifications(self, tickers: List[str]) -> Dict[str, Classification]:
        """
        Get current classification for specified tickers.

        Args:
            tickers: List of stock symbols

        Returns:
            Dictionary of ticker → Classification
        """
        results = {}
        for ticker in tickers:
            context = self.state_store.load_context(ticker)
            if context:
                results[ticker] = context.classification
        return results

    def get_open_trades(self, tickers: List[str]) -> Dict[str, List[TradeRecord]]:
        """
        Get open trades for specified tickers.

        Args:
            tickers: List of stock symbols

        Returns:
            Dictionary of ticker → list of open TradeRecords
        """
        results = {}
        for ticker in tickers:
            results[ticker] = self.trade_store.get_open_trades(ticker)
        return results

    def _process_full_history(
        self,
        ticker: str,
        daily_df: pd.DataFrame,
        debug_callback: Optional[Callable[[str, pd.DataFrame], None]] = None
    ) -> StockContext:
        """
        Process complete historical data for a ticker.

        Args:
            ticker: Stock symbol
            daily_df: Daily OHLCV DataFrame

        Returns:
            Processed StockContext
        """
        # Resample to weekly
        daily_df = daily_df.copy()
        weekly_df = resample_daily_to_weekly(daily_df).copy()

        # Add timeframe column
        daily_df['timeframe'] = 'daily'
        weekly_df['timeframe'] = 'weekly'

        # Compute indicators
        # Compute weekly EMA21 on weekly data only
        from .indicators.ema_engine import compute_weekly_ema21, compute_daily_ema34, compute_daily_ema55

        weekly_df['EMA21'] = compute_weekly_ema21(weekly_df, self.config.ema_weekly_period)

        # Compute daily EMA34 and EMA55 on daily data only
        daily_df['EMA34'] = compute_daily_ema34(daily_df, self.config.ema_daily_fast)
        daily_df['EMA55'] = compute_daily_ema55(daily_df, self.config.ema_daily_slow)

        # Compute zone flags
        weekly_df = compute_zone_flags(
            weekly_df,
            self.config.buy_zone_upper_pct,
            self.config.downtrend_trigger_pct
        )

        # Mark warmup complete
        weekly_df = mark_warmup_complete(weekly_df, self.config.warmup_weeks)
        
        
        # Create FSM
        emitted_signals: List[SignalEvent] = []

        def signal_callback(signal: SignalEvent):
            emitted_signals.append(signal)
            self.signal_engine.process_signal(signal)
            trade = self.trade_manager.process_signal(signal, signal.close_price)
            if trade:
                self.trade_store.save_trade(trade)

        fsm = StockFSM(ticker, self.config, signal_callback)
        self.fsm_instances[ticker] = fsm

        # Process chronologically - merge and sort all candles
        # Assign a secondary sort key so daily (0) always precedes weekly (1)
        # on the same calendar date, which is required for correct intra-week
        # signal detection (daily buy entry must be evaluated before the weekly
        # state transition on the same Friday).
        daily_df['_order'] = 0
        weekly_df['_order'] = 1

        all_candles = pd.concat([daily_df, weekly_df]).reset_index()

        # The date column name may vary depending on yfinance version
        date_col = 'Date' if 'Date' in all_candles.columns else all_candles.columns[0]

        all_candles = (
            all_candles
            .sort_values(by=[date_col, '_order'], kind='stable')
            .set_index(date_col)
            .drop(columns=['_order'])
        )

        debug_rows = [] if debug_callback else None

        for idx, row in all_candles.iterrows():
            emitted_signals.clear()
            state_before = fsm.state
            if row['timeframe'] == 'weekly':
                fsm.process_weekly_candle(row)
            else:
                fsm.process_daily_candle(row)

            # Update trades with each candle
            if row['timeframe'] == 'weekly':  # Update on weekly for efficiency
                closed_trades = self.trade_manager.update_trades(
                    ticker, idx, row['Close']
                )
                for trade in closed_trades:
                    self.trade_store.update_trade(trade)

            if debug_rows is not None:
                debug_rows.append(
                    self._build_debug_row(
                        ticker=ticker,
                        candle_date=idx,
                        row=row,
                        state_before=state_before,
                        state_after=fsm.state,
                        context=fsm.context,
                        emitted_signals=emitted_signals,
                    )
                )

        # Final classification
        update_classification(fsm.context)

        if debug_callback and debug_rows is not None:
            debug_callback(ticker, pd.DataFrame(debug_rows))

        return fsm.context

    @staticmethod
    def _build_debug_row(
        ticker: str,
        candle_date: datetime,
        row: pd.Series,
        state_before: str,
        state_after: str,
        context: StockContext,
        emitted_signals: List[SignalEvent]
    ) -> Dict[str, Any]:
        """Build a single raw analysis debug row."""
        signal_types = [signal.signal_type.name for signal in emitted_signals]
        signal_reasons = [
            str(signal.metadata.get("reason", signal.signal_type.name))
            for signal in emitted_signals
        ]
        signal_metadata = [
            signal.metadata for signal in emitted_signals
        ]

        candle_color = "GREEN" if row.get("Close", 0) >= row.get("Open", 0) else "RED"
        if row.get("Close") == row.get("Open"):
            candle_color = "NEUTRAL"

        return {
            "Ticker": ticker,
            "Date": candle_date,
            "Timeframe": row.get("timeframe"),
            "Candle Color": candle_color,
            "Open": row.get("Open"),
            "High": row.get("High"),
            "Low": row.get("Low"),
            "Close": row.get("Close"),
            "Volume": row.get("Volume"),
            "EMA21": row.get("EMA21"),
            "EMA34": row.get("EMA34"),
            "EMA55": row.get("EMA55"),
            "is_buyzone": row.get("is_buyzone"),
            "is_above_buyzone": row.get("is_above_buyzone"),
            "is_downtrend_trigger": row.get("is_downtrend_trigger"),
            "warmup_complete": row.get("warmup_complete"),
            "State Before": state_before,
            "State After": state_after,
            "Classification": classify_stock(context).name,
            "TR Qualified": context.tr_qualified,
            "Buy Zone": context.is_buyzone,
            "Uptrend Weeks": context.uptrend_weeks,
            "Closes Above EMA": context.closes_above_ema,
            "Closes Below EMA": context.closes_below_ema,
            "Crossover Detected": context.is_crossover_detected,
            "Crossover Date": context.crossover_date,
            "Crossover Price": context.crossover_price,
            "Signal Count": len(emitted_signals),
            "Signal Types": "; ".join(signal_types),
            "Signal Reasons": "; ".join(signal_reasons),
            "Signal Metadata": json.dumps(signal_metadata, default=str) if signal_metadata else "",
        }

    def _restore_fsm(self, ticker: str, context: StockContext) -> StockFSM:
        """
        Restore FSM from saved context.

        Args:
            ticker: Stock symbol
            context: Previously saved StockContext

        Returns:
            Restored StockFSM
        """
        def signal_callback(signal: SignalEvent):
            self.signal_engine.process_signal(signal)
            trade = self.trade_manager.process_signal(signal, signal.close_price)
            if trade:
                self.trade_store.save_trade(trade)

        fsm = StockFSM(ticker, self.config, signal_callback)
        fsm.context = context

        # Use transitions library's set_state() to restore the persisted state
        # without triggering any on_enter_ or on_exit_ callbacks, which would
        # corrupt the already-restored context data.
        target_state = (
            context.current_state.name
            if hasattr(context.current_state, 'name')
            else str(context.current_state)
        )
        fsm.machine.set_state(target_state, model=fsm)

        self.fsm_instances[ticker] = fsm
        return fsm
