import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
from datetime import datetime
import locale
import pandas as pd
from typing import Optional, List

from trend_rider_lib.core.models import StockContext, SignalEvent, TradeRecord, UptrendRecord
from trend_rider_lib.core.enums import UptrendStrength

# ------------------------------------------------------------
# Helper formatting functions (unchanged)
# ------------------------------------------------------------

def _format_date(value: Optional[datetime]) -> str:
    """Format dates as ``DD-MM-YYYY`` or return placeholder."""
    if isinstance(value, (datetime,)):
        return value.strftime("%d-%m-%Y")
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value)
            return dt.strftime("%d-%m-%Y")
        except Exception:
            return value
    return "—"


def _format_number(value: Optional[float], ndigits: int = 2) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.{ndigits}f}"
    return "—"


def _bool_label(parent, text: str, value: bool) -> ttk.Label:
    """Create a label that shows a boolean with green/red coloring."""
    fg = "green" if value else "red"
    return ttk.Label(parent, text=text, foreground=fg)

# Currency formatting helpers
def _format_currency(value: Optional[float]) -> str:
    if value is None or pd.isna(value):
        return "—"
    try:
        locale.setlocale(locale.LC_ALL, "en_IN")
    except locale.Error:
        pass
    return f"₹{value:,.2f}"


def _format_market_cap(value: Optional[float]) -> str:
    if value is None or pd.isna(value):
        return "—"
    if value >= 1e7:
        return f"₹{value/1e7:,.2f} Cr"
    elif value >= 1e5:
        return f"₹{value/1e5:,.2f} L"
    else:
        return f"₹{value:,.2f}"


def _enum_name(value) -> str:
    """Return only the last part of an enum/string representation.

    For example: ``SignalType.UPTREND_START`` → ``UPTREND_START``
    Also handles enum objects with a ``.name`` attribute.
    """
    if value is None:
        return "—"
    if hasattr(value, "name"):
        return value.name
    s = str(value)
    if "." in s:
        return s.rsplit(".", 1)[-1]
    return s


