"""
SQLite persistence provider implementation.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..core.enums import SignalType, TradeStatus, ExitReason, TrendEventType, UptrendStrength
from ..core.models import SignalEvent, StockContext, TradeRecord, TrendEventRecord, UptrendRecord
from ..state_machine.fsm_serializer import deserialize_context, deserialize_uptrend, serialize_context, serialize_uptrend
from .interfaces import ISignalStore, IStateStore, ITradeStore


logger = logging.getLogger(__name__)


class SQLiteProvider(IStateStore, ISignalStore, ITradeStore):
    """
    SQLite implementation of all persistence interfaces.
    """

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self._init_database()

    def _get_connection(self):
        return sqlite3.connect(self.connection_string)

    def _init_database(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS stock_states (
                    ticker TEXT PRIMARY KEY,
                    current_state TEXT,
                    tr_qualified INTEGER,
                    trend_start_date TEXT,
                    trend_end_date TEXT,
                    daily_ema21_cross_date TEXT,
                    daily_ema21_cross_price REAL,
                    daily_downtrend_trigger_date TEXT,
                    daily_downtrend_trigger_price REAL,
                    first_buy_zone_date TEXT,
                    first_buy_zone_price REAL,
                    trend_cycle_id INTEGER,
                    positive_crossover_date TEXT,
                    positive_crossover_price REAL,
                    buy_signal_emitted INTEGER,
                    last_buy_signal_date TEXT,
                    last_buy_signal_type TEXT,
                    last_buy_signal_crossover_date TEXT,
                    uptrend_start_date TEXT,
                    uptrend_weeks INTEGER,
                    weekly_candle_count INTEGER,
                    closes_above_ema INTEGER,
                    closes_below_ema INTEGER,
                    is_buyzone INTEGER,
                    is_crossover_detected INTEGER,
                    crossover_date TEXT,
                    crossover_price REAL,
                    classification TEXT,
                    last_ema21 REAL,
                    last_ema34 REAL,
                    last_ema55 REAL,
                    last_close REAL,
                    last_updated TEXT,
                    context_json TEXT,
                    longName TEXT,
                    sector TEXT,
                    industry TEXT,
                    marketCap REAL,
                    website TEXT,
                    nextDividendDate TEXT,
                    isin TEXT
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS trend_cycles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    cycle_id INTEGER NOT NULL,
                    trend_start_date TEXT NOT NULL,
                    trend_start_price REAL,
                    trend_end_date TEXT,
             trend_end_price REAL,
             daily_ema21_cross_date TEXT,
             daily_ema21_cross_price REAL,
             daily_downtrend_trigger_date TEXT,
             daily_downtrend_trigger_price REAL,
             first_buy_zone_date TEXT,
                    first_buy_zone_price REAL,
                    start_state TEXT,
                    end_state TEXT,
                    status TEXT,
                    tr_qualified INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(ticker, cycle_id)
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS trend_analytics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    cycle_id INTEGER NOT NULL,
                    as_of_date TEXT,
                    num_weeks INTEGER,
                    closes_above_ema INTEGER,
                    closes_below_ema INTEGER,
                    pct_closes_above REAL,
                    strength TEXT,
                    max_profit_pct REAL,
                    trend_roc_pct REAL,
                    roc_1w_pct REAL,
                    roc_3w_pct REAL,
                    roc_6m_pct REAL,
                    roc_9m_pct REAL,
                    ath_price REAL,
                    ath_date TEXT,
                    distance_from_ath_abs REAL,
                    distance_from_ath_pct REAL,
                    ema21_slope REAL,
                    ema34_55_spread REAL,
                    ema34_55_spread_pct REAL,
                    efficiency_ratio REAL,
                    last_close REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(ticker, cycle_id)
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS trend_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    cycle_id INTEGER,
                    event_type TEXT NOT NULL,
                    event_date TEXT NOT NULL,
                    timeframe TEXT,
                    state TEXT,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume REAL,
                    ema21 REAL,
                    ema34 REAL,
                    ema55 REAL,
                    metadata_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT,
                    signal_type TEXT,
                    date TEXT,
                    close_price REAL,
                    ema21 REAL,
                    ema34 REAL,
                    ema55 REAL,
                    timeframe TEXT,
                    state TEXT,
                    trend_cycle_id INTEGER,
                    trend_start_date TEXT,
                    trend_end_date TEXT,
                    reason TEXT,
                    metadata_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY,
                    ticker TEXT,
                    entry_date TEXT,
                    entry_price REAL,
                    exit_date TEXT,
                    exit_price REAL,
                    target_price REAL,
                    initial_sl REAL,
                    current_sl REAL,
                    highest_price_seen REAL,
                    tsl_step_pct REAL,
                    status TEXT,
                    exit_reason TEXT,
                    profit_loss_pct REAL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            conn.commit()

    # ------------------------------------------------------------------
    # IStateStore
    # ------------------------------------------------------------------
    def save_context(self, context: StockContext) -> None:
        serialized = serialize_context(context)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO stock_states
                (ticker, current_state, tr_qualified, trend_start_date, trend_end_date,
                 daily_ema21_cross_date, daily_ema21_cross_price, first_buy_zone_date,
                 first_buy_zone_price, trend_cycle_id, positive_crossover_date,
                 positive_crossover_price, buy_signal_emitted, last_buy_signal_date,
                 last_buy_signal_type, last_buy_signal_crossover_date, uptrend_start_date,
                 uptrend_weeks, weekly_candle_count, closes_above_ema, closes_below_ema,
                 is_buyzone, is_crossover_detected, crossover_date, crossover_price,
                 classification, last_ema21, last_ema34, last_ema55, last_close,
                 last_updated, context_json, longName, sector, industry, marketCap, website, nextDividendDate, isin)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    context.ticker,
                    serialized["current_state"],
                    int(serialized["tr_qualified"]),
                    serialized["trend_start_date"],
                    serialized["trend_end_date"],
                    serialized["daily_ema21_cross_date"],
                    serialized["daily_ema21_cross_price"],
                    serialized["first_buy_zone_date"],
                    serialized["first_buy_zone_price"],
                    serialized["trend_cycle_id"],
                    serialized["positive_crossover_date"],
                    serialized["positive_crossover_price"],
                    int(serialized["buy_signal_emitted"]),
                    serialized["last_buy_signal_date"],
                    serialized["last_buy_signal_type"],
                    serialized["last_buy_signal_crossover_date"],
                    serialized["uptrend_start_date"],
                    serialized["uptrend_weeks"],
                    serialized["weekly_candle_count"],
                    serialized["closes_above_ema"],
                    serialized["closes_below_ema"],
                    int(serialized["is_buyzone"]),
                    int(serialized["is_crossover_detected"]),
                    serialized["crossover_date"],
                    serialized["crossover_price"],
                    serialized["classification"],
                    serialized["last_ema21"],
                    serialized["last_ema34"],
                    serialized["last_ema55"],
                    serialized["last_close"],
                    serialized["last_update"],
                    json.dumps(serialized, default=str),
                    context.longName,
                    context.sector,
                    context.industry,
                    context.marketCap,
                    context.website,
                    context.nextDividendDate,
                    context.isin,
                ),
            )

            self._save_trend_records(cursor, context)
            conn.commit()

    def load_context(self, ticker: str) -> Optional[StockContext]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT context_json, longName, sector, industry, marketCap, website, nextDividendDate, isin 
                FROM stock_states 
                WHERE ticker=?
            """, (ticker,))
            row = cursor.fetchone()
            if row:
                context_dict = json.loads(row[0])
                context_dict['longName'] = row[1]
                context_dict['sector'] = row[2]
                context_dict['industry'] = row[3]
                context_dict['marketCap'] = row[4]
                context_dict['website'] = row[5]
                context_dict['nextDividendDate'] = row[6]
                context_dict['isin'] = row[7]
                return StockContext(**context_dict)
            return None

    def load_all_contexts(self) -> List[StockContext]:
        contexts = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT context_json FROM stock_states")
            for row in cursor.fetchall():
                contexts.append(deserialize_context(json.loads(row[0])))
        return contexts

    def delete_context(self, ticker: str) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM stock_states WHERE ticker = ?", (ticker,))
            cursor.execute("DELETE FROM trend_cycles WHERE ticker = ?", (ticker,))
            cursor.execute("DELETE FROM trend_analytics WHERE ticker = ?", (ticker,))
            cursor.execute("DELETE FROM trend_events WHERE ticker = ?", (ticker,))
            conn.commit()

    # ------------------------------------------------------------------
    # Trend tables
    # ------------------------------------------------------------------
    def _save_trend_records(self, cursor: sqlite3.Cursor, context: StockContext) -> None:
        all_cycles: List[UptrendRecord] = list(context.uptrend_history)
        if context.current_uptrend is not None:
            all_cycles.append(context.current_uptrend)

        for cycle in all_cycles:
            self._upsert_trend_cycle(cursor, context.ticker, cycle, context.tr_qualified)
            self._upsert_trend_analytics(cursor, context.ticker, cycle)

    def _upsert_trend_cycle(self, cursor: sqlite3.Cursor, ticker: str, cycle: UptrendRecord, tr_qualified: bool) -> None:
        cycle_id = cycle.cycle_id if cycle.cycle_id is not None else 0
        end_state = cycle.end_state or ("DOWNTREND" if cycle.end_date is not None else None)
        status = "CLOSED" if cycle.end_date is not None else "ACTIVE"

        cursor.execute(
            """
            INSERT INTO trend_cycles
            (ticker, cycle_id, trend_start_date, trend_start_price, trend_end_date, trend_end_price,
             daily_ema21_cross_date, daily_ema21_cross_price, daily_downtrend_trigger_date,
             daily_downtrend_trigger_price, first_buy_zone_date, first_buy_zone_price,
             start_state, end_state, status, tr_qualified, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(ticker, cycle_id) DO UPDATE SET
                trend_start_date = excluded.trend_start_date,
                trend_start_price = excluded.trend_start_price,
                trend_end_date = excluded.trend_end_date,
                trend_end_price = excluded.trend_end_price,
                daily_ema21_cross_date = excluded.daily_ema21_cross_date,
                daily_ema21_cross_price = excluded.daily_ema21_cross_price,
                daily_downtrend_trigger_date = excluded.daily_downtrend_trigger_date,
                daily_downtrend_trigger_price = excluded.daily_downtrend_trigger_price,
                first_buy_zone_date = excluded.first_buy_zone_date,
                first_buy_zone_price = excluded.first_buy_zone_price,
                start_state = excluded.start_state,
                end_state = excluded.end_state,
                status = excluded.status,
                tr_qualified = excluded.tr_qualified,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                ticker,
                cycle_id,
                cycle.start_date.isoformat() if cycle.start_date else None,
                cycle.start_price,
                cycle.end_date.isoformat() if cycle.end_date else None,
                cycle.end_price,
                cycle.daily_ema21_cross_date.isoformat() if cycle.daily_ema21_cross_date else None,
                cycle.daily_ema21_cross_price,
                cycle.daily_downtrend_trigger_date.isoformat() if cycle.daily_downtrend_trigger_date else None,
                cycle.daily_downtrend_trigger_price,
                cycle.first_buy_zone_date.isoformat() if cycle.first_buy_zone_date else None,
                cycle.first_buy_zone_price,
                cycle.start_state,
                end_state,
                status,
                int(tr_qualified),
            ),
        )

    def _upsert_trend_analytics(self, cursor: sqlite3.Cursor, ticker: str, cycle: UptrendRecord) -> None:
        cycle_id = cycle.cycle_id if cycle.cycle_id is not None else 0
        cursor.execute(
            """
            INSERT INTO trend_analytics
            (ticker, cycle_id, as_of_date, num_weeks, closes_above_ema, closes_below_ema,
             pct_closes_above, strength, max_profit_pct, trend_roc_pct, roc_1w_pct, roc_3w_pct,
             roc_6m_pct, roc_9m_pct, ath_price, ath_date, distance_from_ath_abs,
             distance_from_ath_pct, ema21_slope, ema34_55_spread, ema34_55_spread_pct,
             efficiency_ratio, last_close, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(ticker, cycle_id) DO UPDATE SET
                as_of_date = excluded.as_of_date,
                num_weeks = excluded.num_weeks,
                closes_above_ema = excluded.closes_above_ema,
                closes_below_ema = excluded.closes_below_ema,
                pct_closes_above = excluded.pct_closes_above,
                strength = excluded.strength,
                max_profit_pct = excluded.max_profit_pct,
                trend_roc_pct = excluded.trend_roc_pct,
                roc_1w_pct = excluded.roc_1w_pct,
                roc_3w_pct = excluded.roc_3w_pct,
                roc_6m_pct = excluded.roc_6m_pct,
                roc_9m_pct = excluded.roc_9m_pct,
                ath_price = excluded.ath_price,
                ath_date = excluded.ath_date,
                distance_from_ath_abs = excluded.distance_from_ath_abs,
                distance_from_ath_pct = excluded.distance_from_ath_pct,
                ema21_slope = excluded.ema21_slope,
                ema34_55_spread = excluded.ema34_55_spread,
                ema34_55_spread_pct = excluded.ema34_55_spread_pct,
                efficiency_ratio = excluded.efficiency_ratio,
                last_close = excluded.last_close,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                ticker,
                cycle_id,
                cycle.end_date.isoformat() if cycle.end_date else cycle.start_date.isoformat(),
                cycle.num_weeks,
                cycle.closes_above_ema,
                cycle.closes_below_ema,
                cycle.pct_closes_above,
                cycle.strength.name if cycle.strength else None,
                cycle.max_profit_pct,
                cycle.trend_roc_pct,
                cycle.roc_1w_pct,
                cycle.roc_3w_pct,
                cycle.roc_6m_pct,
                cycle.roc_9m_pct,
                cycle.ath_price,
                cycle.ath_date.isoformat() if cycle.ath_date else None,
                cycle.distance_from_ath_abs,
                cycle.distance_from_ath_pct,
                cycle.ema21_slope,
                cycle.ema34_55_spread,
                cycle.ema34_55_spread_pct,
                cycle.efficiency_ratio,
                cycle.end_price if cycle.end_price is not None else (
                    cycle.daily_close_history[-1][1] if cycle.daily_close_history else None
                ),
            ),
        )

    def save_trend_event(self, event: TrendEventRecord) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO trend_events
                (ticker, cycle_id, event_type, event_date, timeframe, state, open, high, low,
                 close, volume, ema21, ema34, ema55, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.ticker,
                    event.trend_cycle_id,
                    event.event_type.name if isinstance(event.event_type, TrendEventType) else str(event.event_type),
                    event.date.isoformat() if event.date else None,
                    event.timeframe,
                    event.state,
                    event.metadata.get("open"),
                    event.metadata.get("high"),
                    event.metadata.get("low"),
                    event.close_price,
                    event.metadata.get("volume"),
                    event.ema21,
                    event.ema34,
                    event.ema55,
                    json.dumps(event.metadata, default=str),
                ),
            )
            conn.commit()

    def get_trend_events(self, ticker: str) -> List[TrendEventRecord]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT ticker, cycle_id, event_type, event_date, timeframe, state, close, ema21, ema34, ema55, metadata_json
                FROM trend_events
                WHERE ticker = ?
                ORDER BY event_date ASC, id ASC
                """,
                (ticker,),
            )
            events = []
            for row in cursor.fetchall():
                events.append(
                    TrendEventRecord(
                        ticker=row[0],
                        trend_cycle_id=row[1],
                        event_type=TrendEventType[row[2]] if row[2] in TrendEventType.__members__ else TrendEventType.DAILY_EMA21_CONFIRMATION,
                        date=datetime.fromisoformat(row[3]) if row[3] else datetime.now(),
                        timeframe=row[4],
                        state=row[5],
                        close_price=row[6],
                        ema21=row[7],
                        ema34=row[8],
                        ema55=row[9],
                        metadata=json.loads(row[10]) if row[10] else {},
                    )
                )
            return events

    def get_trend_cycles(self, ticker: str) -> List[UptrendRecord]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT cycle_id, trend_start_date, trend_end_date, daily_ema21_cross_date,
                       daily_ema21_cross_price, daily_downtrend_trigger_date,
                       daily_downtrend_trigger_price, first_buy_zone_date, first_buy_zone_price
                FROM trend_cycles
                WHERE ticker = ?
                ORDER BY cycle_id ASC
                """,
                (ticker,),
            )
            records = []
            for row in cursor.fetchall():
                record = UptrendRecord(
                    start_date=datetime.fromisoformat(row[1]) if row[1] else datetime.now()
                )
                record.cycle_id = row[0]
                record.end_date = datetime.fromisoformat(row[2]) if row[2] else None
                record.daily_ema21_cross_date = datetime.fromisoformat(row[3]) if row[3] else None
                record.daily_ema21_cross_price = row[4]
                record.daily_downtrend_trigger_date = datetime.fromisoformat(row[5]) if row[5] else None
                record.daily_downtrend_trigger_price = row[6]
                record.first_buy_zone_date = datetime.fromisoformat(row[7]) if row[7] else None
                record.first_buy_zone_price = row[8]
                records.append(record)
            return records

    def get_trend_analytics(self, ticker: str) -> List[UptrendRecord]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT cycle_id, as_of_date, num_weeks, closes_above_ema, closes_below_ema,
                       pct_closes_above, strength, max_profit_pct, trend_roc_pct, roc_1w_pct,
                       roc_3w_pct, roc_6m_pct, roc_9m_pct, ath_price, ath_date,
                       distance_from_ath_abs, distance_from_ath_pct, ema21_slope,
                       ema34_55_spread, ema34_55_spread_pct, efficiency_ratio, last_close
                FROM trend_analytics
                WHERE ticker = ?
                ORDER BY cycle_id ASC
                """,
                (ticker,),
            )
            records = []
            for row in cursor.fetchall():
                record = UptrendRecord(
                    start_date=datetime.fromisoformat(row[1]) if row[1] else datetime.now()
                )
                record.cycle_id = row[0]
                record.num_weeks = row[2] or 0
                record.closes_above_ema = row[3] or 0
                record.closes_below_ema = row[4] or 0
                record.pct_closes_above = row[5] or 0.0
                record.strength = UptrendStrength[row[6]] if row[6] else None
                record.max_profit_pct = row[7]
                record.trend_roc_pct = row[8]
                record.roc_1w_pct = row[9]
                record.roc_3w_pct = row[10]
                record.roc_6m_pct = row[11]
                record.roc_9m_pct = row[12]
                record.ath_price = row[13]
                record.ath_date = datetime.fromisoformat(row[14]) if row[14] else None
                record.distance_from_ath_abs = row[15]
                record.distance_from_ath_pct = row[16]
                record.ema21_slope = row[17]
                record.ema34_55_spread = row[18]
                record.ema34_55_spread_pct = row[19]
                record.efficiency_ratio = row[20]
                record.end_price = row[21]
                records.append(record)
            return records

    # ------------------------------------------------------------------
    # ISignalStore
    # ------------------------------------------------------------------
    def save_signal(self, signal: SignalEvent) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO signals
                (ticker, signal_type, date, close_price, ema21, ema34, ema55, timeframe,
                 state, trend_cycle_id, trend_start_date, trend_end_date, reason, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    signal.ticker,
                    signal.signal_type.name if isinstance(signal.signal_type, SignalType) else signal.signal_type,
                    signal.date.isoformat() if signal.date else None,
                    signal.close_price,
                    signal.ema21,
                    signal.ema34,
                    signal.ema55,
                    signal.timeframe,
                    signal.state,
                    signal.trend_cycle_id,
                    signal.trend_start_date.isoformat() if signal.trend_start_date else None,
                    signal.trend_end_date.isoformat() if signal.trend_end_date else None,
                    signal.metadata.get("reason"),
                    json.dumps(signal.metadata, default=str),
                ),
            )
            conn.commit()

    def get_signals(self, ticker: str, signal_type: Optional[str] = None, from_date: Optional[str] = None) -> List[SignalEvent]:
        query = """
            SELECT ticker, signal_type, date, close_price, ema21, ema34, ema55, timeframe,
                   state, trend_cycle_id, trend_start_date, trend_end_date, metadata_json
            FROM signals
            WHERE ticker = ?
        """
        params: List[Any] = [ticker]

        if signal_type:
            signal_name = signal_type.name if isinstance(signal_type, SignalType) else signal_type
            query += " AND signal_type = ?"
            params.append(signal_name)
        if from_date:
            query += " AND date >= ?"
            params.append(from_date)

        query += " ORDER BY date ASC, id ASC"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            signals = []
            for row in cursor.fetchall():
                signals.append(
                    SignalEvent(
                        ticker=row[0],
                        signal_type=SignalType[row[1]] if row[1] else None,
                        date=datetime.fromisoformat(row[2]) if row[2] else datetime.now(),
                        close_price=row[3],
                        ema21=row[4],
                        ema34=row[5],
                        ema55=row[6],
                        timeframe=row[7],
                        state=row[8],
                        trend_cycle_id=row[9],
                        trend_start_date=datetime.fromisoformat(row[10]) if row[10] else None,
                        trend_end_date=datetime.fromisoformat(row[11]) if row[11] else None,
                        metadata=json.loads(row[12]) if row[12] else {},
                    )
                )
            return signals

    def get_latest_signal(self, ticker: str, signal_type: Optional[str] = None) -> Optional[SignalEvent]:
        query = """
            SELECT ticker, signal_type, date, close_price, ema21, ema34, ema55, timeframe,
                   state, trend_cycle_id, trend_start_date, trend_end_date, metadata_json
            FROM signals
            WHERE ticker = ?
        """
        params: List[Any] = [ticker]
        if signal_type:
            signal_name = signal_type.name if isinstance(signal_type, SignalType) else signal_type
            query += " AND signal_type = ?"
            params.append(signal_name)
        query += " ORDER BY date DESC, id DESC LIMIT 1"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            row = cursor.fetchone()
            if not row:
                return None
            return SignalEvent(
                ticker=row[0],
                signal_type=SignalType[row[1]] if row[1] else None,
                date=datetime.fromisoformat(row[2]) if row[2] else datetime.now(),
                close_price=row[3],
                ema21=row[4],
                ema34=row[5],
                ema55=row[6],
                timeframe=row[7],
                state=row[8],
                trend_cycle_id=row[9],
                trend_start_date=datetime.fromisoformat(row[10]) if row[10] else None,
                trend_end_date=datetime.fromisoformat(row[11]) if row[11] else None,
                metadata=json.loads(row[12]) if row[12] else {},
            )

    def delete_signals(self, ticker: str) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM signals WHERE ticker = ?", (ticker,))
            conn.commit()

    # ------------------------------------------------------------------
    # ITradeStore
    # ------------------------------------------------------------------
    def delete_trades(self, ticker: str) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM trades WHERE ticker = ?", (ticker,))
            conn.commit()

    def save_trade(self, trade: TradeRecord) -> None:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO trades
                    (id, ticker, entry_date, entry_price, exit_date, exit_price,
                     target_price, initial_sl, current_sl, highest_price_seen,
                     tsl_step_pct, status, exit_reason, profit_loss_pct)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        trade.id,
                        trade.ticker,
                        trade.entry_date.isoformat() if trade.entry_date else None,
                        trade.entry_price,
                        trade.exit_date.isoformat() if trade.exit_date else None,
                        trade.exit_price,
                        trade.target_price,
                        trade.initial_sl,
                        trade.current_sl,
                        trade.highest_price_seen,
                        trade.tsl_step_pct,
                        trade.status.name if isinstance(trade.status, TradeStatus) else trade.status,
                        trade.exit_reason.name if trade.exit_reason else None,
                        trade.profit_loss_pct,
                    ),
                )
                conn.commit()
        except sqlite3.IntegrityError as exc:
            logger.warning("Error saving trade with ID %s: %s", trade.id, exc)

    def update_trade(self, trade: TradeRecord) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE trades SET
                exit_date = ?, exit_price = ?, target_price = ?,
                initial_sl = ?, current_sl = ?, highest_price_seen = ?,
                tsl_step_pct = ?, status = ?, exit_reason = ?, profit_loss_pct = ?
                WHERE id = ?
                """,
                (
                    trade.exit_date.isoformat() if trade.exit_date else None,
                    trade.exit_price,
                    trade.target_price,
                    trade.initial_sl,
                    trade.current_sl,
                    trade.highest_price_seen,
                    trade.tsl_step_pct,
                    trade.status.name if isinstance(trade.status, TradeStatus) else trade.status,
                    trade.exit_reason.name if trade.exit_reason else None,
                    trade.profit_loss_pct,
                    trade.id,
                ),
            )
            conn.commit()

    def get_open_trades(self, ticker: Optional[str] = None) -> List[TradeRecord]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if ticker:
                cursor.execute(
                    "SELECT * FROM trades WHERE status = ? AND ticker = ? ORDER BY id ASC",
                    (TradeStatus.OPEN.name, ticker),
                )
            else:
                cursor.execute("SELECT * FROM trades WHERE status = ? ORDER BY id ASC", (TradeStatus.OPEN.name,))
            return self._rows_to_trades(cursor.fetchall())

    def get_all_trades(self, ticker: Optional[str] = None) -> List[TradeRecord]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if ticker:
                cursor.execute("SELECT * FROM trades WHERE ticker = ? ORDER BY id ASC", (ticker,))
            else:
                cursor.execute("SELECT * FROM trades ORDER BY id ASC")
            return self._rows_to_trades(cursor.fetchall())

    def get_trade_by_id(self, trade_id: int) -> Optional[TradeRecord]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trades WHERE id = ?", (trade_id,))
            row = cursor.fetchone()
            if row:
                trades = self._rows_to_trades([row])
                return trades[0] if trades else None
            return None

    @staticmethod
    def _rows_to_trades(rows: list) -> List[TradeRecord]:
        trades = []
        for row in rows:
            trades.append(
                TradeRecord(
                    id=row[0],
                    ticker=row[1],
                    entry_date=datetime.fromisoformat(row[2]) if row[2] else None,
                    entry_price=row[3],
                    exit_date=datetime.fromisoformat(row[4]) if row[4] else None,
                    exit_price=row[5],
                    target_price=row[6],
                    initial_sl=row[7],
                    current_sl=row[8],
                    highest_price_seen=row[9],
                    tsl_step_pct=row[10],
                    status=TradeStatus[row[11]] if row[11] else TradeStatus.OPEN,
                    exit_reason=ExitReason[row[12]] if row[12] else None,
                    profit_loss_pct=row[13],
                )
            )
        return trades