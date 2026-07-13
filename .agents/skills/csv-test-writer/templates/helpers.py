"""
Reusable helpers and fixtures for FSM scenario tests.

Import these in tests/scenarios/conftest.py and scenario test files.
"""

from pathlib import Path
from typing import Dict, Optional

import pandas as pd
import pytest

from trend_rider_lib import TrendRiderConfig, StockContext, scan_stocks


# ---------------------------------------------------------------------------
# CSV Loading
# ---------------------------------------------------------------------------

def load_raw_ohlcv(ticker: str, timeframe: str, data_dir: Path) -> pd.DataFrame:
    """Load raw OHLCV CSV. Returns DataFrame with Date index and OHLCV columns."""
    path = data_dir / f"{ticker}_{timeframe}_raw.csv"
    df = pd.read_csv(path, parse_dates=["Date"], dayfirst=True)
    df.set_index("Date", inplace=True)
    df.index = df.index.tz_localize(None)
    return df[["Open", "High", "Low", "Close", "Volume"]]


def load_calculated_csv(ticker: str, timeframe: str, data_dir: Path) -> pd.DataFrame:
    """Load pre-calculated StockContext CSV (ISO 8601 date format)."""
    path = data_dir / f"{ticker}_{timeframe}_calculated.csv"
    df = pd.read_csv(path, parse_dates=["Date"])
    return df


# ---------------------------------------------------------------------------
# Context Building
# ---------------------------------------------------------------------------

def build_context_from_range(
    ticker: str,
    raw_df: pd.DataFrame,
    end_date: str,
    config: TrendRiderConfig,
) -> StockContext:
    """Feed raw data from beginning up to end_date via scan_stocks()."""
    data = {ticker: raw_df[raw_df.index <= pd.Timestamp(end_date)]}
    handler = _CaptureHandler()
    results = scan_stocks([ticker], handler, data=data, config=config)
    return results[ticker]


def build_context_from_row(calculated_df: pd.DataFrame, date: str) -> StockContext:
    """Reconstruct StockContext from a calculated CSV row."""
    row = calculated_df[calculated_df["Date"] == pd.Timestamp(date)].iloc[0]
    ctx = StockContext(ticker="TIINDIA")
    ctx.state_before = row.get("State Before", "")
    ctx.state_after = row.get("State After", "")
    ctx.ema21 = row.get("EMA21", 0.0)
    ctx.trend_start = row.get("Trend Start", False)
    ctx.trend_end = row.get("Trend End", False)
    ctx.is_buyzone = row.get("Buy Zone", False)
    ctx.is_above_buyzone = row.get("Above Buy Zone", False)
    ctx.classification = row.get("Classification", "")
    ctx.tr_qualified = row.get("TR Qualified", False)
    ctx.uptrend_weeks = int(row.get("Uptrend Weeks", 0))
    ctx.closes_above_ema = int(row.get("Closes Above EMA", 0))
    ctx.closes_below_ema = int(row.get("Closes Below EMA", 0))
    return ctx


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def assert_context_matches(ctx: StockContext, expected_row: pd.Series) -> None:
    """Assert all StockContext fields match the expected CSV row."""
    checks = {
        "State Before": (ctx.state_before, str),
        "State After": (ctx.state_after, str),
        "EMA21": (ctx.ema21, float),
        "Trend Start": (ctx.trend_start, bool),
        "Trend End": (ctx.trend_end, bool),
        "Buy Zone": (ctx.is_buyzone, bool),
        "Above Buy Zone": (ctx.is_above_buyzone, bool),
        "Classification": (ctx.classification, str),
        "TR Qualified": (ctx.tr_qualified, bool),
        "Uptrend Weeks": (ctx.uptrend_weeks, int),
        "Closes Above EMA": (ctx.closes_above_ema, int),
        "Closes Below EMA": (ctx.closes_below_ema, int),
    }
    for col, (actual, dtype) in checks.items():
        expected = expected_row.get(col)
        if expected is None:
            continue
        if dtype == float:
            assert abs(actual - expected) < 1e-4, (
                f"{col} mismatch: expected {expected}, got {actual}"
            )
        else:
            assert actual == expected, (
                f"{col} mismatch: expected {expected}, got {actual}"
            )


# ---------------------------------------------------------------------------
# Data Preparation
# ---------------------------------------------------------------------------

def filter_to_date(raw_df: pd.DataFrame, end_date: str) -> Dict[str, pd.DataFrame]:
    """Filter raw data up to end_date, keyed by ticker 'TIINDIA'."""
    cutoff = pd.Timestamp(end_date)
    return {"TIINDIA": raw_df[raw_df.index <= cutoff]}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def config() -> TrendRiderConfig:
    return TrendRiderConfig()


@pytest.fixture
def templates_dir() -> Path:
    return (
        Path(__file__).parent.parent.parent
        / ".agents" / "skills" / "csv-test-writer" / "templates"
    )


@pytest.fixture
def raw_weekly(templates_dir: Path) -> pd.DataFrame:
    return load_raw_ohlcv("TIINDIA", "weekly", templates_dir)


@pytest.fixture
def calculated_weekly(templates_dir: Path) -> pd.DataFrame:
    return load_calculated_csv("TIINDIA", "weekly", templates_dir)


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

class _CaptureHandler:
    """Minimal handler to capture scan_stocks() results."""
    def __init__(self):
        self.results = {}

    def handle_result(self, ticker: str, ctx: StockContext) -> None:
        self.results[ticker] = ctx