from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from trend_rider_lib import (
    Classification,
    SignalEvent,
    SignalType,
    State,
    StockContext,
    TrendEventRecord,
    TrendEventType,
    TrendRiderConfig,
    UptrendRecord,
    UptrendStrength,
)
from trend_rider_lib.persistence import SQLiteProvider
from trend_rider_lib.state_machine.fsm import StockFSM
from trend_rider_lib.state_machine.trend_metrics import record_daily_point, record_weekly_point, update_trend_metrics


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "delhivery_weekly_confirmation.csv"


def load_fixture_frame() -> pd.DataFrame:
    frame = pd.read_csv(FIXTURE_PATH)
    frame["Date"] = pd.to_datetime(frame["Date"])
    frame["timeframe"] = frame["Timeframe"].str.lower()
    order = {"daily": 0, "weekly": 1}
    frame["_order"] = frame["timeframe"].map(order)
    frame = frame.sort_values(["Date", "_order"], kind="stable").drop(columns=["_order"])
    frame = frame.set_index("Date")
    return frame


def weekly_row(date: str, open_: float, high: float, low: float, close: float, ema21: float) -> pd.Series:
    return pd.Series(
        {
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": 1_000_000,
            "EMA21": ema21,
            "timeframe": "weekly",
        },
        name=pd.Timestamp(date),
    )


def daily_row(
    date: str,
    open_: float,
    high: float,
    low: float,
    close: float,
    ema34: float,
    ema55: float,
) -> pd.Series:
    return pd.Series(
        {
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": 500_000,
            "EMA34": ema34,
            "EMA55": ema55,
            "timeframe": "daily",
        },
        name=pd.Timestamp(date),
    )


def feed_rows(fsm: StockFSM, frame: pd.DataFrame) -> tuple[list[SignalEvent], list[TrendEventRecord]]:
    signals: list[SignalEvent] = []
    events: list[TrendEventRecord] = []

    def signal_capture(signal: SignalEvent) -> None:
        signals.append(signal)

    def event_capture(event: TrendEventRecord) -> None:
        events.append(event)

    fsm.signal_callback = signal_capture
    fsm.event_callback = event_capture

    for idx, row in frame.iterrows():
        if row["timeframe"] == "weekly":
            fsm.process_weekly_candle(row)
        else:
            fsm.process_daily_candle(row)

    return signals, events


def test_trend_start_is_weekly_confirmed_and_week_is_excluded():
    frame = load_fixture_frame()
    frame = pd.concat(
        [
            frame,
            pd.DataFrame(
                [
                    weekly_row("2023-04-28", 360.0, 380.0, 356.0, 378.0, 351.0),
                ]
            ),
        ]
    ).sort_index(kind="stable")

    fsm = StockFSM("DELHIVERY.NS", TrendRiderConfig())
    signals, events = feed_rows(fsm, frame)

    assert fsm.context.trend_start_date == pd.Timestamp("2023-04-21")
    assert fsm.context.daily_ema21_cross_date == pd.Timestamp("2023-04-21")
    assert fsm.context.current_uptrend is not None
    assert fsm.context.current_uptrend.start_date == pd.Timestamp("2023-04-21")
    assert fsm.context.current_uptrend.num_weeks == 1
    assert fsm.context.uptrend_weeks == 1
    assert any(signal.signal_type == SignalType.UPTREND_START for signal in signals)
    assert [event.event_type for event in events[:2]] == [
        TrendEventType.DAILY_EMA21_CONFIRMATION,
        TrendEventType.WEEKLY_TREND_START,
    ]


