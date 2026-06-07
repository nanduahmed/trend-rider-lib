# Trend Rider V0.3 — Project Rules

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

## Design of algorithm 
- For all algorithm design related clarifications, design.md remains the single source of truth
- When there is a explicity change of design, Update the design.md after clarification

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

