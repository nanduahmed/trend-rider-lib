"""Test script to verify Results tab navigation works."""
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk

# Test importing all modules
try:
    from app.views.scan_tab import ScanTab
    from app.views.results_tab import ResultsTab
    print("✓ All views imported successfully")
except ImportError as e:
    print(f"✗ Import error: {e}")
    exit(1)

# Test creating a simple window with navigation
root = ctk.CTk()
root.title("Test Navigation")
root.geometry("800x600")

sidebar = ctk.CTkFrame(root, width=200, fg_color="#0B192C")
sidebar.pack(side="left", fill="y")
sidebar.pack_propagate(False)

content_area = ctk.CTkFrame(root, fg_color="#F8F9FA")
content_area.pack(side="right", fill="both", expand=True)

def clear_content():
    for widget in content_area.winfo_children():
        widget.destroy()

def show_scan():
    clear_content()
    scan = ScanTab(content_area)
    scan.pack(fill="both", expand=True, padx=15, pady=15)
    print("✓ Scan tab displayed")

def show_results():
    clear_content()
    results = ResultsTab(content_area)
    results.pack(fill="both", expand=True, padx=15, pady=15)
    print("✓ Results tab displayed")

scan_btn = ctk.CTkButton(sidebar, text="Scan", command=show_scan)
scan_btn.pack(pady=10, padx=20)

results_btn = ctk.CTkButton(sidebar, text="Results", command=show_results)
results_btn.pack(pady=10, padx=20)

# Start with Scan tab
show_scan()

print("\nTest completed. The UI should show:")
print("- A dark sidebar on the left with 'Scan' and 'Results' buttons")
print("- The Scan tab content on the right")
print("\nClick 'Results' to test the Results tab navigation.")

root.mainloop()