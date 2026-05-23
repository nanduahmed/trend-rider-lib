"""
Main Trend Rider engine orchestrating all modules.
"""
from typing import Dict, List, Optional
import pandas as pd
from datetime import datetime

from .core.config import TrendRiderConfig
from .core.models import StockContext, SignalEvent, TradeRecord
from .core.enums import Classification

from .indicators.resampler import resample_daily_to_weekly
from .indicators.ema_engine import enrich_with_indicators, incremental_ema
from .indicators.flag_computer import compute_zone_flags, mark_warmup_complete

from .state_machine.fsm import StockFSM
from .state_machine.classifier import update_classification
from .state_machine.fsm_serializer import serialize_context, deserialize_context

from .signals.signal_engine import SignalEngine
from .trading.trade_manager import TradeManager

from .persistence.interfaces import IStateStore, ISignalStore, ITradeStore


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
        daily_data: Dict[str, pd.DataFrame]
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

        for ticker in tickers:
            if ticker not in daily_data:
                print(f"Warning: No data provided for {ticker}")
                continue

            daily_df = daily_data[ticker]
            context = self._process_full_history(ticker, daily_df)

            # Save final state
            self.state_store.save_context(context)

            # Save open trades
            for trade in self.trade_manager.get_open_trades(ticker):
                self.trade_store.save_trade(trade)

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

        for ticker in tickers:
            # Load existing context
            context = self.state_store.load_context(ticker)
            if not context:
                print(f"Warning: No existing context for {ticker}. Run full scan first.")
                continue

            # Restore FSM with loaded context
            fsm = self._restore_fsm(ticker, context)

            if ticker in new_candles:
                new_df = new_candles[ticker]

                # Process new candles in order
                for idx, row in new_df.iterrows():
                    if row.get('timeframe') == 'weekly':
                        # Update EMA incrementally
                        if context.last_ema21 and 'Close' in row:
                            row['EMA21'] = incremental_ema(
                                context.last_ema21,
                                row['Close'],
                                self.config.ema_weekly_period
                            )

                        # Compute zone flags
                        row_df = pd.DataFrame([row])
                        row_df = compute_zone_flags(
                            row_df,
                            self.config.buy_zone_upper_pct,
                            self.config.downtrend_trigger_pct
                        )

                        # Process through FSM
                        fsm.process_weekly_candle(row_df.iloc[0])

                    elif row.get('timeframe') == 'daily':
                        # Update daily EMAs if needed
                        if context.last_ema34 and 'Close' in row:
                            row['EMA34'] = incremental_ema(
                                context.last_ema34,
                                row['Close'],
                                self.config.ema_daily_fast
                            )
                        if context.last_ema55 and 'Close' in row:
                            row['EMA55'] = incremental_ema(
                                context.last_ema55,
                                row['Close'],
                                self.config.ema_daily_slow
                            )

                        # Process through FSM
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

    def _process_full_history(self, ticker: str, daily_df: pd.DataFrame) -> StockContext:
        """
        Process complete historical data for a ticker.

        Args:
            ticker: Stock symbol
            daily_df: Daily OHLCV DataFrame

        Returns:
            Processed StockContext
        """
        # Resample to weekly
        weekly_df = resample_daily_to_weekly(daily_df)

        # Add timeframe column
        daily_df['timeframe'] = 'daily'
        weekly_df['timeframe'] = 'weekly'

        # Compute indicators
        weekly_df = enrich_with_indicators(
            weekly_df,
            self.config.ema_weekly_period,
            self.config.ema_daily_fast,
            self.config.ema_daily_slow
        )

        daily_df = enrich_with_indicators(
            daily_df,
            self.config.ema_weekly_period,
            self.config.ema_daily_fast,
            self.config.ema_daily_slow
        )

        # Compute zone flags
        weekly_df = compute_zone_flags(
            weekly_df,
            self.config.buy_zone_upper_pct,
            self.config.downtrend_trigger_pct
        )

        # Mark warmup complete
        weekly_df = mark_warmup_complete(weekly_df, self.config.warmup_weeks)

        # Create FSM
        def signal_callback(signal: SignalEvent):
            self.signal_engine.process_signal(signal)
            trade = self.trade_manager.process_signal(signal, signal.close_price)
            if trade:
                self.trade_store.save_trade(trade)

        fsm = StockFSM(ticker, self.config, signal_callback)
        self.fsm_instances[ticker] = fsm

        # Process chronologically - merge and sort all candles
        all_candles = pd.concat([daily_df, weekly_df]).sort_index()

        for idx, row in all_candles.iterrows():
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

        # Final classification
        update_classification(fsm.context)

        return fsm.context

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
        fsm.state = context.current_state.name if hasattr(context.current_state, 'name') else context.current_state

        self.fsm_instances[ticker] = fsm
        return fsm
