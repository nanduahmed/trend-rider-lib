"""
Unit tests for TSL engine and trade management.
"""
import pytest
from datetime import datetime

from trend_rider_lib.core import TrendRiderConfig, TradeStatus
from trend_rider_lib.trading import TSLEngine, TradeManager
from trend_rider_lib.core import SignalEvent, SignalType


@pytest.fixture
def config():
    """Create config for testing."""
    return TrendRiderConfig(
        trade_target_pct=0.50,
        trade_initial_sl_pct=0.10,
        trade_tsl_step_pct=0.10,
        max_concurrent_trades=1
    )


@pytest.fixture
def tsl_engine(config):
    """Create TSL engine."""
    return TSLEngine(config)


@pytest.fixture
def trade_manager(config):
    """Create trade manager."""
    return TradeManager(config)


class TestTSLEngine:
    """Test Trailing Stop Loss calculations."""

    def test_initial_sl_calculation(self, tsl_engine):
        """Initial SL should be 10% below entry."""
        entry_price = 100.0
        highest_price = 100.0  # No gain yet

        current_sl, steps = tsl_engine.calculate_tsl(entry_price, highest_price, entry_price)

        assert current_sl == 90.0  # 100 * (1 - 0.10)
        assert steps == 0

    def test_tsl_one_step_at_10_percent_gain(self, tsl_engine):
        """At 10% gain, SL should move to breakeven (entry price)."""
        entry_price = 100.0
        highest_price = 110.0  # 10% gain

        current_sl, steps = tsl_engine.calculate_tsl(entry_price, highest_price, entry_price)

        # SL should be at entry price (breakeven): 100 * (1 + (1-1)*0.10) = 100
        assert current_sl == 100.0
        assert steps == 1

    def test_tsl_two_steps_at_20_percent_gain(self, tsl_engine):
        """At 20% gain, SL should move to entry + 10%."""
        entry_price = 100.0
        highest_price = 120.0  # 20% gain

        current_sl, steps = tsl_engine.calculate_tsl(entry_price, highest_price, entry_price)

        # SL should move to entry + 10%: 100 * (1 + (2-1)*0.10) = 110
        assert current_sl == 110.0
        assert steps == 2

    def test_tsl_five_steps(self, tsl_engine):
        """At 50% gain, should have 5 steps."""
        entry_price = 100.0
        highest_price = 150.0  # 50% gain

        current_sl, steps = tsl_engine.calculate_tsl(entry_price, highest_price, entry_price)

        # SL should be at: 100 * (1 + (5-1)*0.10) = 140
        assert current_sl == 140.0
        assert steps == 5

    def test_should_exit_on_target(self, tsl_engine):
        """Should exit when price hits target."""
        entry_price = 100.0
        current_price = 150.0  # 50% gain = target
        current_sl = 140.0

        should_exit, reason = tsl_engine.should_exit(entry_price, current_price, current_sl)

        assert should_exit
        assert reason == "TARGET"

    def test_should_exit_on_stop_loss(self, tsl_engine):
        """Should exit when price hits stop loss."""
        entry_price = 100.0
        current_price = 89.0  # Below SL
        current_sl = 90.0

        should_exit, reason = tsl_engine.should_exit(entry_price, current_price, current_sl)

        assert should_exit
        assert reason == "STOP_LOSS"

    def test_should_not_exit_in_middle(self, tsl_engine):
        """Should not exit if price between SL and target."""
        entry_price = 100.0
        current_price = 120.0  # Between SL(90) and target(150)
        current_sl = 90.0

        should_exit, reason = tsl_engine.should_exit(entry_price, current_price, current_sl)

        assert not should_exit
        assert reason == ""

    def test_profit_loss_calculation(self, tsl_engine):
        """Should calculate profit/loss correctly."""
        entry_price = 100.0

        # 50% gain
        pnl = tsl_engine.calculate_profit_loss(entry_price, 150.0)
        assert pnl == 50.0

        # 10% loss
        pnl = tsl_engine.calculate_profit_loss(entry_price, 90.0)
        assert pnl == -10.0


