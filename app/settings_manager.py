"""
Settings manager for the Trend Rider app.
Persists user preferences (logging level, etc.) to a JSON config file.
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Default config path relative to this file
DEFAULT_CONFIG_PATH = Path(__file__).parent / "config.json"

# Industry-standard default: INFO
DEFAULT_LOG_LEVEL = "INFO"

# Valid logging levels
VALID_LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

# Mapping from level name to Python logging constant
LOG_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


class SettingsManager:
    """Manages app settings persisted to a JSON config file.

    Settings are loaded on instantiation and saved on every update.
    """

    def __init__(self, config_path: Optional[Path] = None) -> None:
        self._config_path = config_path or DEFAULT_CONFIG_PATH
        self._settings: Dict[str, Any] = {}
        self._load()

    # ── Public API ──────────────────────────────────────────────────────────

    @property
    def log_level(self) -> str:
        """Return the current logging level name (e.g. 'INFO')."""
        return self._settings.get("log_level", DEFAULT_LOG_LEVEL)

    @log_level.setter
    def log_level(self, level: str) -> None:
        """Set and persist the logging level.

        Args:
            level: One of DEBUG, INFO, WARNING, ERROR, CRITICAL.
        """
        if level not in VALID_LOG_LEVELS:
            raise ValueError(f"Invalid log level: {level}. Must be one of {VALID_LOG_LEVELS}")
        self._settings["log_level"] = level
        self._save()

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value by key."""
        return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set and persist a setting value."""
        self._settings[key] = value
        self._save()

    def get_all(self) -> Dict[str, Any]:
        """Return a copy of all settings."""
        return dict(self._settings)

    # ── Internal helpers ────────────────────────────────────────────────────

    def _load(self) -> None:
        """Load settings from the JSON config file."""
        if self._config_path.exists():
            try:
                with open(self._config_path, "r", encoding="utf-8") as f:
                    self._settings = json.load(f)
                logger.debug("Settings loaded from %s", self._config_path)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to load settings from %s: %s. Using defaults.", self._config_path, exc)
                self._settings = {}
        else:
            logger.debug("No config file at %s. Using defaults.", self._config_path)
            self._settings = {}

        # Ensure log_level is always present
        if "log_level" not in self._settings:
            self._settings["log_level"] = DEFAULT_LOG_LEVEL

    def _save(self) -> None:
        """Persist settings to the JSON config file."""
        try:
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, indent=2)
            logger.debug("Settings saved to %s", self._config_path)
        except OSError as exc:
            logger.error("Failed to save settings to %s: %s", self._config_path, exc)


def apply_log_level(level_name: str) -> None:
    """Apply the given logging level to the root logger and all existing loggers.

    Args:
        level_name: One of DEBUG, INFO, WARNING, ERROR, CRITICAL.
    """
    level = LOG_LEVEL_MAP.get(level_name, logging.INFO)
    logging.getLogger().setLevel(level)
    # Also update all existing loggers so the change takes effect immediately
    for name in logging.root.manager.loggerDict:  # type: ignore[union-attr]
        logging.getLogger(name).setLevel(level)
    logger.debug("Log level set to %s", level_name)