def test_trend_end_uses_weekly_close_and_excludes_ending_week():
    frame = load_fixture_frame()
    frame = pd.concat(
        [
            frame,
            pd.DataFrame(
                [
                    weekly_row("2023-04-28", 360.0, 380.0, 356.0, 378.0, 351.0),
                    daily_row("2023-05-05", 305.0, 306.0, 298.0, 300.0, 320.0, 321.0),
                    weekly_row("2023-05-05", 320.0, 325.0, 295.0, 300.0, 340.0),
                ]
            ),
        ]
    ).sort_index(kind="stable")

    fsm = StockFSM("DELHIVERY.NS", TrendRiderConfig())
    signals, events = feed_rows(fsm, frame)

    assert fsm.context.trend_end_date == pd.Timestamp("2023-05-05")
    assert fsm.context.daily_downtrend_trigger_date == pd.Timestamp("2023-05-05")
    assert fsm.context.current_uptrend is None
    assert fsm.context.uptrend_history[-1].end_date == pd.Timestamp("2023-05-05")
    assert fsm.context.uptrend_history[-1].num_weeks == 1
    assert any(signal.signal_type == SignalType.DOWNTREND_START for signal in signals)
    assert any(event.event_type == TrendEventType.DAILY_DOWNTREND_TRIGGER for event in events)
    assert any(event.event_type == TrendEventType.WEEKLY_TREND_END for event in events)


def test_recovering_classification_uses_recovering_label():
    fsm = StockFSM("TEST", TrendRiderConfig())
    fsm.context.current_state = State.RECOVERING
    fsm.machine.set_state(State.RECOVERING.name, model=fsm)

    from trend_rider_lib.state_machine.classifier import classify_stock

    assert classify_stock(fsm.context) == Classification.RECOVERING


def test_recovering_bullish_crossover_resets_start_for_new_uptrend():
    fsm = StockFSM("TEST", TrendRiderConfig())
    fsm.context.current_state = State.RECOVERING
    fsm.machine.set_state(State.RECOVERING.name, model=fsm)
    fsm.context.tr_qualified = True
    fsm.context.current_uptrend = UptrendRecord(start_date=pd.Timestamp("2024-01-01"))
    fsm.context.current_uptrend.cycle_id = 1
    fsm.context.current_uptrend.start_state = State.RECOVERING.name
    fsm.context.last_ema21 = 100.0
    fsm.context.last_ema34 = 99.0
    fsm.context.last_ema55 = 100.0
    fsm.context.last_close = 101.0
    fsm.context.is_buyzone = True

    fsm.process_daily_candle(
        daily_row("2024-01-02", 100.0, 103.0, 99.5, 102.0, 101.0, 100.0)
    )

    assert fsm.state == State.UPTREND.name
    assert fsm.context.current_uptrend is not None
    assert fsm.context.current_uptrend.start_date == pd.Timestamp("2024-01-01")
    assert fsm.context.uptrend_weeks == 0
    assert fsm.context.closes_above_ema == 0
    assert fsm.context.buy_signal_emitted is True


def test_recovering_blocks_buy_signals():
    frame = load_fixture_frame()
    frame = pd.concat(
        [
            frame,
            pd.DataFrame(
                [
                    weekly_row("2023-04-28", 360.0, 380.0, 356.0, 378.0, 351.0),
                    daily_row("2023-05-05", 305.0, 306.0, 298.0, 300.0, 320.0, 321.0),
                    weekly_row("2023-05-05", 320.0, 325.0, 295.0, 300.0, 340.0),
                    weekly_row("2023-05-12", 308.0, 322.0, 307.0, 320.0, 310.0),
                    daily_row("2023-05-15", 318.0, 326.0, 316.0, 324.0, 300.0, 305.0),
                ]
            ),
        ]
    ).sort_index(kind="stable")

    fsm = StockFSM("DELHIVERY.NS", TrendRiderConfig())
    signals, _events = feed_rows(fsm, frame)

    assert fsm.state == State.RECOVERING.name
    assert not any(signal.signal_type in {SignalType.BUY_ENTRY, SignalType.MOMENTUM_ENTRY} for signal in signals)


