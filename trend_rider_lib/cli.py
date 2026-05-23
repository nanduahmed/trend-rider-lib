from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import TrendRiderConfig, TrendRiderEngine, SQLiteProvider, YFinanceDownloader
from .backtesting import StrategyBacktestWrapper
from .core.enums import TradeStatus
from .core.models import TradeRecord, StockContext

app = typer.Typer(help="Trend Rider command line interface")
console = Console()

DEFAULT_DB = Path("trend_rider.sqlite")


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {}
    for column in df.columns:
        lower = column.strip().lower()
        if lower == "date":
            mapping[column] = "Date"
        elif lower == "open":
            mapping[column] = "Open"
        elif lower == "high":
            mapping[column] = "High"
        elif lower == "low":
            mapping[column] = "Low"
        elif lower == "close":
            mapping[column] = "Close"
        elif lower == "volume":
            mapping[column] = "Volume"
        elif lower == "ticker":
            mapping[column] = "Ticker"
    return df.rename(columns=mapping)


def validate_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    df = normalize_columns(df)
    required = {"Open", "High", "Low", "Close", "Volume"}
    missing = required - set(df.columns)
    if missing:
        raise typer.BadParameter(f"Data file is missing required columns: {', '.join(sorted(missing))}")
    return df[[*required, *(c for c in df.columns if c not in required)]]


def load_data_file(data_file: Path) -> Dict[str, pd.DataFrame]:
    if not data_file.exists():
        raise typer.BadParameter(f"Data file does not exist: {data_file}")

    suffix = data_file.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(data_file)
    elif suffix in {".xlsx", ".xls"}:
        df = pd.read_excel(data_file)
    elif suffix in {".parquet"}:
        df = pd.read_parquet(data_file)
    else:
        raise typer.BadParameter("Unsupported data file format. Use CSV, XLSX, or Parquet.")

    df = normalize_columns(df)
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date")
    elif not isinstance(df.index, pd.DatetimeIndex):
        raise typer.BadParameter("Data file must include a Date column or a DatetimeIndex.")

    df = validate_ohlcv(df)

    if "Ticker" in df.columns:
        grouped = {}
        for ticker, group in df.groupby("Ticker"):
            grouped[ticker] = group.drop(columns=["Ticker"]).sort_index()
        return grouped

    return {"data": df.sort_index()}


def build_trade_rows(trades: List[TradeRecord]) -> List[Dict[str, str]]:
    rows = []
    for trade in trades:
        rows.append({
            "ID": trade.id,
            "Ticker": trade.ticker,
            "Status": trade.status.name if trade.status else "UNKNOWN",
            "Entry Date": trade.entry_date.isoformat() if trade.entry_date else "",
            "Entry Price": trade.entry_price,
            "Exit Date": trade.exit_date.isoformat() if trade.exit_date else "",
            "Exit Price": trade.exit_price,
            "Profit/Loss %": trade.profit_loss_pct,
            "Initial SL": trade.initial_sl,
            "Current SL": trade.current_sl,
            "Highest Price": trade.highest_price_seen,
            "Exit Reason": trade.exit_reason.name if trade.exit_reason else "",
        })
    return rows


def context_to_row(context: StockContext) -> Dict[str, str]:
    return {
        "Ticker": context.ticker,
        "Classification": context.classification.name if context.classification else "UNKNOWN",
        "State": context.current_state.name if hasattr(context.current_state, "name") else str(context.current_state),
        "TR Qualified": "Yes" if context.tr_qualified else "No",
        "Buy Zone": "Yes" if context.is_buyzone else "No",
        "Last Close": context.last_close,
        "Last Update": context.last_update.isoformat() if context.last_update else "",
        "Uptrend Weeks": context.uptrend_weeks,
    }


def open_db(db_path: Path) -> SQLiteProvider:
    return SQLiteProvider(str(db_path))


def make_engine(db_path: Path) -> TrendRiderEngine:
    provider = open_db(db_path)
    config = TrendRiderConfig()
    return TrendRiderEngine(config, provider, provider, provider)


