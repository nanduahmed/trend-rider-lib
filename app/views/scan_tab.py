import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import queue
from datetime import datetime
from pathlib import Path

# Import the scan runner
from app.scan_worker import run_scan

class ScanTab(ttk.Frame):
    """Tab for configuring and executing a Trend Rider scan.

    The UI elements are deliberately lightweight – all business logic is delegated to
    ``run_scan`` which uses ``app.handler.ScanResultHandler`` to persist results.
    """

    def __init__(self, master: tk.Widget):
        super().__init__(master)
        self.master = master
        self._build_ui()
        # Queue for thread‑safe progress updates
        self.progress_queue: queue.Queue = queue.Queue()
        self.after(100, self._process_queue)

    def _build_ui(self) -> None:
        # --- Input section -------------------------------------------------
        input_frame = ttk.LabelFrame(self, text="Scan Options")
        input_frame.pack(fill=tk.X, padx=10, pady=10)

        # Tickers (comma‑separated)
        ttk.Label(input_frame, text="Tickers (comma separated):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.tickers_entry = ttk.Entry(input_frame, width=80)
        self.tickers_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)

        # Date range
        ttk.Label(input_frame, text="Start Date (YYYY‑MM‑DD):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.start_date_entry = ttk.Entry(input_frame, width=20)
        self.start_date_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(input_frame, text="End Date (YYYY‑MM‑DD):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.end_date_entry = ttk.Entry(input_frame, width=20)
        self.end_date_entry.grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)

        # Optional data file
        ttk.Label(input_frame, text="Data file (optional):").grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)
        self.data_file_var = tk.StringVar()
        data_file_entry = ttk.Entry(input_frame, textvariable=self.data_file_var, width=60)
        data_file_entry.grid(row=3, column=1, sticky=tk.W, padx=5, pady=2)
        ttk.Button(input_frame, text="Browse", command=self._browse_data_file).grid(row=3, column=2, padx=5, pady=2)

        # Debug CSV flag
        self.debug_var = tk.BooleanVar()
        ttk.Checkbutton(input_frame, text="Generate debug CSV", variable=self.debug_var).grid(row=4, column=1, sticky=tk.W, padx=5, pady=2)

        # --- Action section ------------------------------------------------
        action_frame = ttk.Frame(self)
        action_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(action_frame, text="Run Scan", command=self._start_scan).pack(side=tk.LEFT, padx=5)

        # Progress display
        self.progress_var = tk.StringVar(value="Idle")
        ttk.Label(self, textvariable=self.progress_var, foreground="blue").pack(fill=tk.X, padx=10, pady=5)

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
        start = self.start_date_entry.get().strip()
        end = self.end_date_entry.get().strip()
        try:
            if start:
                datetime.strptime(start, "%Y-%m-%d")
            if end:
                datetime.strptime(end, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Input Error", "Dates must be in YYYY-MM-DD format.")
            return

        # Disable UI while running
        self.progress_var.set("Scanning…")
        threading.Thread(target=self._run_scan_thread, daemon=True).start()

    def _run_scan_thread(self) -> None:
        # Build arguments for ``run_scan`` – they match the CLI signature.
        args = {
            "tickers": [t.strip() for t in self.tickers_entry.get().split(",") if t.strip()],
        }
        if self.start_date_entry.get().strip():
            args["start_date"] = self.start_date_entry.get().strip()
        if self.end_date_entry.get().strip():
            args["end_date"] = self.end_date_entry.get().strip()
        if self.data_file_var.get():
            args["db_path"] = Path(self.data_file_var.get())
        # debug_csv flag is not applicable to run_scan; omitted
        # ``run_scan`` expects positional arguments; use ** to unpack.
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
