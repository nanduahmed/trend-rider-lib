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
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Download full historical daily OHLC data.

        Args:
            ticker: Stock symbol (e.g., 'AAPL')
            start_date: Start date in YYYY-MM-DD format. If omitted, downloads
                the maximum available history from the data source.
            end_date: End date in YYYY-MM-DD format (default: today when a
                start date is supplied, otherwise used as an upper bound on the
                maximum history download)

        Returns:
            DataFrame with columns Open, High, Low, Close, Volume
            Index is DatetimeIndex

        Raises:
            Exception: If download fails
        """
        try:
            stock = yf.Ticker(ticker)
            if start_date:
                if not end_date:
                    end_date = datetime.now().strftime('%Y-%m-%d')
                df = stock.history(start=start_date, end=end_date, interval='1d')
            else:
                df = stock.history(period='max', interval='1d')
                if end_date:
                    df = df.loc[:end_date]

            if df.empty:
                return pd.DataFrame()

            # Keep only OHLCV columns that are actually present in the result.
            expected_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            available_columns = [column for column in expected_columns if column in df.columns]
            if not available_columns:
                return pd.DataFrame()
            df = df[available_columns].copy()

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
        end_date = datetime.now(last_date.tzinfo) if last_date.tzinfo else datetime.now()
        
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
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Download data for multiple tickers.

        Args:
            tickers: List of stock symbols
            start_date: Start date in YYYY-MM-DD format. If omitted, downloads
                the maximum available history from the data source.
            end_date: End date in YYYY-MM-DD format (default: today when a
                start date is supplied)

        Returns:
            Dictionary mapping ticker → DataFrame
        """
        results = {}

        for ticker in tickers:
            df = YFinanceDownloader.download_full_history(ticker, start_date, end_date)
            if not df.empty:
                results[ticker] = df

        return results
