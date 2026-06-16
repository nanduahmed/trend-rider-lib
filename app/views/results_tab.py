import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from app.database import Database
from trend_rider_lib.core.models import StockContext, SignalEvent, TradeRecord


class ResultsTab(ctk.CTkFrame):
    """Tab that displays persisted scan results.

    The UI has been migrated to **customtkinter** for a modern look.
    """

    def __init__(self, master: tk.Widget):
        super().__init__(master)
        self.master = master
        self.db = Database()
        self._build_ui()
        self._populate()

    def _build_ui(self) -> None:
        # Toolbar with refresh button
        toolbar = ctk.CTkFrame(self, corner_radius=0)
        toolbar.pack(fill=tk.X, padx=10, pady=10)
        ctk.CTkButton(toolbar, text="Refresh", command=self._refresh).pack(side=tk.LEFT)

        # Treeview for results (ttk.Treeview does not have a customtkinter equivalent)
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
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Button-3>", self._on_right_click)

        # Right-click context menu
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Remove from Database", command=self._remove_stock)

    def _populate(self) -> None:
        # Clear existing rows
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            contexts = self.db.get_all_contexts()
            for ctx in contexts:
                ticker = getattr(ctx, "ticker", "")
                # Get the attribute, then split by the dot and take the last element
                state_full = getattr(ctx, "current_state", "")
                state = state_full.split(".")[-1] if state_full else "-"
                classification = getattr(ctx, "classification", "")
                if hasattr(classification, "name"):
                    classification = classification.name
                elif classification is None:
                    classification = "-"
                uptrends = len(getattr(ctx, "uptrend_history", []))
                # Query DB for actual signal/trade counts (not stored on context object)
                signals = self.db.get_signal_count(ticker)
                trades = self.db.get_trade_count(ticker)
                last_update = getattr(ctx, "last_update", "")
                # Ensure datetime string for sorting
                if isinstance(last_update, datetime):
                    last_update = last_update.strftime("%d-%m-%Y")
                elif last_update is None:
                    last_update = "-"
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
        from .detail_window import DetailWindow
        DetailWindow(self.master, ctx, signals, trades)

    def _on_right_click(self, event: tk.Event) -> None:
        """Show right-click context menu on the treeview row."""
        item = self.tree.identify_row(event.y)
        if not item:
            return
        self.tree.selection_set(item)
        self.context_menu.post(event.x_root, event.y_root)

    def _remove_stock(self) -> None:
        """Remove the selected stock from the database entirely."""
        selection = self.tree.selection()
        if not selection:
            return
        ticker = self.tree.item(selection[0], "values")[0]
        if messagebox.askyesno("Confirm Remove", f"Remove {ticker} from database?\n\nThis will delete all stored data for this stock."):
            self.db.delete_stock(ticker)
            self._populate()
