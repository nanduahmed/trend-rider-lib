"""
Comprehensive unit tests for FSM macro-state and substate transitions.
"""
import pytest
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from trend_rider_lib.core import State, UptrendSubstate, SignalType, Classification, TrendRiderConfig
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


# ==============================================================================
# WARMUP
# ==============================================================================

class TestFSMWarmup:
    """Test warmup period transitions."""

    def test_initial_state_is_warmup(self, fsm):
        """FSM should start in WARMUP state."""
        assert fsm.state == State.WARMUP.name
        assert fsm.context.uptrend_substate is None

    def test_warmup_to_observing_transition(self, fsm, config):
        """After warmup_weeks, should transition to OBSERVING."""
        base_date = datetime(2023, 1, 1)

        for i in range(config.warmup_weeks):
            date = base_date + timedelta(weeks=i)
            row = create_weekly_row(date, 100.0, 100.0)
            fsm.process_weekly_candle(row)

        assert fsm.state == State.OBSERVING.name
        assert fsm.context.warmup_complete
        assert fsm.context.uptrend_substate is None


# ==============================================================================
# OBSERVING → UPTREND (macro-state entry)
# ==============================================================================

class TestFSMBuyZoneTransition:
    """Test first trend start: OBSERVING → UPTREND with substate."""

    def test_observing_to_uptrend_with_buyzone_substate(self, fsm, config):
        """
        GIVEN FSM in OBSERVING
        WHEN a weekly close > EMA21 and candle is in buy zone
        THEN macro-state becomes UPTREND and substate becomes BUY_ZONE.
        """
        base_date = datetime(2023, 1, 1)

        for i in range(config.warmup_weeks):
            row = create_weekly_row(base_date + timedelta(weeks=i), 100.0, 100.0)
            fsm.process_weekly_candle(row)

        # Enter buy zone (close 102 < EMA21*1.05 = 105)
        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks),
            102.0,
            100.0
        )
        fsm.process_weekly_candle(row)

        # Macro-state should be UPTREND (not BUY_ZONE as a macro-state)
        assert fsm.state == State.UPTREND.name
        assert fsm.context.uptrend_substate == UptrendSubstate.BUY_ZONE.name
        assert fsm.context.is_buyzone

    def test_observing_to_uptrend_with_not_in_buyzone_substate(self, fsm, config):
        """
        GIVEN FSM in OBSERVING
        WHEN a weekly close > EMA21 but close is above EMA21*1.05
        THEN macro-state becomes UPTREND and substate becomes NOT_IN_BUY_ZONE.
        """
        base_date = datetime(2023, 1, 1)

        for i in range(config.warmup_weeks):
            row = create_weekly_row(base_date + timedelta(weeks=i), 100.0, 100.0)
            fsm.process_weekly_candle(row)

        # Close above EMA21 * 1.05 = 105 → NOT_IN_BUY_ZONE
        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks),
            110.0,
            100.0
        )
        fsm.process_weekly_candle(row)

        assert fsm.state == State.UPTREND.name
        assert fsm.context.uptrend_substate == UptrendSubstate.NOT_IN_BUY_ZONE.name
        assert not fsm.context.is_buyzone


# ==============================================================================
# SUBSTATE TRANSITIONS (within UPTREND macro-state)
# ==============================================================================

