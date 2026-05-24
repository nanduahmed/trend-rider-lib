"""
Data downloader wrapper for yfinance.
"""
import logging
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import pandas as pd

try:
    import yfinance as yf
except ImportError:
    raise ImportError(
        "yfinance is required. Install with: pip install yfinance"
    )


logger = logging.getLogger(__name__)


class YFinanceDownloader:
    """
    Wrapper for yfinance to download OHLC data.
    Returns DataFrames directly, no persistence.
    """

    @staticmethod
    def download_full_history(
        ticker: str,
        start_date: str,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Download full historical daily OHLC data.

        Args:
            ticker: Stock symbol (e.g., 'AAPL')
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format (default: today)

        Returns:
            DataFrame with columns Open, High, Low, Close, Volume
            Index is DatetimeIndex

        Raises:
            Exception: If download fails
        """
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')

        try:
            stock = yf.Ticker(ticker)
            df = stock.history(start=start_date, end=end_date, interval='1d')

            if df.empty:
                return pd.DataFrame()

            # Clean column names
            df.columns = ['Open', 'High', 'Low', 'Close', 'Volume', 'Dividends', 'Stock Splits']

            # Keep only OHLCV
            df = df[['Open', 'High', 'Low', 'Close', 'Volume']]

            return df

        except Exception as e:
            logger.warning("Error downloading %s: %s", ticker, e)
            return pd.DataFrame()

    @staticmethod
    def download_incremental(
        ticker: str,
        last_date: datetime,
        interval: str = '1d'
    ) -> pd.DataFrame:
        """
        Download only new candles since last update.

        Args:
            ticker: Stock symbol
            last_date: Last known date in database
            interval: '1d' for daily, '1wk' for weekly

        Returns:
            DataFrame with new candles, or empty DataFrame if no new data
        """
        start_date = last_date + timedelta(days=1)
        end_date = datetime.now()

        if start_date >= end_date:
            return pd.DataFrame()

        try:
            stock = yf.Ticker(ticker)
            df = stock.history(
                start=start_date.strftime('%Y-%m-%d'),
                end=end_date.strftime('%Y-%m-%d'),
                interval=interval
            )

            if df.empty:
                return pd.DataFrame()

            # Clean column names
            df.columns = ['Open', 'High', 'Low', 'Close', 'Volume', 'Dividends', 'Stock Splits']
            df = df[['Open', 'High', 'Low', 'Close', 'Volume']]

            # Add timeframe column
            df['timeframe'] = 'weekly' if interval == '1wk' else 'daily'

            return df

        except Exception as e:
            logger.warning("Error downloading incremental data for %s: %s", ticker, e)
            return pd.DataFrame()

    @staticmethod
    def download_bulk(
        tickers: List[str],
        start_date: str,
        end_date: Optional[str] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Download data for multiple tickers.

        Args:
            tickers: List of stock symbols
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format (default: today)

        Returns:
            Dictionary mapping ticker → DataFrame
        """
        results = {}

        for ticker in tickers:
            df = YFinanceDownloader.download_full_history(ticker, start_date, end_date)
            if not df.empty:
                results[ticker] = df

        return results