def test_buy_signal_gated_by_qualification_and_duplicate_crosses():
    config = TrendRiderConfig()
    fsm = StockFSM("TEST", config)
    signals: list[SignalEvent] = []

    def signal_capture(signal: SignalEvent) -> None:
        signals.append(signal)

    fsm.signal_callback = signal_capture
    fsm.context.current_state = State.RECOVERING
    fsm.machine.set_state(State.RECOVERING.name, model=fsm)
    fsm.context.current_uptrend = UptrendRecord(start_date=pd.Timestamp("2024-01-01"))
    fsm.context.current_uptrend.cycle_id = 1
    fsm.context.current_uptrend.start_state = State.RECOVERING.name
    fsm.context.current_uptrend.first_buy_zone_date = pd.Timestamp("2024-01-01")
    fsm.context.current_uptrend.first_buy_zone_price = 100.0
    fsm.context.last_ema21 = 100.0
    fsm.context.last_close = 101.0
    fsm.context.is_buyzone = True

    first_cross = daily_row("2024-01-02", 100.0, 102.0, 99.0, 101.0, 99.0, 100.0)
    fsm.process_daily_candle(first_cross)
    assert not any(signal.signal_type in {SignalType.BUY_ENTRY, SignalType.MOMENTUM_ENTRY} for signal in signals)

    fsm.context.tr_qualified = True
    bearish_reset = daily_row("2024-01-03", 100.0, 100.5, 98.0, 99.0, 98.0, 100.0)
    fsm.process_daily_candle(bearish_reset)

    qualified_cross = daily_row("2024-01-04", 100.0, 103.0, 99.5, 102.0, 101.0, 100.0)
    fsm.process_daily_candle(qualified_cross)

    assert any(signal.signal_type == SignalType.MOMENTUM_ENTRY for signal in signals)
    buy_signals = [signal for signal in signals if signal.signal_type in {SignalType.BUY_ENTRY, SignalType.MOMENTUM_ENTRY}]
    assert len(buy_signals) == 1


def test_buy_signal_allows_green_breakout_that_opened_inside_upper_band():
    config = TrendRiderConfig()
    fsm = StockFSM("TEST", config)
    signals: list[SignalEvent] = []
    fsm.signal_callback = signals.append
    fsm.context.tr_qualified = True
    fsm.context.current_uptrend = UptrendRecord(start_date=pd.Timestamp("2024-01-01"))
    fsm.context.last_ema21 = 100.0
    fsm.context.last_ema34 = 99.0
    fsm.context.last_ema55 = 100.0
    fsm.machine.set_state(State.UPTREND.name, model=fsm)

    breakout_cross = daily_row("2024-01-02", 104.0, 110.0, 103.0, 110.0, 101.0, 100.0)
    fsm.process_daily_candle(breakout_cross)

    buy_signals = [signal for signal in signals if signal.signal_type == SignalType.BUY_ENTRY]
    assert len(buy_signals) == 1
    assert buy_signals[0].close_price == 110.0


def test_buy_signal_rejects_red_candle_even_when_open_is_inside_upper_band():
    config = TrendRiderConfig()
    fsm = StockFSM("TEST", config)
    signals: list[SignalEvent] = []
    fsm.signal_callback = signals.append
    fsm.context.tr_qualified = True
    fsm.context.current_uptrend = UptrendRecord(start_date=pd.Timestamp("2024-01-01"))
    fsm.context.last_ema21 = 100.0
    fsm.context.last_ema34 = 99.0
    fsm.context.last_ema55 = 100.0
    fsm.machine.set_state(State.UPTREND.name, model=fsm)

    red_cross = daily_row("2024-01-02", 104.0, 105.0, 101.0, 103.0, 101.0, 100.0)
    fsm.process_daily_candle(red_cross)

    assert not any(signal.signal_type == SignalType.BUY_ENTRY for signal in signals)


def test_active_uptrend_strength_updates_with_weekly_stats():
    fsm = StockFSM("TEST", TrendRiderConfig())
    fsm.context.current_uptrend = UptrendRecord(start_date=pd.Timestamp("2024-01-01"))
    fsm.context.current_uptrend.cycle_id = 1

    for offset, close in enumerate([101.0, 102.0, 99.0, 103.0], start=1):
        date = pd.Timestamp("2024-01-01") + pd.Timedelta(weeks=offset)
        fsm.process_weekly_candle(
            weekly_row(
                date.strftime("%Y-%m-%d"),
                close,
                close + 1.0,
                close - 1.0,
                close,
                100.0,
            )
        )

    assert fsm.context.current_uptrend is not None
    assert fsm.context.current_uptrend.num_weeks == 4
    assert fsm.context.current_uptrend.closes_above_ema == 3
    assert fsm.context.current_uptrend.pct_closes_above == pytest.approx(0.75)
    assert fsm.context.current_uptrend.strength == UptrendStrength.DEVELOPING


