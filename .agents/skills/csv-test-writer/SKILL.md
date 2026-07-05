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

We have two types of tests for FSM scenarios:

## Warmup 
Warmup tests are the tests created to feed entire data from beginning to end of OHLCV data
These tests will call the `scan_stocks()` to create a `StockContext` object
Then finally validate the `StockContext` object to ensure library is working as expected and the calculated values are correct. 

# Incremental 
The tests will have precalculeted `StockContext` object from the calculated csv file
The tests will feed the incremental data to the `update_stocks` to agiven date
Then finally validate the `StockContext` object to ensure library is working as expected and the calculated values are correct.

## Usage

When you want to create a test for FSM scenarios with fixtures data, you can use the `csv-test-writer` skill. The skill will generate a test file with the necessary code to validate the FSM scenarios using the provided csv fixtures.

## Steps

1. Identify the asked scenario from `ticker_weekly_calculated`/`ticker_daily_calculated` csv files
  For e.g. if you are asked to write a test for validating "uptrend begin", you must refer to the @design.md file to see the definition of "uptrend_begin"
  
2. Second step
3. Third step
