from pathlib import Path
import typer
import webbrowser
import os
from trend_rider_lib.cli import app, DEFAULT_DB, DEFAULT_CACHE_DIR, DEFAULT_OUTPUT_DIR

# Create a new Typer app
app_new = typer.Typer(help="Enhanced Trend Rider CLI with directory management")

# Add callback to handle directory opening
def open_directory_callback(ctx: typer.Context, param: typer.CallbackParam, value: Path):
    if ctx.invoked_subcommand is not None and value:
        if os.path.exists(str(value)):
            webbrowser.open(str(value))
            typer.echo(f"Opened directory: {value}")
        else:
            typer.echo(f"Directory does not exist: {value}")
    return value

@app_new.callback()
def main(
    open_output: Path = typer.Option(
        DEFAULT_OUTPUT_DIR,
        "--open-output",
        help="Open output directory",
        callback=open_directory_callback
    ),
    open_cache: Path = typer.Option(
        DEFAULT_CACHE_DIR,
        "--open-cache", 
        help="Open cache directory",
        callback=open_directory_callback
    ),
    open_db: Path = typer.Option(
        DEFAULT_DB,
        "--open-db",
        help="Open database file",
        callback=open_directory_callback
    ),
):
    """Enhanced Trend Rider CLI with directory management options."""
    pass

# Copy commands from original app to new app
for command in app.commands.values():
    app_new.registered_commands[command.name] = command

if __name__ == "__main__":
    app_new()