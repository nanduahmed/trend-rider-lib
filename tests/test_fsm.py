"""
Comprehensive unit tests for FSM and state transitions.
"""
import pytest
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from trend_rider_lib.core import State, SignalType, Classification, TrendRiderConfig
from trend_rider_lib.state_machine import StockFSM


@pytest.fixture
def config():
    """Create default config for testing."""
    return TrendRiderConfig(
        ema_weekly_period=21,
        warmup_weeks=25,
        tr_qualify_weeks=40,
        buy_zone_upper_pct=0.05,
        downtrend_trigger_pct=0.10,
        trade_target_pct=0.50,
        trade_initial_sl_pct=0.10
    )


@pytest.fixture
def fsm(config):
    """Create FSM instance for testing."""
    return StockFSM("TEST", config)


def create_weekly_row(date: datetime, close: float, ema21: float) -> pd.Series:
    """Helper to create a weekly candle row."""
    row = pd.Series({
        'Open': close * 0.99,
        'High': close * 1.01,
        'Low': close * 0.98,
        'Close': close,
        'Volume': 1000000,
        'EMA21': ema21,
        'timeframe': 'weekly'
    }, name=date)
    return row


def create_daily_row(date: datetime, close: float, ema34: float = None, ema55: float = None) -> pd.Series:
    """Helper to create a daily candle row."""
    row = pd.Series({
        'Open': close * 0.99,
        'High': close * 1.01,
        'Low': close * 0.98,
        'Close': close,
        'Volume': 500000,
        'EMA34': ema34,
        'EMA55': ema55,
        'timeframe': 'daily'
    }, name=date)
    return row


class TestFSMWarmup:
    """Test warmup period transitions."""

    def test_initial_state_is_warmup(self, fsm):
        """FSM should start in WARMUP state."""
        assert fsm.state == State.WARMUP.name

    def test_warmup_to_observing_transition(self, fsm, config):
        """After warmup_weeks, should transition to OBSERVING."""
        base_date = datetime(2023, 1, 1)

        # Process warmup_weeks candles
        for i in range(config.warmup_weeks):
            date = base_date + timedelta(weeks=i)
            row = create_weekly_row(date, 100.0, 100.0)
            fsm.process_weekly_candle(row)

        assert fsm.state == State.OBSERVING.name
        assert fsm.context.warmup_complete


class TestFSMBuyZoneTransition:
    """Test buy zone entry and exit transitions."""

    def test_observing_to_buyzone(self, fsm, config):
        """From OBSERVING, entering buy zone should transition to BUY_ZONE."""
        base_date = datetime(2023, 1, 1)

        # Complete warmup
        for i in range(config.warmup_weeks):
            row = create_weekly_row(base_date + timedelta(weeks=i), 100.0, 100.0)
            fsm.process_weekly_candle(row)

        # Now enter buy zone (100 < 105, within 5% above EMA21)
        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks),
            102.0,  # Between EMA21(100) and EMA21*1.05(105)
            100.0
        )
        fsm.process_weekly_candle(row)

        assert fsm.state == State.BUY_ZONE.name
        assert fsm.context.is_buyzone


class TestFSMUptrendQualification:
    """Test uptrend start and TR qualification at 40 weeks."""

    def test_uptrend_start_on_daily_close_above_ema21(self, fsm, config):
        """Daily candle closing above EMA21 should trigger uptrend start."""
        base_date = datetime(2023, 1, 1)

        # Complete warmup
        for i in range(config.warmup_weeks):
            row = create_weekly_row(base_date + timedelta(weeks=i), 100.0, 100.0)
            fsm.process_weekly_candle(row)

        # Enter buy zone
        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks),
            102.0,
            100.0
        )
        fsm.process_weekly_candle(row)

        # Process daily candle above EMA21 to trigger uptrend start
        daily_date = base_date + timedelta(weeks=config.warmup_weeks, days=1)
        daily_row = create_daily_row(daily_date, 103.0, 102.0, 101.0)
        fsm.process_daily_candle(daily_row)

        assert fsm.state == State.UPTREND.name
        assert fsm.context.uptrend_weeks == 0  # Will increment on next weekly

    def test_tr_qualified_at_40_weeks(self, fsm, config):
        """Stock should become TR qualified after 40 weeks in uptrend."""
        base_date = datetime(2023, 1, 1)

        # Complete warmup
        for i in range(config.warmup_weeks):
            row = create_weekly_row(base_date + timedelta(weeks=i), 100.0, 100.0)
            fsm.process_weekly_candle(row)

        # Enter buy zone and start uptrend
        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks),
            102.0,
            100.0
        )
        fsm.process_weekly_candle(row)

        daily_date = base_date + timedelta(weeks=config.warmup_weeks, days=1)
        daily_row = create_daily_row(daily_date, 103.0, 102.0, 101.0)
        fsm.process_daily_candle(daily_row)

        # Process 40 weeks of uptrend (close above EMA21 each week)
        for week in range(1, config.tr_qualify_weeks + 1):
            row = create_weekly_row(
                base_date + timedelta(weeks=config.warmup_weeks + week),
                100.0 + week,  # Incrementally higher
                100.0 + week * 0.8  # EMA follows with lag
            )
            fsm.process_weekly_candle(row)

            # Each week process a daily above EMA if in buy zone
            if fsm.state == State.BUY_ZONE.name:
                daily_row = create_daily_row(
                    base_date + timedelta(weeks=config.warmup_weeks + week, days=1),
                    100.0 + week + 0.5,
                    100.0 + week * 0.8,
                    100.0 + week * 0.7
                )
                fsm.process_daily_candle(daily_row)

        # Should be TR qualified
        assert fsm.context.tr_qualified


