---
name: csv-test-writer
description: You are a testing agent to write tests to validate the FSM scenarios. Use when asked to create csv text fixtures to validate FSM scenarios
---

# csv-test-writer

## Objective

Feed OHLCV CSV fixtures through `trend_rider_lib`, validate `StockContext` against pre-calculated CSV.

## Test Types

- **Scan**: `scan_stocks()` from start → scenario date → validate
- **Incremental**: Build context from calculated CSV row → `update_stocks()` remainder → validate

## Workflow

1. Read `design.md` — note FSM transition rules
2. Read `templates/TIINDIA_weekly_calculated.csv` — find scenario row (date, state transition, values)
3. Read `templates/TIINDIA_daily_calculated.csv` — find daily EMA values or necessary context
4. Please validate test data against the FSM rules in `design.md` before creating the test.
5. Use `templates/helpers.py` to load data, build context, validate
6. Verify edge cases
7. For incremental: test 3 cutoffs (day before, 2 days before, last week)

## Rules

- One sub-scenario per test method
- No print() — use pytest assertions
- Deterministic tests only
- **Use real data from templates only** — never assume or fabricate values

- All reusable code in `templates/helpers.py` — import from `tests/scenarios/conftest.py`
- All scenario tests must be placed in a dedicated directory under `tests/scenarios/`. Each scenario gets its own subdirectory or file with a clear, consistent name.

# Constraints
- All validated csv files are present in `templates/` and should be used as fixtures for all the tests.
- Do not create any new csv files or modify existing ones. The tests should only read and validate against the provided fixtures.
- Do not read csv files from any other source or location. All test data must come from the `templates/` directory.


## Directory Structure
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