"""
Tests for core model serialization (to_dict / from_dict roundtrips).
"""
from datetime import datetime
import json
import tempfile
import os

import pytest

from trend_rider_lib.core.enums import (
    Classification,
    State,
    UptrendStrength,
)
from trend_rider_lib.core.models import (
    StockContext,
    UptrendRecord,
    context_from_dict,
)


# ──────────────────────────────────────────────
# Helper
# ──────────────────────────────────────────────

def _json_roundtrip(d: dict) -> dict:
    """Simulate full persistence by JSON-serialising then loading."""
    return json.loads(json.dumps(d, default=str))


# ──────────────────────────────────────────────
# StockContext — basic fields
# ──────────────────────────────────────────────

def test_stock_context_basic_roundtrip():
    """Basic constructor fields roundtrip correctly."""
    original = StockContext(ticker="AAPL", tr_qualified=True, is_buyzone=True)
    d = original.to_dict()
    restored = StockContext.from_dict(d)

    assert restored.ticker == "AAPL"
    assert restored.tr_qualified is True
    assert restored.is_buyzone is True
    assert restored.uptrend_weeks == 0
    assert restored.warmup_complete is False
    assert restored.candle_count == 0


def test_stock_context_default_values():
    """A default-constructed context roundtrips without error."""
    original = StockContext(ticker="TEST")
    d = original.to_dict()
    restored = StockContext.from_dict(d)

    assert restored.ticker == "TEST"
    assert restored.tr_qualified is False
    assert restored.is_buyzone is False
    assert restored.current_state is None
    assert restored.classification is None
    assert restored.current_uptrend is None
    assert restored.uptrend_history == []


# ──────────────────────────────────────────────
# StockContext — enums
# ──────────────────────────────────────────────

def test_stock_context_with_state_enum():
    """current_state as a State enum serialises and restores correctly."""
    original = StockContext(ticker="MSFT", current_state=State.UPTREND)
    d = original.to_dict()
    assert isinstance(d["current_state"], str)
    assert d["current_state"] == "UPTREND"

    restored = StockContext.from_dict(d)
    # current_state is stored as string in StockContext (not State enum)
    assert restored.current_state == "UPTREND"


# ──────────────────────────────────────────────
# StockContext — uptrend_substate
# ──────────────────────────────────────────────

def test_stock_context_uptrend_substate_roundtrip():
    """uptrend_substate serialises and restores correctly via to_dict/from_dict."""
    original = StockContext(ticker="AAPL")
    original.uptrend_substate = "BUY_ZONE"

    d = original.to_dict()
    assert d["uptrend_substate"] == "BUY_ZONE"

    restored = StockContext.from_dict(d)
    assert restored.uptrend_substate == "BUY_ZONE"


def test_stock_context_uptrend_substate_none():
    """None uptrend_substate survives roundtrip."""
    original = StockContext(ticker="TEST")
    original.uptrend_substate = None

    d = original.to_dict()
    assert d["uptrend_substate"] is None

    restored = StockContext.from_dict(d)
    assert restored.uptrend_substate is None


def test_stock_context_uptrend_substate_not_in_buy_zone():
    """NOT_IN_BUY_ZONE substate roundtrips correctly."""
    original = StockContext(ticker="GOOGL")
    original.uptrend_substate = "NOT_IN_BUY_ZONE"

    d = original.to_dict()
    assert d["uptrend_substate"] == "NOT_IN_BUY_ZONE"

    restored = StockContext.from_dict(d)
    assert restored.uptrend_substate == "NOT_IN_BUY_ZONE"


def test_stock_context_uptrend_substate_json_roundtrip():
    """uptrend_substate survives full JSON serialisation roundtrip."""
    import json
    original = StockContext(ticker="MSFT")
    original.uptrend_substate = "BUY_ZONE"

    d = original.to_dict()
    json_str = json.dumps(d, default=str)
    d2 = json.loads(json_str)
    restored = StockContext.from_dict(d2)

    assert restored.uptrend_substate == "BUY_ZONE"


def test_stock_context_uptrend_substate_direct():
    """uptrend_substate can be set and read directly (no dict)."""
    ctx = StockContext(ticker="TEST")
    assert ctx.uptrend_substate is None

    ctx.uptrend_substate = "BUY_ZONE"
    assert ctx.uptrend_substate == "BUY_ZONE"

    ctx.uptrend_substate = "NOT_IN_BUY_ZONE"
    assert ctx.uptrend_substate == "NOT_IN_BUY_ZONE"

    ctx.uptrend_substate = None
    assert ctx.uptrend_substate is None


