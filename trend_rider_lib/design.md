# Trend Rider V0.3 — Design Reference

---

## 1\. Indicators

| Indicator | Timeframe | Library | Purpose |
| --- | --- | --- | --- |
| EMA21 | Weekly | TA-Lib | Primary trend line |
| EMA34 | Daily | TA-Lib | Recovery crossover (fast) |
| EMA55 | Daily | TA-Lib | Recovery crossover (slow) |

**Zone Definitions**

Buy Zone: 

*   EMA21 \< close ≤ EMA21 × 1.05
*   Green Candle close > open on a daily candle

Above Buy Zone: 

*   close > EMA21 × 1.05

Downtrend Trigger: 

*   close \< EMA21 × 0.90 (weekly close only)

**Boundary Behaviour** (exact values)

close \<= EMA21 → NOT in buy zone (strict >)  
close == EMA21 × 1.05 → IN buy zone (inclusive ≤)  
close == EMA21 × 0.90 → NOT downtrend (strict \<)

## 2\. State Machine

```
stateDiagram-v2
    direction TB

    [*] --> WARMUP
    WARMUP --> OBSERVING : week_count >= warmup_weeks

    %% Entry Logic
    OBSERVING --> BUY_ZONE : price in buy zone
    OBSERVING --> ABOVE_BUY_ZONE : price above buy zone

    %% The Active Loop
    BUY_ZONE --> UPTREND : daily close > EMA21
    UPTREND --> ABOVE_BUY_ZONE : price > 1.05 * EMA21
    ABOVE_BUY_ZONE --> BUY_ZONE : price drops to buy zone

    %% Global Exit to Downtrend
    BUY_ZONE --> DOWNTREND : weekly close < 0.90 * EMA21
    ABOVE_BUY_ZONE --> DOWNTREND : weekly close < 0.90 * EMA21
    UPTREND --> DOWNTREND : weekly close < 0.90 * EMA21

    %% Recovery Logic
    DOWNTREND --> RECOVERING : daily EMA34 > EMA55
    RECOVERING --> BUY_ZONE : price enters buy zone\n(Signal: MOMENTUM_ENTRY)
    RECOVERING --> ABOVE_BUY_ZONE : price > 1.05 * EMA21
    RECOVERING --> DOWNTREND : price < 0.90 * EMA21 (Reset)
```

**Key transition rules**

*   Downtrend triggers from: `BUY_ZONE`, `UPTREND`, `ABOVE_BUY_ZONE`, `RECOVERING`
*   `RECOVERING → DOWNTREND` resets `is_crossover_detected = False`
*   Uptrend clock runs across `UPTREND`, `ABOVE_BUY_ZONE`, and `BUY_ZONE`  
    (after uptrend has started)
*   Any uptrend begins when close > EMA21

---

## 3\. tr\_qualified

*   Set `True` when `uptrend_weeks >= 40` for the first time
*   **Permanent. Never reset. Not by downtrend. Not by re-scan.**
*   Clock resets to `0` on each downtrend trigger
*   Any subsequent uptrend ≥ 40 weeks → PRIME eligibility

---

## 4\. WARMUP Period

*   WARMUP period must be kept configurable with 25 weeks as default. This period does not generate Trend, Buy Signals
*   This timeperiod is used to calculate EMAs so tthat we have most precise values on WARMUP complete period

## 5\. Uptrend Record

Tracked per uptrend (completed and active)

start\_date,  
end\_date (None if active)  
num\_weeks  
closes\_above\_ema,  
closes\_below\_ema  
pct\_closes\_above = closes\_above\_ema / num\_weeks strength (see below) highest\_price + date,  
trend\_lowest\_price + date  
trend\_highest\_price + date  
last\_close\_daily

% profit/loss

**Strength thresholds**

\< 0.70 → WEAK  
0.70–0.80 → DEVELOPING  
0.80–0.90 → MODERATE  
0.90–1.00 → STRONG  
1.00 → SUPER\_STRONG

**Finalize on downtrend:**  
set `end_date`,  
calculate `strength`,  
append to `uptrend_history`,  
clear `current_uptrend`.

## 6\. Classification

Requires `tr_qualified == True` for all below.  
uptrend\_weeks >= 40 AND is\_buyzone → PRIME  
uptrend\_weeks >= 40 AND NOT is\_buyzone → PRIME\_WAITLIST   
uptrend\_weeks \< 40 AND positive crossover AND is\_buyzone → MOMENTUM ( New Uptrend ), starts after close > EMA21