class TestUptrendSubstateTransitions:
    """Test substate transitions within UPTREND."""

    def test_buyzone_to_not_in_buyzone_substate(self, fsm, config):
        """
        GIVEN FSM in UPTREND/BUY_ZONE
        WHEN a weekly candle has close above EMA21*1.05
        THEN substate changes to NOT_IN_BUY_ZONE without macro-state change.
        """
        base_date = datetime(2023, 1, 1)

        for i in range(config.warmup_weeks):
            row = create_weekly_row(base_date + timedelta(weeks=i), 100.0, 100.0)
            fsm.process_weekly_candle(row)

        # Enter UPTREND in BUY_ZONE
        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks),
            102.0,
            100.0
        )
        fsm.process_weekly_candle(row)
        assert fsm.state == State.UPTREND.name
        assert fsm.context.uptrend_substate == UptrendSubstate.BUY_ZONE.name

        # Next week: move above buy zone
        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks + 1),
            110.0,
            100.0
        )
        fsm.process_weekly_candle(row)

        assert fsm.state == State.UPTREND.name  # Macro-state unchanged
        assert fsm.context.uptrend_substate == UptrendSubstate.NOT_IN_BUY_ZONE.name

    def test_not_in_buyzone_to_buyzone_substate(self, fsm, config):
        """
        GIVEN FSM in UPTREND/NOT_IN_BUY_ZONE
        WHEN a weekly candle qualifies buy zone
        THEN substate changes to BUY_ZONE without macro-state change.
        """
        base_date = datetime(2023, 1, 1)

        for i in range(config.warmup_weeks):
            row = create_weekly_row(base_date + timedelta(weeks=i), 100.0, 100.0)
            fsm.process_weekly_candle(row)

        # Enter UPTREND in NOT_IN_BUY_ZONE
        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks),
            110.0,
            100.0
        )
        fsm.process_weekly_candle(row)
        assert fsm.context.uptrend_substate == UptrendSubstate.NOT_IN_BUY_ZONE.name

        # Next week: enter buy zone
        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks + 1),
            102.0,
            100.0
        )
        fsm.process_weekly_candle(row)

        assert fsm.state == State.UPTREND.name  # Macro-state unchanged
        assert fsm.context.uptrend_substate == UptrendSubstate.BUY_ZONE.name


# ==============================================================================
# UPTREND → DOWNTREND (macro-state transition)
# ==============================================================================

class TestFsmDowntrend:
    """Test downtrend trigger and recovery."""

    def test_uptrend_to_downtrend_macro_state(self, fsm, config):
        """
        GIVEN FSM in UPTREND
        WHEN weekly close < 0.90 × EMA21
        THEN macro-state transitions to DOWNTREND and substate is cleared.
        """
        base_date = datetime(2023, 1, 1)

        for i in range(config.warmup_weeks):
            row = create_weekly_row(base_date + timedelta(weeks=i), 100.0, 100.0)
            fsm.process_weekly_candle(row)

        # Enter UPTREND
        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks),
            102.0,
            100.0
        )
        fsm.process_weekly_candle(row)

        daily_row = create_daily_row(
            base_date + timedelta(weeks=config.warmup_weeks, days=1),
            103.0, 102.0, 101.0
        )
        fsm.process_daily_candle(daily_row)

        # Move to next week to confirm uptrend
        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks + 1),
            104.0,
            101.0
        )
        fsm.process_weekly_candle(row)
        assert fsm.state == State.UPTREND.name

        # Trigger downtrend: close below 100 * 0.90 = 90
        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks + 2),
            89.0,
            100.0
        )
        fsm.process_weekly_candle(row)

        assert fsm.state == State.DOWNTREND.name
        assert fsm.context.uptrend_substate is None  # Cleared when leaving UPTREND

    def test_downtrend_to_recovering_macro_state(self, fsm, config):
        """
        GIVEN FSM in DOWNTREND
        WHEN weekly close > EMA21
        THEN macro-state transitions to RECOVERING.
        """
        base_date = datetime(2023, 1, 1)

        for i in range(config.warmup_weeks):
            row = create_weekly_row(base_date + timedelta(weeks=i), 100.0, 100.0)
            fsm.process_weekly_candle(row)

        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks),
            102.0,
            100.0
        )
        fsm.process_weekly_candle(row)

        daily_row = create_daily_row(
            base_date + timedelta(weeks=config.warmup_weeks, days=1),
            103.0, 102.0, 101.0
        )
        fsm.process_daily_candle(daily_row)

        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks + 1),
            104.0,
            101.0
        )
        fsm.process_weekly_candle(row)

        # Trigger downtrend
        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks + 2),
            89.0,
            100.0
        )
        fsm.process_weekly_candle(row)
        assert fsm.state == State.DOWNTREND.name

        # Recover: close above EMA21
        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks + 3),
            105.0,
            100.0
        )
        fsm.process_weekly_candle(row)

        assert fsm.state == State.RECOVERING.name
        assert fsm.context.uptrend_substate is None

    def test_recovering_to_uptrend_macro_state(self, fsm, config):
        """
        GIVEN FSM in RECOVERING
        WHEN a bullish daily crossover (EMA34 > EMA55) occurs
        THEN macro-state transitions to UPTREND.
        """
        base_date = datetime(2023, 1, 1)

        for i in range(config.warmup_weeks):
            row = create_weekly_row(base_date + timedelta(weeks=i), 100.0, 100.0)
            fsm.process_weekly_candle(row)

        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks),
            102.0, 100.0
        )
        fsm.process_weekly_candle(row)

        daily_row = create_daily_row(
            base_date + timedelta(weeks=config.warmup_weeks, days=1),
            103.0, 102.0, 101.0
        )
        fsm.process_daily_candle(daily_row)

        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks + 1),
            104.0, 101.0
        )
        fsm.process_weekly_candle(row)

        # Trigger downtrend
        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks + 2),
            89.0, 100.0
        )
        fsm.process_weekly_candle(row)

        # Recover
        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks + 3),
            105.0, 100.0
        )
        fsm.process_weekly_candle(row)
        assert fsm.state == State.RECOVERING.name

        # First daily: establish EMA34 < EMA55 so we have previous values
        # (no crossover yet)
        daily_date_before = base_date + timedelta(weeks=config.warmup_weeks + 3, days=1)
        daily_row_before = create_daily_row(daily_date_before, 100.0, 95.0, 100.0)
        fsm.process_daily_candle(daily_row_before)

        # Second daily: bullish crossover EMA34 > EMA55 → UPTREND
        daily_date = base_date + timedelta(weeks=config.warmup_weeks + 3, days=2)
        daily_row = create_daily_row(daily_date, 110.0, 105.0, 100.0)
        fsm.process_daily_candle(daily_row)

        assert fsm.state == State.UPTREND.name

    def test_recovering_to_downtrend_macro_state(self, fsm, config):
        """
        GIVEN FSM in RECOVERING
        WHEN a weekly close < 0.90 × EMA21 occurs
        THEN macro-state transitions back to DOWNTREND.
        """
        base_date = datetime(2023, 1, 1)

        for i in range(config.warmup_weeks):
            row = create_weekly_row(base_date + timedelta(weeks=i), 100.0, 100.0)
            fsm.process_weekly_candle(row)

        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks),
            102.0, 100.0
        )
        fsm.process_weekly_candle(row)

        daily_row = create_daily_row(
            base_date + timedelta(weeks=config.warmup_weeks, days=1),
            103.0, 102.0, 101.0
        )
        fsm.process_daily_candle(daily_row)

        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks + 1),
            104.0, 101.0
        )
        fsm.process_weekly_candle(row)

        # Downtrend
        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks + 2),
            89.0, 100.0
        )
        fsm.process_weekly_candle(row)

        # Recover
        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks + 3),
            105.0, 100.0
        )
        fsm.process_weekly_candle(row)
        assert fsm.state == State.RECOVERING.name

        # Fall back to downtrend
        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks + 4),
            80.0, 100.0
        )
        fsm.process_weekly_candle(row)

        assert fsm.state == State.DOWNTREND.name


