---
name: csv-test-writer
description: You are a testing agent to write tests to validate the FSM scenarios. Use when asked to create csv text fixtures to validate FSM scenarios
---

# csv-test-writer

## Objective of tests
The test will perform the following validations
* The fixtures of various real data is provided in form of raw OHLCV csv (`ticker_weekly.csv`, `ticker_daily.csv`). 
* Other csv with calculated and validate `StockContext` object is also provided in csv (`ticker_weekly_calculated.csv`, `ticker_daily_calculated.csv`).
* Test must create a `StockContext` object from the OHLCV data using `trend_rider_lib's` `api.py`
* Validate the `StockContext` object to ensure library is working as expected and the calculated values are correct.
* If a bug is found, the test should fail and provide a detailed report of the issue.


## Types of tests
We have two types of tests for FSM scenarios:

### Scan
Scan tests are the tests created to feed entire data from beginning to end of OHLCV data
These tests will call the `scan_stocks()` to create a `StockContext` object
Then finally validate the `StockContext` object to ensure library is working as expected and the calculated values are correct. 

### Incremental 
The tests will have precalculeted `StockContext` object from the calculated csv file
The tests will feed the incremental data to the `update_stocks` to agiven date
Then finally validate the `StockContext` object to ensure library is working as expected and the calculated values are correct.

## Usage

When you want to create a test for FSM scenarios with fixtures data, you can use the `csv-test-writer` skill. The skill will generate a test file with the necessary code to validate the FSM scenarios using the provided csv fixtures.

## Test Directory Structure

All scenario tests must be placed in a dedicated directory under `tests/scenarios/`. Each scenario gets its own subdirectory or file with a clear, consistent name.

```
tests/scenarios/
├── conftest.py              # Shared fixtures and reusable helpers
├── test_uptrend_begin/      # Example: scenario directory
│   ├── __init__.py
│   ├── test_full_scan.py       # Scan test for this scenario
│   └── test_incremental.py  # Incremental tests for this scenario
└── test_downtrend_trigger/  # Another scenario
    ├── __init__.py
    ├── test_full_scan.py
    └── test_incremental.py
```

## Naming Conventions

- **Test file**: `test_<scenario_name>.py` (e.g., `test_uptrend_begin.py`)
- **Test class**: `Test<ScenarioName>` (e.g., `TestUptrendBegin`)
- **Test method**: `test_<scenario>_<sub_scenario>` (e.g., `test_uptrend_begin_scan`, `test_uptrend_begin_incremental_day_before`)
- **Scenario directory**: `tests/scenarios/` for all scenario test files

## Generic Reusable Methods

The following reusable methods should be implemented in `tests/scenarios/conftest.py` and shared across all scenario tests:

### CSV Loading Helpers

```python
def load_raw_ohlcv(ticker: str, timeframe: str, fixtures_dir: Path) -> pd.DataFrame:
    """
    Load raw OHLCV data from CSV.
    
    Parameters
    ----------
    ticker : str
        Stock ticker (e.g., 'TIINDIA').
    timeframe : str
        'weekly' or 'daily'.
    fixtures_dir : Path
        Path to the fixtures directory.
    
    Returns
    -------
    pd.DataFrame
        DataFrame with columns: Date, Open, High, Low, Close, Volume.
        Date is parsed as datetime and set as index.
    """
    ...

def load_calculated_csv(ticker: str, timeframe: str, templates_dir: Path) -> pd.DataFrame:
    """
    Load pre-calculated StockContext CSV.
    
    Returns
    -------
    pd.DataFrame
        DataFrame with all calculated columns (EMA21, Trend Start, State Before/After, etc.).
    """
    ...
```

### Context Building Helpers

