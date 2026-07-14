import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import threading
import queue
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from app.database import Database
from app.ui.date_picker import CTkDatePicker
from app.update_worker import run_update


class UpdateTab(ctk.CTkFrame):
    """Tab for running incremental updates on previously-scanned stocks."""

    def __init__(self, master: tk.Widget):
        super().__init__(master)
        self.master = master
        self.db = Database()
        self._ticker_vars: Dict[str, tk.BooleanVar] = {}
        self.progress_queue: queue.Queue = queue.Queue()
        self._build_ui()
        self._populate_ticker_list()
        self.after(100, self._process_queue)

    def _build_ui(self) -> None:
        # ----- Stock selection section ------------------------------------------
        selection_frame = ctk.CTkFrame(self)
        selection_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        ctk.CTkLabel(
            selection_frame,
            text="Select Stocks to Update",
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor=tk.W, padx=5, pady=(5, 5))

        # Select All / Deselect All toolbar
        btn_frame = ctk.CTkFrame(selection_frame, fg_color="transparent")
        btn_frame.pack(fill=tk.X, padx=5, pady=(0, 5))

        ctk.CTkButton(
            btn_frame,
            text="Select All",
            width=100,
            height=28,
            corner_radius=6,
            command=self._select_all,
        ).pack(side=tk.LEFT, padx=(0, 5))

        ctk.CTkButton(
            btn_frame,
            text="Deselect All",
            width=100,
            height=28,
            corner_radius=6,
            command=self._deselect_all,
        ).pack(side=tk.LEFT)

        # Scrollable ticker list
        self.ticker_scroll = ctk.CTkScrollableFrame(selection_frame, height=180)
        self.ticker_scroll.pack(fill=tk.X, padx=5, pady=(0, 5))

        # ----- Options section --------------------------------------------------
        options_frame = ctk.CTkFrame(self)
        options_frame.pack(fill=tk.X, padx=10, pady=5)

        self.debug_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            options_frame,
            text="Generate debug CSV",
            variable=self.debug_var,
        ).pack(side=tk.LEFT, padx=5, pady=5)

        # ----- End date section -------------------------------------------------
        date_frame = ctk.CTkFrame(self)
        date_frame.pack(fill=tk.X, padx=10, pady=5)

        self.use_end_date = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            date_frame,
            text="Use end date",
            variable=self.use_end_date,
            command=self._toggle_date_picker,
        ).pack(side=tk.LEFT, padx=5, pady=5)

        self.end_date_picker = CTkDatePicker(date_frame, label="End Date")
        self.end_date_picker.pack(side=tk.LEFT, padx=5, pady=5)
        self.end_date_picker.set_enabled(False)

        # ----- Action section ---------------------------------------------------
        action_frame = ctk.CTkFrame(self)
        action_frame.pack(fill=tk.X, padx=10, pady=5)

        self.apply_btn = ctk.CTkButton(
            action_frame,
            text="Apply Incremental Update",
            height=36,
            corner_radius=8,
            command=self._start_update,
        )
        self.apply_btn.pack(side=tk.LEFT, padx=5)

        self.progress_var = tk.StringVar(value="Idle")
        ctk.CTkLabel(
            action_frame,
            textvariable=self.progress_var,
            text_color="blue",
        ).pack(side=tk.LEFT, padx=15)

        # ----- Feedback section -------------------------------------------------
        feedback_frame = ctk.CTkFrame(self)
        feedback_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

        ctk.CTkLabel(
            feedback_frame,
            text="Update Log",
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor=tk.W, padx=5, pady=(5, 2))

        self.feedback_text = ctk.CTkTextbox(feedback_frame, wrap=tk.WORD)
        self.feedback_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.feedback_text.configure(state=tk.DISABLED)

    def _populate_ticker_list(self) -> None:
        """Load all tickers from the database into checkboxes."""
        for widget in self.ticker_scroll.winfo_children():
            widget.destroy()
        self._ticker_vars.clear()

        try:
            tickers = self.db.get_all_tickers()
        except Exception:
            tickers = []

        if not tickers:
            ctk.CTkLabel(
                self.ticker_scroll,
                text="No scanned stocks found. Run a scan first.",
                text_color="gray",
            ).pack(padx=5, pady=10)
            return

        for ticker in tickers:
            var = tk.BooleanVar(value=False)
            self._ticker_vars[ticker] = var
            cb = ctk.CTkCheckBox(
                self.ticker_scroll,
                text=ticker,
                variable=var,
                font=("Consolas", 12),
            )
            cb.pack(anchor=tk.W, padx=8, pady=2)

    def _select_all(self) -> None:
        for var in self._ticker_vars.values():
            var.set(True)

    def _deselect_all(self) -> None:
        for var in self._ticker_vars.values():
            var.set(False)

    def _toggle_date_picker(self) -> None:
        self.end_date_picker.set_enabled(self.use_end_date.get())

    def _log(self, message: str) -> None:
        """Append a line to the feedback text box."""
        self.feedback_text.configure(state=tk.NORMAL)
        self.feedback_text.insert(tk.END, message + "\n")
        self.feedback_text.see(tk.END)
        self.feedback_text.configure(state=tk.DISABLED)

    def _start_update(self) -> None:
        selected = [t for t, v in self._ticker_vars.items() if v.get()]
        if not selected:
            messagebox.showwarning("No Selection", "Please select at least one stock to update.")
            return

        if self.use_end_date.get() and not self.end_date_picker.validate():
            return

        self.apply_btn.configure(state=tk.DISABLED)
        self.feedback_text.configure(state=tk.NORMAL)
        self.feedback_text.delete("1.0", tk.END)
        self.feedback_text.configure(state=tk.DISABLED)

        end_date = self.end_date_picker.get_date_str() if self.use_end_date.get() else None
        self.progress_var.set(f"Updating {len(selected)} stock(s)…")

        threading.Thread(
            target=self._run_update_thread,
            args=(selected, end_date),
            daemon=True,
        ).start()

    def _run_update_thread(
        self, tickers: List[str], end_date: Optional[str]
    ) -> None:
        self.progress_queue.put(f"Starting incremental update for {len(tickers)} ticker(s)")
        if end_date:
            self.progress_queue.put(f"End date: {end_date}")
        debug_csv = self.debug_var.get()
        if debug_csv:
            self.progress_queue.put("Debug CSV generation enabled")

        try:
            results, skipped = run_update(tickers, end_date=end_date, debug_csv=debug_csv)

            for ticker in skipped:
                self.progress_queue.put(f"  {ticker} ⏭ Skipped – no saved context")

            for ticker in sorted(results.keys()):
                ctx = results[ticker]
                cls_name = ctx.classification.name if ctx.classification else "UNKNOWN"
                last_up = ctx.last_update
                if hasattr(last_up, "strftime"):
                    last_up = last_up.strftime("%d-%m-%Y")
                self.progress_queue.put(f"  {ticker} ✓ Updated – {cls_name} ({last_up})")

            total = len(results)
            self.progress_queue.put(
                f"Update complete. {total} ticker(s) updated, {len(skipped)} skipped."
            )
        except Exception as exc:
            self.progress_queue.put(f"Update failed: {exc}")

        self.progress_queue.put("__DONE__")

    def _process_queue(self) -> None:
        try:
            while True:
                msg = self.progress_queue.get_nowait()
                if msg == "__DONE__":
                    self.apply_btn.configure(state=tk.NORMAL)
                    self.progress_var.set("Idle")
                else:
                    self._log(msg)
        except queue.Empty:
            pass
        finally:
            self.after(200, self._process_queue)