uptrend\_weeks \< 40 AND crossover AND NOT is\_buyzone → MOMENTUM\_WAITLIST

MOMENTUM graduates to PRIME when its uptrend reaches 40 weeks.

---

## 7\. Signals

| Signal | Timeframe | Trigger |
| --- | --- | --- |
| UPTREND\_START | Daily | Daily close > EMA21 from BUY\_ZONE |
| BUY\_ENTRY | Daily | Same event as UPTREND\_START |
| ABOVE\_BUY\_RANGE | Daily | Daily close > EMA21 × 1.05 |
| REENTRY | Weekly | tr\_qualified + price back in buy zone |
| MOMENTUM\_ENTRY | Weekly | RECOVERING → BUY\_ZONE |
| DOWNTREND\_START | Weekly | Weekly close \< EMA21 × 0.90 |
| EMA\_CROSSOVER | Daily | EMA34 crosses above EMA55 (first time) |
| TR\_QUALIFIED | Weekly | uptrend\_weeks hits 40 |

Every signal stores: `ticker, signal_type, date, close, ema21, ema34, ema55`

---

## 8\. Trade Manager

Entry: on BUY\_ENTRY, REENTRY, or MOMENTUM\_ENTRY signal  
Target: entry × 1.50 (configurable)  
Init SL: entry × 0.90 (configurable)  
TSL: step-wise, 10% steps (configurable)

**TSL Formula**

steps = FLOOR((highest\_seen - entry) / (entry × tsl\_step))

sl = entry × (1 - init\_sl\_pct) if steps == 0  
sl = entry × (1 + (steps - 1) × tsl\_step) if steps > 0

**TSL Example** (entry=100, tsl\_step=10%, init\_sl=10%)  
Highest 100–109 → SL = 90 (-10%)  
Highest 110–119 → SL = 100 (breakeven)  
Highest 120–129 → SL = 110 (+10%)  
Highest 130–139 → SL = 120 (+20%)  
Highest 140–149 → SL = 130 (+30%)  
Highest ≥ 150 → TARGET EXIT (+50%)

**Exit:**  
`price ≥ target` → TARGET | `price ≤ current_sl` → STOP

---

## 9\. Processing Pipeline

### Full Scan

1.  Download daily OHLC (yfinance)
2.  Resample → weekly (W-FRI)
3.  Compute EMA21 on weekly, EMA34+EMA55 on daily (TA-Lib)
4.  Compute zone flags on weekly rows
5.  Tag: daily.\_order=0, weekly.\_order=1
6.  Merge + sort by (date, \_order) ← daily before weekly, same date
7.  Feed chronologically → process\_daily\_candle() / process\_weekly\_candle()
8.  Save Signals with metadata to process the next candle
9.  Finalize active current\_uptrend metadata
10.  update\_classification()
11.  save\_context() + write uptrend\_records independently

### Incremental Update

1.  load\_context() from SQLite
2.  fsm.machine.set\_state(saved\_state, model=fsm)
3.  Apply incremental EMA to new candles
4.  Sort (date, \_order) — same rule as full scan
5.  Feed new candles through FSM
6.  Finalize + classify + save

## 10\. Database Schema

\`\`\`sql  
stock\_states -- serialized StockContext (context\_json blob + query columns)  
uptrend\_records -- every UptrendRecord, written independently  
signals -- every SignalEvent  
trades -- every TradeRecord

uptrend\_records uses (ticker, start\_date) as unique key for upsert.

## 11.Key Test Cases

```
TC Input Expected  
01 close == EMA21 is\_buyzone = False  
02 close == EMA21 × 0.90 is\_downtrend = False  
03 39 weeks uptrend tr\_qualified = False  
04 40 weeks uptrend tr\_qualified = True  
05 tr\_qualified=True then downtrend tr\_qualified still True  
06 highest=140, price drops to 130 Exit triggered (TSL step 4)  
07 pct\_closes\_above = 1.00 strength = SUPER\_STRONG  
08 serialize → save → load → deserialize uptrend\_history intact  
09 daily + weekly same date daily processed first  
10 RECOVERING + weekly close \< EMA21×0.90 back to DOWNTREND, crossover reset
```