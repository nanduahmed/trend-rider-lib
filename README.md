# Trend Rider V0.81 Library
A sophisticated stock trend analysis and trading system using EMA indicators, finite state machine architecture, and trailing stop-loss mechanics for automated trade management.

## Features
- **EMA-Based Trend Analysis**: Weekly EMA21 for trend direction, daily EMA34/EMA55 for recovery detection
- **State Machine Architecture**: Seven distinct states tracking stock progression from warmup through qualified status
- **Automatic Qualification**: Stocks qualify for "Prime" status after 40 consecutive weeks of uptrend
- **Classification System**: Classifies stocks into Prime, Prime Waitlist, Momentum, or Momentum Waitlist categories
- **Trailing Stop Loss**: Intelligent step-wise stop loss that moves up 10% for every 10% price gain
- **Recovery Detection**: Detects EMA crossover (EMA34 > EMA55) during downtrends to identify momentum trades
- **Persistence Layer**: SQLite storage for stock states, signals, and trades- **Signal System**: Emits signals for uptrend start, entry points, downtrends, and milestones

## Installation
```bash
pip install -r requirements.txt python setup.py install
```
Or for development:
```bash
bashpip install -e .
```

## Quick Start 

### Run commands
- `python -m trend_rider_lib scan TIINDIA.NS --start-date 2017-10-29 --end-date 2026-05-23`
- `python -m trend_rider_lib show`
- `python -m trend_rider_lib report`
- `python -m trend_rider_lib clean TIINDIA.NS`

### 1. Download Market Data
```python
from trend_rider_lib import YFinanceDownloader
downloader = YFinanceDownloader()
daily_data = downloader.download_bulk(
    tickers=['AAPL', 'MSFT', 'GOOGL'],
    start_date='2020-01-01',
    end_date='2023-12-31'
)
```

### 2. Initialize Engine
```python
from trend_rider_lib import TrendRiderEngine, TrendRiderConfig
from trend_rider_lib.persistence import SQLiteProvider

config = TrendRiderConfig()
provider = SQLiteProvider(':memory:')  # or 'path/to/db.sqlite'
engine = TrendRiderEngine(
    config=config,
    state_store=provider,
    signal_store=provider,
    trade_store=provider
)
```

### 3. Run Full Analysis
```python
tickers = ['AAPL', 'MSFT', 'GOOGL']
results = engine.run_full_scan(tickers, daily_data)

# Check classifications
classifications = engine.get_classifications(tickers)
print(classifications)
# Output: {'AAPL': Classification.PRIME, 'MSFT': Classification.UNQUALIFIED, ...}

# Get open trades
open_trades = engine.get_open_trades(tickers)
for ticker, trades in open_trades.items():
    print(f"{ticker}: {len(trades)} open trades")
```

## Core Concepts
### Stock States
The FSM transitions through these states:
1. **WARMUP**: Initial period for EMA calculation stabilization (25 weeks by default)
2. **OBSERVING**: Post-warmup, watching for entry conditions
3. **BUY_ZONE**: Price within buy zone (EMA21 to EMA21×1.05)
4. **UPTREND**: Price above EMA21, counting weeks toward qualification5. **ABOVE_BUY_ZONE**: Price significantly above EMA21 (>5%)
6. **DOWNTREND**: Triggered when weekly close < EMA21×0.90
7. **RECOVERING**: Post-downtrend, waiting for EMA crossover confirmation

### Stock Classification
- **UNQUALIFIED**: Less than 40 weeks in uptrend
- **PRIME**: 40+ weeks uptrend, TR qualified, currently in buy zone
- **PRIME_WAITLIST**: 40+ weeks uptrend, TR qualified, above buy zone
- **MOMENTUM**: 40+ weeks uptrend, TR qualified, recovered from downtrend, in buy zone
- **MOMENTUM_WAITLIST**: Same as momentum but above buy zone

### Trading Rules 
**Entry**: When daily candle closes above EMA21 from buy zone  
**Target**: 50% profit (configurable)  
**Stop Loss**: 
- Initial: 10% below entry
- Trailing: Moves up in 10% increments
  - At 10% gain: SL at breakeven
  - At 20% gain: SL at +10%
  - At 30% gain: SL at +20%

