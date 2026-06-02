from datetime import datetime, timezone, timedelta
from trend_rider_lib.downloader.yfinance_downloader import YFinanceDownloader

# Use a date 5 days ago to ensure there is new data
last = datetime.now(timezone.utc) - timedelta(days=5)
print('Calling download_incremental with last_date =', last.isoformat())

df = YFinanceDownloader.download_incremental('AAPL', last, interval='1d')
print('Rows:', len(df))
print(df.head())
