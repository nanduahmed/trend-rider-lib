import customtkinter as ctk
import tkinter as tk
from tkinter import ttk

# Import view modules
try:
    from app.views.scan_tab import ScanTab
    from app.views.results_tab import ResultsTab
except ImportError as e:
    print(f"Warning: Could not import views: {e}")
    ScanTab = None
    ResultsTab = None


def main() -> None:
    """Create and run the main application window using customtkinter.

    The UI follows a modern SaaS‑style layout with a dark sidebar and a tab view.
    """
    # Set the appearance and theme for customtkinter
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.title("Trend Rider Scanner")
    root.geometry("1024x768")

    # -----------------------------------------------------------------
    # Sidebar navigation – fixed width, dark background, proper padding
    # -----------------------------------------------------------------
    sidebar = ctk.CTkFrame(root, width=220, corner_radius=0, fg_color="#0B192C")
    sidebar.pack(side="left", fill="y")
    sidebar.pack_propagate(False)  # Maintain fixed width

    # Branding at the top of the sidebar
    branding_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
    branding_frame.pack(fill="x", padx=20, pady=(30, 40))

    branding = ctk.CTkLabel(
        branding_frame,
        text="Trend Rider",
        font=("Segoe UI", 20, "bold"),
        text_color="white"
    )
    branding.pack(pady=5)

    # Navigation buttons frame with proper padding
    nav_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
    nav_frame.pack(fill="x", padx=20, pady=10)

    # Current view tracking
    current_view = {"frame": None, "button": None}

    def clear_content():
        """Remove all widgets from content area."""
        for widget in content_area.winfo_children():
            widget.destroy()

    def set_active_button(btn):
        """Highlight the active navigation button."""
        if current_view["button"]:
            current_view["button"].configure(fg_color="transparent", text_color="white")
        btn.configure(fg_color="#1E40AF", text_color="white")  # Royal blue accent

    def show_scan():
        """Display the Scan tab."""
        clear_content()
        if ScanTab:
            scan_view = ScanTab(content_area)
            scan_view.pack(fill="both", expand=True, padx=15, pady=15)
        set_active_button(scan_btn)
        current_view["button"] = scan_btn

    def show_results():
        """Display the Results tab."""
        clear_content()
        if ResultsTab:
            results_view = ResultsTab(content_area)
            results_view.pack(fill="both", expand=True, padx=15, pady=15)
        else:
            # Show placeholder if ResultsTab is not available
            placeholder = ctk.CTkLabel(content_area, text="Results view not available", 
                                       font=("Segoe UI", 16))
            placeholder.pack(pady=50)
        set_active_button(results_btn)
        current_view["button"] = results_btn

    # Navigation buttons with proper styling
    scan_btn = ctk.CTkButton(
        nav_frame,
        text="Scan",
        width=180,
        height=40,
        corner_radius=8,
        fg_color="transparent",
        text_color="white",
        font=("Segoe UI", 14),
        anchor="w",
        command=show_scan
    )
    scan_btn.pack(pady=8)

    results_btn = ctk.CTkButton(
        nav_frame,
        text="Results",
        width=180,
        height=40,
        corner_radius=8,
        fg_color="transparent",
        text_color="white",
        font=("Segoe UI", 14),
        anchor="w",
        command=show_results
    )
    results_btn.pack(pady=8)

    # Spacer to push bottom elements down
    spacer = ctk.CTkFrame(sidebar, fg_color="transparent")
    spacer.pack(fill="both", expand=True)

    # Bottom section – Export button and connection status
    bottom_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
    bottom_frame.pack(fill="x", padx=20, pady=(10, 20))

    # Export Data button
    export_btn = ctk.CTkButton(
        bottom_frame,
        text="Export Data",
        width=180,
        height=35,
        corner_radius=8,
        fg_color="#374151",  # Gray background
        text_color="white",
        font=("Segoe UI", 12),
        anchor="w"
    )
    export_btn.pack(pady=8)

    # Connection status indicator
    status_frame = ctk.CTkFrame(bottom_frame, fg_color="transparent")
    status_frame.pack(fill="x", pady=5)

    # Green dot indicator
    status_dot = ctk.CTkLabel(
        status_frame,
        text="●",
        text_color="#22C55E",  # Green color
        font=("Segoe UI", 12)
    )
    status_dot.pack(side="left", padx=(0, 5))

    status_text = ctk.CTkLabel(
        status_frame,
        text="Connected - Live Data",
        text_color="#9CA3AF",  # Gray text
        font=("Segoe UI", 11)
    )
    status_text.pack(side="left")

    # -----------------------------------------------------------------
    # Main content area – will host the current view
    # -----------------------------------------------------------------
    content_area = ctk.CTkFrame(root, fg_color="#F8F9FA")  # Light gray background
    content_area.pack(side="right", fill="both", expand=True)

    # Initialize with Scan view as default
    show_scan()

    # Start the Tkinter (customtkinter) main loop
    root.mainloop()


if __name__ == "__main__":
    main()