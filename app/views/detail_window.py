import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from trend_rider_lib.core.models import StockContext, SignalEvent, TradeRecord

class DetailWindow(tk.Toplevel):
    """Display full information for a single ticker.

    Shows three tabs:
    * Context – aggregated fields from :class:`StockContext`
    * Signals – list of :class:`SignalEvent`
    * Trades   – list of :class:`TradeRecord`
    """

    def __init__(self, master: tk.Widget, context: StockContext, signals: list[SignalEvent], trades: list[TradeRecord]):
        super().__init__(master)
        self.title(f"Details – {getattr(context, 'ticker', '')}")
        self.geometry("800x600")
        self.context = context
        self.signals = signals
        self.trades = trades
        self._build_ui()
        self._populate_context()
        self._populate_signals()
        self._populate_trades()

    def _build_ui(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True)

        # Context tab – simple label/value list
        self.context_frame = ttk.Frame(notebook)
        notebook.add(self.context_frame, text="Context")

        # Signals tab – treeview
        self.signals_frame = ttk.Frame(notebook)
        notebook.add(self.signals_frame, text="Signals")

        # Trades tab – treeview
        self.trades_frame = ttk.Frame(notebook)
        notebook.add(self.trades_frame, text="Trades")

        # Build Signals treeview
        sig_cols = ("ts", "type", "strength", "price")
        self.sig_tree = ttk.Treeview(self.signals_frame, columns=sig_cols, show="headings")
        for col in sig_cols:
            self.sig_tree.heading(col, text=col.title())
            self.sig_tree.column(col, width=100, anchor="center")
        self.sig_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Build Trades treeview
        tr_cols = ("id", "status", "entry_ts", "exit_ts", "entry_price", "exit_price", "profit_pct")
        self.tr_tree = ttk.Treeview(self.trades_frame, columns=tr_cols, show="headings")
        for col in tr_cols:
            self.tr_tree.heading(col, text=col.replace('_', ' ').title())
            self.tr_tree.column(col, width=100, anchor="center")
        self.tr_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _populate_context(self) -> None:
        # Use a simple grid of labels for context attributes
        row = 0
        for attr, value in vars(self.context).items():
            # Skip internal collections that are displayed elsewhere
            if attr in ("signals", "trades", "uptrends"):
                continue
            ttk.Label(self.context_frame, text=f"{attr}:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)
            ttk.Label(self.context_frame, text=str(value)).grid(row=row, column=1, sticky=tk.W, padx=5, pady=2)
            row += 1

    def _populate_signals(self) -> None:
        for sig in self.signals:
            ts = getattr(sig, "ts", "")
            typ = getattr(sig, "type", "")
            strength = getattr(sig, "strength", "")
            price = getattr(sig, "price", "")
            self.sig_tree.insert("", tk.END, values=(ts, typ, strength, price))

    def _populate_trades(self) -> None:
        for tr in self.trades:
            tr_id = getattr(tr, "id", "")
            status = getattr(tr, "status", "")
            entry_ts = getattr(tr, "entry_ts", "")
            exit_ts = getattr(tr, "exit_ts", "")
            entry_price = getattr(tr, "entry_price", "")
            exit_price = getattr(tr, "exit_price", "")
            profit_pct = getattr(tr, "profit_pct", "")
            self.tr_tree.insert(
                "",
                tk.END,
                values=(tr_id, status, entry_ts, exit_ts, entry_price, exit_price, profit_pct),
            )
