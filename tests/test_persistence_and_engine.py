"""
Tests for persistence round-trips and incremental engine restoration.
"""
from datetime import datetime

import pandas as pd

from trend_rider_lib import (
    Classification,
    ExitReason,
    SignalEvent,
    SignalType,
    State,
    StockContext,
    TradeRecord,
    TradeStatus,
    TrendRiderConfig,
    TrendRiderEngine,
)
from trend_rider_lib.persistence import SQLiteProvider


def test_signal_and_trade_enum_round_trip(tmp_path):
    db_path = tmp_path / "trend_rider.sqlite"
    provider = SQLiteProvider(str(db_path))

    signal = SignalEvent(
        ticker="TEST",
        signal_type=SignalType.BUY_ENTRY,
        date=datetime(2024, 1, 1),
        close_price=100.0,
        ema21=99.0,
        ema34=98.0,
        ema55=97.0,
    )
    provider.save_signal(signal)

    loaded_signal = provider.get_latest_signal("TEST")
    assert loaded_signal is not None
    assert loaded_signal.signal_type == SignalType.BUY_ENTRY

    trade = TradeRecord(
        id=1,
        ticker="TEST",
        entry_date=datetime(2024, 1, 1),
        entry_price=100.0,
        exit_date=datetime(2024, 1, 2),
        exit_price=110.0,
        target_price=150.0,
        initial_sl=90.0,
        current_sl=100.0,
        highest_price_seen=110.0,
        tsl_step_pct=0.10,
        status=TradeStatus.CLOSED_TSL,
        exit_reason=ExitReason.TRAILING_STOP,
        profit_loss_pct=10.0,
    )
    provider.save_trade(trade)

    loaded_trade = provider.get_trade_by_id(1)
    assert loaded_trade is not None
    assert loaded_trade.exit_reason == ExitReason.TRAILING_STOP


def test_incremental_update_restores_open_trades(tmp_path):
    db_path = tmp_path / "trend_rider.sqlite"
    provider = SQLiteProvider(str(db_path))
    config = TrendRiderConfig()
    engine = TrendRiderEngine(config, provider, provider, provider)

    context = StockContext(
        ticker="TEST",
        current_state=State.BUY_ZONE,
        tr_qualified=False,
        last_ema21=100.0,
        last_update=datetime(2024, 1, 1),
        classification=Classification.UNQUALIFIED,
    )
    provider.save_context(context)

    provider.save_trade(
        TradeRecord(
            id=7,
            ticker="TEST",
            entry_date=datetime(2024, 1, 1),
            entry_price=100.0,
            exit_date=None,
            exit_price=None,
            target_price=150.0,
            initial_sl=90.0,
            current_sl=90.0,
            highest_price_seen=100.0,
            tsl_step_pct=0.10,
            status=TradeStatus.OPEN,
            exit_reason=None,
            profit_loss_pct=0.0,
        )
    )

    update_frame = pd.DataFrame(
        [
            {
                "Open": 149.0,
                "High": 151.0,
                "Low": 148.0,
                "Close": 150.0,
                "Volume": 1_000_000,
                "timeframe": "weekly",
            }
        ],
        index=[datetime(2024, 1, 8)],
    )

    results = engine.run_incremental_update(["TEST"], {"TEST": update_frame})

    assert "TEST" in results
    closed_trade = provider.get_trade_by_id(7)
    assert closed_trade is not None
    assert closed_trade.status == TradeStatus.CLOSED_TARGET
    assert engine.trade_manager.trade_id_counter >= 7
