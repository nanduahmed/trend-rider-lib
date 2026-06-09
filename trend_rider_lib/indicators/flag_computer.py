"""
Vectorized flag computation for buy zones and downtrend triggers.
"""
import pandas as pd
import numpy as np


def candle_intersects_buy_zone(
    open_price: float,
    close: float,
    ema21: float,
    buy_zone_upper_pct: float = 0.05
) -> bool:
    """Return True when a green candle qualifies against the EMA21 buy zone."""
    values = [open_price, close, ema21]
    if any(pd.isna(value) for value in values):
        return False

    upper_bound = ema21 * (1 + buy_zone_upper_pct)
    return close > open_price and close > ema21 and open_price <= upper_bound


def compute_zone_flags(
    df: pd.DataFrame,
    buy_zone_upper_pct: float = 0.05,
    downtrend_trigger_pct: float = 0.10
) -> pd.DataFrame:
    """
    Vectorized computation of zone flags.

    Adds columns:
    - is_buyzone: True if green candle opens below/inside upper band and closes above EMA21
    - is_above_buyzone: True if price above buy zone (close > EMA21 * 1.05)
    - is_downtrend_trigger: True if downtrend triggered (close < EMA21 * 0.90)

    Args:
        df: DataFrame with Open, Close, and EMA21 columns
        buy_zone_upper_pct: Upper bound of buy zone as fraction above EMA21
        downtrend_trigger_pct: Downtrend trigger as fraction below EMA21

    Returns:
        DataFrame with zone flag columns added
    """
    df = df.copy()

    # Initialize flag columns
    df['is_buyzone'] = False
    df['is_above_buyzone'] = False
    df['is_downtrend_trigger'] = False

    # Only compute for rows with valid EMA21
    has_ema = df['EMA21'].notna()

    if has_ema.any():
        ema21 = df.loc[has_ema, 'EMA21']
        close = df.loc[has_ema, 'Close']
        open_price = df.loc[has_ema, 'Open']

        # Buy zone: green candle opens below/inside upper band and closes above EMA21.
        buy_zone_upper = ema21 * (1 + buy_zone_upper_pct)
        is_green = close > open_price
        qualifies_buy_zone = (close > ema21) & (open_price <= buy_zone_upper)
        df.loc[has_ema, 'is_buyzone'] = is_green & qualifies_buy_zone

        # Above buy zone: close > EMA21 * (1 + buy_zone_upper_pct)
        df.loc[has_ema, 'is_above_buyzone'] = close > buy_zone_upper

        # Downtrend trigger: close < EMA21 * (1 - downtrend_trigger_pct)
        downtrend_level = ema21 * (1 - downtrend_trigger_pct)
        df.loc[has_ema, 'is_downtrend_trigger'] = close < downtrend_level

    return df


def mark_warmup_complete(df: pd.DataFrame, warmup_weeks: int = 25) -> pd.DataFrame:
    """
    Mark rows after warmup period as complete.

    Args:
        df: DataFrame with timeframe column (should have 'weekly' rows)
        warmup_weeks: Number of weeks in warmup period

    Returns:
        DataFrame with warmup_complete column added
    """
    df = df.copy()
    df['warmup_complete'] = False

    weekly_index = df.index[df['timeframe'] == 'weekly']
    if len(weekly_index) >= warmup_weeks:
        # Mark only weekly rows after the warmup window as complete.
        warmup_end_index = weekly_index[warmup_weeks:]
        df.loc[df.index.isin(warmup_end_index), 'warmup_complete'] = True

    return df
