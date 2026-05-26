"""
Tests for downloader history bounds and reporting format helpers.
"""
from datetime import datetime

import pandas as pd

from trend_rider_lib.core.enums import SignalType
from trend_rider_lib.core.models import SignalEvent
from trend_rider_lib.downloader.yfinance_downloader import YFinanceDownloader
from trend_rider_lib.reporting.export_utils import build_signal_rows, prepare_debug_csv_frame


class _FakeTicker:
    def __init__(self, history_frame: pd.DataFrame):
        self.history_frame = history_frame
        self.calls = []

    def history(self, **kwargs):
        self.calls.append(kwargs)
        return self.history_frame.copy()


def test_download_full_history_uses_max_when_start_missing(monkeypatch):
    history_frame = pd.DataFrame(
        {
            "Open": [1.111, 2.222],
            "High": [1.555, 2.555],
            "Low": [1.0, 2.0],
            "Close": [1.333, 2.333],
            "Volume": [100, 200],
            "Dividends": [0, 0],
            "Stock Splits": [0, 0],
        },
        index=pd.to_datetime(["2024-01-01", "2024-01-03"]),
    )
    fake_ticker = _FakeTicker(history_frame)
    monkeypatch.setattr("trend_rider_lib.downloader.yfinance_downloader.yf.Ticker", lambda ticker: fake_ticker)

    result = YFinanceDownloader.download_full_history("TEST")

    assert fake_ticker.calls == [{"period": "max", "interval": "1d"}]
    assert list(result.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert len(result) == 2


def test_download_full_history_uses_start_and_default_end(monkeypatch):
    history_frame = pd.DataFrame(
        {
            "Open": [1.111],
            "High": [1.555],
            "Low": [1.0],
            "Close": [1.333],
            "Volume": [100],
            "Dividends": [0],
            "Stock Splits": [0],
        },
        index=pd.to_datetime(["2024-01-01"]),
    )
    fake_ticker = _FakeTicker(history_frame)
    monkeypatch.setattr("trend_rider_lib.downloader.yfinance_downloader.yf.Ticker", lambda ticker: fake_ticker)

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls):
            return cls(2024, 5, 24)

    monkeypatch.setattr("trend_rider_lib.downloader.yfinance_downloader.datetime", _FrozenDatetime)

    YFinanceDownloader.download_full_history("TEST", start_date="2024-01-01")

    assert fake_ticker.calls == [
        {"start": "2024-01-01", "end": "2024-05-24", "interval": "1d"}
    ]


def test_download_full_history_applies_end_filter_when_start_missing(monkeypatch):
    history_frame = pd.DataFrame(
        {
            "Open": [1.111, 2.222],
            "High": [1.555, 2.555],
            "Low": [1.0, 2.0],
            "Close": [1.333, 2.333],
            "Volume": [100, 200],
            "Dividends": [0, 0],
            "Stock Splits": [0, 0],
        },
        index=pd.to_datetime(["2024-01-01", "2024-01-03"]),
    )
    fake_ticker = _FakeTicker(history_frame)
    monkeypatch.setattr("trend_rider_lib.downloader.yfinance_downloader.yf.Ticker", lambda ticker: fake_ticker)

    result = YFinanceDownloader.download_full_history("TEST", end_date="2024-01-02")

    assert fake_ticker.calls == [{"period": "max", "interval": "1d"}]
    assert list(result.index) == [pd.Timestamp("2024-01-01")]


def test_prepare_debug_csv_frame_rounds_and_formats_dates():
    frame = pd.DataFrame(
        {
            "Date": [datetime(2024, 1, 1)],
            "Open": [82.51234],
            "Volume": [100],
            "is_buyzone": [True],
        }
    )

    prepared = prepare_debug_csv_frame(frame)

    assert prepared.loc[0, "Date"] == "2024-01-01"
    assert prepared.loc[0, "Open"] == 82.51
    assert prepared.loc[0, "Volume"] == 100.0
    assert bool(prepared.loc[0, "is_buyzone"]) is True


def test_build_signal_rows_includes_reason_and_metadata():
    signal = SignalEvent(
        ticker="TEST",
        signal_type=SignalType.BUY_ENTRY,
        date=datetime(2024, 1, 1),
        close_price=100.1234,
        ema21=99.1234,
        ema34=98.1234,
        ema55=97.1234,
        metadata={
            "reason": "Daily buy entry confirmed above EMA21",
            "timeframe": "daily",
            "state": "BUY_ZONE",
            "open": 99.0,
            "close": 100.1234,
            "candle_count": 26,
        },
    )

    frame = build_signal_rows([signal])

    assert list(frame.columns) == [
        "Date",
        "Ticker",
        "Signal Type",
        "Signal Reason",
        "Candle Color",
        "Timeframe",
        "State",
        "Close",
        "EMA21",
        "EMA34",
        "EMA55",
        "Trend Cycle",
        "Trend Start",
        "Trend End",
        "Supporting Values",
        "Metadata",
    ]
    assert frame.loc[0, "Signal Reason"] == "Daily buy entry confirmed above EMA21"
    assert frame.loc[0, "Candle Color"] == "GREEN"
    assert "candle_count=26" in frame.loc[0, "Supporting Values"]