```python
def build_stock_context_from_range(
    ticker: str,
    raw_df: pd.DataFrame,
    calculated_df: pd.DataFrame,
    end_date: str,
    config: TrendRiderConfig,
) -> StockContext:
    """
    Build a StockContext by feeding raw OHLCV data from beginning up to end_date.
    Uses scan_stocks() internally.
    
    Parameters
    ----------
    ticker : str
    raw_df : pd.DataFrame
        Full raw OHLCV data.
    calculated_df : pd.DataFrame
        Pre-calculated CSV for validation reference.
    end_date : str
        Cutoff date (YYYY-MM-DD). Only data up to this date is fed.
    config : TrendRiderConfig
    
    Returns
    -------
    StockContext
    """
    ...

def build_context_from_calculated_row(
    calculated_df: pd.DataFrame,
    date: str,
) -> StockContext:
    """
    Reconstruct a StockContext object from a specific row in the calculated CSV.
    Used as the starting context for incremental tests.
    
    Parameters
    ----------
    calculated_df : pd.DataFrame
    date : str
        The date row to extract context from.
    
    Returns
    -------
    StockContext
    """
    ...
```

### Validation Helpers

```python
def validate_state_transition(
    ctx: StockContext,
    expected_state_before: str,
    expected_state_after: str,
    expected_classification: str,
    expected_tr_qualified: bool,
) -> None:
    """
    Assert FSM state transition matches expected values.
    """
    ...

def validate_ema_values(
    ctx: StockContext,
    expected_ema21: float,
    rel_tol: float = 1e-4,
) -> None:
    """
    Assert EMA21 matches expected value within tolerance.
    """
    ...

def validate_trend_metrics(
    ctx: StockContext,
    expected_uptrend_weeks: int,
    expected_closes_above_ema: int,
    expected_closes_below_ema: int,
) -> None:
    """
    Assert trend statistics match expected values.
    """
    ...

def validate_buy_zone(
    ctx: StockContext,
    expected_is_buyzone: bool,
    expected_is_above_buyzone: bool,
) -> None:
    """
    Assert buy zone flags match expected values.
    """
    ...

def assert_stock_context_equals(
    actual: StockContext,
    expected_row: pd.Series,
) -> None:
    """
    Comprehensive validation of StockContext against a calculated CSV row.
    Checks all fields: state, EMA21, trend dates, buy zone, classification,
    uptrend weeks, closes above/below EMA, etc.
    """
    ...
```

### Data Preparation Helpers

```python
def prepare_data_for_scan(
    raw_df: pd.DataFrame,
    start_date: str,
    end_date: str,
) -> Dict[str, pd.DataFrame]:
    """
    Filter raw OHLCV data to the specified date range and prepare for scan_stocks().
    
    Returns
    -------
    dict[str, pd.DataFrame]
        Dictionary keyed by ticker with filtered DataFrame.
    """
    ...

def mock_dates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure datetime index is properly set and timezone-naive.
    Handles various date formats from CSV files.
    """
    ...
```

### Test Lifecycle Helpers

```python
@pytest.fixture
def config() -> TrendRiderConfig:
    """Shared TrendRiderConfig fixture."""
    return TrendRiderConfig()

@pytest.fixture
def templates_dir() -> Path:
    """Path to the skill templates directory."""
    return Path(__file__).parent.parent.parent / ".agents" / "skills" / "csv-test-writer" / "templates"

@pytest.fixture
def fixtures_dir() -> Path:
    """Path to the test fixtures directory."""
    return Path(__file__).parent.parent / "fixtures"

@pytest.fixture
def raw_weekly(templates_dir: Path) -> pd.DataFrame:
    """Load raw weekly OHLCV data."""
    return load_raw_ohlcv("TIINDIA", "weekly", templates_dir)

@pytest.fixture
def calculated_weekly(templates_dir: Path) -> pd.DataFrame:
    """Load calculated weekly data."""
    return load_calculated_csv("TIINDIA", "weekly", templates_dir)
```

## Steps

### Step 1: Read `trend_rider_lib/design.md` and find the scenario