def test_analytics_and_ath_metrics_from_first_official_buy_zone():
    uptrend = UptrendRecord(start_date=pd.Timestamp("2024-01-01"))
    uptrend.cycle_id = 1
    uptrend.first_buy_zone_date = pd.Timestamp("2024-01-01")
    uptrend.first_buy_zone_price = 100.0
    uptrend.start_price = 100.0

    for offset, close in enumerate([100.0, 103.0, 108.0, 112.0, 120.0]):
        date = pd.Timestamp("2024-01-01") + pd.Timedelta(weeks=offset)
        record_weekly_point(uptrend, date, close)

    for offset, close in enumerate([100.0, 101.0, 105.0, 110.0, 115.0, 120.0]):
        date = pd.Timestamp("2024-01-01") + pd.Timedelta(days=offset)
        record_daily_point(uptrend, date, close, 90.0 + offset, 80.0 + offset, 70.0 + offset)

    uptrend.highest_price = 130.0
    uptrend.highest_price_date = pd.Timestamp("2024-01-10")
    update_trend_metrics(uptrend, 120.0)

    assert uptrend.max_profit_pct == 30.0
    assert uptrend.trend_roc_pct == 20.0
    assert uptrend.ath_price == 130.0
    assert uptrend.ath_date == pd.Timestamp("2024-01-10")
    assert uptrend.distance_from_ath_abs == 10.0
    assert uptrend.distance_from_ath_pct == pytest.approx(7.6923, rel=1e-3)
    assert uptrend.roc_1w_pct == pytest.approx(7.1429, rel=1e-3)
    assert uptrend.roc_3w_pct == pytest.approx(16.5049, rel=1e-3)
    assert uptrend.roc_6m_pct is None
    assert uptrend.roc_9m_pct is None
    assert uptrend.ema21_slope is not None
    assert uptrend.ema34_55_spread == pytest.approx(10.0)
    assert uptrend.efficiency_ratio == pytest.approx(1.0)


