"""
EMA indicator calculation engine using TA-Lib.
"""
from typing import Optional
import pandas as pd
import numpy as np

try:
    import talib
except ImportError:
    raise ImportError(
        "TA-Lib is required. Install with: pip install TA-Lib"
    )


def compute_weekly_ema21(weekly_df: pd.DataFrame, period: int = 21) -> pd.Series:
    """
    Calculate EMA21 on weekly close prices using TA-Lib.

    Args:
        weekly_df: DataFrame with Close column
        period: EMA period (default 21)

    Returns:
        Series with EMA values
    """
    return pd.Series(
        talib.EMA(weekly_df['Close'].values, timeperiod=period),
        index=weekly_df.index
    )


def compute_daily_ema34(daily_df: pd.DataFrame, period: int = 34) -> pd.Series:
    """
    Calculate EMA34 on daily close prices.

    Args:
        daily_df: DataFrame with Close column
        period: EMA period (default 34)

    Returns:
        Series with EMA values
    """
    return pd.Series(
        talib.EMA(daily_df['Close'].values, timeperiod=period),
        index=daily_df.index
    )


def compute_daily_ema55(daily_df: pd.DataFrame, period: int = 55) -> pd.Series:
    """
    Calculate EMA55 on daily close prices.

    Args:
        daily_df: DataFrame with Close column
        period: EMA period (default 55)

    Returns:
        Series with EMA values
    """
    return pd.Series(
        talib.EMA(daily_df['Close'].values, timeperiod=period),
        index=daily_df.index
    )


def incremental_ema(previous_ema: float, new_price: float, period: int) -> float:
    """
    Calculate new EMA value incrementally without full recalculation.

    Formula: EMA = price * k + previous_ema * (1 - k)
    where k = 2 / (period + 1)

    Args:
        previous_ema: Previous EMA value
        new_price: New price data point
        period: EMA period

    Returns:
        New EMA value
    """
    k = 2.0 / (period + 1)
    return new_price * k + previous_ema * (1 - k)


def enrich_with_indicators(
    df: pd.DataFrame,
    ema21_period: int = 21,
    ema34_period: int = 34,
    ema55_period: int = 55
) -> pd.DataFrame:
    """
    Add all required technical indicators to DataFrame.

    Expects 'timeframe' column to distinguish daily vs weekly rows.
    Adds EMA21 for weekly data, EMA34 and EMA55 for daily data.

    Args:
        df: DataFrame with OHLCV data and 'timeframe' column
        ema21_period: Period for weekly EMA
        ema34_period: Period for daily fast EMA
        ema55_period: Period for daily slow EMA

    Returns:
        DataFrame with indicator columns added
    """
    df = df.copy()

    # Initialize EMA columns
    df['EMA21'] = np.nan
    df['EMA34'] = np.nan
    df['EMA55'] = np.nan

    # Weekly indicators
    weekly_mask = df['timeframe'] == 'weekly'
    if weekly_mask.any():
        weekly_data = df[weekly_mask]
        if len(weekly_data) > 0:
            weekly_ema21 = compute_weekly_ema21(weekly_data, ema21_period)
            df.loc[weekly_mask, 'EMA21'] = weekly_ema21.values

    # Daily indicators
    daily_mask = df['timeframe'] == 'daily'
    if daily_mask.any():
        daily_data = df[daily_mask]
        if len(daily_data) > 0:
            daily_ema34 = compute_daily_ema34(daily_data, ema34_period)
            daily_ema55 = compute_daily_ema55(daily_data, ema55_period)
            df.loc[daily_mask, 'EMA34'] = daily_ema34.values
            df.loc[daily_mask, 'EMA55'] = daily_ema55.values

    return df
