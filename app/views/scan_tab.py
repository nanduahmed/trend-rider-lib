import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import queue
from datetime import datetime
from pathlib import Path

# Import the scan runner
from app.scan_worker import run_scan
from app.ui.date_picker import CTkDatePicker


class ScanTab(ctk.CTkFrame):
    """Tab for configuring and executing a Trend Rider scan.

    The UI has been migrated to **customtkinter** for a modern look.
    """

    def __init__(self, master: tk.Widget):
        super().__init__(master)
        self.master = master
        self._build_ui()
        # Queue for thread‑safe progress updates
        self.progress_queue: queue.Queue = queue.Queue()
        self.after(100, self._process_queue)

    def _build_ui(self) -> None:
        """Create input fields and controls using customtkinter widgets."""
        # ----- Input section -------------------------------------------------
        input_frame = ctk.CTkFrame(self)
        input_frame.pack(fill=tk.X, padx=10, pady=10)

        # Tickers (comma‑separated)
        ctk.CTkLabel(input_frame, text="Tickers (comma separated):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.tickers_entry = ctk.CTkEntry(input_frame, width=500)
        self.tickers_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)

        self.use_date_range = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            input_frame,
            text="Use custom date range",
            variable=self.use_date_range,
            command=self._toggle_date_pickers,
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=5, pady=2)

        self.start_date_picker = CTkDatePicker(input_frame, label="Start Date")
        self.start_date_picker.grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=5, pady=2)

        self.end_date_picker = CTkDatePicker(input_frame, label="End Date")
        self.end_date_picker.grid(row=3, column=0, columnspan=2, sticky=tk.W, padx=5, pady=2)

        # Optional data file
        ctk.CTkLabel(input_frame, text="Data file (optional):").grid(row=4, column=0, sticky=tk.W, padx=5, pady=2)
        self.data_file_var = tk.StringVar()
        data_file_entry = ctk.CTkEntry(input_frame, textvariable=self.data_file_var, width=400)
        data_file_entry.grid(row=4, column=1, sticky=tk.W, padx=5, pady=2)
        ctk.CTkButton(input_frame, text="Browse", command=self._browse_data_file).grid(row=4, column=2, padx=5, pady=2)

        # Debug CSV flag
        self.debug_var = tk.BooleanVar()
        ctk.CTkCheckBox(input_frame, text="Generate debug CSV", variable=self.debug_var).grid(row=5, column=1, sticky=tk.W, padx=5, pady=2)

        # ----- Action section ------------------------------------------------
        action_frame = ctk.CTkFrame(self)
        action_frame.pack(fill=tk.X, padx=10, pady=5)
        ctk.CTkButton(action_frame, text="Run Scan", command=self._start_scan).pack(side=tk.LEFT, padx=5)

        # Progress display (using a CTkLabel for styling)
        self.progress_var = tk.StringVar(value="Idle")
        ctk.CTkLabel(self, textvariable=self.progress_var, text_color="blue").pack(fill=tk.X, padx=10, pady=5)

    def _toggle_date_pickers(self) -> None:
        """Enable or disable the date pickers based on the checkbox state."""
        enabled = self.use_date_range.get()
        self.start_date_picker.set_enabled(enabled)
        self.end_date_picker.set_enabled(enabled)

    def _browse_data_file(self) -> None:
        file_path = filedialog.askopenfilename(title="Select Data File")
        if file_path:
            self.data_file_var.set(file_path)

    def _start_scan(self) -> None:
        # Basic validation – UI only, not business logic.
        tickers = self.tickers_entry.get().strip()
        if not tickers:
            messagebox.showerror("Input Error", "Please provide at least one ticker.")
            return
        # Validate dates only when date range is enabled
        if self.use_date_range.get():
            if not self.start_date_picker.validate():
                return
            if not self.end_date_picker.validate(other_date=self.start_date_picker.get_date()):
                return

        # Disable UI while running
        self.progress_var.set("Scanning…")
        threading.Thread(target=self._run_scan_thread, daemon=True).start()

    def _run_scan_thread(self) -> None:
        # Build arguments for ``run_scan`` – they match the CLI signature.
        args = {
            "tickers": [t.strip() for t in self.tickers_entry.get().split(",") if t.strip()],
        }
        start_str = self.start_date_picker.get_date_str()
        if start_str:
            args["start_date"] = start_str
        end_str = self.end_date_picker.get_date_str()
        if end_str:
            args["end_date"] = end_str
        if self.data_file_var.get():
            args["db_path"] = Path(self.data_file_var.get())
        # debug_csv flag is not applicable to run_scan; omitted
        try:
            run_scan(**args)
            self.progress_queue.put("Scan completed successfully.")
        except Exception as exc:  # pragma: no cover – UI surface only
            self.progress_queue.put(f"Scan failed: {exc}")

    def _process_queue(self) -> None:
        try:
            while True:
                msg = self.progress_queue.get_nowait()
                self.progress_var.set(msg)
        except queue.Empty:
            pass
        finally:
            # Re‑schedule after a short delay.
            self.after(200, self._process_queue)