class TestTradeManager:
    """Test trade lifecycle management."""

    def test_open_trade_on_signal(self, trade_manager):
        """Opening a trade on BUY_ENTRY signal."""
        date = datetime(2023, 1, 1)
        signal = SignalEvent(
            ticker="TEST",
            signal_type=SignalType.BUY_ENTRY,
            date=date,
            close_price=100.0
        )

        trade = trade_manager.process_signal(signal, 100.0)

        assert trade is not None
        assert trade.ticker == "TEST"
        assert trade.entry_price == 100.0
        assert trade.target_price == 150.0  # 50% target
        assert trade.status == TradeStatus.OPEN

    def test_max_concurrent_trades_limit(self, trade_manager):
        """Should not exceed max concurrent trades."""
        date = datetime(2023, 1, 1)
        signal = SignalEvent(
            ticker="TEST",
            signal_type=SignalType.BUY_ENTRY,
            date=date,
            close_price=100.0
        )

        # Open first trade (should succeed)
        trade1 = trade_manager.process_signal(signal, 100.0)
        assert trade1 is not None

        # Try to open second trade (should fail due to limit)
        trade2 = trade_manager.process_signal(signal, 101.0)
        assert trade2 is None

    def test_update_trade_highest_price(self, trade_manager):
        """Trade should track highest price seen."""
        date = datetime(2023, 1, 1)
        signal = SignalEvent(
            ticker="TEST",
            signal_type=SignalType.BUY_ENTRY,
            date=date,
            close_price=100.0
        )

        trade = trade_manager.open_trade("TEST", date, 100.0)
        assert trade.highest_price_seen == 100.0

        # Update with higher price
        date2 = datetime(2023, 1, 2)
        closed = trade_manager.update_trades("TEST", date2, 110.0)

        assert trade.highest_price_seen == 110.0
        assert len(closed) == 0  # Not closed yet

    def test_trade_closure_on_target(self, trade_manager):
        """Trade should close when target is hit."""
        date = datetime(2023, 1, 1)
        trade = trade_manager.open_trade("TEST", date, 100.0)

        # Update to target price
        date2 = datetime(2023, 1, 2)
        closed = trade_manager.update_trades("TEST", date2, 150.0)

        assert len(closed) == 1
        assert closed[0].status == TradeStatus.CLOSED_TARGET
        assert closed[0].profit_loss_pct == 50.0

    def test_trade_closure_on_stop_loss(self, trade_manager):
        """Trade should close when stop loss is hit."""
        date = datetime(2023, 1, 1)
        trade = trade_manager.open_trade("TEST", date, 100.0)

        # Update to stop loss price (below initial SL of 90)
        date2 = datetime(2023, 1, 2)
        closed = trade_manager.update_trades("TEST", date2, 89.0)

        assert len(closed) == 1
        assert closed[0].status == TradeStatus.CLOSED_SL
        assert closed[0].profit_loss_pct < 0

    def test_performance_summary(self, trade_manager):
        """Should calculate performance metrics correctly."""
        date = datetime(2023, 1, 1)

        # Win trade
        trade1 = trade_manager.open_trade("TEST", date, 100.0)
        trade_manager.update_trades("TEST", datetime(2023, 1, 2), 150.0)

        # Loss trade
        trade2 = trade_manager.open_trade("TEST", datetime(2023, 1, 3), 100.0)
        trade_manager.update_trades("TEST", datetime(2023, 1, 4), 85.0)

        summary = trade_manager.get_performance_summary("TEST")

        assert summary['total_trades'] == 2
        assert summary['winning_trades'] == 1
        assert summary['losing_trades'] == 1
        assert summary['win_rate'] == 50.0
        assert summary['avg_profit'] == 50.0
        assert summary['avg_loss'] == -15.0
        assert summary['total_pnl'] == 35.0

    def test_get_open_trades(self, trade_manager):
        """Should retrieve open trades."""
        date = datetime(2023, 1, 1)

        trade1 = trade_manager.open_trade("TEST1", date, 100.0)
        trade2 = trade_manager.open_trade("TEST2", date, 200.0)

        open_trades = trade_manager.get_open_trades()
        assert len(open_trades) == 2

        # Close one trade
        trade_manager.update_trades("TEST1", datetime(2023, 1, 2), 150.0)

        open_trades = trade_manager.get_open_trades()
        assert len(open_trades) == 1
        assert open_trades[0].ticker == "TEST2"

    def test_get_all_trades(self, trade_manager):
        """Should retrieve all trades regardless of status."""
        date = datetime(2023, 1, 1)

        trade1 = trade_manager.open_trade("TEST", date, 100.0)
        trade_manager.update_trades("TEST", datetime(2023, 1, 2), 150.0)

        trade2 = trade_manager.open_trade("TEST", datetime(2023, 1, 3), 100.0)

        all_trades = trade_manager.get_all_trades("TEST")
        assert len(all_trades) == 2