def test_normalized_persistence_round_trip(tmp_path):
    db_path = tmp_path / "trend_rider.sqlite"
    provider = SQLiteProvider(str(db_path))

    context = StockContext(
        ticker="TEST",
        current_state=State.UPTREND,
        tr_qualified=True,
        trend_start_date=datetime(2024, 1, 1),
        trend_end_date=None,
        daily_ema21_cross_date=datetime(2024, 1, 1),
        first_buy_zone_date=datetime(2024, 1, 1),
    )
    context.trend_cycle_id = 1
    context.daily_ema21_cross_price = 100.0
    context.first_buy_zone_price = 100.0
    context.buy_signal_emitted = True
    context.last_buy_signal_date = datetime(2024, 1, 2)
    context.last_buy_signal_type = SignalType.BUY_ENTRY
    context.last_buy_signal_crossover_date = datetime(2024, 1, 2)
    context.last_close = 120.0
    context.last_update = datetime(2024, 1, 2)
    context.current_uptrend = UptrendRecord(start_date=datetime(2024, 1, 1))
    context.current_uptrend.cycle_id = 1
    context.current_uptrend.start_state = State.UPTREND.name
    context.current_uptrend.start_price = 100.0
    context.current_uptrend.first_buy_zone_date = datetime(2024, 1, 1)
    context.current_uptrend.first_buy_zone_price = 100.0
    context.current_uptrend.num_weeks = 1
    context.current_uptrend.closes_above_ema = 1
    context.current_uptrend.pct_closes_above = 1.0
    context.current_uptrend.strength = UptrendStrength.SUPER_STRONG
    context.current_uptrend.highest_price = 130.0
    context.current_uptrend.highest_price_date = datetime(2024, 1, 2)
    context.current_uptrend.max_profit_pct = 30.0
    context.current_uptrend.trend_roc_pct = 20.0
    context.current_uptrend.ath_price = 130.0
    context.current_uptrend.ath_date = datetime(2024, 1, 2)
    context.current_uptrend.distance_from_ath_abs = 10.0
    context.current_uptrend.distance_from_ath_pct = 7.6923
    context.current_uptrend.weekly_close_history = [(datetime(2024, 1, 1), 100.0), (datetime(2024, 1, 8), 110.0)]
    context.current_uptrend.daily_close_history = [(datetime(2024, 1, 1), 100.0), (datetime(2024, 1, 2), 120.0)]
    context.current_uptrend.daily_ema21_history = [(datetime(2024, 1, 1), 100.0), (datetime(2024, 1, 2), 101.0)]
    context.current_uptrend.daily_ema34_history = [(datetime(2024, 1, 1), 99.0), (datetime(2024, 1, 2), 102.0)]
    context.current_uptrend.daily_ema55_history = [(datetime(2024, 1, 1), 98.0), (datetime(2024, 1, 2), 100.0)]
    context.uptrend_history = []

    provider.save_context(context)
    provider.save_signal(
        SignalEvent(
            ticker="TEST",
            signal_type=SignalType.BUY_ENTRY,
            date=datetime(2024, 1, 2),
            close_price=120.0,
            ema21=100.0,
            ema34=102.0,
            ema55=100.0,
            timeframe="daily",
            state="UPTREND",
            trend_cycle_id=1,
            trend_start_date=datetime(2024, 1, 1),
            metadata={"reason": "First qualifying bullish crossover after trend qualification"},
        )
    )
    provider.save_trend_event(
        TrendEventRecord(
            ticker="TEST",
            event_type=TrendEventType.WEEKLY_TREND_START,
            date=datetime(2024, 1, 1),
            close_price=100.0,
            ema21=100.0,
            timeframe="weekly",
            state="UPTREND",
            trend_cycle_id=1,
            metadata={"reason": "Weekly close confirmed the official trend start"},
        )
    )

    loaded = provider.load_context("TEST")
    assert loaded is not None
    assert loaded.trend_start_date == datetime(2024, 1, 1)
    assert loaded.current_uptrend is not None
    assert loaded.current_uptrend.max_profit_pct == 30.0
    assert loaded.current_uptrend.strength == UptrendStrength.SUPER_STRONG

    cycles = provider.get_trend_cycles("TEST")
    analytics = provider.get_trend_analytics("TEST")
    events = provider.get_trend_events("TEST")
    latest_signal = provider.get_latest_signal("TEST")

    assert cycles
    assert analytics
    assert analytics[0].strength == UptrendStrength.SUPER_STRONG
    assert events
    assert latest_signal is not None
    assert latest_signal.timeframe == "daily"
    assert latest_signal.state == "UPTREND"
    assert latest_signal.trend_cycle_id == 1


def _setup_with_uptrend_and_downtrend(fsm: StockFSM) -> None:
    """Run warmup then simulate an uptrend followed by downtrend trigger.
    Leaves FSM in DOWNTREND state with the ended uptrend in history."""
    config = TrendRiderConfig()
    # Push through warmup by sending 25 weekly candles with close BELOW EMA21
    # to avoid triggering an uptrend during warmup.
    base_date = pd.Timestamp("2023-01-06")
    for i in range(25):
        date = base_date + pd.Timedelta(weeks=i)
        fsm.process_weekly_candle(
            weekly_row(date.strftime("%Y-%m-%d"), 99.0, 101.0, 98.0, 99.0, 100.0)
        )
    assert fsm.state == State.OBSERVING.name

    # Uptrend week 1: close > EMA21
    date = base_date + pd.Timedelta(weeks=25)
    fsm.process_weekly_candle(
        weekly_row(date.strftime("%Y-%m-%d"), 101.0, 104.0, 100.0, 103.0, 100.0)
    )

    # Uptrend week 2: continues
    date = base_date + pd.Timedelta(weeks=26)
    fsm.process_weekly_candle(
        weekly_row(date.strftime("%Y-%m-%d"), 102.0, 105.0, 101.0, 104.0, 100.0)
    )

    # Downtrend trigger week: close < 90
    date = base_date + pd.Timedelta(weeks=27)
    fsm.process_weekly_candle(
        weekly_row(date.strftime("%Y-%m-%d"), 88.0, 89.0, 85.0, 87.0, 100.0)
    )
    assert fsm.state == State.DOWNTREND.name
    assert fsm.context.current_uptrend is None
    assert len(fsm.context.uptrend_history) == 1