class TestFSMDowntrend:
    """Test downtrend trigger and recovery."""

    def test_downtrend_trigger_below_90_percent(self, fsm, config):
        """Close below EMA21 * 0.90 should trigger downtrend."""
        base_date = datetime(2023, 1, 1)

        # Setup: complete warmup and enter uptrend
        for i in range(config.warmup_weeks):
            row = create_weekly_row(base_date + timedelta(weeks=i), 100.0, 100.0)
            fsm.process_weekly_candle(row)

        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks),
            102.0,
            100.0
        )
        fsm.process_weekly_candle(row)

        # Trigger uptrend
        daily_row = create_daily_row(
            base_date + timedelta(weeks=config.warmup_weeks, days=1),
            103.0,
            102.0,
            101.0
        )
        fsm.process_daily_candle(daily_row)

        # Move to uptrend state
        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks + 1),
            104.0,
            101.0
        )
        fsm.process_weekly_candle(row)

        # Trigger downtrend: close below 100 * 0.90 = 90
        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks + 2),
            89.0,  # Below trigger
            100.0
        )
        fsm.process_weekly_candle(row)

        assert fsm.state == State.DOWNTREND.name


class TestFSMClassification:
    """Test stock classification logic."""

    def test_unqualified_initially(self, fsm):
        """Unqualified stock should have UNQUALIFIED classification."""
        assert fsm.context.classification == Classification.UNQUALIFIED

    def test_momentum_classification_post_recovery(self, fsm, config):
        """Post-recovery with < 40 weeks uptrend should be MOMENTUM if in buy zone."""
        fsm.context.tr_qualified = True
        fsm.context.is_crossover_detected = True
        fsm.context.uptrend_weeks = 20
        fsm.context.is_buyzone = True

        from trend_rider_lib.state_machine.classifier import classify_stock
        classification = classify_stock(fsm.context)

        assert classification == Classification.MOMENTUM

    def test_prime_classification(self, fsm, config):
        """40+ weeks uptrend, TR qualified, in buy zone should be PRIME."""
        fsm.context.tr_qualified = True
        fsm.context.uptrend_weeks = 45
        fsm.context.is_buyzone = True

        from trend_rider_lib.state_machine.classifier import classify_stock
        classification = classify_stock(fsm.context)

        assert classification == Classification.PRIME


class TestSignalEmission:
    """Test that signals are emitted correctly."""

    def test_uptrend_start_signal(self, fsm, config):
        """UPTREND_START signal should be emitted when uptrend begins."""
        signals_emitted = []

        def signal_capture(signal):
            signals_emitted.append(signal)

        fsm.signal_callback = signal_capture

        base_date = datetime(2023, 1, 1)

        # Complete warmup and enter buy zone
        for i in range(config.warmup_weeks):
            row = create_weekly_row(base_date + timedelta(weeks=i), 100.0, 100.0)
            fsm.process_weekly_candle(row)

        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks),
            102.0,
            100.0
        )
        fsm.process_weekly_candle(row)

        # Trigger uptrend start
        daily_row = create_daily_row(
            base_date + timedelta(weeks=config.warmup_weeks, days=1),
            103.0,
            102.0,
            101.0
        )
        fsm.process_daily_candle(daily_row)

        # Check that signal was emitted
        uptrend_signals = [s for s in signals_emitted if s.signal_type == SignalType.UPTREND_START]
        assert len(uptrend_signals) > 0
