"""
State machine for stock trend analysis.
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional

import pandas as pd

from ..core.config import TrendRiderConfig
from ..core.enums import Classification, SignalType, State, TrendEventType, UptrendSubstate
from ..indicators.flag_computer import candle_intersects_buy_zone
from ..core.models import SignalEvent, StockContext, TrendEventRecord, UptrendRecord
from .trend_metrics import record_daily_point, update_trend_metrics

try:
    from transitions import Machine
except ImportError:
    raise ImportError("transitions library is required. Install with: pip install transitions")


class StockFSM:
    """
    Finite state machine for a single stock.

    Macro-states (State enum):
      WARMUP → OBSERVING → UPTREND ⇄ DOWNTREND ⇄ RECOVERING → UPTREND
                                                        ↘ DOWNTREND

    When in UPTREND, a separate substate (UptrendSubstate) tracks the
    current candle's buy-zone position.  Substate transitions do NOT
    change the macro-state — the uptrend cycle continues uninterrupted.
    """

    # Macro-states only; substates tracked via context.uptrend_substate
    states = [s.name for s in State]

    def __init__(
        self,
        ticker: str,
        config: TrendRiderConfig,
        signal_callback: Optional[Callable[[SignalEvent], None]] = None,
        event_callback: Optional[Callable[[TrendEventRecord], None]] = None,
    ):
        self.ticker = ticker
        self.config = config
        self.context = StockContext(ticker=ticker)
        self.context.classification = Classification.UNQUALIFIED
        self.context.current_state = State.WARMUP
        self.signal_callback = signal_callback
        self.event_callback = event_callback
        self._current_row: Optional[pd.Series] = None

        self.machine = Machine(
            model=self,
            states=StockFSM.states,
            initial=State.WARMUP.name,
            auto_transitions=False,
            send_event=False,
        )

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def process_weekly_candle(self, row: pd.Series) -> None:
        """Process a weekly candle through the lifecycle."""
        self._current_row = row
        try:
            self.context.candle_count += 1
            self.context.weekly_candle_count += 1
            self.context.last_close = row["Close"]
            self.context.last_ema21 = row.get("EMA21")
            self.context.last_update = row.name
            self._refresh_zone_flags(row)

            if self.state == State.WARMUP.name and self.context.weekly_candle_count >= self.config.warmup_weeks:
                self.context.warmup_complete = True
                self._set_macro_state(State.OBSERVING)

            if pd.isna(self.context.last_ema21):
                return

            # --- Official downtrend end (UPTREND → DOWNTREND) ---
            if self.context.current_uptrend and self.is_downtrend_trigger():
                self._finalize_trend_end(row)
                return

            # --- New trend start (OBSERVING → UPTREND or DOWNTREND → RECOVERING) ---
            if self.context.current_uptrend is None and self.context.last_close > self.context.last_ema21:
                self._start_new_trend(row)
                return

            # --- Active trend continuation ---
            if self.context.current_uptrend and self.context.current_uptrend.start_date is not None:
                if row.name > self.context.current_uptrend.start_date:
                    # Do NOT count weekly analytics during RECOVERING. The recovery
                    # phase is not an analytics-counted uptrend period and must be
                    # excluded from week count, % above EMA, and strength until
                    # the bullish crossover confirms the recovered trend.
                    if self.state != State.RECOVERING.name:
                        self._update_active_trend_weekly(row)

                # Substate tracking (only meaningful within UPTREND macro-state)
                if self.state == State.UPTREND.name and self.context.current_uptrend is not None:
                    self._update_uptrend_substate(row)

        finally:
            self._current_row = None

    def process_daily_candle(self, row: pd.Series) -> None:
        """Process a daily candle for confirmations and buy-signal gating."""
        self._current_row = row
        previous_ema34 = self.context.last_ema34
        previous_ema55 = self.context.last_ema55
        previous_close = self.context.last_close
        try:
            self.context.candle_count += 1
            self.context.last_close = row["Close"]
            self.context.last_ema34 = row.get("EMA34")
            self.context.last_ema55 = row.get("EMA55")
            self.context.last_update = row.name
            self._refresh_zone_flags(row)

            self._maybe_record_daily_ema21_confirmation(row, previous_close)
            self._maybe_record_daily_downtrend_trigger(row)
            bullish_cross = self._is_bullish_ema_cross(previous_ema34, previous_ema55, self.context.last_ema34, self.context.last_ema55)
            bearish_cross = self._is_bearish_ema_cross(previous_ema34, previous_ema55, self.context.last_ema34, self.context.last_ema55)

            if bullish_cross:
                self._handle_bullish_crossover(row)
            elif bearish_cross:
                self._reset_bullish_crossover_latch()

            if self.context.current_uptrend and self.context.current_uptrend.first_buy_zone_date is not None:
                self._update_extremes(row)
                record_daily_point(
                    self.context.current_uptrend,
                    row.name,
                    row.get("Close"),
                    self.context.last_ema21,
                    self.context.last_ema34,
                    self.context.last_ema55,
                )
                update_trend_metrics(self.context.current_uptrend, self.context.last_close)

            if self.state == State.WARMUP.name and self.context.weekly_candle_count >= self.config.warmup_weeks:
                self.context.warmup_complete = True
                self._set_macro_state(State.OBSERVING)

        finally:
            self._current_row = None

    # ---------------------------------------------------------------------
    # State helpers
    # ---------------------------------------------------------------------
    def _set_macro_state(self, state: State) -> None:
        """Set the macro-level state (WARMUP, OBSERVING, UPTREND, DOWNTREND, RECOVERING).

        When transitioning *into* UPTREND the substate is determined by
        the current candle's zone position.  When transitioning *out of*
        UPTREND the substate is cleared.
        """
        self.machine.set_state(state.name, model=self)
        self.context.current_state = state
        if state != State.UPTREND:
            self.context.uptrend_substate = None

    def _set_uptrend_substate(self, substate: UptrendSubstate) -> None:
        """Transition between substates *within* UPTREND.

        The macro-state UPTREND remains unchanged — only the substate
        tracking field on context is updated.
        """
        if self.state != State.UPTREND.name:
            return
        previous = self.context.uptrend_substate
        self.context.uptrend_substate = substate.name

    def _update_uptrend_substate(self, row: pd.Series) -> None:
        """Update the UPTREND substate based on zone flags.

        Called once per weekly candle when the macro-state is UPTREND.
        """
        if self.is_in_buyzone():
            was_not_in_buyzone = self.context.uptrend_substate != UptrendSubstate.BUY_ZONE.name
            self._set_uptrend_substate(UptrendSubstate.BUY_ZONE)
            if was_not_in_buyzone and self.context.tr_qualified:
                self.emit_signal(SignalType.REENTRY, row)
            if self.context.current_uptrend and self.context.current_uptrend.first_buy_zone_date is None:
                self._set_first_buy_zone(row)
        elif self.is_above_buyzone():
            self._set_uptrend_substate(UptrendSubstate.NOT_IN_BUY_ZONE)

    # ---------------------------------------------------------------------
    # Zone guards (unchanged logic, renamed method kept for clarity)
    # ---------------------------------------------------------------------
    def _refresh_zone_flags(self, row: pd.Series) -> None:
        if pd.isna(self.context.last_ema21) or pd.isna(self.context.last_close):
            self.context.is_buyzone = False
            return

        self.context.is_buyzone = candle_intersects_buy_zone(
            row.get("Open"),
            self.context.last_close,
            self.context.last_ema21,
            self.config.buy_zone_upper_pct,
        )

    def is_in_buyzone(self) -> bool:
        return self.context.is_buyzone

    def is_above_buyzone(self) -> bool:
        if pd.isna(self.context.last_ema21) or pd.isna(self.context.last_close):
            return False
        upper_bound = self.context.last_ema21 * (1 + self.config.buy_zone_upper_pct)
        return self.context.last_close > upper_bound

    def is_downtrend_trigger(self) -> bool:
        if pd.isna(self.context.last_ema21) or pd.isna(self.context.last_close):
            return False
        trigger_level = self.context.last_ema21 * (1 - self.config.downtrend_trigger_pct)
        return self.context.last_close < trigger_level

    # ---------------------------------------------------------------------
    # EMA crossover detection
    # ---------------------------------------------------------------------
    def _is_bullish_ema_cross(
        self,
        previous_ema34: Optional[float],
        previous_ema55: Optional[float],
        current_ema34: Optional[float],
        current_ema55: Optional[float],
    ) -> bool:
        if any(pd.isna(value) for value in [previous_ema34, previous_ema55, current_ema34, current_ema55]):
            return False
        return previous_ema34 <= previous_ema55 and current_ema34 > current_ema55

    def _is_bearish_ema_cross(
        self,
        previous_ema34: Optional[float],
        previous_ema55: Optional[float],
        current_ema34: Optional[float],
        current_ema55: Optional[float],
    ) -> bool:
        if any(pd.isna(value) for value in [previous_ema34, previous_ema55, current_ema34, current_ema55]):
            return False
        return previous_ema34 >= previous_ema55 and current_ema34 < current_ema55

    # ---------------------------------------------------------------------
    # Daily confirmation / trigger recording
    # ---------------------------------------------------------------------
    def _maybe_record_daily_ema21_confirmation(self, row: pd.Series, previous_close: Optional[float]) -> None:
        if pd.isna(self.context.last_ema21) or pd.isna(self.context.last_close):
            return
        if previous_close is None:
            return
        crossed_above = previous_close <= self.context.last_ema21 and self.context.last_close > self.context.last_ema21
        if not crossed_above:
            return
        if self.context.daily_ema21_cross_date is None:
            self.context.daily_ema21_cross_date = row.name
            self.context.daily_ema21_cross_price = self.context.last_close
        if self.context.current_uptrend is not None and self.context.current_uptrend.daily_ema21_cross_date is None:
            self.context.current_uptrend.daily_ema21_cross_date = row.name
            self.context.current_uptrend.daily_ema21_cross_price = self.context.last_close
        self._emit_trend_event(
            TrendEventType.DAILY_EMA21_CONFIRMATION,
            row,
            {"reason": "Daily close crossed above weekly EMA21 for confirmation"},
        )

    def _maybe_record_daily_downtrend_trigger(self, row: pd.Series) -> None:
        if pd.isna(self.context.last_ema21) or pd.isna(self.context.last_close):
            return
        trigger_level = self.context.last_ema21 * (1 - self.config.downtrend_trigger_pct)
        if self.context.last_close >= trigger_level:
            return
        if self.context.daily_downtrend_trigger_date is None:
            self.context.daily_downtrend_trigger_date = row.name
            self.context.daily_downtrend_trigger_price = self.context.last_close
        if self.context.current_uptrend is not None and self.context.current_uptrend.daily_downtrend_trigger_date is None:
            self.context.current_uptrend.daily_downtrend_trigger_date = row.name
            self.context.current_uptrend.daily_downtrend_trigger_price = self.context.last_close
        self._emit_trend_event(
            TrendEventType.DAILY_DOWNTREND_TRIGGER,
            row,
            {"reason": "Daily close fell below the 0.90 * EMA21 trigger"},
        )

    # ---------------------------------------------------------------------
    # Trend lifecycle
    # ---------------------------------------------------------------------
    def _start_new_trend(self, row: pd.Series) -> None:
        """Handle weekly close > EMA21 when not already in an uptrend.

        Two paths:
          - OBSERVING → UPTREND   (first entry into an uptrend)
          - DOWNTREND → RECOVERING (recovery from prior downtrend)
        """
        self.context.trend_cycle_id = (self.context.trend_cycle_id or 0) + 1
        self.context.trend_start_date = row.name
        self.context.uptrend_start_date = row.name
        self.context.trend_end_date = None
        self.context.uptrend_weeks = 0
        self.context.closes_above_ema = 0
        self.context.closes_below_ema = 0
        self.context.buy_signal_emitted = False
        self.context.last_buy_signal_date = None
        self.context.last_buy_signal_type = None
        self.context.last_buy_signal_crossover_date = None
        self.context.positive_crossover_date = None
        self.context.positive_crossover_price = None
        self.context.is_crossover_detected = False
        self.context.daily_downtrend_trigger_date = None
        self.context.daily_downtrend_trigger_price = None
        self.context.first_buy_zone_date = None
        self.context.first_buy_zone_price = None
        self.context.recovery_crossover_week = None
        self.context.current_uptrend = UptrendRecord(start_date=row.name)
        self.context.current_uptrend.cycle_id = self.context.trend_cycle_id
        self.context.current_uptrend.start_price = row.get("Close")
        self.context.current_uptrend.daily_ema21_cross_date = self.context.daily_ema21_cross_date
        self.context.current_uptrend.daily_ema21_cross_price = self.context.daily_ema21_cross_price
        self.context.current_uptrend.first_buy_zone_date = None
        self.context.current_uptrend.first_buy_zone_price = None
        self.context.current_uptrend.ath_price = None
        self.context.current_uptrend.ath_date = None
        self.context.current_uptrend.highest_price = None
        self.context.current_uptrend.highest_price_date = None
        self.context.current_uptrend.lowest_price = None
        self.context.current_uptrend.lowest_price_date = None
        self._emit_trend_event(
            TrendEventType.WEEKLY_TREND_START,
            row,
            {"reason": "Weekly close confirmed the official trend start"},
        )
        self.emit_signal(SignalType.UPTREND_START, row)

        if self.context.trend_cycle_id is not None:
            self.context.current_uptrend.start_date = row.name

        # Determine macro-state: RECOVERING if coming from DOWNTREND, else UPTREND
        if self.state == State.DOWNTREND.name:
            self._set_macro_state(State.RECOVERING)
        else:
            # OBSERVING → UPTREND — enter macro-state with appropriate substate
            self._set_macro_state(State.UPTREND)
            self._update_uptrend_substate(row)

        self.context.current_uptrend.start_state = self.state

        if self.is_in_buyzone():
            self._set_first_buy_zone(row)

        self._update_extremes(row)
        if self.context.current_uptrend is not None:
            update_trend_metrics(self.context.current_uptrend, self.context.last_close)

    def _update_active_trend_weekly(self, row: pd.Series) -> None:
        if self.context.current_uptrend is None:
            return
        if self.context.current_uptrend.start_date is not None and row.name <= self.context.current_uptrend.start_date:
            return
        if self.context.recovery_crossover_week is not None and row.name == self.context.recovery_crossover_week:
            return

        self.context.uptrend_weeks += 1
        if self.context.last_close > self.context.last_ema21:
            self.context.closes_above_ema += 1
        else:
            self.context.closes_below_ema += 1

        self.context.current_uptrend.num_weeks = self.context.uptrend_weeks
        self.context.current_uptrend.closes_above_ema = self.context.closes_above_ema
        self.context.current_uptrend.closes_below_ema = self.context.closes_below_ema
        if self.context.uptrend_weeks > 0:
            self.context.current_uptrend.pct_closes_above = self.context.closes_above_ema / self.context.uptrend_weeks
            self.context.current_uptrend.strength = self.context.current_uptrend.calculate_strength()

        if self.context.current_uptrend.first_buy_zone_date is None and self.is_in_buyzone():
            self._set_first_buy_zone(row)

        self._update_extremes(row)
        if self.context.current_uptrend.first_buy_zone_date is not None:
            update_trend_metrics(self.context.current_uptrend, self.context.last_close)

        if self.context.uptrend_weeks == self.config.tr_qualify_weeks and not self.context.tr_qualified:
            self.context.tr_qualified = True
            self._emit_trend_event(
                TrendEventType.TR_QUALIFIED,
                row,
                {"reason": "Uptrend weeks reached the qualification threshold"},
            )
            self.emit_signal(SignalType.TR_QUALIFIED, row)

    def _set_first_buy_zone(self, row: pd.Series) -> None:
        if self.context.current_uptrend is None or self.context.first_buy_zone_date is not None:
            return
        self.context.first_buy_zone_date = row.name
        self.context.first_buy_zone_price = row.get("Close")
        self.context.current_uptrend.first_buy_zone_date = row.name
        self.context.current_uptrend.first_buy_zone_price = row.get("Close")
        self._update_extremes(row)

    def _update_extremes(self, row: pd.Series) -> None:
        if self.context.current_uptrend is None:
            return
        high = row.get("High")
        low = row.get("Low")
        if high is not None and not pd.isna(high):
            if self.context.current_uptrend.highest_price is None or high > self.context.current_uptrend.highest_price:
                self.context.current_uptrend.highest_price = high
                self.context.current_uptrend.highest_price_date = row.name
        if low is not None and not pd.isna(low):
            if self.context.current_uptrend.lowest_price is None or low < self.context.current_uptrend.lowest_price:
                self.context.current_uptrend.lowest_price = low
                self.context.current_uptrend.lowest_price_date = row.name

    def _handle_bullish_crossover(self, row: pd.Series) -> None:
        self.context.is_crossover_detected = True
        self.context.positive_crossover_date = row.name
        self.context.positive_crossover_price = row.get("Close")

        self._emit_trend_event(
            TrendEventType.DAILY_POSITIVE_CROSSOVER,
            row,
            {"reason": "EMA34 crossed above EMA55"},
        )
        self.emit_signal(SignalType.EMA_CROSSOVER, row)

        was_recovering = self.state == State.RECOVERING.name

        # RECOVERING → UPTREND: bullish crossover confirms the recovered trend.
        if was_recovering:
            anchor_date = (
                self.context.current_uptrend.start_date
                if self.context.current_uptrend is not None and self.context.current_uptrend.start_date is not None
                else row.name
            )
            self.context.trend_start_date = anchor_date
            self.context.uptrend_start_date = anchor_date
            self.context.uptrend_weeks = 0
            self.context.closes_above_ema = 0
            self.context.closes_below_ema = 0

            crossover_week_end = self._compute_week_end(row.name)
            self.context.recovery_crossover_week = crossover_week_end

            if self.context.current_uptrend is not None:
                if self.context.current_uptrend.start_date is None:
                    self.context.current_uptrend.start_date = row.name
                self.context.current_uptrend.num_weeks = 0
                self.context.current_uptrend.closes_above_ema = 0
                self.context.current_uptrend.closes_below_ema = 0
                self.context.current_uptrend.pct_closes_above = 0.0
                self.context.current_uptrend.strength = None
                self.context.current_uptrend.first_buy_zone_date = None
                self.context.current_uptrend.first_buy_zone_price = None

            # Enter UPTREND macro-state; substate determined on next weekly candle
            self._set_macro_state(State.UPTREND)

        # Buy signal emission requires tr_qualified, buy zone, and no duplicate
        if not self.context.tr_qualified:
            return
        if self.context.buy_signal_emitted:
            return
        if self.context.current_uptrend is None:
            return
        if not self.is_in_buyzone():
            return

        signal_type = SignalType.MOMENTUM_ENTRY if was_recovering else SignalType.BUY_ENTRY
        self.emit_signal(signal_type, row)
        self.context.buy_signal_emitted = True
        self.context.last_buy_signal_date = row.name
        self.context.last_buy_signal_type = signal_type
        self.context.last_buy_signal_crossover_date = row.name

    def _compute_week_end(self, date) -> pd.Timestamp:
        """Compute the end of the W-FRI week for the given date."""
        ts = pd.Timestamp(date) if not isinstance(date, pd.Timestamp) else date
        week_period = ts.to_period("W-FRI")
        return week_period.end_time

    def _reset_bullish_crossover_latch(self) -> None:
        self.context.is_crossover_detected = False
        self.context.positive_crossover_date = None
        self.context.positive_crossover_price = None
        self.context.buy_signal_emitted = False
        self.context.last_buy_signal_crossover_date = None

    def _finalize_trend_end(self, row: pd.Series) -> None:
        """UPTREND → DOWNTREND: end the current uptrend cycle."""
        if self.context.current_uptrend is not None:
            self._update_extremes(row)
            update_trend_metrics(self.context.current_uptrend, self.context.last_close)
            self.context.current_uptrend.end_date = row.name
            self.context.current_uptrend.strength = self.context.current_uptrend.calculate_strength()
            self.context.current_uptrend.trend_roc_pct = self.context.current_uptrend.trend_roc_pct
            self.context.uptrend_history.append(self.context.current_uptrend)

        self.context.trend_end_date = row.name
        self.context.trend_start_date = self.context.current_uptrend.start_date if self.context.current_uptrend else self.context.trend_start_date
        if self.context.current_uptrend is not None:
            self.context.current_uptrend.end_state = State.DOWNTREND.name
            self.context.current_uptrend.end_price = row.get("Close")
        self._emit_trend_event(
            TrendEventType.WEEKLY_TREND_END,
            row,
            {"reason": "Weekly close fell below the 0.90 * EMA21 downtrend trigger"},
        )
        self.emit_signal(SignalType.DOWNTREND_START, row)

        self.context.current_uptrend = None
        self.context.uptrend_start_date = None
        self.context.uptrend_weeks = 0
        self.context.closes_above_ema = 0
        self.context.closes_below_ema = 0
        self.context.buy_signal_emitted = False
        self.context.daily_ema21_cross_date = None
        self.context.daily_ema21_cross_price = None
        self.context.recovery_crossover_week = None
        self._reset_bullish_crossover_latch()
        self._set_macro_state(State.DOWNTREND)

    # ---------------------------------------------------------------------
    # Signal / event emission
    # ---------------------------------------------------------------------
    def emit_signal(self, signal_type: SignalType, row: Optional[pd.Series] = None) -> None:
        if not self.signal_callback:
            return
        source_row = row if row is not None else self._current_row
        metadata = self._build_signal_metadata(signal_type, source_row)
        signal = SignalEvent(
            ticker=self.ticker,
            signal_type=signal_type,
            date=self.context.last_update,
            close_price=self.context.last_close,
            ema21=self.context.last_ema21,
            ema34=self.context.last_ema34,
            ema55=self.context.last_ema55,
            timeframe=source_row.get("timeframe") if source_row is not None and "timeframe" in source_row else None,
            state=self.state,
            trend_cycle_id=self.context.trend_cycle_id,
            trend_start_date=self.context.trend_start_date,
            trend_end_date=self.context.trend_end_date,
            metadata=metadata,
        )
        self.signal_callback(signal)

    def _emit_trend_event(
        self,
        event_type: TrendEventType,
        row: Optional[pd.Series] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        if not self.event_callback:
            return
        source_row = row if row is not None else self._current_row
        event = TrendEventRecord(
            ticker=self.ticker,
            event_type=event_type,
            date=self.context.last_update,
            close_price=self.context.last_close,
            ema21=self.context.last_ema21,
            ema34=self.context.last_ema34,
            ema55=self.context.last_ema55,
            timeframe=source_row.get("timeframe") if source_row is not None and "timeframe" in source_row else None,
            state=self.state,
            trend_cycle_id=self.context.trend_cycle_id,
            metadata=metadata or {},
        )
        self.event_callback(event)

    @staticmethod
    def _to_isoformat(value) -> Optional[str]:
        """Safely convert a datetime or compatible value to ISO format string."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace(' ', 'T'))
                return parsed.isoformat()
            except (ValueError, TypeError):
                return value
        return None

    def _build_signal_metadata(self, signal_type: SignalType, row: Optional[pd.Series]) -> dict:
        reason_map = {
            SignalType.UPTREND_START: "Weekly close confirmed the official trend start",
            SignalType.BUY_ENTRY: "First qualifying bullish crossover after trend qualification",
            SignalType.REENTRY: "TR-qualified stock re-entered the buy zone",
            SignalType.MOMENTUM_ENTRY: "Qualified bullish crossover during recovery",
            SignalType.DOWNTREND_START: "Weekly close fell below the 0.90 * EMA21 trigger",
            SignalType.EMA_CROSSOVER: "EMA34 crossed above EMA55",
            SignalType.TR_QUALIFIED: "Uptrend weeks reached the qualification threshold",
        }

        metadata = {
            "reason": reason_map.get(signal_type, signal_type.name),
            "timeframe": row.get("timeframe") if row is not None and "timeframe" in row else None,
            "state": self.state,
            "uptrend_substate": self.context.uptrend_substate,
            "candle_count": self.context.candle_count,
            "weekly_candle_count": self.context.weekly_candle_count,
            "uptrend_weeks": self.context.uptrend_weeks,
            "tr_qualified": self.context.tr_qualified,
            "is_buyzone": self.context.is_buyzone,
            "is_crossover_detected": self.context.is_crossover_detected,
            "trend_start_date": self._to_isoformat(self.context.trend_start_date),
            "trend_end_date": self._to_isoformat(self.context.trend_end_date),
            "first_buy_zone_date": self._to_isoformat(self.context.first_buy_zone_date),
            "daily_ema21_cross_date": self._to_isoformat(self.context.daily_ema21_cross_date),
        }

        source = row if row is not None else self._current_row
        if source is not None:
            metadata.update(
                {
                    "open": source.get("Open"),
                    "high": source.get("High"),
                    "low": source.get("Low"),
                    "close": source.get("Close"),
                    "volume": source.get("Volume"),
                    "ema21": source.get("EMA21") if "EMA21" in source else self.context.last_ema21,
                    "ema34": source.get("EMA34") if "EMA34" in source else self.context.last_ema34,
                    "ema55": source.get("EMA55") if "EMA55" in source else self.context.last_ema55,
                }
            )

        return {key: value for key, value in metadata.items() if value is not None}