def test_stock_context_with_classification_enum():
    """Classification enum roundtrips correctly."""
    original = StockContext(ticker="GOOGL")
    original.classification = Classification.PRIME

    d = original.to_dict()
    assert d["classification"] == "PRIME"

    restored = StockContext.from_dict(d)
    assert restored.classification == Classification.PRIME


def test_stock_context_with_classification_none():
    """None classification survives roundtrip."""
    original = StockContext(ticker="TEST")
    original.classification = None
    d = original.to_dict()
    assert d["classification"] is None
    restored = StockContext.from_dict(d)
    assert restored.classification is None


# ──────────────────────────────────────────────
# StockContext — datetime fields
# ──────────────────────────────────────────────

def test_stock_context_with_datetimes():
    """Datetime fields serialise to ISO strings and restore to datetimes."""
    original = StockContext(ticker="AMZN")
    dt = datetime(2025, 6, 15, 10, 30, 0)
    original.last_update = dt
    original.last_buy_signal_date = dt
    original.uptrend_start_date = dt

    d = original.to_dict()
    assert d["last_update"] == "2025-06-15T10:30:00"
    assert d["last_buy_signal_date"] == "2025-06-15T10:30:00"
    assert d["uptrend_start_date"] == "2025-06-15T10:30:00"

    restored = StockContext.from_dict(d)
    assert restored.last_update == dt
    assert restored.last_buy_signal_date == dt
    assert restored.uptrend_start_date == dt


def test_stock_context_with_datetime_none():
    """None datetime fields survive roundtrip."""
    original = StockContext(ticker="TEST")
    original.last_update = None
    d = original.to_dict()
    assert d["last_update"] is None
    restored = StockContext.from_dict(d)
    assert restored.last_update is None


# ──────────────────────────────────────────────
# StockContext — numeric extra fields
# ──────────────────────────────────────────────

def test_stock_context_extra_numeric_fields():
    """Extra numeric fields like daily_ema21_cross_price roundtrip."""
    original = StockContext(ticker="NVDA")
    original.daily_ema21_cross_price = 150.25
    original.daily_downtrend_trigger_price = 140.00
    original.first_buy_zone_price = 145.50
    original.positive_crossover_price = 148.00
    original.last_close = 152.10
    original.trend_cycle_id = 42

    d = original.to_dict()
    restored = StockContext.from_dict(d)

    assert restored.daily_ema21_cross_price == 150.25
    assert restored.daily_downtrend_trigger_price == 140.00
    assert restored.first_buy_zone_price == 145.50
    assert restored.positive_crossover_price == 148.00
    assert restored.last_close == 152.10
    assert restored.trend_cycle_id == 42


def test_stock_context_extra_bool_fields():
    """Boolean extra fields roundtrip."""
    original = StockContext(ticker="AMD")
    original.buy_signal_emitted = True
    original.warmup_complete = True

    d = original.to_dict()
    restored = StockContext.from_dict(d)

    assert restored.buy_signal_emitted is True
    assert restored.warmup_complete is True


# ──────────────────────────────────────────────
# StockContext — current_uptrend
# ──────────────────────────────────────────────

def test_stock_context_with_current_uptrend():
    """A populated current_uptrend (UptrendRecord) roundtrips."""
    original = StockContext(ticker="TSLA")
    rec = UptrendRecord(start_date=datetime(2025, 1, 10))
    rec.cycle_id = 1
    rec.start_state = "UPTREND"
    rec.start_price = 200.0
    rec.num_weeks = 8
    rec.closes_above_ema = 6
    rec.closes_below_ema = 2
    rec.pct_closes_above = 0.75
    rec.strength = UptrendStrength.DEVELOPING
    rec.highest_price = 250.0
    rec.highest_price_date = datetime(2025, 3, 1)
    original.current_uptrend = rec

    d = original.to_dict()
    restored = StockContext.from_dict(d)

    assert restored.current_uptrend is not None
    r = restored.current_uptrend
    assert r.start_date == datetime(2025, 1, 10)
    assert r.cycle_id == 1
    assert r.start_state == "UPTREND"
    assert r.start_price == 200.0
    assert r.num_weeks == 8
    assert r.closes_above_ema == 6
    assert r.closes_below_ema == 2
    assert r.pct_closes_above == 0.75
    assert r.strength == UptrendStrength.DEVELOPING
    assert r.highest_price == 250.0
    assert r.highest_price_date == datetime(2025, 3, 1)


