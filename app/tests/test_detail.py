"""Test script to verify DetailWindow works properly."""
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
from datetime import datetime

# Test importing DetailWindow
try:
    from app.views.detail_window import DetailWindow
    print("✓ DetailWindow imported successfully")
except ImportError as e:
    print(f"✗ Import error: {e}")
    exit(1)

# Create a dummy context for testing
from trend_rider_lib.core.models import StockContext, SignalEvent, TradeRecord

# StockContext constructor only accepts these parameters:
ctx = StockContext(
    ticker="TIINDIA.NS",
    longName="Tube Investments of India Limited",
    sector="Industrials",
    industry="Auto Parts",
    marketCap=1e7,
    website="https://www.tiindia.com",
    isin="INE485J01029",
    current_state="UPTREND",
    tr_qualified=True,
    is_buyzone=False,
    is_crossover_detected=False,
    last_ema21=95.0,
    last_ema34=90.0,
    last_ema55=85.0,
    closes_above_ema=3,
    closes_below_ema=0,
    uptrend_weeks=4,
    weekly_candle_count=10,
    crossover_date=None,
    crossover_price=None,
    nextDividendDate=None,
    trend_start_date=datetime.now().isoformat(),
    trend_end_date=None,
    daily_ema21_cross_date=None,
    daily_downtrend_trigger_date=None,
    first_buy_zone_date=None,
    positive_crossover_date=None,
)

# Set extra fields that are not in constructor
ctx.last_close = 100.0
ctx.last_update = datetime.now()
ctx.warmup_complete = True
ctx.candle_count = 50
ctx.current_uptrend = None
ctx.classification = None
ctx.daily_ema21_cross_price = None
ctx.daily_downtrend_trigger_price = None
ctx.first_buy_zone_price = None
ctx.positive_crossover_price = None
ctx.buy_signal_emitted = True
ctx.last_buy_signal_date = datetime.now()
ctx.last_buy_signal_type = "BUY"
ctx.last_buy_signal_crossover_date = datetime.now()
ctx.uptrend_start_date = datetime.now()

signals = []
trades = []

# Create a test window
root = ctk.CTk()
root.title("Test DetailWindow")
root.geometry("400x200")

def open_detail():
    detail = DetailWindow(root, ctx, signals, trades)

btn = ctk.CTkButton(root, text="Open DetailWindow", command=open_detail)
btn.pack(pady=50)

print("✓ Test window created. Click 'Open DetailWindow' to test.")
root.mainloop()