# Bugs 

## Lib 
- There seems to be a bug in signal generation. We must validate this. THis is just a note, Any value (OHLC) crossing above EMA21 might be generating EMA21 Cross. TIINDIA/06/07/2018, Crossover has not happened but is showing a false signal 
- The lib must enable tr flag on completion/close of 40th week. Its doing it on 41st week
- Check the logic for Buy Zone. Since weekly candle close does not show it and daily might be in Buy Zone
- Showing Buyzone tickmark in downtrend start. State shows correct but Buy Zone is wrong 

## App
- For stock TIINDIA.NS, The app shows BUY_ZONE status but the UI displays the red cross 
- The, 'Current State & Status' section, the values overlaps with the icons in a way that second row values are overlapping on fiist row. - Fixed
- Above buy zone shows green tick
- Current State and Buy Zone do not match with weekly and daily update
- Classification in list results must show qualified

# Improvements Required

## App
- The fundamental Identity and Other sections can display in a better format, vix responsive tiles, with some padding. Current implementation  seems a thrown off and scattered.
- Show last incremental date on update tab so reading the contexttual date becomes easier 
- With Daily close, Show % above EMA21 
- Check states, For Buy Zone it is showing Uptrend in App, post TR Qualification, Craftsman.NS

## Lib
- For progressing week (daily) update the buy zone and process current week
- How do we get the Debug CSV for incremental update
- Show Week Day Candle color with OHLCV values
- Include Day of scan with date. Use last daily date and last weekly date in records


