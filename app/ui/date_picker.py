"""
Tkinter-friendly wrapper around tkcalendar's DateEntry.

Features:
- Optional year/month drop‑downs.
- Validation that end date is not earlier than start date.
- Provides ``get_date`` and ``set_date`` API.
- Emits a custom virtual event ``<<DateChanged>>`` whenever a new date is selected.
- Styles to match the surrounding Tkinter theme.
- Exposes `is_valid` flag.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from datetime import datetime
from typing import Optional

try:
    from tkcalendar import DateEntry
except Exception as exc:  # pragma: no cover – optional dependency
    raise ImportError(
        "tkcalendar is required for date pickers. Install it using 'pip install tkcalendar'."
    ) from exc


class HistoricalDatePicker(ttk.Frame):
    """A configurable date picker that supports historical dates.

    The widget is built on top of `tkcalendar.DateEntry` but adds a few
    conveniences for the scanner UI:
    * Drop‑down for year and month.
    * ISO‑style ``YYYY-MM-DD`` output.
    * Validation that the end date cannot precede the start date.
    * Optional label text.
    * ``<<DateChanged>>`` virtual event is emitted when the date changes.
    """

    def __init__(self,
                 parent: tk.Widget,
                 *,
                 label: str | None = None,
                 initial: Optional[datetime] = None,
                 min_date: Optional[datetime] = None,
                 max_date: Optional[datetime] = None,
                 **kwargs):
        super().__init__(parent, **kwargs)
        self._label_var = tk.StringVar(value=label or "" if label else "")
        if label:
            ttk.Label(self, textvariable=self._label_var).pack(side=tk.LEFT)

        # Configure DateEntry options
        de_kwargs = {
            "width": 12,
            "mindate": min_date,
            "maxdate": max_date,
            "borderwidth": 1,
            "relief": "ridge",
            "background": "#f0f0f0" if self.cget("bg") == "SystemButtonFace" else self.cget("bg"),  # adjust background
            "date_pattern": "yyyy-mm-dd",
            "showweeknumbers": False,
        }
        if initial:
            de_kwargs["year"] = initial.year
            de_kwargs["month"] = initial.month
            de_kwargs["day"] = initial.day

        # year and month drop‑down menus are enabled by default in tkcalendar
        self.date_entry = DateEntry(self, **de_kwargs)
        self.date_entry.pack(side=tk.LEFT, padx=2, pady=2)

        self.date_entry.bind("<<DateEntrySelected>>", self._on_date_change)
        self.is_valid = True

    def _on_date_change(self, event: tk.Event | None = None) -> None:
        self.is_valid = True
        self.event_generate("<<DateChanged>>")

    def get_date(self) -> Optional[datetime]:
        """Return the selected date as a ``datetime`` object.

        If the widget does not have a valid date, ``None`` is returned.
        """
        try:
            return self.date_entry.get_date()
        except Exception:
            return None

    def set_date(self, date: datetime | str) -> None:
        """Set the picker to the given date.

        ``date`` may be a ``datetime`` object or a string of the form
        ``YYYY-MM-DD``.
        """
        if isinstance(date, str):
            try:
                date = datetime.strptime(date, "%Y-%m-%d")
            except Exception as exc:  # pragma: no cover – defensive
                raise ValueError(repr(date)) from exc
        if not isinstance(date, datetime):  # pragma: no cover – defensive
            raise TypeError("date must be datetime or string")
        self.date_entry.set_date(date)

    def validate(self, other_date: Optional[datetime] = None) -> bool:
        """Validate the date and optionally enforce bounds.

        Parameters
        ----------
        other_date:
            If provided and ``self.get_date()`` is later than ``other_date``
            then an error dialog is shown and ``False`` is returned.
            This method is handy for ensuring that an EndDate picker does
            not precede a StartDate picker.
        """
        date = self.get_date()
        if date is None:
            self.is_valid = False
            return False
        if other_date and date < other_date:
            messagebox.showerror(
                "Date Validation", "End Date cannot be earlier than Start Date."
            )
            self.is_valid = False
            return False
        self.is_valid = True
        return True

    def bind_validate(self, callback) -> None:
        """Convenience to bind to the ``<<DateChanged>>`` virtual event.

        ``callback`` receives no arguments.
        """
        self.bind("<<DateChanged>>", lambda e: callback())

# End of file
