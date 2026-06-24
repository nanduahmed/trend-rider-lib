"""
Tests for scan behaviour at different points in the trading week.
Uses real TIINDIA.NS data to validate weekly candle inclusion and
state transitions depending on the day of the scan.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from trend_rider_lib import TrendRiderConfig
from trend_rider_lib.state_machine.fsm import StockFSM

# ---------------------------------------------------------------------------
# Fixture data directory
# ---------------------------------------------------------------------------
FIXTURES = Path(__file__).parent.parent / "fixtures"
DEBUG_CSV = FIXTURES / "TIINDIA.NS_analysis_debug.csv"

# ---------------------------------------------------------------------------
# Inline row data for the test week 2019-05-13 – 2019-05-24
# Every CSV column is present so the test file is self-documenting.
# ---------------------------------------------------------------------------

_DAILY_BASE = {
    "Ticker": "TIINDIA.NS",
    "Candle Color": "",
    "Trend Start": "2018-07-06",
    "Trend End": None,
    "Daily EMA21 Cross": "2018-07-06",
    "Daily Downtrend Trigger": None,
    "First Buy Zone": "2018-07-06",
    "Positive Crossover": "2018-07-06",
    "Crossover Detected": True,
    "Crossover Date": "2018-07-25",
    "Crossover Price": 242.09,
    "Signal Count": 0,
    "Signal Types": "",
    "Signal Reasons": "",
    "Signal Metadata": "",
}

_WEEKLY_BASE = {
    **_DAILY_BASE,
    "Signal Metadata": "",
}

# --- 2019-05-13 Monday daily ---
R13_DAILY = {
    **_DAILY_BASE,
    "Date": "2019-05-13",
    "Timeframe": "daily",
    "Candle Color": "RED",
    "Open": 364.93,
    "High": 366.21,
    "Low": 358.4,
    "Close": 364.64,
    "Volume": 162071,
    "EMA21": None,
    "EMA34": 367.05,
    "EMA55": 362.5,
    "is_buyzone": False,
    "is_above_buyzone": False,
    "is_downtrend_trigger": False,
    "warmup_complete": True,
    "State Before": "ABOVE_BUY_ZONE",
    "State After": "ABOVE_BUY_ZONE",
    "Classification": "PRIME_WAITLIST",
    "TR Qualified": True,
    "Buy Zone": False,
    "Uptrend Weeks": 44,
    "Weekly Candle Count": 80,
    "Closes Above EMA": 42,
    "Closes Below EMA": 2,
}

# --- 2019-05-14 Tuesday daily ---
R14_DAILY = {
    **_DAILY_BASE,
    "Date": "2019-05-14",
    "Timeframe": "daily",
    "Candle Color": "GREEN",
    "Open": 361.1,
    "High": 369.2,
    "Low": 359.04,
    "Close": 365.37,
    "Volume": 20578,
    "EMA21": None,
    "EMA34": 366.95,
    "EMA55": 362.61,
    "is_buyzone": False,
    "is_above_buyzone": False,
    "is_downtrend_trigger": False,
    "warmup_complete": True,
    "State Before": "ABOVE_BUY_ZONE",
    "State After": "ABOVE_BUY_ZONE",
    "Classification": "PRIME",
    "TR Qualified": True,
    "Buy Zone": True,
    "Uptrend Weeks": 44,
    "Weekly Candle Count": 80,
    "Closes Above EMA": 42,
    "Closes Below EMA": 2,
}

# --- 2019-05-15 Wednesday daily ---
R15_DAILY = {
    **_DAILY_BASE,
    "Date": "2019-05-15",
    "Timeframe": "daily",
    "Candle Color": "RED",
    "Open": 372.15,
    "High": 372.15,
    "Low": 363.31,
    "Close": 364.24,
    "Volume": 5046,
    "EMA21": None,
    "EMA34": 366.8,
    "EMA55": 362.66,
    "is_buyzone": False,
    "is_above_buyzone": False,
    "is_downtrend_trigger": False,
    "warmup_complete": True,
    "State Before": "ABOVE_BUY_ZONE",
    "State After": "ABOVE_BUY_ZONE",
    "Classification": "PRIME_WAITLIST",
    "TR Qualified": True,
    "Buy Zone": False,
    "Uptrend Weeks": 44,
    "Weekly Candle Count": 80,
    "Closes Above EMA": 42,
    "Closes Below EMA": 2,
}

# --- 2019-05-16 Thursday daily ---
R16_DAILY = {
    **_DAILY_BASE,
    "Date": "2019-05-16",
    "Timeframe": "daily",
    "Candle Color": "RED",
    "Open": 369.2,
    "High": 377.06,
    "Low": 359.38,
    "Close": 368.71,
    "Volume": 45830,
    "EMA21": None,
    "EMA34": 366.9,
    "EMA55": 362.88,
    "is_buyzone": False,
    "is_above_buyzone": False,
    "is_downtrend_trigger": False,
    "warmup_complete": True,
    "State Before": "ABOVE_BUY_ZONE",
    "State After": "ABOVE_BUY_ZONE",
    "Classification": "PRIME_WAITLIST",
    "TR Qualified": True,
    "Buy Zone": False,
    "Uptrend Weeks": 44,
    "Weekly Candle Count": 80,
    "Closes Above EMA": 42,
    "Closes Below EMA": 2,
}

# --- 2019-05-17 Friday daily ---
R17_DAILY = {
    **_DAILY_BASE,
    "Date": "2019-05-17",
    "Timeframe": "daily",
    "Candle Color": "GREEN",
    "Open": 370.87,
    "High": 375.09,
    "Low": 364.49,
    "Close": 372.79,
    "Volume": 26785,
    "EMA21": None,
    "EMA34": 367.24,
    "EMA55": 363.23,
    "is_buyzone": False,
    "is_above_buyzone": False,
    "is_downtrend_trigger": False,
    "warmup_complete": True,
    "State Before": "ABOVE_BUY_ZONE",
    "State After": "ABOVE_BUY_ZONE",
    "Classification": "PRIME_WAITLIST",
    "TR Qualified": True,
    "Buy Zone": False,
    "Uptrend Weeks": 44,
    "Weekly Candle Count": 80,
    "Closes Above EMA": 42,
    "Closes Below EMA": 2,
}

# --- 2019-05-17 weekly ---
R17_WEEKLY = {
    **_DAILY_BASE,
    "Date": "2019-05-17",
    "Timeframe": "weekly",
    "Candle Color": "GREEN",
    "Open": 364.93,
    "High": 377.06,
    "Low": 358.4,
    "Close": 372.79,
    "Volume": 260310,
    "EMA21": 353.08,
    "EMA34": None,
    "EMA55": None,
    "is_buyzone": True,
    "is_above_buyzone": True,
    "is_downtrend_trigger": False,
    "warmup_complete": True,
    "State Before": "ABOVE_BUY_ZONE",
    "State After": "BUY_ZONE",
    "Classification": "PRIME",
    "TR Qualified": True,
    "Buy Zone": True,
    "Uptrend Weeks": 45,
    "Weekly Candle Count": 81,
    "Closes Above EMA": 43,
    "Closes Below EMA": 2,
    "Signal Count": 1,
    "Signal Types": "REENTRY",
    "Signal Reasons": "TR-qualified stock re-entered the buy zone",
    "Signal Metadata": (
        '[{"reason": "TR-qualified stock re-entered the buy zone",'
        ' "timeframe": "weekly", "state": "BUY_ZONE",'
        ' "candle_count": 459, "weekly_candle_count": 81,'
        ' "uptrend_weeks": 45, "tr_qualified": true,'
        ' "is_buyzone": true, "is_crossover_detected": true,'
        ' "trend_start_date": "2018-07-06T00:00:00+05:30",'
        ' "first_buy_zone_date": "2018-07-06T00:00:00+05:30",'
        ' "daily_ema21_cross_date": "2018-07-06T00:00:00+05:30",'
        ' "open": 364.93, "high": 377.06, "low": 358.4,'
        ' "close": 372.79, "volume": 260310,'
        ' "ema21": 353.08}]'
    ),
}

# --- 2019-05-20 Monday daily ---
R20_DAILY = {
    **_DAILY_BASE,
    "Date": "2019-05-20",
    "Timeframe": "daily",
    "Candle Color": "GREEN",
    "Open": 377.06,
    "High": 381.33,
    "Low": 368.56,
    "Close": 380.1,
    "Volume": 46984,
    "EMA21": None,
    "EMA34": 367.98,
    "EMA55": 363.84,
    "is_buyzone": False,
    "is_above_buyzone": False,
    "is_downtrend_trigger": False,
    "warmup_complete": True,
    "State Before": "BUY_ZONE",
    "State After": "BUY_ZONE",
    "Classification": "PRIME_WAITLIST",
    "TR Qualified": True,
    "Buy Zone": False,
    "Uptrend Weeks": 45,
    "Weekly Candle Count": 81,
    "Closes Above EMA": 43,
    "Closes Below EMA": 2,
}

# --- 2019-05-21 Tuesday daily ---
R21_DAILY = {
    **_DAILY_BASE,
    "Date": "2019-05-21",
    "Timeframe": "daily",
    "Candle Color": "RED",
    "Open": 378.78,
    "High": 380.49,
    "Low": 363.36,
    "Close": 376.86,
    "Volume": 46194,
    "EMA21": None,
    "EMA34": 368.48,
    "EMA55": 364.3,
    "is_buyzone": False,
    "is_above_buyzone": False,
    "is_downtrend_trigger": False,
    "warmup_complete": True,
    "State Before": "BUY_ZONE",
    "State After": "BUY_ZONE",
    "Classification": "PRIME_WAITLIST",
    "TR Qualified": True,
    "Buy Zone": False,
    "Uptrend Weeks": 45,
    "Weekly Candle Count": 81,
    "Closes Above EMA": 43,
    "Closes Below EMA": 2,
}

# --- 2019-05-22 Wednesday daily ---
R22_DAILY = {
    **_DAILY_BASE,
    "Date": "2019-05-22",
    "Timeframe": "daily",
    "Candle Color": "RED",
    "Open": 378.04,
    "High": 378.04,
    "Low": 371.21,
    "Close": 372.93,
    "Volume": 68428,
    "EMA21": None,
    "EMA34": 368.74,
    "EMA55": 364.61,
    "is_buyzone": False,
    "is_above_buyzone": False,
    "is_downtrend_trigger": False,
    "warmup_complete": True,
    "State Before": "BUY_ZONE",
    "State After": "BUY_ZONE",
    "Classification": "PRIME_WAITLIST",
    "TR Qualified": True,
    "Buy Zone": False,
    "Uptrend Weeks": 45,
    "Weekly Candle Count": 81,
    "Closes Above EMA": 43,
    "Closes Below EMA": 2,
}

# --- 2019-05-23 Thursday daily ---
R23_DAILY = {
    **_DAILY_BASE,
    "Date": "2019-05-23",
    "Timeframe": "daily",
    "Candle Color": "RED",
    "Open": 375.0,
    "High": 380.0,
    "Low": 365.27,
    "Close": 371.21,
    "Volume": 43279,
    "EMA21": None,
    "EMA34": 368.88,
    "EMA55": 364.85,
    "is_buyzone": False,
    "is_above_buyzone": False,
    "is_downtrend_trigger": False,
    "warmup_complete": True,
    "State Before": "BUY_ZONE",
    "State After": "BUY_ZONE",
    "Classification": "PRIME_WAITLIST",
    "TR Qualified": True,
    "Buy Zone": False,
    "Uptrend Weeks": 45,
    "Weekly Candle Count": 81,
    "Closes Above EMA": 43,
    "Closes Below EMA": 2,
}

# --- 2019-05-24 Friday daily ---
R24_DAILY = {
    **_DAILY_BASE,
    "Date": "2019-05-24",
    "Timeframe": "daily",
    "Candle Color": "GREEN",
    "Open": 377.16,
    "High": 395.66,
    "Low": 372.98,
    "Close": 391.64,
    "Volume": 76209,
    "EMA21": None,
    "EMA34": 370.18,
    "EMA55": 365.8,
    "is_buyzone": False,
    "is_above_buyzone": False,
    "is_downtrend_trigger": False,
    "warmup_complete": True,
    "State Before": "BUY_ZONE",
    "State After": "BUY_ZONE",
    "Classification": "PRIME_WAITLIST",
    "TR Qualified": True,
    "Buy Zone": False,
    "Uptrend Weeks": 45,
    "Weekly Candle Count": 81,
    "Closes Above EMA": 43,
    "Closes Below EMA": 2,
}

# --- 2019-05-24 weekly ---
R24_WEEKLY = {
    **_DAILY_BASE,
    "Date": "2019-05-24",
    "Timeframe": "weekly",
    "Candle Color": "GREEN",
    "Open": 377.06,
    "High": 395.66,
    "Low": 363.36,
    "Close": 391.64,
    "Volume": 281094,
    "EMA21": 356.59,
    "EMA34": None,
    "EMA55": None,
    "is_buyzone": False,
    "is_above_buyzone": True,
    "is_downtrend_trigger": False,
    "warmup_complete": True,
    "State Before": "BUY_ZONE",
    "State After": "ABOVE_BUY_ZONE",
    "Classification": "PRIME_WAITLIST",
    "TR Qualified": True,
    "Buy Zone": False,
    "Uptrend Weeks": 46,
    "Weekly Candle Count": 82,
    "Closes Above EMA": 44,
    "Closes Below EMA": 2,
}

# Map of date → list of rows (daily first, weekly second when same date)
WEEK_ROWS: dict[str, list[dict]] = {
    "2019-05-13": [R13_DAILY],
    "2019-05-14": [R14_DAILY],
    "2019-05-15": [R15_DAILY],
    "2019-05-16": [R16_DAILY],
    "2019-05-17": [R17_DAILY, R17_WEEKLY],
    "2019-05-20": [R20_DAILY],
    "2019-05-21": [R21_DAILY],
    "2019-05-22": [R22_DAILY],
    "2019-05-23": [R23_DAILY],
    "2019-05-24": [R24_DAILY, R24_WEEKLY],
}

WEEK_END = "2019-05-24"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dict_to_row(d: dict) -> pd.Series:
    """Convert a raw dict to a pd.Series suitable for FSM processing."""
    idx = pd.Timestamp(d["Date"])
    s = pd.Series(d, name=idx)
    s["timeframe"] = s["Timeframe"].lower()
    return s


def _build_test_frame(daily_last: str, weekly_last: str | None = None) -> pd.DataFrame:
    """Build a DataFrame with base history plus selected test-week rows.

    Parameters
    ----------
    daily_last : str
        Last date for which daily rows are included (inclusive).
    weekly_last : str or None
        Last date for which weekly rows are included (inclusive).
        Use *None* when no weekly candle from the test week should be
        present (e.g. Friday open before the weekly candle exists).

    Base history (rows before 2019-05-13) is loaded from the fixture CSV.
    Test-week rows come from the inline :data:`WEEK_ROWS` dict.
    """
    base = pd.read_csv(DEBUG_CSV)
    base["Date"] = pd.to_datetime(base["Date"])

    # Keep only rows strictly before the test week
    before = base[base["Date"] < "2019-05-13"].copy()
    before["timeframe"] = before["Timeframe"].str.lower()

    order = {"daily": 0, "weekly": 1}
    before["_order"] = before["timeframe"].map(order)
    before = before.sort_values(["Date", "_order"], kind="stable").drop(columns=["_order"])
    before = before.set_index("Date")

    # Append selected week rows
    extra: list[pd.Series] = []
    for date_str, rows in WEEK_ROWS.items():
        if date_str > daily_last:
            break
        for r in rows:
            if r["Timeframe"] == "daily":
                extra.append(_dict_to_row(r))
            elif r["Timeframe"] == "weekly" and weekly_last is not None:
                if date_str <= weekly_last:
                    extra.append(_dict_to_row(r))

    if extra:
        extras = pd.DataFrame(extra)
        extras.index.name = "Date"
        result = pd.concat([before, extras])
    else:
        result = before

    return result


def feed_rows(fsm: StockFSM, frame: pd.DataFrame) -> None:
    """Feed all candles in the frame through the FSM."""
    for _idx, row in frame.iterrows():
        if row["timeframe"] == "weekly":
            fsm.process_weekly_candle(row)
        else:
            fsm.process_daily_candle(row)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWeeklyScanScenarios:
    """Verify FSM state after scans at different days of the week."""

    @pytest.fixture
    def config(self) -> TrendRiderConfig:
        return TrendRiderConfig()

    def test_sunday_scan_includes_weekly_candle(self, config: TrendRiderConfig) -> None:
        """
        GIVEN a scan performed on a Sunday
        WHEN the previous week's data (daily + weekly candle) is available
        THEN the weekly candle is processed and the FSM reaches the expected state.
        """
        frame = _build_test_frame(daily_last="2019-05-17", weekly_last="2019-05-17")
        fsm = StockFSM("TIINDIA.NS", config)
        feed_rows(fsm, frame)

        assert fsm.context.last_update == pd.Timestamp("2019-05-17")
        assert fsm.context.last_ema21 == pytest.approx(353.08, rel=1e-4)
        assert fsm.state == "BUY_ZONE"
        assert fsm.context.weekly_candle_count == 81
        assert fsm.context.uptrend_weeks == 45
        assert fsm.context.is_buyzone is True

    def test_monday_morning_processes_same_as_sunday(self, config: TrendRiderConfig) -> None:
        """
        GIVEN a scan on Monday morning before any Monday trading data
        WHEN only the prior week's data is available
        THEN the result is identical to a Sunday scan.
        """
        frame = _build_test_frame(daily_last="2019-05-17", weekly_last="2019-05-17")
        fsm = StockFSM("TIINDIA.NS", config)
        feed_rows(fsm, frame)

        assert fsm.context.last_update == pd.Timestamp("2019-05-17")
        assert fsm.state == "BUY_ZONE"
        assert fsm.context.weekly_candle_count == 81

    def test_monday_after_close_includes_monday_data(self, config: TrendRiderConfig) -> None:
        """
        GIVEN a scan after Monday's market close
        WHEN Monday's daily candle is included
        THEN the FSM processes it and remains in the correct state.
        """
        frame = _build_test_frame(daily_last="2019-05-20", weekly_last="2019-05-17")
        fsm = StockFSM("TIINDIA.NS", config)
        feed_rows(fsm, frame)

        assert fsm.context.last_update == pd.Timestamp("2019-05-20")
        assert fsm.context.last_close == pytest.approx(380.1, rel=1e-4)
        assert fsm.state == "BUY_ZONE"
        assert fsm.context.weekly_candle_count == 81  # No new weekly yet

    def test_friday_open_processes_until_thursday(self, config: TrendRiderConfig) -> None:
        """
        GIVEN a scan on Friday morning before the market opens
        WHEN only Mon–Thu daily data is available (no Friday daily, no weekly)
        THEN the FSM state reflects the data ending Thursday.
        """
        frame = _build_test_frame(daily_last="2019-05-23", weekly_last="2019-05-17")
        fsm = StockFSM("TIINDIA.NS", config)
        feed_rows(fsm, frame)

        assert fsm.context.last_update == pd.Timestamp("2019-05-23")
        assert fsm.state == "BUY_ZONE"
        assert fsm.context.weekly_candle_count == 81  # No new weekly created yet

    def test_friday_after_close_processes_completed_week(self, config: TrendRiderConfig) -> None:
        """
        GIVEN a scan on Friday after market close
        WHEN the full week's daily data AND the weekly candle are included
        THEN the weekly candle transitions the state to ABOVE_BUY_ZONE.
        """
        frame = _build_test_frame(daily_last="2019-05-24", weekly_last="2019-05-24")
        fsm = StockFSM("TIINDIA.NS", config)
        feed_rows(fsm, frame)

        assert fsm.context.last_update == pd.Timestamp("2019-05-24")
        assert fsm.context.last_ema21 == pytest.approx(356.59, rel=1e-4)
        assert fsm.state == "ABOVE_BUY_ZONE"
        assert fsm.context.weekly_candle_count == 82
        assert fsm.context.uptrend_weeks == 46
        assert fsm.is_above_buyzone() is True
        assert fsm.context.is_buyzone is False