def test_stock_context_with_current_uptrend_none():
    """None current_uptrend survives roundtrip."""
    original = StockContext(ticker="TEST")
    original.current_uptrend = None
    d = original.to_dict()
    assert d["current_uptrend"] is None
    restored = StockContext.from_dict(d)
    assert restored.current_uptrend is None


# ──────────────────────────────────────────────
# StockContext — uptrend_history
# ──────────────────────────────────────────────

def test_stock_context_with_uptrend_history():
    """List of UptrendRecord roundtrips correctly."""
    original = StockContext(ticker="META")

    rec1 = UptrendRecord(start_date=datetime(2025, 1, 10))
    rec1.cycle_id = 1
    rec1.start_price = 300.0
    rec1.num_weeks = 5
    rec1.strength = UptrendStrength.MODERATE

    rec2 = UptrendRecord(start_date=datetime(2025, 3, 15))
    rec2.cycle_id = 2
    rec2.start_price = 350.0
    rec2.num_weeks = 10
    rec2.strength = UptrendStrength.STRONG
    rec2.end_date = datetime(2025, 5, 20)

    original.uptrend_history = [rec1, rec2]

    d = original.to_dict()
    restored = StockContext.from_dict(d)

    assert len(restored.uptrend_history) == 2

    r1 = restored.uptrend_history[0]
    assert r1.start_date == datetime(2025, 1, 10)
    assert r1.cycle_id == 1
    assert r1.start_price == 300.0
    assert r1.num_weeks == 5
    assert r1.strength == UptrendStrength.MODERATE

    r2 = restored.uptrend_history[1]
    assert r2.start_date == datetime(2025, 3, 15)
    assert r2.cycle_id == 2
    assert r2.start_price == 350.0
    assert r2.num_weeks == 10
    assert r2.strength == UptrendStrength.STRONG
    assert r2.end_date == datetime(2025, 5, 20)


def test_stock_context_empty_uptrend_history():
    """Empty uptrend_history survives roundtrip."""
    original = StockContext(ticker="TEST")
    original.uptrend_history = []
    d = original.to_dict()
    restored = StockContext.from_dict(d)
    assert restored.uptrend_history == []


# ──────────────────────────────────────────────
# Full JSON persistence roundtrip
# ──────────────────────────────────────────────

