"""
SQLite persistence provider implementation.
"""
import logging
import sqlite3
import json
from typing import List, Optional
from datetime import datetime

from ..core.models import StockContext, SignalEvent, TradeRecord
from ..state_machine.fsm_serializer import serialize_context, deserialize_context
from ..core.enums import TradeStatus, SignalType, ExitReason
from .interfaces import IStateStore, ISignalStore, ITradeStore


logger = logging.getLogger(__name__)


class SQLiteProvider(IStateStore, ISignalStore, ITradeStore):
    """
    SQLite implementation of all persistence interfaces.
    Supports saving and loading stock states, signals, and trades.
    """

    def __init__(self, connection_string: str):
        """
        Initialize SQLite provider.

        Args:
            connection_string: Path to SQLite database file
        """
        self.connection_string = connection_string
        self._init_database()

    def _get_connection(self):
        """Get database connection."""
        return sqlite3.connect(self.connection_string)

    def _init_database(self) -> None:
        """Initialize database tables if they don't exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Stock states table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stock_states (
                    ticker TEXT PRIMARY KEY,
                    current_state TEXT,
                    tr_qualified INTEGER,
                    uptrend_start_date TEXT,
                    uptrend_weeks INTEGER,
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
                    context_json TEXT
                )
            ''')

            # Signals table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT,
                    signal_type TEXT,
                    date TEXT,
                    close_price REAL,
                    ema21 REAL,
                    ema34 REAL,
                    ema55 REAL,
                    metadata_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Trades table
            cursor.execute('''
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
            ''')

            conn.commit()

    # IStateStore implementation
    def save_context(self, context: StockContext) -> None:
        """Save or update stock context."""
        serialized = serialize_context(context)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO stock_states
                (ticker, current_state, tr_qualified, uptrend_start_date,
                 uptrend_weeks, closes_above_ema, closes_below_ema, is_buyzone,
                 is_crossover_detected, crossover_date, crossover_price,
                 classification, last_ema21, last_ema34, last_ema55,
                 last_close, last_updated, context_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                context.ticker,
                serialized['current_state'],
                int(serialized['tr_qualified']),
                serialized['uptrend_start_date'],
                serialized['uptrend_weeks'],
                serialized['closes_above_ema'],
                serialized['closes_below_ema'],
                int(serialized['is_buyzone']),
                int(serialized['is_crossover_detected']),
                serialized['crossover_date'],
                serialized['crossover_price'],
                serialized['classification'],
                serialized['last_ema21'],
                serialized['last_ema34'],
                serialized['last_ema55'],
                serialized['last_close'],
                serialized['last_update'],
                json.dumps(serialized)
            ))
            conn.commit()

    def load_context(self, ticker: str) -> Optional[StockContext]:
        """Load stock context by ticker."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT context_json FROM stock_states WHERE ticker = ?',
                (ticker,)
            )
            row = cursor.fetchone()

            if row:
                return deserialize_context(json.loads(row[0]))
            return None

    def load_all_contexts(self) -> List[StockContext]:
        """Load all stock contexts."""
        contexts = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT context_json FROM stock_states')

            for row in cursor.fetchall():
                contexts.append(deserialize_context(json.loads(row[0])))

        return contexts

    def delete_context(self, ticker: str) -> None:
        """Delete stock context."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM stock_states WHERE ticker = ?', (ticker,))
            conn.commit()

    def delete_signals(self, ticker: str) -> None:
        """Delete all signal records for a ticker."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM signals WHERE ticker = ?", (ticker,))
            conn.commit()

    def delete_trades(self, ticker: str) -> None:
        """Delete all trade records for a ticker."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM trades WHERE ticker = ?", (ticker,))
            conn.commit()

    # ISignalStore implementation
    def save_signal(self, signal: SignalEvent) -> None:
        """Save signal event."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO signals
                (ticker, signal_type, date, close_price, ema21, ema34, ema55, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                signal.ticker,
                signal.signal_type.name if isinstance(signal.signal_type, SignalType) else signal.signal_type,
                signal.date.isoformat() if signal.date else None,
                signal.close_price,
                signal.ema21,
                signal.ema34,
                signal.ema55,
                json.dumps(signal.metadata)
            ))
            conn.commit()

    def get_signals(
        self,
        ticker: str,
        signal_type: Optional[str] = None,
        from_date: Optional[str] = None
    ) -> List[SignalEvent]:
        """Get signals with optional filters."""
        query = '''
            SELECT ticker, signal_type, date, close_price, ema21, ema34, ema55, metadata_json
            FROM signals
            WHERE ticker = ?
        '''
        params = [ticker]

        if signal_type:
            signal_name = signal_type.name if isinstance(signal_type, SignalType) else signal_type
            query += ' AND signal_type = ?'
            params.append(signal_name)

        if from_date:
            query += ' AND date >= ?'
            params.append(from_date)

        query += ' ORDER BY date ASC'

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            signals = []
            for row in cursor.fetchall():
                signal = SignalEvent(
                    ticker=row[0],
                    signal_type=SignalType[row[1]] if row[1] else None,
                    date=datetime.fromisoformat(row[2]) if row[2] else datetime.now(),
                    close_price=row[3],
                    ema21=row[4],
                    ema34=row[5],
                    ema55=row[6],
                    metadata=json.loads(row[7]) if row[7] else {}
                )
                signals.append(signal)
            return signals

    def get_latest_signal(
        self,
        ticker: str,
        signal_type: Optional[str] = None
    ) -> Optional[SignalEvent]:
        """Get most recent signal for ticker."""
        query = '''
            SELECT ticker, signal_type, date, close_price, ema21, ema34, ema55, metadata_json
            FROM signals
            WHERE ticker = ?
        '''
        params = [ticker]
        if signal_type:
            signal_name = signal_type.name if isinstance(signal_type, SignalType) else signal_type
            query += ' AND signal_type = ?'
            params.append(signal_name)
        query += ' ORDER BY date DESC LIMIT 1'

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            row = cursor.fetchone()

            if row:
                return SignalEvent(
                    ticker=row[0],
                    signal_type=SignalType[row[1]] if row[1] else None,
                    date=datetime.fromisoformat(row[2]) if row[2] else datetime.now(),
                    close_price=row[3],
                    ema21=row[4],
                    ema34=row[5],
                    ema55=row[6],
                    metadata=json.loads(row[7]) if row[7] else {}
                )
            return None

    # ITradeStore implementation
    def save_trade(self, trade: TradeRecord) -> None:
        """Save new trade."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO trades
                    (id, ticker, entry_date, entry_price, exit_date, exit_price,
                    target_price, initial_sl, current_sl, highest_price_seen,
                    tsl_step_pct, status, exit_reason, profit_loss_pct)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
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
                    trade.profit_loss_pct
                ))
                conn.commit()
        except sqlite3.IntegrityError as e:
            logger.warning("Error saving trade with ID %s: %s", trade.id, e)

    def update_trade(self, trade: TradeRecord) -> None:
        """Update existing trade."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE trades SET
                exit_date = ?, exit_price = ?, target_price = ?,
                initial_sl = ?, current_sl = ?, highest_price_seen = ?,
                tsl_step_pct = ?, status = ?, exit_reason = ?, profit_loss_pct = ?
                WHERE id = ?
            ''', (
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
                trade.id
            ))
            conn.commit()

    def get_open_trades(self, ticker: Optional[str] = None) -> List[TradeRecord]:
        """Get open trades."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if ticker:
                cursor.execute(
                    'SELECT * FROM trades WHERE status = ? AND ticker = ? ORDER BY id ASC',
                    (TradeStatus.OPEN.name, ticker)
                )
            else:
                cursor.execute(
                    'SELECT * FROM trades WHERE status = ? ORDER BY id ASC',
                    (TradeStatus.OPEN.name,)
                )
            return self._rows_to_trades(cursor.fetchall())

    def get_all_trades(self, ticker: Optional[str] = None) -> List[TradeRecord]:
        """Get all trades (open and closed)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if ticker:
                cursor.execute('SELECT * FROM trades WHERE ticker = ? ORDER BY id ASC', (ticker,))
            else:
                cursor.execute('SELECT * FROM trades ORDER BY id ASC')
            return self._rows_to_trades(cursor.fetchall())

    def get_trade_by_id(self, trade_id: int) -> Optional[TradeRecord]:
        """Get specific trade by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM trades WHERE id = ?', (trade_id,))
            row = cursor.fetchone()
            if row:
                trades = self._rows_to_trades([row])
                return trades[0] if trades else None
            return None

    @staticmethod
    def _rows_to_trades(rows: list) -> List[TradeRecord]:
        """Convert database rows to TradeRecord objects."""
        trades = []
        for row in rows:
            trade = TradeRecord(
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
                profit_loss_pct=row[13]
            )
            trades.append(trade)
        return trades