@app.command()
def scan(
    tickers: List[str] = typer.Argument(..., help="Stock tickers to scan."),
    db_path: Path = typer.Option(DEFAULT_DB, help="SQLite database file for persistence."),
    start_date: str = typer.Option("2000-01-01", help="Start date for historical download."),
    end_date: Optional[str] = typer.Option(None, help="End date for historical download."),
    data_file: Optional[Path] = typer.Option(None, help="Optional CSV/XLSX/Parquet file containing OHLCV data."),
):
    """Run a full historical scan for the given tickers."""
    engine = make_engine(db_path)
    daily_data: Dict[str, pd.DataFrame]

    if data_file:
        loaded = load_data_file(data_file)
        if len(loaded) == 1 and "data" in loaded:
            if len(tickers) != 1:
                raise typer.BadParameter("Provide exactly one ticker when passing a single data file without ticker column.")
            daily_data = {tickers[0]: loaded["data"]}
        else:
            daily_data = loaded
            if tickers and set(tickers) != set(daily_data.keys()):
                typer.echo("[yellow]Warning:[/yellow] tickers list and data file tickers do not match; using tickers from data file.")
                tickers = list(daily_data.keys())
    else:
        if not tickers:
            raise typer.BadParameter("At least one ticker is required when no data file is provided.")
        end_date = end_date or datetime.now().strftime("%Y-%m-%d")
        daily_data = YFinanceDownloader.download_bulk(tickers, start_date, end_date)
        if not daily_data:
            raise typer.Exit(code=1, message="No download data returned from yfinance.")

    results = engine.run_full_scan(tickers, daily_data)
    table = Table(title="Full Scan Results")
    table.add_column("Ticker", style="bold cyan")
    table.add_column("Classification", style="green")
    table.add_column("Last Update", style="magenta")
    for ticker, context in results.items():
        table.add_row(
            ticker,
            context.classification.name if context.classification else "UNKNOWN",
            context.last_update.isoformat() if context.last_update else "",
        )
    console.print(table)
    console.print(Panel(f"Scan complete. Persisted results to {db_path}", style="green"))


@app.command()
def update(
    tickers: Optional[List[str]] = typer.Argument(None, help="Optional tickers to update. If omitted, updates all stored tickers."),
    db_path: Path = typer.Option(DEFAULT_DB, help="SQLite database file for persistence."),
):
    """Run an incremental update for saved tickers."""
    provider = open_db(db_path)
    contexts = provider.load_all_contexts()
    if not contexts:
        raise typer.Exit(code=1, message="No stored stock contexts found. Run scan first.")
    if tickers:
        contexts = [ctx for ctx in contexts if ctx.ticker in tickers]
        if not contexts:
            raise typer.Exit(code=1, message="No matching tickers found in persistence.")

    engine = make_engine(db_path)
    updated = {}
    for context in contexts:
        if not context.last_update:
            console.print(f"[yellow]Skipping {context.ticker}: no last update date available.[/yellow]")
            continue

        last_date = context.last_update
        daily_df = YFinanceDownloader.download_incremental(context.ticker, last_date, interval="1d")
        weekly_df = YFinanceDownloader.download_incremental(context.ticker, last_date, interval="1wk")
        new_candles = {}
        if not daily_df.empty and not weekly_df.empty:
            merged_df = pd.concat([daily_df, weekly_df]).sort_index()
            new_candles[context.ticker] = merged_df
        elif not daily_df.empty:
            new_candles[context.ticker] = daily_df
        elif not weekly_df.empty:
            new_candles[context.ticker] = weekly_df
        else:
            console.print(f"[blue]{context.ticker}[/blue]: no new candles available.")
            continue

        updated_contexts = engine.run_incremental_update([context.ticker], new_candles)
        updated.update(updated_contexts)

    if updated:
        table = Table(title="Incremental Update Results")
        table.add_column("Ticker", style="bold cyan")
        table.add_column("Classification", style="green")
        table.add_column("Last Update", style="magenta")
        for ticker, context in updated.items():
            table.add_row(
                ticker,
                context.classification.name if context.classification else "UNKNOWN",
                context.last_update.isoformat() if context.last_update else "",
            )
        console.print(table)
    console.print(Panel(f"Update complete. Persisted results to {db_path}", style="green"))