# ==============================================================================
# UPTREND QUALIFICATION
# ==============================================================================

class TestFSMUptrendQualification:
    """Test uptrend start and TR qualification at 40 weeks."""

    def test_uptrend_start_on_weekly_confirmation(self, fsm, config):
        """Weekly confirmation should start the trend with UPTREND macro-state."""
        base_date = datetime(2023, 1, 1)

        for i in range(config.warmup_weeks):
            row = create_weekly_row(base_date + timedelta(weeks=i), 100.0, 100.0)
            fsm.process_weekly_candle(row)

        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks),
            102.0, 100.0
        )
        fsm.process_weekly_candle(row)

        daily_date = base_date + timedelta(weeks=config.warmup_weeks, days=1)
        daily_row = create_daily_row(daily_date, 103.0, 102.0, 101.0)
        fsm.process_daily_candle(daily_row)

        # Macro-state is UPTREND (not BUY_ZONE as before)
        assert fsm.state == State.UPTREND.name
        assert fsm.context.uptrend_substate == UptrendSubstate.BUY_ZONE.name
        assert fsm.context.trend_start_date == base_date + timedelta(weeks=config.warmup_weeks)
        assert fsm.context.uptrend_weeks == 0  # Will increment on next weekly

    def test_tr_qualified_at_40_weeks(self, fsm, config):
        """Stock should become TR qualified after 40 weeks in uptrend."""
        base_date = datetime(2023, 1, 1)

        for i in range(config.warmup_weeks):
            row = create_weekly_row(base_date + timedelta(weeks=i), 100.0, 100.0)
            fsm.process_weekly_candle(row)

        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks),
            102.0, 100.0
        )
        fsm.process_weekly_candle(row)

        daily_date = base_date + timedelta(weeks=config.warmup_weeks, days=1)
        daily_row = create_daily_row(daily_date, 103.0, 102.0, 101.0)
        fsm.process_daily_candle(daily_row)

        for week in range(1, config.tr_qualify_weeks + 1):
            row = create_weekly_row(
                base_date + timedelta(weeks=config.warmup_weeks + week),
                100.0 + week,
                100.0 + week * 0.8
            )
            fsm.process_weekly_candle(row)

            if fsm.context.uptrend_substate == UptrendSubstate.BUY_ZONE.name:
                daily_row = create_daily_row(
                    base_date + timedelta(weeks=config.warmup_weeks + week, days=1),
                    100.0 + week + 0.5,
                    100.0 + week * 0.8,
                    100.0 + week * 0.7
                )
                fsm.process_daily_candle(daily_row)

        assert fsm.context.tr_qualified
        assert fsm.state == State.UPTREND.name  # Still in uptrend

    def test_uptrend_weeks_continue_while_in_buyzone_substate(self, fsm, config):
        """Uptrend week counting should continue regardless of substate."""
        base_date = datetime(2023, 1, 1)

        for i in range(config.warmup_weeks):
            row = create_weekly_row(base_date + timedelta(weeks=i), 100.0, 100.0)
            fsm.process_weekly_candle(row)

        entry_row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks),
            102.0, 100.0
        )
        fsm.process_weekly_candle(entry_row)

        daily_row = create_daily_row(
            base_date + timedelta(weeks=config.warmup_weeks, days=1),
            103.0, 102.0, 101.0
        )
        fsm.process_daily_candle(daily_row)

        first_buyzone_week = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks + 1),
            101.0, 100.0
        )
        fsm.process_weekly_candle(first_buyzone_week)

        assert fsm.state == State.UPTREND.name
        assert fsm.context.uptrend_substate == UptrendSubstate.BUY_ZONE.name
        assert fsm.context.uptrend_weeks == 1

        second_buyzone_week = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks + 2),
            101.5, 100.0
        )
        fsm.process_weekly_candle(second_buyzone_week)

        assert fsm.state == State.UPTREND.name
        assert fsm.context.uptrend_weeks == 2


