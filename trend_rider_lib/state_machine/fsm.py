"""
State Machine for stock trend analysis using transitions library.
"""
from typing import Optional, Callable
import pandas as pd
from datetime import datetime

from ..core.config import TrendRiderConfig
from ..core.enums import State, SignalType
from ..core.models import StockContext, UptrendRecord, SignalEvent

try:
    from transitions import Machine
except ImportError:
    raise ImportError(
        "transitions library is required. Install with: pip install transitions"
    )


class StockFSM:
    """
    Finite State Machine for a single stock.
    Uses transitions library for clean state management.
    """

    # Define all possible states
    states = [state.name for state in State]

    def __init__(
        self,
        ticker: str,
        config: TrendRiderConfig,
        signal_callback: Optional[Callable[[SignalEvent], None]] = None
    ):
        """
        Initialize FSM for a stock.

        Args:
            ticker: Stock symbol
            config: TrendRiderConfig with analysis parameters
            signal_callback: Optional callback for signal events
        """
        self.ticker = ticker
        self.config = config
        self.context = StockContext(ticker=ticker)
        self.signal_callback = signal_callback

        # Define state transitions with guards and callbacks
        transitions = [
            # WARMUP → OBSERVING (after warmup period)
            {
                'trigger': 'warmup_done',
                'source': State.WARMUP.name,
                'dest': State.OBSERVING.name,
                'after': 'on_warmup_complete'
            },

            # OBSERVING → BUY_ZONE (enters buy zone)
            {
                'trigger': 'enter_buyzone',
                'source': State.OBSERVING.name,
                'dest': State.BUY_ZONE.name,
                'conditions': 'is_in_buyzone',
                'after': 'on_enter_buyzone'
            },

            # OBSERVING → ABOVE_BUY_ZONE (skips buy zone directly)
            {
                'trigger': 'go_above_buyzone',
                'source': State.OBSERVING.name,
                'dest': State.ABOVE_BUY_ZONE.name,
                'conditions': 'is_above_buyzone',
                'after': 'on_above_buyzone'
            },

            # BUY_ZONE → UPTREND (daily close above EMA21)
            {
                'trigger': 'start_uptrend',
                'source': State.BUY_ZONE.name,
                'dest': State.UPTREND.name,
                'after': 'on_uptrend_start'
            },

            # BUY_ZONE → DOWNTREND (weekly close below trigger)
            {
                'trigger': 'enter_downtrend',
                'source': State.BUY_ZONE.name,
                'dest': State.DOWNTREND.name,
                'conditions': 'is_downtrend_trigger',
                'after': 'on_downtrend_start'
            },

            # UPTREND → ABOVE_BUY_ZONE (moves above zone)
            {
                'trigger': 'leave_buyzone',
                'source': State.UPTREND.name,
                'dest': State.ABOVE_BUY_ZONE.name,
                'conditions': 'is_above_buyzone',
                'after': 'on_leave_buyzone'
            },

            # UPTREND → BUY_ZONE (re-enters zone, for TR qualified)
            {
                'trigger': 'reenter_buyzone',
                'source': State.UPTREND.name,
                'dest': State.BUY_ZONE.name,
                'conditions': 'is_in_buyzone',
                'after': 'on_reentry'
            },

            # UPTREND → DOWNTREND (downtrend triggered)
            {
                'trigger': 'enter_downtrend',
                'source': State.UPTREND.name,
                'dest': State.DOWNTREND.name,
                'conditions': 'is_downtrend_trigger',
                'after': 'on_downtrend_start'
            },

            # ABOVE_BUY_ZONE → BUY_ZONE (re-enters buy zone)
            {
                'trigger': 'reenter_buyzone',
                'source': State.ABOVE_BUY_ZONE.name,
                'dest': State.BUY_ZONE.name,
                'conditions': 'is_in_buyzone',
                'after': 'on_reentry'
            },

            # ABOVE_BUY_ZONE → DOWNTREND (downtrend triggered)
            {
                'trigger': 'enter_downtrend',
                'source': State.ABOVE_BUY_ZONE.name,
                'dest': State.DOWNTREND.name,
                'conditions': 'is_downtrend_trigger',
                'after': 'on_downtrend_start'
            },

            # DOWNTREND → RECOVERING (EMA crossover detected)
            {
                'trigger': 'detect_crossover',
                'source': State.DOWNTREND.name,
                'dest': State.RECOVERING.name,
                'after': 'on_crossover_detected'
            },

            # RECOVERING → BUY_ZONE (recovery succeeds, enters buy zone)
            {
                'trigger': 'momentum_entry',
                'source': State.RECOVERING.name,
                'dest': State.BUY_ZONE.name,
                'conditions': 'is_in_buyzone',
                'after': 'on_momentum_entry'
            },

            # RECOVERING → ABOVE_BUY_ZONE (recovery succeeds, skips buy zone)
            {
                'trigger': 'go_above_buyzone',
                'source': State.RECOVERING.name,
                'dest': State.ABOVE_BUY_ZONE.name,
                'conditions': 'is_above_buyzone',
                'after': 'on_above_buyzone'
            },

            # RECOVERING → DOWNTREND (failed recovery)
            {
                'trigger': 'reenter_downtrend',
                'source': State.RECOVERING.name,
                'dest': State.DOWNTREND.name,
                'conditions': 'is_downtrend_trigger',
                'after': 'on_failed_recovery'
            }
        ]

        # Initialize state machine
        self.machine = Machine(
            model=self,
            states=StockFSM.states,
            transitions=transitions,
            initial=State.WARMUP.name,
            auto_transitions=False,
            send_event=False
        )

    def process_weekly_candle(self, row: pd.Series) -> None:
        """
        Process a weekly candle through the state machine.

        Args:
            row: Series with OHLCV data, EMA21, and flags
        """
        self.context.candle_count += 1
        self.context.last_close = row['Close']
        self.context.last_ema21 = row.get('EMA21')
        self.context.last_update = row.name  # Assumes index is datetime

        # Update zone flags
        if pd.notna(self.context.last_ema21):
            close = self.context.last_close
            ema21 = self.context.last_ema21
            upper_bound = ema21 * (1 + self.config.buy_zone_upper_pct)

            self.context.is_buyzone = (close > ema21) and (close <= upper_bound)

            # Track uptrend statistics only once an uptrend has started.
            if self.context.current_uptrend and self.state in [
                State.BUY_ZONE.name,
                State.UPTREND.name,
                State.ABOVE_BUY_ZONE.name,
            ]:
                self.context.uptrend_weeks += 1
                if close > ema21:
                    self.context.closes_above_ema += 1
                else:
                    self.context.closes_below_ema += 1

                # Check for TR qualified milestone
                if (
                    self.context.uptrend_weeks == self.config.tr_qualify_weeks
                    and not self.context.tr_qualified
                ):
                    self.context.tr_qualified = True
                    self.emit_signal(SignalType.TR_QUALIFIED, row)

                # Update current uptrend record
                if self.context.current_uptrend:
                    self.context.current_uptrend.num_weeks = self.context.uptrend_weeks
                    self.context.current_uptrend.closes_above_ema = self.context.closes_above_ema
                    self.context.current_uptrend.closes_below_ema = self.context.closes_below_ema
                    if self.context.uptrend_weeks > 0:
                        self.context.current_uptrend.pct_closes_above = (
                            self.context.closes_above_ema / self.context.uptrend_weeks
                        )

                    # Track weekly extreme prices for the active uptrend.
                    if (
                        self.context.current_uptrend.highest_price is None
                        or row['High'] > self.context.current_uptrend.highest_price
                    ):
                        self.context.current_uptrend.highest_price = row['High']
                        self.context.current_uptrend.highest_price_date = row.name

                    if (
                        self.context.current_uptrend.lowest_price is None
                        or row['Low'] < self.context.current_uptrend.lowest_price
                    ):
                        self.context.current_uptrend.lowest_price = row['Low']
                        self.context.current_uptrend.lowest_price_date = row.name

        # Handle state transitions based on current state
        if self.state == State.WARMUP.name:
            if self.context.candle_count >= self.config.warmup_weeks:
                self.context.warmup_complete = True
                self.warmup_done()

        elif self.state == State.OBSERVING.name:
            if self.is_in_buyzone():
                self.enter_buyzone()
            elif self.is_above_buyzone():
                self.go_above_buyzone()

        elif self.state == State.BUY_ZONE.name:
            if self.is_downtrend_trigger():
                self.enter_downtrend()

        elif self.state == State.UPTREND.name:
            if self.is_downtrend_trigger():
                self.enter_downtrend()
            elif self.is_above_buyzone():
                self.leave_buyzone()
            elif self.is_in_buyzone():
                self.reenter_buyzone()

        elif self.state == State.ABOVE_BUY_ZONE.name:
            if self.is_downtrend_trigger():
                self.enter_downtrend()
            elif self.is_in_buyzone():
                self.reenter_buyzone()

        elif self.state == State.RECOVERING.name:
            if self.is_in_buyzone():
                self.momentum_entry()
            elif self.is_above_buyzone():
                self.go_above_buyzone()
            elif self.is_downtrend_trigger():
                self.reenter_downtrend()

    def process_daily_candle(self, row: pd.Series) -> None:
        """
        Process daily candle for intra-week signals.

        Args:
            row: Series with daily OHLCV data and EMAs
        """
        self.context.last_ema34 = row.get('EMA34')
        self.context.last_ema55 = row.get('EMA55')

        # Check for uptrend start from buy zone
        if (
            self.state == State.BUY_ZONE.name
            and self.context.current_uptrend is None
            and pd.notna(self.context.last_ema21)
            and row['Close'] > self.context.last_ema21
        ):
            self.start_uptrend()
            self.emit_signal(SignalType.BUY_ENTRY, row)

        # Check for EMA crossover in downtrend (EMA34 > EMA55)
        elif (
            self.state == State.DOWNTREND.name
            and pd.notna(self.context.last_ema34)
            and pd.notna(self.context.last_ema55)
            and self.context.last_ema34 > self.context.last_ema55
            and not self.context.is_crossover_detected
        ):
            self.detect_crossover()
            self.context.crossover_date = row.name
            self.context.crossover_price = row['Close']

    # Guard conditions
    def is_in_buyzone(self) -> bool:
        """Check if price is in buy zone."""
        return self.context.is_buyzone

    def is_above_buyzone(self) -> bool:
        """Check if price is above buy zone."""
        if pd.isna(self.context.last_ema21) or pd.isna(self.context.last_close):
            return False
        upper_bound = self.context.last_ema21 * (1 + self.config.buy_zone_upper_pct)
        return self.context.last_close > upper_bound

    def is_downtrend_trigger(self) -> bool:
        """Check if downtrend trigger is hit."""
        if pd.isna(self.context.last_ema21) or pd.isna(self.context.last_close):
            return False
        trigger_level = self.context.last_ema21 * (1 - self.config.downtrend_trigger_pct)
        return self.context.last_close < trigger_level

    # State callbacks
    def on_warmup_complete(self) -> None:
        """Callback when warmup period completes."""
        pass

    def on_enter_buyzone(self) -> None:
        """Callback when entering buy zone."""
        self.context.is_buyzone = True

    def on_above_buyzone(self) -> None:
        """Callback when moving above buy zone."""
        self.context.is_buyzone = False

    def on_uptrend_start(self) -> None:
        """Callback when uptrend starts."""
        self.context.uptrend_start_date = self.context.last_update
        self.context.uptrend_weeks = 0
        self.context.closes_above_ema = 0
        self.context.closes_below_ema = 0
        self.context.current_uptrend = UptrendRecord(
            start_date=self.context.uptrend_start_date
        )
        self.emit_signal(SignalType.UPTREND_START)

    def on_downtrend_start(self) -> None:
        """Callback when downtrend starts."""
        # Finalize current uptrend record
        if self.context.current_uptrend:
            self.context.current_uptrend.end_date = self.context.last_update
            self.context.current_uptrend.strength = (
                self.context.current_uptrend.calculate_strength()
            )
            self.context.uptrend_history.append(self.context.current_uptrend)
            self.context.current_uptrend = None

        self.context.uptrend_weeks = 0
        self.context.closes_above_ema = 0
        self.context.closes_below_ema = 0
        self.context.is_crossover_detected = False
        self.emit_signal(SignalType.DOWNTREND_START)

    def on_leave_buyzone(self) -> None:
        """Callback when leaving buy zone upward."""
        self.context.is_buyzone = False

    def on_reentry(self) -> None:
        """Callback when re-entering buy zone."""
        self.context.is_buyzone = True
        if self.context.tr_qualified:
            self.emit_signal(SignalType.REENTRY)

    def on_crossover_detected(self) -> None:
        """Callback when EMA crossover detected."""
        self.context.is_crossover_detected = True
        self.emit_signal(SignalType.EMA_CROSSOVER)

    def on_momentum_entry(self) -> None:
        """Callback when momentum entry occurs."""
        self.context.is_buyzone = True
        self.emit_signal(SignalType.MOMENTUM_ENTRY)

    def on_failed_recovery(self) -> None:
        """Callback when recovery fails and re-enters downtrend."""
        self.context.is_buyzone = False
        self.context.is_crossover_detected = False
        self.context.crossover_date = None
        self.context.crossover_price = None
        self.emit_signal(SignalType.DOWNTREND_START)

    def emit_signal(
        self,
        signal_type: SignalType,
        row: Optional[pd.Series] = None
    ) -> None:
        """
        Emit signal to callback if registered.

        Args:
            signal_type: Type of signal
            row: Optional row data for metadata
        """
        if self.signal_callback:
            signal = SignalEvent(
                ticker=self.ticker,
                signal_type=signal_type,
                date=self.context.last_update,
                close_price=self.context.last_close,
                ema21=self.context.last_ema21,
                ema34=self.context.last_ema34,
                ema55=self.context.last_ema55
            )
            self.signal_callback(signal)
