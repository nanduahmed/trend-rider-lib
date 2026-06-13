import tkinter as tk
from tkinter import ttk

# Import view modules (they will be created later)
try:
    from .views.scan_tab import ScanTab
    from .views.results_tab import ResultsTab
except ImportError:
    # Views may not exist yet during initial development; placeholder classes will be defined later.
    ScanTab = None
    ResultsTab = None

def main() -> None:
    """Create and run the main Tkinter application window."""
    root = tk.Tk()
    root.title("Trend Rider Scanner")
    root.geometry("1024x768")

    # Create a notebook (tabbed interface)
    notebook = ttk.Notebook(root)
    notebook.pack(fill=tk.BOTH, expand=True)

    # Scan configuration and execution tab
    if ScanTab is not None:
        scan_frame = ScanTab(notebook)
        notebook.add(scan_frame, text="Scan")

    # Results viewing tab
    if ResultsTab is not None:
        results_frame = ResultsTab(notebook)
        notebook.add(results_frame, text="Results")

    # Start the Tkinter main loop
    root.mainloop()

if __name__ == "__main__":
    main()