- Identify the FSM state, transition, or signal definition for the scenario being tested
- For example, "uptrend begin" is defined as: `weekly close > EMA21` (OBSERVING → UPTREND)
- Note the exact transition rules, boundary conditions, and any exclusion rules:
  - Confirmation week is excluded from `#weeks`, strength, duration, and performance counts
  - The exact week the trend starts is excluded from weekly statistics until the next weekly candle is processed
  - `tr_qualified` is a one-way latch and never resets
- Document the scenario definition clearly before writing any test code

### Step 2: Give an example of the scenario from the calculated CSV

- Read the `ticker_weekly_calculated.csv` (e.g., `TIINDIA_weekly_calculated.csv`) to find a concrete instance of the scenario. Never read the file from `fixtures` directory; always use the templates directory for test generation.
- For "uptrend begin":
  - Locate the row where `Trend Start` transitions from `FALSE` to `TRUE`
  - Note the date, EMA21 value, close price, and surrounding context
  - Identify the state transition (State Before → State After)
- Document the exact row values that will be used for validation
- Example from TIINDIA: `06/07/2018` where Trend Start becomes `TRUE`, close=244.3, EMA21=239.07

### Step 3: Identify the data range fed to be calculated from the CSV

- Determine the exact date range (start date to end date) from the raw OHLCV CSV that produces the scenario
- The range must start from the **beginning** of the data and end at or just after the scenario date
- Ensure the range includes enough data for warmup (25+ weeks) and the scenario itself
- For warmup tests: feed from the first row of the CSV to the scenario accomplished date
- For incremental tests: identify the cutoff date where the pre-calculated context ends and new data begins

### Step 4: Feed the range to the scan API

- Load the raw OHLCV data for the identified date range using `load_raw_ohlcv()`
- Call `scan_stocks()` from `trend_rider_lib.api` with the data to create a `StockContext` object
- Use a `BridgeProvider` / `IScanResultHandler` to capture the results
- For warmup tests: feed the entire range from beginning to scenario date in one call

### Step 5: Feed the raw data and mock the dates

- Prepare the raw OHLCV data as a `pd.DataFrame` with the correct column names (Open, High, Low, Close, Volume)
- Ensure the datetime index matches the CSV dates using `mock_dates()`
- For incremental tests (3 variations per scenario):
  - **Test 1 (Day Before)**: Build context from calculated CSV up to 1 day before the scenario date, then feed 1 day of incremental data via `update_stocks()`
  - **Test 2 (2 Days Before)**: Build context from calculated CSV up to 2 days before the scenario date, then feed 2 days of incremental data via `update_stocks()`
  - **Test 3 (Last Week)**: Build context from calculated CSV up to the last weekly candle before the scenario, then feed 1 week of incremental data via `update_stocks()`
- Each incremental test must restore the FSM state using `machine.set_state()` before feeding new data

### Step 6: Compare the results

- Validate the `StockContext` object fields against the calculated CSV values using the reusable helpers:
  - State transitions (State Before, State After)
  - EMA21 values (using `pytest.approx` with appropriate tolerance)
  - Trend Start / Trend End flags
  - Buy Zone flags (is_buyzone, is_above_buyzone)
  - Classification and TR Qualified status
  - Uptrend weeks, closes above/below EMA counts
  - Signal counts and signal types
- Assert exact matches for dates, prices, and derived values
- Each test must validate only **one sub-scenario** — keep tests focused and clean

### Step 7: File the bug if any

- If any validation fails, create a detailed bug report including:
  - The expected value (from calculated CSV) vs actual value (from library output)
  - The date and context of the discrepancy
  - The FSM state and transition involved
  - Steps to reproduce with exact data range and parameters
- The test must fail with a clear error message describing the discrepancy
- Use pytest's assertion introspection for clear failure messages:
  ```python
  assert actual_state == expected_state, (
      f"State mismatch on {date}: expected {expected_state}, got {actual_state}"
  )
  ```

