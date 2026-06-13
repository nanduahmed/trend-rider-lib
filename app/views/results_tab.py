import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from app.database import Database
from trend_rider_lib.core.models import StockContext, SignalEvent, TradeRecord

class ResultsTab(ttk.Frame):
    """Tab that displays persisted scan results.

    It fetches all stored :class:`StockContext` objects from the SQLite DB and
    presents them in a sortable ``Treeview``.  Double‑clicking a row opens a
    ``DetailWindow`` showing the full context, signals and trades.
    """

    def __init__(self, master: tk.Widget):
        super().__init__(master)
        self.master = master
        self.db = Database()
        self._build_ui()
        self._populate()

    def _build_ui(self) -> None:
        # Toolbar with refresh button
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(toolbar, text="Refresh", command=self._refresh).pack(side=tk.LEFT)

        # Treeview for results
        columns = (
            "ticker",
            "state",
            "classification",
            "uptrends",
            "signals",
            "trades",
            "last_update",
        )
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        for col in columns:
            self.tree.heading(col, text=col.replace('_', ' ').title(), command=lambda _c=col: self._sort_by(_c, False))
            self.tree.column(col, width=100, anchor="center")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.tree.bind("<Double-1>", self._on_double_click)

    def _populate(self) -> None:
        # Clear existing rows
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            contexts = self.db.get_all_contexts()
            for ctx in contexts:
                ticker = getattr(ctx, "ticker", "")
                state = getattr(ctx, "state", "")
                classification = getattr(ctx, "classification", "")
                uptrends = len(getattr(ctx, "uptrends", []))
                signals = len(getattr(ctx, "signals", []))
                trades = len(getattr(ctx, "trades", []))
                last_update = getattr(ctx, "last_update", "")
                # Ensure datetime string for sorting
                if isinstance(last_update, datetime):
                    last_update = last_update.isoformat()
                self.tree.insert(
                    "",
                    tk.END,
                    values=(ticker, state, classification, uptrends, signals, trades, last_update),
                )
        except Exception as exc:  # pragma: no cover – UI surface only
            messagebox.showerror("Error", f"Failed to load results: {exc}")

    def _refresh(self) -> None:
        self._populate()

    def _sort_by(self, col: str, descending: bool) -> None:
        # Grab data to sort
        data = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        # Try to convert to appropriate type for numeric columns
        try:
            data = [(float(v), k) for v, k in data]
        except ValueError:
            pass
        data.sort(reverse=descending)
        for index, (val, k) in enumerate(data):
            self.tree.move(k, "", index)
        # Reverse sort next time
        self.tree.heading(col, command=lambda: self._sort_by(col, not descending))

    def _on_double_click(self, event: tk.Event) -> None:
        item = self.tree.identify_row(event.y)
        if not item:
            return
        ticker = self.tree.item(item, "values")[0]
        ctx = self.db.get_context(ticker)
        if not ctx:
            messagebox.showwarning("Missing", f"No context found for {ticker}")
            return
        # Load related signals and trades
        signals = self.db.get_signals(ticker)
        trades = self.db.get_trades(ticker)
        # Open detail window
        DetailWindow(self.master, ctx, signals, trades)

# Import placed at end to avoid circular import issues
from .detail_window import DetailWindow
