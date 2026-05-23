"""
OHLC data resampling utilities.
"""
import pandas as pd


def resample_daily_to_weekly(daily_df: pd.DataFrame) -> pd.DataFrame:
    """
    Resample daily OHLC data to weekly OHLC.
    Week ends on Friday.

    Args:
        daily_df: DataFrame with columns Open, High, Low, Close, Volume
                  Index must be DatetimeIndex

    Returns:
        DataFrame with weekly OHLC data
    """
    weekly = daily_df.resample('W-FRI').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }).dropna()

    return weekly