## Test Structure Template

### Warmup Test Template

```python
class TestUptrendBegin:
    """Validate uptrend begin scenario."""

    def test_uptrend_begin_warmup(
        self,
        config: TrendRiderConfig,
        raw_weekly: pd.DataFrame,
        calculated_weekly: pd.DataFrame,
    ) -> None:
        """
        GIVEN full weekly OHLCV data from beginning to scenario date
        WHEN scan_stocks() processes all candles
        THEN the StockContext matches the calculated CSV values at the scenario date.
        """
        # Arrange: filter data from beginning to scenario date
        scenario_date = "2018-07-06"
        data = prepare_data_for_scan(raw_weekly, start_date=None, end_date=scenario_date)
        
        # Act: run full scan
        handler = CaptureHandler()
        results = scan_stocks(["TIINDIA"], handler, data=data)
        ctx = results["TIINDIA"]
        
        # Assert: validate against calculated CSV row
        expected_row = calculated_weekly[calculated_weekly["Date"] == scenario_date].iloc[0]
        assert_stock_context_equals(ctx, expected_row)
```

### Incremental Test Template

```python
class TestUptrendBeginIncremental:
    """Validate uptrend begin with incremental data feed."""

    @pytest.mark.parametrize(
        "cutoff_date, feed_days, description",
        [
            ("2018-07-05", 1, "day_before"),
            ("2018-07-04", 2, "two_days_before"),
            ("2018-06-29", 7, "last_week"),
        ],
    )
    def test_uptrend_begin_incremental(
        self,
        config: TrendRiderConfig,
        raw_weekly: pd.DataFrame,
        calculated_weekly: pd.DataFrame,
        cutoff_date: str,
        feed_days: int,
        description: str,
    ) -> None:
        """
        GIVEN a pre-calculated StockContext up to {cutoff_date}
        WHEN {feed_days} days of incremental data is fed via update_stocks()
        THEN the uptrend begin scenario is correctly detected.
        """
        # Arrange: build context from calculated CSV up to cutoff
        ctx = build_context_from_calculated_row(calculated_weekly, cutoff_date)
        
        # Act: feed incremental data
        incremental_data = prepare_incremental_data(raw_weekly, cutoff_date, scenario_date)
        handler = CaptureHandler()
        results = update_stocks(
            ["TIINDIA"],
            handler,
            existing_contexts={"TIINDIA": ctx},
            existing_trades={},
        )
        updated_ctx = results["TIINDIA"]
        
        # Assert: scenario occurred
        scenario_date = "2018-07-06"
        expected_row = calculated_weekly[calculated_weekly["Date"] == scenario_date].iloc[0]
        assert_stock_context_equals(updated_ctx, expected_row)
```

## Edge Cases to Cover

When designing tests for any scenario, ensure the following edge cases are covered:

1. **Boundary conditions**: Values exactly at threshold (e.g., close == EMA21 × 0.90 for downtrend trigger)
2. **State transitions at week boundaries**: Weekly close that triggers a state change
3. **Multiple signals on same date**: Daily and weekly candles on the same date (daily must process first)
4. **Recovery scenarios**: RECOVERING → UPTREND transition with bullish crossover
5. **Qualification boundary**: Exactly at 40 weeks for tr_qualified
6. **Empty or missing data**: No new candles to process
7. **Consecutive same-state candles**: Multiple candles without state change
8. **First candle after warmup**: First candle after week_count >= 25

## Important Rules

- **Use real data from fixtures only** — never assume or fabricate values
- **One sub-scenario per test method** — keep tests focused and clean
- **Standard test lifecycle**: Use pytest fixtures for setup/teardown (config, data loading, context building)
- **Consistent nomenclature**: Follow the naming conventions defined above
- **No hardcoded paths**: Use fixture directories and relative paths
- **No print() statements**: Use logging or pytest assertions for feedback
- **All tests must be deterministic**: Same input must always produce same output