def test_recovering_weeks_not_counted_in_uptrend_analytics():
    """
    Weekly candles processed during RECOVERING must NOT be counted in
    uptrend_weeks, closes_above_ema, closes_below_ema, or pct_closes_above.
    Only weeks AFTER the bullish crossover confirmation should count.
    """
    fsm = StockFSM("TEST", TrendRiderConfig())
    _setup_with_uptrend_and_downtrend(fsm)

    # RECOVERING Week A: close > EMA21 (but only starts trend if current_uptrend is None)
    # Since we're in DOWNTREND with no current_uptrend, this should work
    fsm.process_weekly_candle(
        weekly_row("2024-02-02", 101.0, 104.0, 100.0, 103.0, 100.0)
    )
    assert fsm.state == State.RECOVERING.name
    assert fsm.context.uptrend_weeks == 0

    # RECOVERING Week B: should NOT count
    fsm.process_weekly_candle(
        weekly_row("2024-02-09", 102.0, 105.0, 101.0, 104.0, 100.0)
    )
    assert fsm.state == State.RECOVERING.name
    assert fsm.context.uptrend_weeks == 0
    assert fsm.context.closes_above_ema == 0
    assert fsm.context.closes_below_ema == 0

    # RECOVERING Week C: should NOT count
    fsm.process_weekly_candle(
        weekly_row("2024-02-16", 103.0, 106.0, 102.0, 105.0, 100.0)
    )
    assert fsm.state == State.RECOVERING.name
    assert fsm.context.uptrend_weeks == 0

    # Now bullish crossover happens (daily), confirming the recovery
    # Set previous EMAs so the crossover is detected
    fsm.context.last_ema34 = 99.0
    fsm.context.last_ema55 = 101.0
    fsm.context.tr_qualified = True
    fsm.context.is_buyzone = True
    signals: list = []
    fsm.signal_callback = signals.append
    fsm.process_daily_candle(
        daily_row("2024-02-19", 103.0, 106.0, 102.0, 105.0, 102.0, 101.0)
    )
    assert fsm.state == State.UPTREND.name
    assert fsm.context.uptrend_weeks == 0
    assert fsm.context.closes_above_ema == 0
    assert fsm.context.closes_below_ema == 0

    # Week D: now counted (first week after crossover)
    fsm.process_weekly_candle(
        weekly_row("2024-02-23", 104.0, 107.0, 103.0, 106.0, 100.0)
    )
    assert fsm.context.uptrend_weeks == 1
    assert fsm.context.closes_above_ema == 1
    assert fsm.context.closes_below_ema == 0

    # Week E: counted
    fsm.process_weekly_candle(
        weekly_row("2024-03-01", 103.0, 104.0, 100.0, 101.0, 100.0)
    )
    assert fsm.context.uptrend_weeks == 2
    assert fsm.context.closes_above_ema == 2
    assert fsm.context.closes_below_ema == 0


def test_recovering_bullish_crossover_transitions_to_uptrend_without_tr_qualified():
    """
    A bullish crossover during RECOVERING must transition to UPTREND and
    reset analytics even when tr_qualified is False. Buy signals remain
    gated but the state transition and analytics reset must occur.
    """
    fsm = StockFSM("TEST", TrendRiderConfig())
    _setup_with_uptrend_and_downtrend(fsm)

    # Enter RECOVERING
    fsm.process_weekly_candle(
        weekly_row("2024-02-02", 101.0, 104.0, 100.0, 103.0, 100.0)
    )
    assert fsm.state == State.RECOVERING.name

    # Some weeks pass in RECOVERING (not counted)
    fsm.process_weekly_candle(
        weekly_row("2024-02-09", 102.0, 105.0, 101.0, 104.0, 100.0)
    )
    assert fsm.context.uptrend_weeks == 0

    # Bullish crossover WITHOUT tr_qualified
    fsm.context.last_ema34 = 99.0
    fsm.context.last_ema55 = 102.0
    fsm.context.is_buyzone = True
    signals: list = []
    fsm.signal_callback = signals.append
    fsm.process_daily_candle(
        daily_row("2024-02-12", 103.0, 106.0, 102.0, 105.0, 102.0, 101.0)
    )
    # MUST transition to UPTREND even without tr_qualified
    assert fsm.state == State.UPTREND.name
    assert fsm.context.uptrend_weeks == 0
    assert fsm.context.closes_above_ema == 0
    assert fsm.context.closes_below_ema == 0

    # No buy signal should have been emitted since tr_qualified=False
    buy_entry_signals = [s for s in signals if s.signal_type in {SignalType.BUY_ENTRY, SignalType.MOMENTUM_ENTRY}]
    assert len(buy_entry_signals) == 0