@app.command()
def classify(
    tickers: Optional[List[str]] = typer.Argument(None, help="Optional tickers to show classification for."),
    db_path: Path = typer.Option(DEFAULT_DB, help="SQLite database file for persistence."),
):
    """Display current classifications from persistence."""
    provider = open_db(db_path)
    contexts = provider.load_all_contexts()
    if tickers:
        contexts = [ctx for ctx in contexts if ctx.ticker in tickers]
    if not contexts:
        raise typer.Exit(code=1, message="No classification records found.")

    table = Table(title="Current Classifications")
    table.add_column("Ticker", style="bold cyan")
    table.add_column("Classification", style="green")
    table.add_column("State", style="yellow")
    table.add_column("TR Qualified", justify="center")
    table.add_column("Last Update", style="magenta")
    for context in contexts:
        table.add_row(
            context.ticker,
            context.classification.name if context.classification else "UNKNOWN",
            context.current_state.name if hasattr(context.current_state, "name") else str(context.current_state),
            "Yes" if context.tr_qualified else "No",
            context.last_update.isoformat() if context.last_update else "",
        )
    console.print(table)


@app.command()
def trades(
    ticker: Optional[str] = typer.Option(None, help="Optional ticker to filter trades."),
    db_path: Path = typer.Option(DEFAULT_DB, help="SQLite database file for persistence."),
    status: str = typer.Option("open", help="Trade status to show: open, closed, or all."),
):
    """Show open or closed trades from persistence."""
    provider = open_db(db_path)
    if status.lower() == "open":
        trades = provider.get_open_trades(ticker)
    else:
        all_trades = provider.get_all_trades(ticker)
        if status.lower() == "closed":
            trades = [trade for trade in all_trades if trade.status != TradeStatus.OPEN]
        else:
            trades = all_trades

    if not trades:
        typer.echo("No matching trades found.")
        raise typer.Exit(code=0)

    table = Table(title=f"Trades ({status.title()})")
    table.add_column("ID", style="bold cyan")
    table.add_column("Ticker", style="white")
    table.add_column("Status", style="green")
    table.add_column("Entry Date", style="magenta")
    table.add_column("Entry Price", justify="right")
    table.add_column("Exit Date", style="magenta")
    table.add_column("Exit Price", justify="right")
    table.add_column("P/L %", justify="right")
    for trade in trades:
        table.add_row(
            str(trade.id),
            trade.ticker,
            trade.status.name if trade.status else "UNKNOWN",
            trade.entry_date.isoformat() if trade.entry_date else "",
            f"{trade.entry_price:.2f}",
            trade.exit_date.isoformat() if trade.exit_date else "",
            f"{trade.exit_price:.2f}" if trade.exit_price else "",
            f"{trade.profit_loss_pct:.2f}%",
        )
    console.print(table)


