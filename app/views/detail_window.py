import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
from datetime import datetime
import locale
import pandas as pd
from typing import Optional, List

from trend_rider_lib.core.models import StockContext, SignalEvent, TradeRecord


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


class DetailWindow(tk.Toplevel):
    """Display full information for a single ticker using grouped sections."""

    def __init__(self, master: tk.Widget, context: StockContext,
                 signals: List[SignalEvent], trades: List[TradeRecord]):
        super().__init__(master)
        self.title(f"Details – {getattr(context, 'ticker', '')}")
        self.geometry("900x700")
        self.context = context
        self.signals = signals
        self.trades = trades

        self._build_ui()
        self._populate_sections()
        self._populate_signals()
        self._populate_trades()

    # --------------------------------------------------------------------- #
    # UI construction
    # --------------------------------------------------------------------- #
    def _build_ui(self) -> None:
        """Create a scrollable canvas containing labelled sections."""
        # ----- main container ------------------------------------------------
        self.container = ttk.Frame(self)
        self.container.pack(fill=tk.BOTH, expand=True)

        # ----- canvas + scrollbar for scrolling -------------------------------
        self.canvas = tk.Canvas(self.container, borderwidth=0)
        self.vscroll = ttk.Scrollbar(self.container, orient=tk.VERTICAL,
                                     command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vscroll.set)

        self.vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # ----- inner frame where all sections will live -----------------------
        self.inner = ttk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        # Bind resize to reflow sections
        self.inner.bind("<Configure>", self._on_resize)

        self.inner.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))

        # ----- style for section headers ------------------------------------
        style = ttk.Style()
        style.configure("Header.TLabel", font=("Segoe UI", 10, "bold"))

        # ----- Section: Fundamental Identity ---------------------------------
        self.fundamental_frame = ttk.LabelFrame(
            self.inner, text="Fundamental Identity")
        self.fundamental_frame.grid(row=0, column=0,
                                   sticky="ew", padx=8, pady=4)
        self._make_grid(self.fundamental_frame)

        # ----- Section: Current State & Status -------------------------------
        self.state_frame = ttk.LabelFrame(
            self.inner, text="Current State & Status")
        self.state_frame.grid(row=1, column=0,
                              sticky="ew", padx=8, pady=4)
        self._make_grid(self.state_frame)

        # ----- Section: EMA Indicators ---------------------------------------
        self.ema_frame = ttk.LabelFrame(self.inner, text="EMA Indicators")
        self.ema_frame.grid(row=2, column=0,
                             sticky="ew", padx=8, pady=4)
        self._make_grid(self.ema_frame)

        # ----- Section: Trend Information -----------------------------------
        self.trend_frame = ttk.LabelFrame(
            self.inner, text="Trend Information")
        self.trend_frame.grid(row=3, column=0,
                              sticky="ew", padx=8, pady=4)
        self._make_grid(self.trend_frame)

        # ----- Section: Key Date & Price Triggers ---------------------------
        self.triggers_frame = ttk.LabelFrame(
            self.inner, text="Key Date & Price Triggers")
        self.triggers_frame.grid(row=4, column=0,
                                 sticky="ew", padx=8, pady=4)
        # Treeview for triggers
        cols = ("event", "date", "price")
        self.triggers_tree = ttk.Treeview(
            self.triggers_frame, columns=cols, show="headings", height=6)
        for col in cols:
            self.triggers_tree.heading(col, text=col.title())
            self.triggers_tree.column(col, width=150, anchor="center")
        self.triggers_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # ----- Section: Buy Signal Information -----------------------------
        self.buy_signal_frame = ttk.LabelFrame(
            self.inner, text="Buy Signal Information")
        self.buy_signal_frame.grid(row=5, column=0,
                                   sticky="ew", padx=8, pady=4)
        self._make_grid(self.buy_signal_frame)

        # ----- Section: Candle & Update Metadata ---------------------------
        self.meta_frame = ttk.LabelFrame(
            self.inner, text="Candle & Update Metadata")
        self.meta_frame.grid(row=6, column=0,
                             sticky="ew", padx=8, pady=4)
        self._make_grid(self.meta_frame)

        # ----- Signals and Trades tabs (keep existing layout) ---------------
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True)
        self.signals_frame = ttk.Frame(notebook)
        notebook.add(self.signals_frame, text="Signals")
        self.trades_frame = ttk.Frame(notebook)
        notebook.add(self.trades_frame, text="Trades")

        # Signals treeview
        sig_cols = ("ts", "type", "strength", "price")
        self.sig_tree = ttk.Treeview(self.signals_frame, columns=sig_cols,
                                     show="headings")
        for col in sig_cols:
            self.sig_tree.heading(col, text=col.title())
            anchor = "e" if col in ("strength", "price") else "center"
            self.sig_tree.column(col, width=100, anchor=anchor)
        self.sig_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Trades treeview
        tr_cols = ("id", "status", "entry_ts", "exit_ts",
                   "entry_price", "exit_price", "profit_pct")
        self.tr_tree = ttk.Treeview(self.trades_frame, columns=tr_cols,
                                    show="headings")
        for col in tr_cols:
            self.tr_tree.heading(col, text=col.replace('_', ' ').title())
            anchor = "e" if col in ("entry_price", "exit_price", "profit_pct") else "center"
            self.tr_tree.column(col, width=100, anchor=anchor)
        self.tr_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _make_grid(self, frame: ttk.LabelFrame) -> None:
        """Configure a 2‑column grid helper for label/value pairs."""
        frame.columnconfigure(0, weight=1, minsize=150)
        frame.columnconfigure(1, weight=2, minsize=200)

    # --------------------------------------------------------------------- #
    # Responsive layout handling
    # --------------------------------------------------------------------- #
    def _on_resize(self, event) -> None:
        """Reflow sections based on current width."""
        width = event.width
        if width < 700:
            cols = 1
        elif width < 1100:
            cols = 2
        else:
            cols = 3
        self._relayout_sections(cols)

    def _relayout_sections(self, columns: int) -> None:
        """Place section frames into a responsive grid."""
        frames = [
            self.fundamental_frame,
            self.state_frame,
            self.ema_frame,
            self.trend_frame,
            self.triggers_frame,
            self.buy_signal_frame,
            self.meta_frame,
        ]
        # Clear any existing column configurations
        for c in range(columns):
            self.inner.columnconfigure(c, weight=1, uniform="col", minsize=350)

        for idx, frame in enumerate(frames):
            row = idx // columns
            col = idx % columns
            frame.grid_configure(row=row, column=col, sticky="ew", padx=8, pady=4)

    # --------------------------------------------------------------------- #
    # Populate grouped sections
    # --------------------------------------------------------------------- #
    def _populate_sections(self) -> None:
        ctx = self.context

        # ---- Fundamental Identity -----------------------------------------
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
            ttk.Label(self.fundamental_frame,
                      text=f"{label}:").grid(row=r, column=0,
                                            sticky=tk.W, padx=5, pady=2)
            if label == "Website" and value and value != "—":
                link = ttk.Label(self.fundamental_frame, text=value,
                                 foreground="blue", cursor="hand2")
                link.grid(row=r, column=1, sticky=tk.W, padx=5, pady=2)
                link.bind("<Button-1>", lambda e, url=value: webbrowser.open(url))
            else:
                ttk.Label(self.fundamental_frame,
                          text=value).grid(row=r, column=1,
                                          sticky=tk.W, padx=5, pady=2)

        # ---- Current State & Status ----------------------------------------
        state_items = [
            ("Current State", ctx.current_state),
            ("TR Qualified", ctx.tr_qualified),
            ("Buy Zone", ctx.is_buyzone),
            ("Warmup Complete", ctx.warmup_complete),
            ("Crossover Detected", ctx.is_crossover_detected),
        ]
        for r, (label, value) in enumerate(state_items):
            ttk.Label(self.state_frame,
                      text=f"{label}:").grid(row=r, column=0,
                                            sticky=tk.W, padx=5, pady=2)
            if isinstance(value, bool):
                _bool_label(self.state_frame,
                            text=("✓" if value else "✗"), value=value).grid(
                    row=r, column=1, sticky=tk.W, padx=5, pady=2)
            else:
                ttk.Label(self.state_frame,
                          text=value or "—").grid(row=r, column=1,
                                                sticky=tk.W, padx=5, pady=2)

        # ---- EMA Indicators -------------------------------------------------
        ema_items = [
            ("EMA21", _format_number(ctx.last_ema21)),
            ("EMA34", _format_number(ctx.last_ema34)),
            ("EMA55", _format_number(ctx.last_ema55)),
            ("Closes Above EMA", ctx.closes_above_ema),
            ("Closes Below EMA", ctx.closes_below_ema),
        ]
        for r, (label, value) in enumerate(ema_items):
            ttk.Label(self.ema_frame,
                      text=f"{label}:").grid(row=r, column=0,
                                            sticky=tk.W, padx=5, pady=2)
            ttk.Label(self.ema_frame,
                      text=value if value is not None else "—").grid(
                row=r, column=1, sticky=tk.W, padx=5, pady=2)

        # ---- Trend Information -----------------------------------------------
        trend_items = [
            ("Trend Start Date", _format_date(ctx.trend_start_date)),
            ("Trend End Date", _format_date(ctx.trend_end_date)),
            ("Uptrend Weeks", ctx.uptrend_weeks),
            ("Uptrend Start", _format_date(ctx.uptrend_start_date)),
            ("Current Uptrend", str(ctx.current_uptrend) if ctx.current_uptrend else "—"),
        ]
        for r, (label, value) in enumerate(trend_items):
            ttk.Label(self.trend_frame,
                      text=f"{label}:").grid(row=r, column=0,
                                            sticky=tk.W, padx=5, pady=2)
            ttk.Label(self.trend_frame,
                      text=value).grid(row=r, column=1,
                                      sticky=tk.W, padx=5, pady=2)

        # ---- Key Date & Price Triggers --------------------------------------
        trigger_rows = [
            ("Daily EMA21 Cross", _format_date(ctx.daily_ema21_cross_date),
             _format_currency(getattr(ctx, "daily_ema21_cross_price", None))),
            ("Daily Downtrend Trigger", _format_date(ctx.daily_downtrend_trigger_date),
             _format_currency(getattr(ctx, "daily_downtrend_trigger_price", None))),
            ("First Buy Zone", _format_date(ctx.first_buy_zone_date),
             _format_currency(getattr(ctx, "first_buy_zone_price", None))),
            ("Positive Crossover", _format_date(ctx.positive_crossover_date),
             _format_currency(getattr(ctx, "positive_crossover_price", None))),
            ("Crossover", _format_date(ctx.crossover_date),
             _format_currency(ctx.crossover_price)),
        ]
        for row in trigger_rows:
            self.triggers_tree.insert("", tk.END, values=row)

        # ---- Buy Signal Information -----------------------------------------
        buy_items = [
            ("Signal Emitted", ctx.buy_signal_emitted),
            ("Last Signal Date", _format_date(ctx.last_buy_signal_date)),
            ("Last Signal Type", ctx.last_buy_signal_type),
            ("Last Signal Crossover",
             _format_date(ctx.last_buy_signal_crossover_date)),
        ]
        for r, (label, value) in enumerate(buy_items):
            ttk.Label(self.buy_signal_frame,
                      text=f"{label}:").grid(row=r, column=0,
                                            sticky=tk.W, padx=5, pady=2)
            if isinstance(value, bool):
                _bool_label(self.buy_signal_frame,
                            text=("✓" if value else "✗"),
                            value=value).grid(row=r, column=1,
                                             sticky=tk.W, padx=5, pady=2)
            else:
                ttk.Label(self.buy_signal_frame,
                          text=value or "—").grid(row=r, column=1,
                                                sticky=tk.W, padx=5, pady=2)

        # ---- Candle & Update Metadata ---------------------------------------
        meta_items = [
            ("Weekly Candle Count", ctx.weekly_candle_count),
            ("Candle Count", ctx.candle_count),
            ("Last Close", _format_currency(ctx.last_close)),
            ("Last Update", _format_date(ctx.last_update)),
            ("Classification", str(ctx.classification) if ctx.classification else "—"),
        ]
        for r, (label, value) in enumerate(meta_items):
            ttk.Label(self.meta_frame,
                      text=f"{label}:").grid(row=r, column=0,
                                            sticky=tk.W, padx=5, pady=2)
            ttk.Label(self.meta_frame,
                      text=value if value is not None else "—").grid(
                row=r, column=1, sticky=tk.W, padx=5, pady=2)

    # --------------------------------------------------------------------- #
    # Populate Signals and Trades tables
    # --------------------------------------------------------------------- #
    def _populate_signals(self) -> None:
        for sig in self.signals:
            ts = _format_date(getattr(sig, "date", None))
            typ = getattr(sig, "signal_type", "")
            strength = _format_number(getattr(sig, "strength", None))
            price = _format_currency(getattr(sig, "close_price", None))
            self.sig_tree.insert("", tk.END,
                                 values=(ts, typ, strength, price))

    def _populate_trades(self) -> None:
        for tr in self.trades:
            tr_id = getattr(tr, "id", "")
            status = getattr(tr, "status", "")
            entry_ts = _format_date(getattr(tr, "entry_date", None))
            exit_ts = _format_date(getattr(tr, "exit_date", None))
            entry_price = _format_currency(getattr(tr, "entry_price", None))
            exit_price = _format_currency(getattr(tr, "exit_price", None))
            profit_pct = _format_number(getattr(tr, "profit_loss_pct", None))
            self.tr_tree.insert(
                "",
                tk.END,
                values=(tr_id, status, entry_ts, exit_ts,
                        entry_price, exit_price, profit_pct),
            )