def test_full_recovery_lifecycle_analytics():
    """
    Simulate a full lifecycle: UPTREND → DOWNTREND → RECOVERING (several weeks)
    → bullish crossover confirms uptrend → uptrend weeks counted correctly.
    This tests the exact scenario reported in the TIINDIA.NS bug.
    """
    fsm = StockFSM("TEST", TrendRiderConfig())
    _setup_with_uptrend_and_downtrend(fsm)

    # RECOVERING weeks: close above EMA21 after downtrend
    # These MUST NOT count towards uptrend analytics
    fsm.process_weekly_candle(
        weekly_row("2024-02-02", 101.0, 105.0, 100.0, 103.0, 100.0)
    )
    assert fsm.state == State.RECOVERING.name

    fsm.process_weekly_candle(
        weekly_row("2024-02-09", 102.0, 106.0, 101.0, 104.0, 100.0)
    )
    fsm.process_weekly_candle(
        weekly_row("2024-02-16", 103.0, 107.0, 102.0, 105.0, 100.0)
    )
    fsm.process_weekly_candle(
        weekly_row("2024-02-23", 104.0, 108.0, 103.0, 106.0, 100.0)
    )

    # All RECOVERING weeks should NOT be counted
    assert fsm.context.uptrend_weeks == 0
    assert fsm.context.closes_above_ema == 0
    assert fsm.context.closes_below_ema == 0

    # Bullish crossover confirms recovery (MOMENTUM_ENTRY when tr_qualified)
    fsm.context.last_ema34 = 99.0
    fsm.context.last_ema55 = 103.0
    fsm.context.tr_qualified = True
    fsm.context.is_buyzone = True
    fsm.process_daily_candle(
        daily_row("2024-02-26", 105.0, 109.0, 104.0, 108.0, 103.0, 102.0)
    )
    assert fsm.state == State.UPTREND.name
    # Analytics should be reset to 0
    assert fsm.context.uptrend_weeks == 0
    assert fsm.context.closes_above_ema == 0
    assert fsm.context.closes_below_ema == 0

    # Now uptrend weeks should count properly (not including recovery weeks)
    fsm.process_weekly_candle(
        weekly_row("2024-03-01", 106.0, 110.0, 105.0, 109.0, 100.0)
    )
    assert fsm.context.uptrend_weeks == 1
    assert fsm.context.closes_above_ema == 1

    fsm.process_weekly_candle(
        weekly_row("2024-03-08", 107.0, 111.0, 106.0, 110.0, 100.0)
    )
    assert fsm.context.uptrend_weeks == 2
    assert fsm.context.closes_above_ema == 2

    fsm.process_weekly_candle(
        weekly_row("2024-03-15", 106.0, 108.0, 99.0, 99.0, 100.0)
    )
    assert fsm.context.uptrend_weeks == 3
    assert fsm.context.closes_above_ema == 2
    assert fsm.context.closes_below_ema == 1

    # Verify final analytics
    assert fsm.context.current_uptrend is not None
    assert fsm.context.current_uptrend.num_weeks == 3
    assert fsm.context.current_uptrend.closes_above_ema == 2
    assert fsm.context.current_uptrend.pct_closes_above == pytest.approx(2/3)
    # Should be DEVELOPING (pct ~ 0.667, which is < 0.70 threshold)
    assert fsm.context.current_uptrend.strength == UptrendStrength.WEAK