def test_full_json_persistence_roundtrip():
    """Serialize to dict → JSON dump → JSON load → from_dict preserves all."""
    original = StockContext(
        ticker="NFLX",
        current_state=State.UPTREND,
        last_ema21=500.0,
        last_ema34=490.0,
        last_ema55=480.0,
        tr_qualified=True,
        is_buyzone=False,
        uptrend_weeks=12,
        closes_above_ema=9,
        closes_below_ema=3,
        is_crossover_detected=True,
        longName="Netflix Inc",
        sector="Technology",
        industry="Entertainment",
        marketCap=200_000_000_000,
    )
    original.classification = Classification.PRIME
    original.last_update = datetime(2025, 6, 20, 14, 30, 0)
    original.last_buy_signal_date = datetime(2025, 6, 15, 9, 45, 0)
    original.uptrend_start_date = datetime(2025, 3, 1)
    original.last_close = 520.0
    original.buy_signal_emitted = True
    original.warmup_complete = True
    original.candle_count = 250
    original.trend_cycle_id = 7

    rec = UptrendRecord(start_date=datetime(2025, 3, 1))
    rec.cycle_id = 7
    rec.start_state = "UPTREND"
    rec.start_price = 450.0
    rec.num_weeks = 16
    rec.closes_above_ema = 13
    rec.closes_below_ema = 3
    rec.pct_closes_above = 0.8125
    rec.strength = UptrendStrength.MODERATE
    rec.highest_price = 550.0
    rec.highest_price_date = datetime(2025, 6, 10)
    original.current_uptrend = rec

    # Serialise → JSON → deserialise
    d = original.to_dict()
    json_str = json.dumps(d, default=str)
    d2 = json.loads(json_str)
    restored = StockContext.from_dict(d2)

    # Assert all constructor fields
    assert restored.ticker == "NFLX"
    assert restored.current_state == "UPTREND"
    assert restored.last_ema21 == 500.0
    assert restored.last_ema34 == 490.0
    assert restored.last_ema55 == 480.0
    assert restored.tr_qualified is True
    assert restored.is_buyzone is False
    assert restored.uptrend_weeks == 12
    assert restored.closes_above_ema == 9
    assert restored.closes_below_ema == 3
    assert restored.is_crossover_detected is True
    assert restored.longName == "Netflix Inc"
    assert restored.sector == "Technology"
    assert restored.industry == "Entertainment"
    assert restored.marketCap == 200_000_000_000

    # Assert classification
    assert restored.classification == Classification.PRIME

    # Assert datetimes
    assert restored.last_update == datetime(2025, 6, 20, 14, 30, 0)
    assert restored.last_buy_signal_date == datetime(2025, 6, 15, 9, 45, 0)
    assert restored.uptrend_start_date == datetime(2025, 3, 1)

    # Assert extra fields
    assert restored.last_close == 520.0
    assert restored.buy_signal_emitted is True
    assert restored.warmup_complete is True
    assert restored.candle_count == 250
    assert restored.trend_cycle_id == 7

    # Assert current_uptrend
    assert restored.current_uptrend is not None
    r = restored.current_uptrend
    assert r.start_date == datetime(2025, 3, 1)
    assert r.cycle_id == 7
    assert r.start_state == "UPTREND"
    assert r.start_price == 450.0
    assert r.num_weeks == 16
    assert r.closes_above_ema == 13
    assert r.closes_below_ema == 3
    assert r.pct_closes_above == 0.8125
    assert r.strength == UptrendStrength.MODERATE
    assert r.highest_price == 550.0
    assert r.highest_price_date == datetime(2025, 6, 10)


# ──────────────────────────────────────────────
# Backward compatibility
# ──────────────────────────────────────────────

def test_context_from_dict_backward_compat_state_prefix():
    """context_from_dict handles legacy 'State.DOWNTREND' prefix."""
    d = {
        "ticker": "LEGACY",
        "current_state": "State.DOWNTREND",
    }
    ctx = context_from_dict(d)
    assert ctx.current_state == "DOWNTREND"


def test_stock_context_from_dict_backward_compat_state_prefix():
    """StockContext.from_dict handles legacy 'State.DOWNTREND' prefix."""
    d = {
        "ticker": "LEGACY",
        "current_state": "State.DOWNTREND",
    }
    ctx = StockContext.from_dict(d)
    assert ctx.current_state == "DOWNTREND"


# ──────────────────────────────────────────────
# context_from_dict delegates to StockContext.from_dict
# ──────────────────────────────────────────────

def test_context_from_dict_delegates():
    """Standalone context_from_dict produces the same result."""
    d = {
        "ticker": "DELEGATE",
        "tr_qualified": True,
        "is_buyzone": True,
        "classification": "MOMENTUM",
    }
    direct = StockContext.from_dict(d)
    delegated = context_from_dict(d)
    assert delegated.ticker == direct.ticker
    assert delegated.tr_qualified == direct.tr_qualified
    assert delegated.is_buyzone == direct.is_buyzone
    assert delegated.classification == direct.classification


# ──────────────────────────────────────────────
# UptrendRecord — full roundtrip
# ──────────────────────────────────────────────

