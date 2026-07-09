"""
Settings tab for the Trend Rider app.
Provides a logging level selector and other user preferences.
"""
import logging
import tkinter as tk
from typing import Optional

import customtkinter as ctk

from app.settings_manager import SettingsManager, VALID_LOG_LEVELS, apply_log_level


logger = logging.getLogger(__name__)


class SettingsTab(ctk.CTkFrame):
    """Tab for configuring application settings.

    Currently provides:
        - Logging level selector (persisted across sessions)
    """

    def __init__(self, master: tk.Widget, settings_manager: Optional[SettingsManager] = None) -> None:
        super().__init__(master)
        self.master = master
        self._settings = settings_manager or SettingsManager()
        self._build_ui()

    def _build_ui(self) -> None:
        """Create the settings UI using customtkinter widgets."""

        # ── Header ──────────────────────────────────────────────────────────
        header = ctk.CTkLabel(
            self,
            text="Settings",
            font=("Segoe UI", 20, "bold"),
            text_color="#1E293B",
        )
        header.pack(anchor=tk.W, padx=20, pady=(20, 10))

        separator = ctk.CTkFrame(self, height=2, fg_color="#E2E8F0")
        separator.pack(fill=tk.X, padx=20, pady=(0, 20))

        # ── Logging Section ─────────────────────────────────────────────────
        logging_frame = ctk.CTkFrame(self, fg_color="white", corner_radius=10)
        logging_frame.pack(fill=tk.X, padx=20, pady=10)

        section_header = ctk.CTkLabel(
            logging_frame,
            text="Logging",
            font=("Segoe UI", 16, "bold"),
            text_color="#1E293B",
        )
        section_header.pack(anchor=tk.W, padx=15, pady=(15, 5))

        section_desc = ctk.CTkLabel(
            logging_frame,
            text="Control the verbosity of application logs. Changes take effect immediately.",
            font=("Segoe UI", 12),
            text_color="#64748B",
            wraplength=600,
            justify=tk.LEFT,
        )
        section_desc.pack(anchor=tk.W, padx=15, pady=(0, 15))

        # Logging level row
        level_row = ctk.CTkFrame(logging_frame, fg_color="transparent")
        level_row.pack(fill=tk.X, padx=15, pady=(0, 15))

        level_label = ctk.CTkLabel(
            level_row,
            text="Log Level:",
            font=("Segoe UI", 13),
            text_color="#334155",
        )
        level_label.pack(side=tk.LEFT, padx=(0, 10))

        # Current saved level
        current_level = self._settings.log_level
        # Ensure it's a valid value
        if current_level not in VALID_LOG_LEVELS:
            current_level = "INFO"

        self._level_var = tk.StringVar(value=current_level)
        self._level_combo = ctk.CTkComboBox(
            level_row,
            values=VALID_LOG_LEVELS,
            variable=self._level_var,
            width=150,
            state="readonly",
            font=("Segoe UI", 12),
        )
        self._level_combo.pack(side=tk.LEFT, padx=(0, 10))

        self._apply_btn = ctk.CTkButton(
            level_row,
            text="Apply",
            width=80,
            height=32,
            corner_radius=8,
            fg_color="#1E40AF",
            text_color="white",
            font=("Segoe UI", 12),
            command=self._apply_log_level,
        )
        self._apply_btn.pack(side=tk.LEFT)

        # Status label for feedback
        self._status_var = tk.StringVar(value="")
        self._status_label = ctk.CTkLabel(
            logging_frame,
            textvariable=self._status_var,
            font=("Segoe UI", 11),
            text_color="#22C55E",
        )
        self._status_label.pack(anchor=tk.W, padx=15, pady=(0, 15))

        # ── Info Section ────────────────────────────────────────────────────
        info_frame = ctk.CTkFrame(self, fg_color="white", corner_radius=10)
        info_frame.pack(fill=tk.X, padx=20, pady=10)

        info_header = ctk.CTkLabel(
            info_frame,
            text="About Log Levels",
            font=("Segoe UI", 16, "bold"),
            text_color="#1E293B",
        )
        info_header.pack(anchor=tk.W, padx=15, pady=(15, 10))

        level_descriptions = [
            ("DEBUG", "Detailed diagnostic information for development and troubleshooting."),
            ("INFO", "General operational messages about application progress. (Default)"),
            ("WARNING", "Indications of potential issues that are not yet errors."),
            ("ERROR", "Error events that might still allow the application to continue."),
            ("CRITICAL", "Severe error events that may lead to application termination."),
        ]

        for level_name, description in level_descriptions:
            level_info_row = ctk.CTkFrame(info_frame, fg_color="transparent")
            level_info_row.pack(fill=tk.X, padx=15, pady=2)

            level_badge = ctk.CTkLabel(
                level_info_row,
                text=level_name,
                font=("Segoe UI", 11, "bold"),
                text_color="#1E40AF",
                width=80,
                anchor=tk.W,
            )
            level_badge.pack(side=tk.LEFT)

            level_desc = ctk.CTkLabel(
                level_info_row,
                text=description,
                font=("Segoe UI", 11),
                text_color="#64748B",
                anchor=tk.W,
            )
            level_desc.pack(side=tk.LEFT, padx=(5, 0))

        info_frame.pack_propagate(False)

    def _apply_log_level(self) -> None:
        """Apply the selected logging level and persist the setting."""
        selected = self._level_var.get()
        if selected not in VALID_LOG_LEVELS:
            return

        try:
            # Persist the setting
            self._settings.log_level = selected
            # Apply to all loggers
            apply_log_level(selected)
            # Show feedback
            self._status_var.set(f"✓ Log level changed to {selected}")
            self._status_label.configure(text_color="#22C55E")
            logger.info("Log level changed to %s via Settings tab", selected)
        except Exception as exc:
            self._status_var.set(f"✗ Failed to apply: {exc}")
            self._status_label.configure(text_color="#EF4444")
            logger.exception("Failed to apply log level %s", selected)