# ==============================================================================
# CLASSIFICATION TESTS
# ==============================================================================

class TestFSMClassification:
    """Test stock classification logic."""

    def test_unqualified_initially(self, fsm):
        """Unqualified stock should have UNQUALIFIED classification."""
        assert fsm.context.classification == Classification.UNQUALIFIED

    def test_momentum_classification_post_recovery(self, fsm, config):
        """Post-recovery with < 40 weeks uptrend should be MOMENTUM if in buy zone substate."""
        fsm.context.tr_qualified = True
        fsm.context.is_crossover_detected = True
        fsm.context.uptrend_weeks = 20
        fsm.context.uptrend_substate = UptrendSubstate.BUY_ZONE.name
        fsm.context.is_buyzone = True
        fsm.context.current_state = State.UPTREND

        from trend_rider_lib.state_machine.classifier import classify_stock
        classification = classify_stock(fsm.context)

        assert classification == Classification.MOMENTUM

    def test_prime_classification(self, fsm, config):
        """40+ weeks uptrend, TR qualified, in BUY_ZONE substate should be PRIME."""
        fsm.context.tr_qualified = True
        fsm.context.uptrend_weeks = 45
        fsm.context.uptrend_substate = UptrendSubstate.BUY_ZONE.name
        fsm.context.is_buyzone = True

        from trend_rider_lib.state_machine.classifier import classify_stock
        classification = classify_stock(fsm.context)

        assert classification == Classification.PRIME

    def test_prime_waitlist_when_not_in_buyzone(self, fsm, config):
        """40+ weeks uptrend, TR qualified, but NOT_IN_BUY_ZONE substate → PRIME_WAITLIST."""
        fsm.context.tr_qualified = True
        fsm.context.uptrend_weeks = 45
        fsm.context.uptrend_substate = UptrendSubstate.NOT_IN_BUY_ZONE.name

        from trend_rider_lib.state_machine.classifier import classify_stock
        classification = classify_stock(fsm.context)

        assert classification == Classification.PRIME_WAITLIST


