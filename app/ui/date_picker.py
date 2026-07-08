"""
CustomTkinter‑compatible date picker wrapper around tkcalendar's DateEntry.

Features
--------
- Matches CustomTkinter dark/light appearance.
- Optional year/month drop‑downs (enabled by tkcalendar by default).
- Returns dates as ``datetime`` objects and ISO ``YYYY‑MM‑DD`` strings.
- Validation that an end date does not precede a start date.
- Emits a ``<<DateChanged>>`` virtual event on selection.
"""

from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import messagebox
from tkinter import ttk

import customtkinter as ctk

try:
    from tkcalendar import DateEntry
except Exception as exc:  # pragma: no cover – optional dependency
    raise ImportError(
        "tkcalendar is required for date pickers. Install it using 'pip install tkcalendar'."
    ) from exc


class CTkDatePicker(ctk.CTkFrame):
    """A CustomTkinter‑styled wrapper for ``tkcalendar.DateEntry``.

    Parameters
    ----------
    master: tk.Widget
        Parent widget.
    label: str | None, optional
        Optional text label displayed to the left of the picker.
    initial: datetime | None, optional
        Initial date to display; defaults to today.
    min_date, max_date: datetime | None, optional
        Limits for selectable dates.
    **kwargs:
        Additional keyword arguments passed to ``CTkFrame``.
    """

    def __init__(
        self,
        master: tk.Widget,
        *,
        label: str | None = None,
        initial: datetime | None = None,
        min_date: datetime | None = None,
        max_date: datetime | None = None,
        enabled: bool = True,
        allow_blank: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)
        self._label_var = tk.StringVar(value=label or "")
        self._allow_blank = allow_blank
        if label:
            ctk.CTkLabel(self, textvariable=self._label_var).pack(side=tk.LEFT, padx=2)

        # Determine background colour that matches CustomTkinter theme.
        # ``CTkFrame`` background can be obtained via ``cget('bg_color')``.
        bg = self.cget("bg_color")
        de_kwargs: dict = {
            "width": 12,
            "mindate": min_date,
            "maxdate": max_date,
            "borderwidth": 1,
            "relief": "ridge",
            # "background": bg[1] if isinstance(bg, tuple) else bg,
            "date_pattern": "yyyy-mm-dd",
            "showweeknumbers": False,
        }
        if initial:
            de_kwargs.update({"year": initial.year, "month": initial.month, "day": initial.day})

        # Create the underlying DateEntry.
        self.date_entry = DateEntry(self, **de_kwargs)
        self.date_entry.pack(side=tk.LEFT, padx=2, pady=2)

        # Bind tkcalendar's event to our custom virtual event.
        self.date_entry.bind("<<DateEntrySelected>>", self._on_date_change)
        self.is_valid = True
        self._enabled = enabled

        # Apply initial enabled/disabled state
        state = "normal" if enabled else "disabled"
        self.date_entry.configure(state=state)

        # Clear button for blankable pickers
        if allow_blank:
            self._clear_btn = ctk.CTkButton(
                self, text="✕", width=24, height=24,
                fg_color="transparent", text_color="gray",
                hover_color="#E0E0E0",
                command=self._clear_date,
            )
            self._clear_btn.pack(side=tk.LEFT, padx=1)
            self._cleared = False

    def _clear_date(self) -> None:
        """Clear the selected date (set to blank/None)."""
        self._cleared = True
        self.date_entry.configure(state="disabled")
        self._clear_btn.configure(text="↻")  # Show reset icon

    # ---------------------------------------------------------------------
    # Event handling
    # ---------------------------------------------------------------------
    def _on_date_change(self, event: tk.Event | None = None) -> None:
        """Callback when the user selects a new date.

        Emits ``<<DateChanged>>`` so external code can react.
        """
        self.is_valid = True
        self.event_generate("<<DateChanged>>")

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the date picker widget.

        When disabled, ``get_date()`` and ``get_date_str()`` return ``None``
        so callers naturally omit date parameters for full-history downloads.
        """
        self._enabled = enabled
        state = "normal" if enabled else "disabled"
        self.date_entry.configure(state=state)

    def get_date(self) -> datetime | None:
        """Return the selected date as a ``datetime`` object or ``None``.

        Returns ``None`` when the picker is disabled or has been cleared.
        """
        if not self._enabled:
            return None
        if getattr(self, "_cleared", False):
            return None
        try:
            return self.date_entry.get_date()
        except Exception:
            return None

    def get_date_str(self) -> str | None:
        """Return the selected date formatted as ``YYYY‑MM‑DD``.

        Returns ``None`` when the picker is disabled or has been cleared.
        """
        dt = self.get_date()
        return dt.strftime("%Y-%m-%d") if dt else None

    def set_date(self, date: datetime | str) -> None:
        """Set the picker to ``date``.

        ``date`` may be a ``datetime`` instance or an ISO ``YYYY‑MM‑DD`` string.
        """
        if isinstance(date, str):
            try:
                date = datetime.strptime(date, "%Y-%m-%d")
            except Exception as exc:  # pragma: no cover – defensive
                raise ValueError(f"Invalid date string: {date}") from exc
        if not isinstance(date, datetime):  # pragma: no cover – defensive
            raise TypeError("date must be datetime or str")
        self.date_entry.set_date(date)

    def validate(self, other_date: datetime | None = None) -> bool:
        """Validate the selected date.

        If ``other_date`` is provided and the current date is earlier, an error
        dialog is shown and ``False`` is returned.
        """
        cur = self.get_date()
        if cur is None:
            self.is_valid = False
            return False
        if other_date and cur < other_date:
            messagebox.showerror(
                "Date Validation",
                "End Date cannot be earlier than Start Date.",
            )
            self.is_valid = False
            return False
        self.is_valid = True
        return True

    def bind_validate(self, callback) -> None:
        """Convenient helper to bind a ``callback`` to ``<<DateChanged>>``.
        """
        self.bind("<<DateChanged>>", lambda e: callback())

    # End of class
