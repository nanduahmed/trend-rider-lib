# Trend Rider — Project Rules

## Package Structure
Two packages. Strictly separate.
- `trend_rider_lib/` — logic only
- `trend_rider_cli/` — display and wiring only

## Module Layout

### trend_rider_lib/
core/ enums.py, config.py, models.py indicators/ resampler.py, ema_engine.py, flag_computer.py state_machine/ fsm.py, stock_context.py, uptrend_record.py, classifier.py, fsm_serializer.py signals/ signal_engine.py, signal_store.py trading/ tsl_engine.py, trade_manager.py, trade_store.py persistence/ interfaces.py, sqlite_provider.py, xlsx_provider.py downloader/ yfinance_downloader.py engine.py


### trend_rider_cli/
cli/ app.py commands/ scan.py, update.py, show.py, classify.py, trades.py, report.py, backtest.py, clean.py display/ tables.py, panels.py, progress.py, formatters.py utils/ resolver.py, provider_factory.py, ticker_loader.py

## Hard Rules

## Algorithm Design & Modification Protocol
1. Single Source of Truth
- `design.md` is the absolute authority for all algorithm design specifications and clarifications.

- Always consult `design.md` before making any modifications to the trend_rider_lib algorithm.

2. Design Change Workflow

    When a request is made to change the core design of `trend_rider_lib` or the associated Pine Script, adhere to the following sequence:

    1. Verify Intent: Ensure the requested update represents an explicit, intentional change to the foundational design.

    2. Clarify & Confirm: Discuss and clarify the technical details with the user to align on the approach.

    3. Execute & Document: Once the user explicitly approves the change, implement the update and immediately document it in design.md.

### Library
- NO typer, rich, click, or any UI import
- NO hardcoded paths or DB strings
- NO print() — use logging only
- NO reading env vars or config files
- All external dependencies injected via constructor

### CLI
- Absolute imports only: `from trend_rider_lib import ...`
- NEVER relative import from library
- ZERO business logic — only wiring, display, error handling
- ONE `Console` instance created in `app.py`, passed everywhere
- All errors: `console.print(...)` + `raise typer.Exit(code=1)`
- NEVER `typer.Exit(message=...)` — invalid parameter
- NEVER `typer.echo()` for Rich markup — use `console.print()`

---

## Environment
Always install and execute in venv (check existing .venv)

## Critical Implementation Rules

### Candle Processing Order
Daily candle MUST be processed before weekly candle on the same date.
Enforce with secondary sort key: `daily=0, weekly=1`.

### FSM State Restoration
```python
# CORRECT
fsm.machine.set_state(state_name, model=fsm)
# FORBIDDEN
fsm.state = state_name
```

### Stock tr_qualified Flag
tr_qualified
One-way latch. Once True, never set False. Ever.

### EMA Calculations
Full history: Always use TA-Lib only (talib.EMA)
Single candle update: incremental formula only EMA_new = close × k + EMA_prev × (1 − k) where k = 2/(period+1)


## Pine Scripts

The library provides a indicator and a strategy for TradingView platform using pine scripts. These pine scripts must be exactly according to the design mentioned in `design.md` 
The design of algorithm, trend_ider_lib and pine script must have exactly same design

### Rules for pine scripts

- All code for pine scripts must live in `trading_view` diretory
- Refer to `README.md` in `trading_view/docs`
- Whenever there is a change required in pine scripts, it must strictly not break design of the algorithm unless explitly required
- Keep indicator and strategy syned so single design

