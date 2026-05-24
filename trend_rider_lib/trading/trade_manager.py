"""
Trade lifecycle management with entry, tracking, and exit.
"""
from typing import List, Optional, Dict, Iterable
from datetime import datetime

from ..core.models import TradeRecord, SignalEvent
from ..core.enums import TradeStatus, SignalType, ExitReason
from ..core.config import TrendRiderConfig
from .tsl_engine import TSLEngine


class TradeManager:
    """
    Manages trade lifecycle: entry, tracking, and exit.
    Subscribes to signals and executes trades based on rules.
    """

    def __init__(self, config: TrendRiderConfig):
        """
        Initialize trade manager.

        Args:
            config: TrendRiderConfig with trading parameters
        """
        self.config = config
        self.tsl_engine = TSLEngine(config)
        self.open_trades: Dict[str, List[TradeRecord]] = {}
        self.all_trades: List[TradeRecord] = []
        self.trade_id_counter = 0

    def reset(self) -> None:
        """Reset in-memory trade tracking state."""
        self.open_trades = {}
        self.all_trades = []
        self.trade_id_counter = 0

    def seed_trade_id_counter(self, trades: Iterable[TradeRecord]) -> None:
        """Seed the ID counter from existing persisted trades."""
        max_id = max((trade.id or 0 for trade in trades), default=0)
        self.trade_id_counter = max(self.trade_id_counter, max_id)

    def restore_from_trades(self, trades: List[TradeRecord]) -> None:
        """
        Restore in-memory state from persisted trades.

        Open trades are loaded into the active tracker; all trades are kept for
        history/performance calculations.
        """
        self.reset()
        self.all_trades = list(trades)
        for trade in trades:
            if trade.id is not None:
                self.trade_id_counter = max(self.trade_id_counter, trade.id)
            if trade.status == TradeStatus.OPEN:
                self.open_trades.setdefault(trade.ticker, []).append(trade)

    def process_signal(
        self,
        signal: SignalEvent,
        current_price: float
    ) -> Optional[TradeRecord]:
        """
        Process a signal and potentially open a trade.

        Opens trades on BUY_ENTRY, REENTRY, or MOMENTUM_ENTRY signals
        if below max concurrent trades limit.

        Args:
            signal: Signal event to process
            current_price: Current price at signal

        Returns:
            New trade if opened, None otherwise
        """
        ticker = signal.ticker

        # Check if we should open a trade
        if signal.signal_type in [
            SignalType.BUY_ENTRY,
            SignalType.REENTRY,
            SignalType.MOMENTUM_ENTRY
        ]:
            # Check if we can open a new trade
            open_count = len(self.open_trades.get(ticker, []))
            if open_count < self.config.max_concurrent_trades:
                trade = self.open_trade(ticker, signal.date, current_price)
                return trade

        return None

    def open_trade(
        self,
        ticker: str,
        date: datetime,
        entry_price: float
    ) -> TradeRecord:
        """
        Open a new trade.

        Args:
            ticker: Stock symbol
            date: Entry date
            entry_price: Entry price

        Returns:
            New TradeRecord
        """
        self.trade_id_counter += 1

        trade = TradeRecord(
            id=self.trade_id_counter,
            ticker=ticker,
            entry_date=date,
            entry_price=entry_price,
            target_price=entry_price * (1 + self.config.trade_target_pct),
            initial_sl=entry_price * (1 - self.config.trade_initial_sl_pct),
            current_sl=entry_price * (1 - self.config.trade_initial_sl_pct),
            highest_price_seen=entry_price,
            tsl_step_pct=self.config.trade_tsl_step_pct,
            status=TradeStatus.OPEN
        )

        # Add to open trades
        if ticker not in self.open_trades:
            self.open_trades[ticker] = []
        self.open_trades[ticker].append(trade)
        self.all_trades.append(trade)

        return trade

    def update_trades(
        self,
        ticker: str,
        date: datetime,
        current_price: float
    ) -> List[TradeRecord]:
        """
        Update all open trades for a ticker with current price.

        Updates highest price, trailing stop loss, and checks for exits.

        Args:
            ticker: Stock symbol
            date: Current date
            current_price: Current price

        Returns:
            List of trades that were closed
        """
        closed_trades = []

        if ticker not in self.open_trades:
            return closed_trades

        remaining_trades = []

        for trade in self.open_trades[ticker]:
            # Update highest price
            if current_price > trade.highest_price_seen:
                trade.highest_price_seen = current_price

            # Update trailing stop loss
            trade.current_sl, _steps = self.tsl_engine.calculate_tsl(
                trade.entry_price,
                trade.highest_price_seen,
                current_price
            )

            # Check for exit
            should_exit, reason = self.tsl_engine.should_exit(
                trade.entry_price,
                current_price,
                trade.current_sl
            )

            if should_exit:
                # Close the trade
                trade.exit_date = date
                trade.exit_price = current_price
                trade.status = (
                    TradeStatus.CLOSED_TARGET
                    if reason == "TARGET"
                    else TradeStatus.CLOSED_SL
                )
                trade.exit_reason = (
                    ExitReason.TARGET_HIT
                    if reason == "TARGET"
                    else ExitReason.STOP_LOSS
                )
                trade.profit_loss_pct = self.tsl_engine.calculate_profit_loss(
                    trade.entry_price,
                    current_price
                )
                closed_trades.append(trade)
            else:
                remaining_trades.append(trade)

        self.open_trades[ticker] = remaining_trades

        return closed_trades

    def get_open_trades(self, ticker: Optional[str] = None) -> List[TradeRecord]:
        """
        Get all open trades, optionally filtered by ticker.

        Args:
            ticker: Optional stock symbol to filter

        Returns:
            List of open trades
        """
        if ticker:
            return self.open_trades.get(ticker, [])

        all_open = []
        for trades in self.open_trades.values():
            all_open.extend(trades)
        return all_open

    def get_all_trades(self, ticker: Optional[str] = None) -> List[TradeRecord]:
        """
        Get all trades (open and closed), optionally filtered by ticker.

        Args:
            ticker: Optional stock symbol to filter

        Returns:
            List of all trades
        """
        if ticker:
            return [t for t in self.all_trades if t.ticker == ticker]
        return self.all_trades

    def get_performance_summary(self, ticker: Optional[str] = None) -> Dict:
        """
        Calculate performance metrics.

        Args:
            ticker: Optional stock symbol to filter

        Returns:
            Dictionary with performance metrics
        """
        trades = self.get_all_trades(ticker)
        closed_trades = [t for t in trades if t.status != TradeStatus.OPEN]

        if not closed_trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'avg_profit': 0,
                'avg_loss': 0,
                'total_pnl': 0
            }

        winning = [t for t in closed_trades if t.profit_loss_pct > 0]
        losing = [t for t in closed_trades if t.profit_loss_pct <= 0]

        return {
            'total_trades': len(closed_trades),
            'winning_trades': len(winning),
            'losing_trades': len(losing),
            'win_rate': len(winning) / len(closed_trades) * 100 if closed_trades else 0,
            'avg_profit': sum(t.profit_loss_pct for t in winning) / len(winning) if winning else 0,
            'avg_loss': sum(t.profit_loss_pct for t in losing) / len(losing) if losing else 0,
            'total_pnl': sum(t.profit_loss_pct for t in closed_trades)
        }
