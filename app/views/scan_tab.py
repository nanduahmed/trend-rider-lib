import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import queue
import webbrowser
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
        self.tickers_entry = ctk.CTkEntry(input_frame, width=500, placeholder_text="POLYCAB.NS")
        self.tickers_entry.insert(0, "TIINDIA.NS")
        self.tickers_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)

        self.use_date_range = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            input_frame,
            text="Use custom date range",
            variable=self.use_date_range,
            command=self._toggle_date_pickers,
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=5, pady=2)

        self.start_date_picker = CTkDatePicker(input_frame, label="Start Date", allow_blank=True)
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
            start_date = self.start_date_picker.get_date()
            # Allow blank start date (None) – user may want full history
            if self.start_date_picker.get_date_str() and not self.start_date_picker.validate():
                return
            if not self.end_date_picker.validate(other_date=start_date):
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
        if self.debug_var.get():
            args["debug_csv"] = True
        try:
            result = run_scan(**args)
            # Build success message with CSV links if debug was enabled
            msg = "Scan completed successfully."
            if isinstance(result, dict) and result.get("debug_csv_paths"):
                paths = result["debug_csv_paths"]
                dir_path = result.get("debug_csv_dir", "")
                msg = f"Scan completed. {len(paths)} debug CSV(s) generated."
                self.progress_queue.put(("success_with_csv", msg, paths, dir_path))
            else:
                self.progress_queue.put(("success", msg))
        except Exception as exc:  # pragma: no cover – UI surface only
            self.progress_queue.put(("error", f"Scan failed: {exc}"))

    def _process_queue(self) -> None:
        try:
            while True:
                msg = self.progress_queue.get_nowait()
                if isinstance(msg, tuple):
                    msg_type = msg[0]
                    if msg_type == "success_with_csv":
                        text = msg[1]
                        csv_paths = msg[2]
                        csv_dir = msg[3]
                        self.progress_var.set(text)
                        # Show CSV links in a frame below progress
                        self._show_csv_links(csv_paths, csv_dir)
                    elif msg_type == "success":
                        self.progress_var.set(msg[1])
                    elif msg_type == "error":
                        self.progress_var.set(msg[1])
                else:
                    self.progress_var.set(msg)
        except queue.Empty:
            pass
        finally:
            # Re‑schedule after a short delay.
            self.after(200, self._process_queue)

    def _show_csv_links(self, csv_paths: list, csv_dir: str) -> None:
        """Display clickable links to generated CSV files and their folder."""
        # Remove any previous CSV links frame
        for widget in getattr(self, "_csv_links_frame", None) or []:
            widget.destroy()
        self._csv_links_frame = []

        links_frame = ctk.CTkFrame(self, fg_color="#F0F8FF")
        links_frame.pack(fill=tk.X, padx=10, pady=5)
        self._csv_links_frame.append(links_frame)

        # Link to containing folder
        if csv_dir:
            folder_link = ctk.CTkLabel(
                links_frame, text=f"📁 Open CSV folder: {csv_dir}",
                text_color="blue", cursor="hand2",
                font=("Segoe UI", 11, "underline"),
            )
            folder_link.pack(anchor=tk.W, padx=5, pady=2)
            folder_link.bind("<Button-1>", lambda e, d=csv_dir: webbrowser.open(d))

        # Links to individual CSV files
        for path in csv_paths:
            csv_link = ctk.CTkLabel(
                links_frame, text=f"📄 {Path(path).name}",
                text_color="blue", cursor="hand2",
                font=("Segoe UI", 11, "underline"),
            )
            csv_link.pack(anchor=tk.W, padx=5, pady=1)
            csv_link.bind("<Button-1>", lambda e, p=path: webbrowser.open(p))