def test_uptrend_record_roundtrip():
    """UptrendRecord with all fields populated roundtrips via JSON."""
    original = UptrendRecord(start_date=datetime(2025, 1, 5))
    original.end_date = datetime(2025, 6, 10)
    original.cycle_id = 3
    original.start_state = "BUY_ZONE"
    original.end_state = "DOWNTREND"
    original.start_price = 100.0
    original.end_price = 180.0
    original.first_buy_zone_date = datetime(2025, 1, 10)
    original.first_buy_zone_price = 105.0
    original.daily_ema21_cross_date = datetime(2025, 2, 1)
    original.daily_ema21_cross_price = 120.0
    original.daily_downtrend_trigger_date = datetime(2025, 5, 25)
    original.daily_downtrend_trigger_price = 170.0
    original.num_weeks = 22
    original.closes_above_ema = 18
    original.closes_below_ema = 4
    original.pct_closes_above = 0.818
    original.strength = UptrendStrength.MODERATE
    original.highest_price = 200.0
    original.highest_price_date = datetime(2025, 5, 15)
    original.lowest_price = 95.0
    original.lowest_price_date = datetime(2025, 1, 7)
    original.roc_1w_pct = 5.2
    original.roc_3w_pct = 12.8
    original.roc_6m_pct = 45.0
    original.roc_9m_pct = 60.0
    original.max_profit_pct = 80.0
    original.trend_roc_pct = 55.0
    original.ema21_slope = 0.35
    original.ema34_55_spread = 8.5
    original.ema34_55_spread_pct = 4.2
    original.efficiency_ratio = 0.72
    original.ath_price = 250.0
    original.ath_date = datetime(2024, 12, 1)
    original.distance_from_ath_abs = 50.0
    original.distance_from_ath_pct = 20.0

    d = original.to_dict()
    d2 = json.loads(json.dumps(d, default=str))
    restored = UptrendRecord.from_dict(d2)

    assert restored.start_date == datetime(2025, 1, 5)
    assert restored.end_date == datetime(2025, 6, 10)
    assert restored.cycle_id == 3
    assert restored.start_state == "BUY_ZONE"
    assert restored.end_state == "DOWNTREND"
    assert restored.start_price == 100.0
    assert restored.end_price == 180.0
    assert restored.first_buy_zone_date == datetime(2025, 1, 10)
    assert restored.first_buy_zone_price == 105.0
    assert restored.daily_ema21_cross_date == datetime(2025, 2, 1)
    assert restored.daily_ema21_cross_price == 120.0
    assert restored.daily_downtrend_trigger_date == datetime(2025, 5, 25)
    assert restored.daily_downtrend_trigger_price == 170.0
    assert restored.num_weeks == 22
    assert restored.closes_above_ema == 18
    assert restored.closes_below_ema == 4
    assert restored.pct_closes_above == 0.818
    assert restored.strength == UptrendStrength.MODERATE
    assert restored.highest_price == 200.0
    assert restored.highest_price_date == datetime(2025, 5, 15)
    assert restored.lowest_price == 95.0
    assert restored.lowest_price_date == datetime(2025, 1, 7)
    assert restored.roc_1w_pct == 5.2
    assert restored.roc_3w_pct == 12.8
    assert restored.roc_6m_pct == 45.0
    assert restored.roc_9m_pct == 60.0
    assert restored.max_profit_pct == 80.0
    assert restored.trend_roc_pct == 55.0
    assert restored.ema21_slope == 0.35
    assert restored.ema34_55_spread == 8.5
    assert restored.ema34_55_spread_pct == 4.2
    assert restored.efficiency_ratio == 0.72
    assert restored.ath_price == 250.0
    assert restored.ath_date == datetime(2024, 12, 1)
    assert restored.distance_from_ath_abs == 50.0
    assert restored.distance_from_ath_pct == 20.0


def test_uptrend_record_strength_none():
    """UptrendRecord with None strength roundtrips."""
    original = UptrendRecord(start_date=datetime(2025, 1, 1))
    original.strength = None
    d = original.to_dict()
    assert d["strength"] is None
    restored = UptrendRecord.from_dict(d)
    assert restored.strength is None


# ──────────────────────────────────────────────
# UptrendRecord — history lists
# ──────────────────────────────────────────────

def test_uptrend_record_daily_ema_history():
    """Daily EMA history lists roundtrip via JSON."""
    original = UptrendRecord(start_date=datetime(2025, 1, 1))
    original.daily_ema21_history = [100.0, 101.5, 103.0]
    original.daily_ema34_history = [98.0, 99.0, 100.0]
    original.daily_ema55_history = [95.0, 96.0, 97.5]

    d = original.to_dict()
    d2 = json.loads(json.dumps(d, default=str))
    restored = UptrendRecord.from_dict(d2)

    assert restored.daily_ema21_history == [100.0, 101.5, 103.0]
    assert restored.daily_ema34_history == [98.0, 99.0, 100.0]
    assert restored.daily_ema55_history == [95.0, 96.0, 97.5]