# ==============================================================================
# SIGNAL EMISSION TESTS
# ==============================================================================

class TestSignalEmission:
    """Test that signals are emitted correctly."""

    def test_uptrend_start_signal(self, fsm, config):
        """UPTREND_START signal should be emitted when uptrend begins."""
        signals_emitted = []

        def signal_capture(signal):
            signals_emitted.append(signal)

        fsm.signal_callback = signal_capture

        base_date = datetime(2023, 1, 1)

        for i in range(config.warmup_weeks):
            row = create_weekly_row(base_date + timedelta(weeks=i), 100.0, 100.0)
            fsm.process_weekly_candle(row)

        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks),
            102.0, 100.0
        )
        fsm.process_weekly_candle(row)

        daily_row = create_daily_row(
            base_date + timedelta(weeks=config.warmup_weeks, days=1),
            103.0, 102.0, 101.0
        )
        fsm.process_daily_candle(daily_row)

        uptrend_signals = [s for s in signals_emitted if s.signal_type == SignalType.UPTREND_START]
        assert len(uptrend_signals) > 0


# ==============================================================================
# SERIALIZATION TESTS
# ==============================================================================

class TestFSMSerialization:
    """Test that FSM state serializes and restores correctly."""

    def test_state_serialization_roundtrip(self, fsm, config):
        """Macro-state and substate survive serialization roundtrip."""
        from trend_rider_lib.state_machine.fsm_serializer import serialize_context, deserialize_context

        base_date = datetime(2023, 1, 1)

        for i in range(config.warmup_weeks):
            row = create_weekly_row(base_date + timedelta(weeks=i), 100.0, 100.0)
            fsm.process_weekly_candle(row)

        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks),
            102.0, 100.0
        )
        fsm.process_weekly_candle(row)

        # Verify we're in UPTREND with BUY_ZONE substate
        assert fsm.state == State.UPTREND.name
        assert fsm.context.uptrend_substate == UptrendSubstate.BUY_ZONE.name

        # Serialize
        data = serialize_context(fsm.context)
        assert data['current_state'] == State.UPTREND.name
        assert data['uptrend_substate'] == UptrendSubstate.BUY_ZONE.name

        # Deserialize into a new FSM
        restored = deserialize_context(data)
        assert restored.current_state == State.UPTREND
        assert restored.ticker == "TEST"
        assert restored.uptrend_substate == UptrendSubstate.BUY_ZONE.name

    def test_uptrend_substate_cleared_on_downtrend(self, fsm, config):
        """When leaving UPTREND for DOWNTREND, substate is cleared."""
        from trend_rider_lib.state_machine.fsm_serializer import serialize_context

        base_date = datetime(2023, 1, 1)

        for i in range(config.warmup_weeks):
            row = create_weekly_row(base_date + timedelta(weeks=i), 100.0, 100.0)
            fsm.process_weekly_candle(row)

        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks),
            102.0, 100.0
        )
        fsm.process_weekly_candle(row)

        daily_row = create_daily_row(
            base_date + timedelta(weeks=config.warmup_weeks, days=1),
            103.0, 102.0, 101.0
        )
        fsm.process_daily_candle(daily_row)

        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks + 1),
            104.0, 101.0
        )
        fsm.process_weekly_candle(row)

        # Downtrend
        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks + 2),
            89.0, 100.0
        )
        fsm.process_weekly_candle(row)

        data = serialize_context(fsm.context)
        assert data['current_state'] == State.DOWNTREND.name
        assert data['uptrend_substate'] is None


# ==============================================================================
# BLOCKED TRANSITION TESTS
# ==============================================================================

