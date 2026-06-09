"""
Indicators module containing EMA calculations and zone detection.
"""
from .resampler import resample_daily_to_weekly
from .ema_engine import (
    compute_weekly_ema21,
    compute_daily_ema34,
    compute_daily_ema55,
    incremental_ema,
    enrich_with_indicators,
)
from .flag_computer import candle_intersects_buy_zone, compute_zone_flags, mark_warmup_complete

__all__ = [
    "resample_daily_to_weekly",
    "compute_weekly_ema21",
    "compute_daily_ema34",
    "compute_daily_ema55",
    "incremental_ema",
    "enrich_with_indicators",
    "compute_zone_flags",
    "candle_intersects_buy_zone",
    "mark_warmup_complete",
]
