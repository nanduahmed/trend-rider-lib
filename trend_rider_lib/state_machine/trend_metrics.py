"""
Trend analytics helpers for lifecycle records.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import numpy as np

from ..core.models import UptrendRecord


def _append_point(history: list, date: datetime, value: Optional[float]) -> None:
    if date is None or value is None:
        return
    history.append((date, float(value)))


def _roc(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    if current is None or previous in (None, 0):
        return None
    return ((current - previous) / previous) * 100.0


def _normalized_regression_slope(points: list[tuple[datetime, float]]) -> Optional[float]:
    if len(points) < 2:
        return None

    values = np.array([value for _, value in points], dtype=float)
    x = np.arange(len(values), dtype=float)
    slope, _intercept = np.polyfit(x, values, 1)
    mean_value = float(np.mean(values))
    if mean_value == 0:
        return None
    return float((slope / mean_value) * 100.0)


def _efficiency_ratio(points: list[tuple[datetime, float]]) -> Optional[float]:
    if len(points) < 2:
        return None

    closes = [value for _, value in points]
    numerator = abs(closes[-1] - closes[0])
    denominator = sum(abs(curr - prev) for prev, curr in zip(closes, closes[1:]))
    if denominator == 0:
        return None
    return float(numerator / denominator)


def record_daily_point(
    uptrend: UptrendRecord,
    date: datetime,
    close: Optional[float],
    ema21: Optional[float],
    ema34: Optional[float],
    ema55: Optional[float],
) -> None:
    """Track daily history for active analytics."""
    _append_point(uptrend.daily_close_history, date, close)
    _append_point(uptrend.daily_ema21_history, date, ema21)
    _append_point(uptrend.daily_ema34_history, date, ema34)
    _append_point(uptrend.daily_ema55_history, date, ema55)


def record_weekly_point(
    uptrend: UptrendRecord,
    date: datetime,
    close: Optional[float],
) -> None:
    """Track weekly history for ROC metrics."""
    _append_point(uptrend.weekly_close_history, date, close)


def update_trend_metrics(uptrend: UptrendRecord, current_close: Optional[float]) -> None:
    """Recompute summary analytics for an active trend record."""
    if uptrend.first_buy_zone_price is None:
        return

    anchor = uptrend.first_buy_zone_price
    if anchor == 0:
        return

    if uptrend.highest_price is not None:
        uptrend.max_profit_pct = ((uptrend.highest_price - anchor) / anchor) * 100.0
        uptrend.ath_price = uptrend.highest_price
        uptrend.ath_date = uptrend.highest_price_date
    else:
        uptrend.max_profit_pct = None

    if current_close is not None:
        uptrend.trend_roc_pct = ((current_close - anchor) / anchor) * 100.0

        if uptrend.ath_price is not None:
            uptrend.distance_from_ath_abs = uptrend.ath_price - current_close
            uptrend.distance_from_ath_pct = ((uptrend.ath_price - current_close) / uptrend.ath_price) * 100.0

    if uptrend.weekly_close_history:
        weekly_closes = [value for _, value in uptrend.weekly_close_history]
        if len(weekly_closes) > 1:
            uptrend.roc_1w_pct = _roc(weekly_closes[-1], weekly_closes[-2])
        if len(weekly_closes) > 3:
            uptrend.roc_3w_pct = _roc(weekly_closes[-1], weekly_closes[-4])
        if len(weekly_closes) > 26:
            uptrend.roc_6m_pct = _roc(weekly_closes[-1], weekly_closes[-27])
        if len(weekly_closes) > 39:
            uptrend.roc_9m_pct = _roc(weekly_closes[-1], weekly_closes[-40])

    uptrend.ema21_slope = _normalized_regression_slope(uptrend.daily_ema21_history[-10:])

    if uptrend.daily_ema34_history and uptrend.daily_ema55_history:
        ema34 = uptrend.daily_ema34_history[-1][1]
        ema55 = uptrend.daily_ema55_history[-1][1]
        uptrend.ema34_55_spread = ema34 - ema55
        if ema55 != 0:
            uptrend.ema34_55_spread_pct = ((ema34 - ema55) / ema55) * 100.0

    uptrend.efficiency_ratio = _efficiency_ratio(uptrend.daily_close_history)

