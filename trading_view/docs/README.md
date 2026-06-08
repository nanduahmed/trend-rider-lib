# Trend Rider V0.81 Pine Indicator

The script `./trading_view/indicator/trend_rider_indicator.pine` is an overlay indicator. It uses weekly data for trend qualification and daily data for EMA34/EMA55 confirmation, so it can be used on intraday, daily, or weekly charts.

The script `./trading_view/strategy/trend_rider_strategy.pine` is the corresponding strategy implementation with trade management logic.

Default EMA colors:

- Weekly EMA21: blue
- Daily EMA34: dark green
- Daily EMA55: red

# Instructions for Change

- The scripts derive their algorithm design strictly from `design.md` (located at `trend_rider_lib/design.md`)
- Any changes done to the design or `trend_rider_lib` must be applied to **both** indicator and strategy scripts
- Refer to `project.rules.md` for the full design change protocol and rules
- Pine Scripts must refer to `design.md` for FSM state definitions, transitions, and all design specifications
- Indicator and strategy must be kept strictly synchronized with each other and with `design.md`
- Pine Scripts cannot be tested. They must be committed directly.
- No versioning of Pine Scripts is necessary.