@app.command()
def report(
    output: Path = typer.Option(Path("trend_rider_report.xlsx"), help="Output XLSX report path."),
    db_path: Path = typer.Option(DEFAULT_DB, help="SQLite database file for persistence."),
    tickers: Optional[List[str]] = typer.Argument(None, help="Optional tickers to include in the report."),
):
    """Generate an XLSX report from persistence data."""
    provider = open_db(db_path)
    contexts = provider.load_all_contexts()
    if tickers:
        contexts = [ctx for ctx in contexts if ctx.ticker in tickers]
    if not contexts:
        raise typer.Exit(code=1, message="No data available for report.")

    classification_rows = [context_to_row(ctx) for ctx in contexts]
    classification_df = pd.DataFrame(classification_rows)
    # Build uptrend details
    uptrend_rows = []
    for ctx in contexts:
        # combine persisted history and current uptrend (if any)
        all_uptrends = list(ctx.uptrend_history)
        if ctx.current_uptrend:
            all_uptrends.append(ctx.current_uptrend)
        for up in all_uptrends:
            uptrend_rows.append({
                "Ticker": ctx.ticker,
                "Classification": ctx.classification.name if ctx.classification else "",
                "Start Date": up.start_date.isoformat() if up.start_date else "",
                "End Date": up.end_date.isoformat() if getattr(up, "end_date", None) else "",
                "Weeks": up.num_weeks,
                "Pct Closes Above": up.pct_closes_above,
                "Strength": up.strength.name if up.strength else "",
                "Highest Price": up.highest_price,
                "Highest Price Date": up.highest_price_date.isoformat() if up.highest_price_date else "",
                "Lowest Price": up.lowest_price,
                "Lowest Price Date": up.lowest_price_date.isoformat() if up.lowest_price_date else "",
            })
    # Ensure at least one row for the sheet
    if not uptrend_rows:
        uptrend_rows.append({
            "Ticker": "",
            "Classification": "",
            "Start Date": "",
            "End Date": "",
            "Weeks": "",
            "Pct Closes Above": "",
            "Strength": "",
            "Highest Price": "",
            "Highest Price Date": "",
            "Lowest Price": "",
            "Lowest Price Date": "",
        })
    uptrends_df = pd.DataFrame(uptrend_rows)
    trade_records = provider.get_all_trades()
    if tickers:
        trade_records = [trade for trade in trade_records if trade.ticker in tickers]
    trades_df = pd.DataFrame(build_trade_rows(trade_records))

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        classification_df.to_excel(writer, sheet_name="Classifications", index=False)
        uptrends_df.to_excel(writer, sheet_name="Uptrends", index=False)
        trades_df.to_excel(writer, sheet_name="Trades", index=False)

    console.print(Panel(f"Report written to {output}", style="green"))


@app.command()
def backtest(
    tickers: List[str] = typer.Argument(..., help="Stock tickers to backtest."),
    db_path: Path = typer.Option(DEFAULT_DB, help="SQLite database file for persistence."),
    output: Path = typer.Option(Path("backtest_results.xlsx"), help="Backtest XLSX output path."),
    start_date: str = typer.Option("2000-01-01", help="Start date for historical backtest."),
    end_date: Optional[str] = typer.Option(None, help="End date for historical backtest."),
    data_file: Optional[Path] = typer.Option(None, help="Optional CSV/XLSX/Parquet file containing OHLCV data."),
):
    """Run backtesting using the Trend Rider strategy wrapper."""
    engine = make_engine(db_path)
    if data_file:
        loaded = load_data_file(data_file)
        if len(loaded) == 1 and "data" in loaded:
            if len(tickers) != 1:
                raise typer.BadParameter("Provide exactly one ticker when passing a single data file without ticker column.")
            daily_data = {tickers[0]: loaded["data"]}
        else:
            daily_data = loaded
            if tickers and set(tickers) != set(daily_data.keys()):
                typer.echo("[yellow]Warning:[/yellow] tickers list and data file tickers do not match; using tickers from data file.")
                tickers = list(daily_data.keys())
    else:
        end_date = end_date or datetime.now().strftime("%Y-%m-%d")
        daily_data = YFinanceDownloader.download_bulk(tickers, start_date, end_date)
        if not daily_data:
            raise typer.Exit(code=1, message="No historical data returned from yfinance.")

    wrapper = StrategyBacktestWrapper(engine, tickers, daily_data)
    report_path = wrapper.run(output)
    console.print(Panel(f"Backtest complete. Results saved to {report_path}", style="green"))


@app.command()
def clean(
    ticker: str = typer.Argument(..., help="Ticker to clean all data for."),
    db_path: Path = typer.Option(DEFAULT_DB, help="SQLite database file for persistence."),
):
    """Delete all persisted data for a ticker (contexts, signals, trades)."""
    provider = open_db(db_path)
    provider.delete_context(ticker)
    provider.delete_signals(ticker)
    provider.delete_trades(ticker)
    console.print(f"All data for ticker '{ticker}' has been removed from {db_path}")

if __name__ == "__main__":
    app()