class DetailWindow(ctk.CTkToplevel):
    """Display full information for a single ticker using grouped sections.

    The UI has been migrated to **customtkinter** for a modern SaaS‑style look.
    """

    def __init__(self, master: tk.Widget, context: StockContext,
                 signals: List[SignalEvent], trades: List[TradeRecord]):
        super().__init__(master)
        self.title(f"Details – {getattr(context, 'ticker', '')}")
        self.geometry("900x700")
        self.context = context
        self.signals = signals
        self.trades = trades

        # Apply a light appearance with navy sidebar palette (can be tweaked later)
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")  # uses built‑in blue theme

        self._build_ui()
        self._populate_sections()
        self._populate_signals()
        self._populate_trades()
        self._populate_uptrends()

    # ---------------------------------------------------------------------
    # UI construction – customtkinter frames + ttk widgets where necessary
    # ---------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Create a scrollable canvas containing labelled sections."""
        # Main container – customtkinter frame for consistent styling
        self.container = ctk.CTkFrame(self)
        self.container.pack(fill=tk.BOTH, expand=True)

        # Canvas + scrollbar for scrolling (standard tkinter widgets)
        self.canvas = tk.Canvas(self.container, borderwidth=0, background="#F8F9FA")
        self.vscroll = ttk.Scrollbar(self.container, orient=tk.VERTICAL,
                                     command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vscroll.set)
        self.vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Enable mouse wheel scrolling
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self.canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Inner frame that will hold all cards – customtkinter frame
        self.inner = ctk.CTkFrame(self.canvas)
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        # self.inner.bind("<Configure>", self._on_resize)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))

        # ------------------------------------------------------------
        # Section cards – each is a CTkFrame with a 2‑column grid
        # ------------------------------------------------------------
        def make_card(parent, title):
            card = ctk.CTkFrame(parent, corner_radius=10, fg_color="#FFFFFF")
            card.grid(sticky="ew", padx=8, pady=4)
            lbl = ctk.CTkLabel(card, text=title, font=("Segoe UI", 12, "bold"), fg_color="transparent")
            lbl.grid(row=0, column=0, columnspan=2, sticky="w", padx=5, pady=5)
            return card

        self.fundamental_frame = make_card(self.inner, "Fundamental Identity")
        self.state_frame = make_card(self.inner, "Current State & Status")
        self.ema_frame = make_card(self.inner, "EMA Indicators")
        self.meta_frame = make_card(self.inner, "Candle & Update Metadata")
        self.trend_frame = make_card(self.inner, "Trend Information")
        self.triggers_frame = make_card(self.inner, "Key Date & Price Triggers")
        self.buy_signal_frame = make_card(self.inner, "Buy Signal Information")

        # Grid helper for label/value pairs (2 columns)
        for frame in [self.fundamental_frame, self.state_frame, self.ema_frame,
                      self.meta_frame, self.trend_frame, self.buy_signal_frame]:
            frame.columnconfigure(0, weight=1, minsize=150)
            frame.columnconfigure(1, weight=2, minsize=200)

        # Treeview for triggers stays inside a standard ttk.Frame for simplicity
        ttk_frame = ttk.Frame(self.triggers_frame)
        ttk_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        cols = ("event", "date", "price")
        self.triggers_tree = ttk.Treeview(ttk_frame, columns=cols, show="headings", height=6)
        for col in cols:
            self.triggers_tree.heading(col, text=col.title())
            self.triggers_tree.column(col, width=150, anchor="center")
        self.triggers_tree.pack(fill=tk.BOTH, expand=True)

        # -----------------------------------------------------------------
        # Bottom notebook inside the scrollable area
        # -----------------------------------------------------------------
        self.notebook_card = ctk.CTkFrame(self.inner, corner_radius=10, fg_color="#FFFFFF")
        self.notebook_card.grid(sticky="ew", padx=8, pady=4)
        notebook = ttk.Notebook(self.notebook_card)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.signals_frame = ttk.Frame(notebook)
        notebook.add(self.signals_frame, text="Signals")
        self.trades_frame = ttk.Frame(notebook)
        notebook.add(self.trades_frame, text="Trades")
        self.uptrends_frame = ttk.Frame(notebook)
        notebook.add(self.uptrends_frame, text="Uptrends")

        # Signals treeview
        sig_cols = ("ts", "type", "strength", "price")
        self.sig_tree = ttk.Treeview(self.signals_frame, columns=sig_cols, show="headings", height=6)
        for col in sig_cols:
            self.sig_tree.heading(col, text=col.title())
            anchor = "e" if col in ("strength", "price") else "center"
            self.sig_tree.column(col, width=100, anchor=anchor)
        self.sig_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Trades treeview
        tr_cols = ("id", "status", "entry_ts", "exit_ts", "entry_price", "exit_price", "profit_pct")
        self.tr_tree = ttk.Treeview(self.trades_frame, columns=tr_cols, show="headings", height=6)
        for col in tr_cols:
            self.tr_tree.heading(col, text=col.replace('_', ' ').title())
            anchor = "e" if col in ("entry_price", "exit_price", "profit_pct") else "center"
            self.tr_tree.column(col, width=100, anchor=anchor)
        self.tr_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Uptrends treeview
        ut_cols = ("cycle_id", "start_date", "end_date", "strength", "num_weeks",
                    "pct_above_ema", "start_price", "end_price", "roc_1w", "roc_3w",
                    "efficiency")
        self.ut_tree = ttk.Treeview(self.uptrends_frame, columns=ut_cols, show="headings", height=6)
        for col in ut_cols:
            self.ut_tree.heading(col, text=col.replace('_', ' ').title())
            anchor = "e" if col in ("num_weeks", "pct_above_ema", "start_price", "end_price",
                                     "roc_1w", "roc_3w", "efficiency") else "center"
            self.ut_tree.column(col, width=90, anchor=anchor)
        self.ut_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # ---------------------------------------------------------------------
    def _on_resize(self, event) -> None:
        """Reflow section cards based on current width (1‑3 columns)."""
        width = event.width
        if width < 700:
            cols = 1
        elif width < 1100:
            cols = 2
        else:
            cols = 3
        self._relayout_sections(cols)

    def _relayout_sections(self, columns: int) -> None:
        """Place card frames into a responsive grid."""
        frames = [self.fundamental_frame, self.state_frame, self.ema_frame,
                  self.meta_frame, self.trend_frame, self.triggers_frame,
                  self.buy_signal_frame]
        # Reset column configuration for the inner frame
        for c in range(columns):
            self.inner.columnconfigure(c, weight=1, uniform="col", minsize=350)
        for idx, frame in enumerate(frames):
            row = idx // columns
            col = idx % columns
            frame.grid_configure(row=row, column=col, sticky="ew", padx=8, pady=4)

    # ---------------------------------------------------------------------
    # Populate sections – unchanged logic, only using ttk.Labels for text
    # ---------------------------------------------------------------------
    def _populate_sections(self) -> None:
        ctx = self.context
        # Fundamental Identity
        fund_items = [
            ("Ticker", ctx.ticker),
            ("Long Name", ctx.longName),
            ("Sector", ctx.sector),
            ("Industry", ctx.industry),
            ("Market Cap", _format_market_cap(ctx.marketCap)),
            ("Website", ctx.website),
            ("ISIN", ctx.isin),
            ("Next Dividend", _format_date(ctx.nextDividendDate)),
        ]
        for r, (label, value) in enumerate(fund_items):
            ttk.Label(self.fundamental_frame, text=f"{label}:").grid(row=r+1, column=0, sticky=tk.W, padx=5, pady=2)
            if label == "Website" and value and value != "—":
                link = ttk.Label(self.fundamental_frame, text=value, foreground="blue", cursor="hand2")
                link.grid(row=r+1, column=1, sticky=tk.W, padx=5, pady=2)
                link.bind("<Button-1>", lambda e, url=value: webbrowser.open(url))
            else:
                ttk.Label(self.fundamental_frame, text=value).grid(row=r+1, column=1, sticky=tk.W, padx=5, pady=2)

        # Current State & Status
        state_items = [
            ("Current State", ctx.current_state),
            ("TR Qualified", ctx.tr_qualified),
            ("Buy Zone", ctx.is_buyzone),
            ("Warmup Complete", ctx.warmup_complete),
            ("Crossover Detected", ctx.is_crossover_detected),
        ]
        for r, (label, value) in enumerate(state_items):
            ttk.Label(self.state_frame, text=f"{label}:").grid(row=r+1, column=0, sticky=tk.W, padx=5, pady=2)
            if isinstance(value, bool):
                _bool_label(self.state_frame, text=("✓" if value else "✗"), value=value).grid(row=r+1, column=1, sticky=tk.W, padx=5, pady=2)
            else:
                ttk.Label(self.state_frame, text=_enum_name(value)).grid(row=r+1, column=1, sticky=tk.W, padx=5, pady=2)

        # EMA Indicators
        ema_items = [
            ("EMA21", _format_number(ctx.last_ema21)),
            ("EMA34", _format_number(ctx.last_ema34)),
            ("EMA55", _format_number(ctx.last_ema55)),
            ("Closes Above EMA", ctx.closes_above_ema),
            ("Closes Below EMA", ctx.closes_below_ema),
        ]
        for r, (label, value) in enumerate(ema_items):
            ttk.Label(self.ema_frame, text=f"{label}:").grid(row=r+1, column=0, sticky=tk.W, padx=5, pady=2)
            ttk.Label(self.ema_frame, text=value if value is not None else "—").grid(row=r+1, column=1, sticky=tk.W, padx=5, pady=2)

        # Trend Information
        trend_items = [
            ("Trend Start Date", _format_date(ctx.trend_start_date)),
            ("Trend End Date", _format_date(ctx.trend_end_date)),
            ("Uptrend Weeks", ctx.uptrend_weeks),
            ("Uptrend Start", _format_date(ctx.uptrend_start_date)),
            ("Current Uptrend", _enum_name(ctx.current_uptrend.strength) if ctx.current_uptrend else "—"),
        ]
        for r, (label, value) in enumerate(trend_items):
            ttk.Label(self.trend_frame, text=f"{label}:").grid(row=r+1, column=0, sticky=tk.W, padx=5, pady=2)
            ttk.Label(self.trend_frame, text=value).grid(row=r+1, column=1, sticky=tk.W, padx=5, pady=2)

        # Key Date & Price Triggers – already populated in treeview later
        trigger_rows = [
            ("Daily EMA21 Cross", _format_date(ctx.daily_ema21_cross_date),
             _format_currency(getattr(ctx, "daily_ema21_cross_price", None))),
            ("Daily Downtrend Trigger", _format_date(ctx.daily_downtrend_trigger_date),
             _format_currency(getattr(ctx, "daily_downtrend_trigger_price", None))),
            ("First Buy Zone", _format_date(ctx.first_buy_zone_date),
             _format_currency(getattr(ctx, "first_buy_zone_price", None))),
            ("Positive Crossover", _format_date(ctx.positive_crossover_date),
             _format_currency(getattr(ctx, "positive_crossover_price", None))),
        ]
        for row in trigger_rows:
            self.triggers_tree.insert("", tk.END, values=row)

        # Buy Signal Information
        buy_items = [
            ("Signal Emitted", ctx.buy_signal_emitted),
            ("Last Signal Date", _format_date(ctx.last_buy_signal_date)),
            ("Last Signal Type", _enum_name(ctx.last_buy_signal_type)),
            ("Last Signal Crossover", _format_date(ctx.last_buy_signal_crossover_date)),
        ]
        for r, (label, value) in enumerate(buy_items):
            ttk.Label(self.buy_signal_frame, text=f"{label}:").grid(row=r+1, column=0, sticky=tk.W, padx=5, pady=2)
            if isinstance(value, bool):
                _bool_label(self.buy_signal_frame, text=("✓" if value else "✗"), value=value).grid(row=r+1, column=1, sticky=tk.W, padx=5, pady=2)
            else:
                ttk.Label(self.buy_signal_frame, text=value or "—").grid(row=r+1, column=1, sticky=tk.W, padx=5, pady=2)

        # Candle & Update Metadata
        meta_items = [
            ("Weekly Candle Count", ctx.weekly_candle_count),
            ("Candle Count", ctx.candle_count),
            ("Last Update", _format_date(ctx.last_update)),
            ("Classification", _enum_name(ctx.classification)),
        ]
        for r, (label, value) in enumerate(meta_items):
            ttk.Label(self.meta_frame, text=f"{label}:").grid(row=r+1, column=0, sticky=tk.W, padx=5, pady=2)
            ttk.Label(self.meta_frame, text=value if value is not None else "—").grid(row=r+1, column=1, sticky=tk.W, padx=5, pady=2)

        # Last Close row with EMA21 percentage difference
        r = len(meta_items)
        close_val = ctx.last_close
        ema21_val = ctx.last_ema21
        close_text = _format_currency(close_val)
        pct_str = ""
        fg = None
        if close_val is not None and ema21_val is not None and ema21_val != 0:
            pct = (close_val - ema21_val) / ema21_val * 100
            sign = "+" if pct >= 0 else ""
            pct_str = f" ({sign}{pct:.2f}%)"
            if pct < 0:
                fg = "red"
            elif pct <= 5:
                fg = "green"
            else:
                fg = "#333333"
        ttk.Label(self.meta_frame, text="Last Close:").grid(row=r+1, column=0, sticky=tk.W, padx=5, pady=2)
        val_label = ttk.Label(self.meta_frame, text=close_text + pct_str)
        if fg:
            val_label.configure(foreground=fg)
        val_label.grid(row=r+1, column=1, sticky=tk.W, padx=5, pady=2)

    # ---------------------------------------------------------------------
    # Populate Signals and Trades tables – unchanged logic
    # ---------------------------------------------------------------------
    def _populate_signals(self) -> None:
        for sig in self.signals:
            ts = _format_date(getattr(sig, "date", None))
            typ = _enum_name(getattr(sig, "signal_type", ""))
            strength = _format_number(getattr(sig, "strength", None))
            price = _format_currency(getattr(sig, "close_price", None))
            self.sig_tree.insert("", tk.END, values=(ts, typ, strength, price))

    def _populate_trades(self) -> None:
        for tr in self.trades:
            tr_id = getattr(tr, "id", "")
            status = _enum_name(getattr(tr, "status", ""))
            entry_ts = _format_date(getattr(tr, "entry_date", None))
            exit_ts = _format_date(getattr(tr, "exit_date", None))
            entry_price = _format_currency(getattr(tr, "entry_price", None))
            exit_price = _format_currency(getattr(tr, "exit_price", None))
            profit_pct = _format_number(getattr(tr, "profit_loss_pct", None))
            self.tr_tree.insert("", tk.END, values=(tr_id, status, entry_ts, exit_ts,
                                               entry_price, exit_price, profit_pct))

    def _populate_uptrends(self) -> None:
        """Populate the Uptrends treeview from context.uptrend_history."""
        uptrends = getattr(self.context, "uptrend_history", [])
        if not uptrends:
            return
        for ut in uptrends:
            cycle_id = getattr(ut, "cycle_id", "")
            start_date = _format_date(getattr(ut, "start_date", None))
            end_date = _format_date(getattr(ut, "end_date", None))
            strength = _enum_name(getattr(ut, "strength", None))
            num_weeks = getattr(ut, "num_weeks", 0)
            pct_above = _format_number(getattr(ut, "pct_closes_above", None), 1)
            start_price = _format_currency(getattr(ut, "start_price", None))
            end_price = _format_currency(getattr(ut, "end_price", None))
            roc_1w = _format_number(getattr(ut, "roc_1w_pct", None), 1)
            roc_3w = _format_number(getattr(ut, "roc_3w_pct", None), 1)
            efficiency = _format_number(getattr(ut, "efficiency_ratio", None), 3)
            self.ut_tree.insert("", tk.END, values=(
                cycle_id, start_date, end_date, strength, num_weeks,
                pct_above, start_price, end_price, roc_1w, roc_3w, efficiency
            ))