import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from trend_rider_lib.core.models import StockContext, SignalEvent, TradeRecord, context_from_dict


class _DatetimeEncoder(json.JSONEncoder):
    """JSON encoder that serialises datetime objects to ISO 8601 with 'T'.

    Falls back to ``str()`` for any other non-serialisable type (e.g. enums)
    so that the behaviour matches the previous ``default=str`` approach while
    still producing ISO 8601 for datetimes.
    """

    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        return str(o)


class Database:
    """Simple SQLite wrapper for storing scan results, signals and trades.

    The schema is deliberately minimal – each object is stored as a JSON blob.
    This keeps the UI layer free of any business logic.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or (Path(__file__).parent / "trend_rider_app.sqlite")
        self.conn = sqlite3.connect(self.db_path)
        self._create_tables()

    def _create_tables(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS contexts (
                ticker TEXT PRIMARY KEY,
                json TEXT NOT NULL,
                last_update TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                json TEXT NOT NULL,
                ts TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                json TEXT NOT NULL,
                ts TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    # ---------- Context ----------
    def save_context(self, context: StockContext) -> None:
        data = json.dumps(context.to_dict(), cls=_DatetimeEncoder)
        ts = datetime.utcnow().isoformat()
        cur = self.conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO contexts (ticker, json, last_update) VALUES (?, ?, ?)",
            (context.ticker, data, ts),
        )
        self.conn.commit()

    def get_all_contexts(self) -> List[StockContext]:
        cur = self.conn.cursor()
        cur.execute("SELECT json, last_update FROM contexts")
        rows = cur.fetchall()
        contexts = []
        for (j, ts) in rows:
            d = json.loads(j)
            ctx = context_from_dict(d)
            # Restore last_update from the DB column (not from JSON, which predates this fix)
            if not ctx.last_update and ts:
                try:
                    ctx.last_update = datetime.fromisoformat(ts)
                except (ValueError, TypeError):
                    ctx.last_update = ts
            contexts.append(ctx)
        return contexts

    def get_context(self, ticker: str) -> Optional[StockContext]:
        cur = self.conn.cursor()
        cur.execute("SELECT json, last_update FROM contexts WHERE ticker = ?", (ticker,))
        row = cur.fetchone()
        if row:
            d = json.loads(row[0])
            ctx = context_from_dict(d)
            # Restore last_update from the DB column
            if not ctx.last_update:
                try:
                    ctx.last_update = datetime.fromisoformat(row[1])
                except (ValueError, TypeError):
                    ctx.last_update = row[1]
            return ctx
        return None

    # ---------- Signals ----------
    def save_signal(self, ticker: str, signal: SignalEvent) -> None:
        data = json.dumps(signal.__dict__, cls=_DatetimeEncoder)
        ts = datetime.utcnow().isoformat()
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO signals (ticker, json, ts) VALUES (?, ?, ?)",
            (ticker, data, ts),
        )
        self.conn.commit()

    def get_signal_count(self, ticker: str) -> int:
        """Get the count of signals for a ticker (without loading all objects)."""
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM signals WHERE ticker = ?", (ticker,))
        row = cur.fetchone()
        return row[0] if row else 0

    def get_signals(self, ticker: str) -> List[SignalEvent]:
        cur = self.conn.cursor()
        cur.execute("SELECT json FROM signals WHERE ticker = ? ORDER BY id", (ticker,))
        rows = cur.fetchall()
        signals = []
        for (j,) in rows:
            d = json.loads(j)
            # Construct SignalEvent – use dict unpacking where possible
            sig = SignalEvent(**d)  # type: ignore[arg-type]
            signals.append(sig)
        return signals

    # ---------- Trades ----------
    def save_trade(self, trade: TradeRecord) -> None:
        data = json.dumps(trade.__dict__, cls=_DatetimeEncoder)
        ts = datetime.utcnow().isoformat()
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO trades (ticker, json, ts) VALUES (?, ?, ?)",
            (trade.ticker, data, ts),
        )
        self.conn.commit()

    def get_trade_count(self, ticker: str) -> int:
        """Get the count of trades for a ticker (without loading all objects)."""
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM trades WHERE ticker = ?", (ticker,))
        row = cur.fetchone()
        return row[0] if row else 0

    def get_trades(self, ticker: str) -> List[TradeRecord]:
        cur = self.conn.cursor()
        cur.execute("SELECT json FROM trades WHERE ticker = ? ORDER BY id", (ticker,))
        rows = cur.fetchall()
        trades = []
        for (j,) in rows:
            d = json.loads(j)
            tr = TradeRecord(**d)  # type: ignore[arg-type]
            trades.append(tr)
        return trades

    def get_all_tickers(self) -> List[str]:
        """Get all tickers in the database."""
        cur = self.conn.cursor()
        cur.execute("SELECT ticker FROM contexts ORDER BY ticker")
        return [row[0] for row in cur.fetchall()]

    def delete_stock(self, ticker: str) -> None:
        """Delete all data for a given ticker from all tables."""
        cur = self.conn.cursor()
        cur.execute("DELETE FROM contexts WHERE ticker = ?", (ticker,))
        cur.execute("DELETE FROM signals WHERE ticker = ?", (ticker,))
        cur.execute("DELETE FROM trades WHERE ticker = ?", (ticker,))
        self.conn.commit()