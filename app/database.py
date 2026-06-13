import sqlite3
import json
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from trend_rider_lib.core.models import StockContext, SignalEvent, TradeRecord


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
        data = json.dumps(context.to_dict(), default=str)
        ts = datetime.utcnow().isoformat()
        cur = self.conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO contexts (ticker, json, last_update) VALUES (?, ?, ?)",
            (context.ticker, data, ts),
        )
        self.conn.commit()

    def get_all_contexts(self) -> List[StockContext]:
        cur = self.conn.cursor()
        cur.execute("SELECT json FROM contexts")
        rows = cur.fetchall()
        contexts = []
        for (j,) in rows:
            d = json.loads(j)
            # Recreate a StockContext – the library provides a constructor that matches the fields
            ctx = StockContext(**d)  # type: ignore[arg-type]
            contexts.append(ctx)
        return contexts

    def get_context(self, ticker: str) -> Optional[StockContext]:
        cur = self.conn.cursor()
        cur.execute("SELECT json FROM contexts WHERE ticker = ?", (ticker,))
        row = cur.fetchone()
        if row:
            d = json.loads(row[0])
            return StockContext(**d)  # type: ignore[arg-type]
        return None

    # ---------- Signals ----------
    def save_signal(self, ticker: str, signal: SignalEvent) -> None:
        data = json.dumps(signal.__dict__, default=str)
        ts = datetime.utcnow().isoformat()
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO signals (ticker, json, ts) VALUES (?, ?, ?)",
            (ticker, data, ts),
        )
        self.conn.commit()

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
        data = json.dumps(trade.__dict__, default=str)
        ts = datetime.utcnow().isoformat()
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO trades (ticker, json, ts) VALUES (?, ?, ?)",
            (trade.ticker, data, ts),
        )
        self.conn.commit()

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
