# Trend Rider V0.81 Pine Indicator

The script `./trading_view/indicator/trend_rider_indicator.pine` is an overlay indicator. It uses weekly data for trend qualification and daily data for EMA34/EMA55 confirmation, so it can be used on intraday, daily, or weekly charts.

The script `./trading_view/strategy/trend_rider_strategy.pine` is the corresponding strategy implementation with trade management logic.

Default EMA colors:

- Weekly EMA21: blue
- Daily EMA34: dark green
- Daily EMA55: red

Buy zone interval rule:

- Weekly trend qualification and weekly buy-zone state continue to use weekly OHLC and weekly EMA21.
- Buy-zone marking on daily or any non-weekly chart must use the chart interval's own OHLC data directly: green interval candle, interval close above weekly EMA21, and interval open at or below `weekly EMA21 * buyZoneMax`.
- Do not drive chart-interval buy-zone background marking from a higher-timeframe `request.security` OHLC result. Higher-timeframe data may provide the EMA band, but the interval bar being marked must satisfy the buy-zone candle rule itself.

# Instructions for Change

- The scripts derive their algorithm design strictly from `design.md` (located at `trend_rider_lib/design.md`)
- Any changes done to the design or `trend_rider_lib` must be applied to **both** indicator and strategy scripts
- Refer to `project.rules.md` for the full design change protocol and rules
- Pine Scripts must refer to `design.md` for FSM state definitions, transitions, and all design specifications
- Indicator and strategy must be kept strictly synchronized with each other and with `design.md`
- Pine Scripts cannot be tested. They must be committed directly.
- No versioning of Pine Scripts is necessary.