## Configuration
```python
config = TrendRiderConfig(
    # EMA periods
    ema_weekly_period=21,
    ema_daily_fast=34,
    ema_daily_slow=55,
    
    # Warmup and qualification
    warmup_weeks=25,
    tr_qualify_weeks=40,
    
    # Zone parameters    buy_zone_upper_pct=0.05,
    downtrend_trigger_pct=0.10,
    
    # Trading
    trade_target_pct=0.50,
    trade_initial_sl_pct=0.10,
    trade_tsl_step_pct=0.10,
    max_concurrent_trades=1,
    trade_slippage_pct=0.0005,
    
    # Uptrend Strength Thresholds
    strength_weak_threshold=0.70,
    strength_developing_threshold=0.80,
    strength_moderate_threshold=0.90,
    strength_strong_threshold=1.00,
)
```

## API Reference

### TrendRiderEngine
- **run_full_scan(tickers: List[str], daily_data: Dict[str, pd.DataFrame], debug_callback: Optional[Callable[[str, pd.DataFrame], None]) -> Dict[str, StockContext]**
  - Runs a full historical scan on provided tickers.
  - Processes complete daily data through indicators, FSM, trading system.
  - Returns a dictionary mapping ticker symbols to their final StockContext.

- **run_incremental_update(tickers: List[str], new_candles: Dict[str, pd.DataFrame]) -> Dict[str, StockContext]**
  - Updates the analysis with new candle data.
  - Processes new candles in chronological order.
  - Returns updated StockContext for each ticker.

- **get_classifications(tickers: List[str]) -> Dict[str, Classification]**
  - Retrieves current classifications for specified tickers.
  - Returns a dictionary mapping ticker symbols to their Classification.

- **get_open_trades(tickers: List[str]) -> Dict[str, List[TradeRecord]]**
  - Gets open trades for specified tickers.
  - Returns a dictionary mapping ticker symbols to lists of open TradeRecords.

### Configuration Parameters
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| **ema_weekly_period** | int | 21 | Weekly EMA period |
| **ema_daily_fast** | int | 34 | Daily fast EMA (EMA34) |
| **ema_daily_slow** | int | 55 | Daily slow EMA (EMA55) |
| **warmup_weeks** | int | 25 | Initial warmup period in weeks |
| **buy_zone_upper_pct** | float | 0.05 | Buy zone upper bound as % above EMA21 (5% = 0.05) |
| **downtrend_trigger_pct** | float | 0.10 | Downtrend trigger as % below EMA21 (10% = 0.10) |
| **tr_qualify_weeks** | int | 40 | Weeks in uptrend to achieve TR qualification |
| **trade_target_pct** | float | 0.50 | Trade target profit percentage (50% = 0.50) |
| **trade_initial_sl_pct** | float | 0.10 | Initial stop loss as % below entry (10% = 0.10) |
| **trade_tsl_step_pct** | float | 0.10 | Trailing stop loss step increment percentage |
| **max_concurrent_trades** | int | 1 | Maximum concurrent trades per stock |
| **trade_slippage_pct** | float | 0.0005 | Entry slippage applied to daily market-on-close fills (0.05% = 0.0005) |
| **strength_weak_threshold** | float | 0.70 | Threshold for weak uptrend (% closes above EMA) |
| **strength_developing_threshold** | float | 0.80 | Threshold for developing uptrend |
| **strength_moderate_threshold** | float | 0.90 | Threshold for moderate uptrend |
| **strength_strong_threshold** | float | 1.00 | Threshold for strong uptrend |

### Core Models
- **StockContext**: Runtime state of a stock.
  - `current_state`: Current FSM state.
  - `tr_qualified`: Whether stock achieved TR qualification.
  - `uptrend_weeks`: Current uptrend duration.
  - `classification`: Current classification.
  - `last_ema21`, `last_ema34`, `last_ema55`: Latest indicator values.

- **TradeRecord**: Trade lifecycle tracking.
  - `entry_date`, `entry_price`: Entry details.
  - `exit_date`, `exit_price`: Exit details.
  - `target_price`, `current_sl`: Trade targets.
  - `status`: OPEN, CLOSED_TARGET, CLOSED_SL.
  - `profit_loss_pct`: Final P&L percentage.

- **SignalEvent**: Signal emission.
  - `signal_type`: Type of signal (UPTREND_START, BUY_ENTRY, etc.).
  - `date`, `close_price`: When and at what price.
  - `ema21`, `ema34`, `ema55`: Technical indicators at time.

## Module Interfaces

### Configuration- **TrendRiderConfig**: Holds all configuration parameters (see above).

### Persistence
- **IStateStore**:
  - `save_context(context: StockContext) -> None`
  - `load_context(ticker: str) -> Optional[StockContext]`
  - `load_all_contexts() -> List[StockContext]`
  - `delete_context(ticker: str) -> None`
- **ISignalStore**:
  - `save_signal(signal: SignalEvent) -> None`
  - `get_signals(ticker: str, signal_type: Optional[str] = None, from_date: Optional[str] = None) -> List[SignalEvent]`
  - `get_latest_signal(ticker: str, signal_type: Optional[str] = None) -> Optional[SignalEvent]`
  - `delete_signals(ticker: str) -> None`
- **ITradeStore**:
  - `save_trade(trade: TradeRecord) -> None`
  - `update_trade(trade: TradeRecord) -> None`
  - `get_open_trades(ticker: Optional[str] = None) -> List[TradeRecord]`
  - `get_all_trades(ticker: Optional[str] = None) -> List[TradeRecord]`
  - `get_trade_by_id(trade_id: int) -> Optional[TradeRecord]`

### Engine
- **TrendRiderEngine**:
  - `run_full_scan(tickers: List[str], daily_data: Dict[str, pd.DataFrame], debug_callback: Optional[Callable[[str, pd.DataFrame], None]) -> Dict[str, StockContext]`
  - `run_incremental_update(tickers: List[str], new_candles: Dict[str, pd.DataFrame]) -> Dict[str, StockContext]`
  - `get_classifications(tickers: List[str]) -> Dict[str, Classification]`
  - `get_open_trades(tickers: List[str]) -> Dict[str, List[TradeRecord]]`

### Indicators
- **resample_daily_to_weekly(daily_df: pd.DataFrame) -> pd.DataFrame**
- **compute_zone_flags(df: pd.DataFrame, buy_zone_upper_pct: float, downtrend_trigger_pct: float) -> pd.DataFrame**
- **mark_warmup_complete(df: pd.DataFrame, warmup_weeks: int) -> pd.DataFrame**
- **enrich_with_indicators(df: pd.DataFrame, config: TrendRiderConfig) -> pd.DataFrame**

### State Machine
- **StockFSM**: Main FSM class for stock state transitions.
- **classify_stock(context: StockContext) -> Classification**
- **update_classification(context: StockContext) -> None**

### Trading
- **TradeManager**: Manages trade lifecycle and trailing stop logic.
- **TSLEngine**: Implements trailing stop loss mechanics.

### Signals
- **SignalEngine**: Processes and stores signal events.

## Data Requirements
The library expects daily OHLCV data with:
- **Columns**: Open, High, Low, Close, Volume
- **Index**: DatetimeIndex (daily frequency)
- **Quality**: No gaps or NaN values in essential columns (Close, Volume)

Example DataFrame structure:
```
                 Open    High     Low   Close    Volume
2023-01-01   150.00  152.50  149.50  151.00  50000000
2023-01-02   151.00  153.00  150.75  152.50  45000000
...
```

## Performance Considerations
- Full scan of 100 stocks with 3 years of data: ~30-60 seconds
- Incremental updates: <1 second per stock
- SQLite database: ~1MB per 10,000 trades

## Known Limitations
- Single-threaded processing (no parallel stock analysis)
- No division of cash/capital allocation
- yfinance is used for data (rate limits apply)
- No commission or slippage modeling beyond basic slippage_pct

## Architecture
```
trend_rider_lib/
├── core/           # Models, enums, config
├── indicators/     # EMA calculations, zone detection
├── state_machine/  # FSM, classification, serialization
├── trading/        # TSL engine, trade management
├── signals/        # Signal engine
├── persistence/    # Database interfaces and implementations
├── downloader/     # yfinance wrapper
└── engine.py       # Main orchestrator
```

## Contributing
See CONTRIBUTING.md for guidelines.

## License
MIT

## Version History
### V0.81 (Current)
- Initial release
- Core FSM and state transitions
- EMA-based indicators
- Trailing stop loss system
- Classification engine
- SQLite persistence- Signal emission system