class TestBlockedTransitions:
    """Verify that disallowed macro-state transitions are impossible."""

    def test_uptrend_cannot_go_directly_to_observing(self, fsm, config):
        """UPTREND → OBSERVING is blocked."""
        base_date = datetime(2023, 1, 1)

        for i in range(config.warmup_weeks):
            row = create_weekly_row(base_date + timedelta(weeks=i), 100.0, 100.0)
            fsm.process_weekly_candle(row)

        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks),
            102.0, 100.0
        )
        fsm.process_weekly_candle(row)

        assert fsm.state == State.UPTREND.name

        # Even after many weeks in uptrend, we cannot go to OBSERVING
        for week in range(1, 10):
            row = create_weekly_row(
                base_date + timedelta(weeks=config.warmup_weeks + week),
                100.0 + week, 100.0 + week * 0.8
            )
            fsm.process_weekly_candle(row)

        assert fsm.state == State.UPTREND.name

    def test_downtrend_cannot_go_directly_to_uptrend(self, fsm, config):
        """DOWNTREND → UPTREND is blocked (must go through RECOVERING)."""
        base_date = datetime(2023, 1, 1)

        for i in range(config.warmup_weeks):
            row = create_weekly_row(base_date + timedelta(weeks=i), 100.0, 100.0)
            fsm.process_weekly_candle(row)

        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks),
            102.0, 100.0
        )
        fsm.process_weekly_candle(row)

        daily_row = create_daily_row(
            base_date + timedelta(weeks=config.warmup_weeks, days=1),
            103.0, 102.0, 101.0
        )
        fsm.process_daily_candle(daily_row)

        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks + 1),
            104.0, 101.0
        )
        fsm.process_weekly_candle(row)

        # Downtrend
        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks + 2),
            89.0, 100.0
        )
        fsm.process_weekly_candle(row)
        assert fsm.state == State.DOWNTREND.name

        # Close above EMA21 goes to RECOVERING, not directly to UPTREND
        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks + 3),
            105.0, 100.0
        )
        fsm.process_weekly_candle(row)

        assert fsm.state == State.RECOVERING.name
        assert fsm.state != State.UPTREND.name

    def test_uptrend_cannot_go_directly_to_recovering(self, fsm, config):
        """UPTREND → RECOVERING is blocked (must go through DOWNTREND first)."""
        base_date = datetime(2023, 1, 1)

        for i in range(config.warmup_weeks):
            row = create_weekly_row(base_date + timedelta(weeks=i), 100.0, 100.0)
            fsm.process_weekly_candle(row)

        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks),
            102.0, 100.0
        )
        fsm.process_weekly_candle(row)

        daily_row = create_daily_row(
            base_date + timedelta(weeks=config.warmup_weeks, days=1),
            103.0, 102.0, 101.0
        )
        fsm.process_daily_candle(daily_row)

        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks + 1),
            104.0, 101.0
        )
        fsm.process_weekly_candle(row)

        # Even after close above EMA21, if we're in UPTREND we stay in UPTREND
        # (can't go to RECOVERING from UPTREND)
        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks + 2),
            102.0, 100.0
        )
        fsm.process_weekly_candle(row)

        assert fsm.state == State.UPTREND.name


# ==============================================================================
# UPTREND RECORD START/END STATE
# ==============================================================================

class TestUptrendRecordStateTracking:
    """Test that UptrendRecord tracks start_state and end_state correctly."""

    def test_uptrend_record_start_state(self, fsm, config):
        """UptrendRecord.start_state should reflect the macro-state at trend start."""
        base_date = datetime(2023, 1, 1)

        for i in range(config.warmup_weeks):
            row = create_weekly_row(base_date + timedelta(weeks=i), 100.0, 100.0)
            fsm.process_weekly_candle(row)

        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks),
            102.0, 100.0
        )
        fsm.process_weekly_candle(row)

        assert fsm.context.current_uptrend is not None
        assert fsm.context.current_uptrend.start_state == State.UPTREND.name

    def test_uptrend_record_end_state(self, fsm, config):
        """UptrendRecord.end_state should be DOWNTREND when cycle ends."""
        base_date = datetime(2023, 1, 1)

        for i in range(config.warmup_weeks):
            row = create_weekly_row(base_date + timedelta(weeks=i), 100.0, 100.0)
            fsm.process_weekly_candle(row)

        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks),
            102.0, 100.0
        )
        fsm.process_weekly_candle(row)

        daily_row = create_daily_row(
            base_date + timedelta(weeks=config.warmup_weeks, days=1),
            103.0, 102.0, 101.0
        )
        fsm.process_daily_candle(daily_row)

        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks + 1),
            104.0, 101.0
        )
        fsm.process_weekly_candle(row)

        row = create_weekly_row(
            base_date + timedelta(weeks=config.warmup_weeks + 2),
            89.0, 100.0
        )
        fsm.process_weekly_candle(row)

        # The ended cycle should have DOWNTREND as end_state
        assert len(fsm.context.uptrend_history) >= 1
        ended = fsm.context.uptrend_history[-1]
        assert ended.end_state == State.DOWNTREND.name