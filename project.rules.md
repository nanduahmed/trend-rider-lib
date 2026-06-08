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

    1. **Verify Intent**: Ensure the requested update represents an explicit, intentional change to the foundational design. If a user requests a Pine Script change that modifies the design, inform them that it is a design change which must be applied to both library and Pine Scripts.

    2. **Clarify & Confirm**: Discuss and clarify the technical details with the user to align on the approach. Get explicit approval before proceeding with any design change.

    3. **Execute & Document**: Once the user explicitly approves the change:
       - Apply the same change to **all three** components: `trend_rider_lib`, Pine Script **indicator**, and Pine Script **strategy** (where applicable)
       - Immediately document the change at the **end** of `design.md`
       - Update the design change log section

3. Design Change Classification
   - Any change to FSM states, transitions, signal definitions, EMA parameters, zone definitions, trade rules, or qualification logic is a **design change**
   - A user requesting a Pine Script change that affects design must be informed that it is a design change requiring updates across all components
   - When in doubt, verify with the user

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
`tr_qualified` is a **one-way latch**. Once set to `True`, it must never be set to `False`. This applies to both the Python library and Pine Script implementations. Refer to `design.md` (Section 3. Trend Qualification) for the exact qualification logic.

### EMA Calculations
EMA calculations must follow this priority:
1. **First choice**: TA-Lib (`talib.EMA`) for all full-history calculations
2. **Fallback**: Use the incremental formula only when TA-Lib is not usable in certain cases
   - Incremental formula: `EMA_new = close × k + EMA_prev × (1 − k)` where `k = 2/(period+1)`
- Full history batch calculations must always use TA-Lib
---

## Pine Scripts

The library provides an indicator and a strategy for TradingView platform using Pine Script. These Pine Scripts must be exactly according to the design mentioned in `design.md`.
The design of the algorithm, `trend_rider_lib`, and Pine Scripts must have exactly the **same design**.

### Design Change Protocol for Pine Scripts
- When a change is required in Pine Scripts, the change must be applied to **both** indicator and strategy where applicable
- If a user mistakenly asks for a change that affects design, inform them that it is a design change requiring updates to all components (library, indicator, strategy)
- After explicit user approval, apply the change consistently across all components
- Document the change at the end of `design.md`

### Rules for Pine Scripts
- All code for Pine Scripts must live in `trading_view/` directory
  - `trading_view/indicator/` — for the indicator script
  - `trading_view/strategy/` — for the strategy script
  - `trading_view/docs/` — for documentation
- Pine Scripts must refer to `design.md` for FSM state definitions, transitions, and all design specifications
- Refer to `README.md` in `trading_view/docs` for Pine Script specific  implementation references
- Indicator and strategy must be kept strictly synchronized with each other and with `design.md`
- Pine Scripts cannot be tested. They must be committed directly.
- No versioning of Pine Scripts is necessary.

### What Constitutes a Design-Breaking Change
Changes to any of the following require a coordinated update across all components:
- FSM states or transitions
- Signal definitions or trigger conditions
- EMA parameters or zone definitions
- Trade rules or qualification logic
- tr_qualified logic or classification rules

---

## Documentation

### design.md
- `design.md` must capture **design**. This is the SSoT for entire algorithm
- It must NOT contain implementation code
- It should include formulas where necessary for clarity
- All algorithm-level changes must be documented at the **end** of `design.md`
