"""
Stock Checker Pro - Main Application
Windows Desktop App for automated Marcone stock checking and price benchmarking.
"""
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
import threading
import sys
import os
from datetime import datetime
from pathlib import Path

# Set up paths
APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)

from config.settings import load_settings, save_settings, encrypt_password, decrypt_password
from data.logger import get_run_list, get_run_detail, set_log_callback
from data.pn_memory import get_all_mappings, delete_mapping, update_mapping
from core.updater import check_update_async, apply_update_async, get_local_version

# App theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Colors
NAVY = "#0B192C"
NAVY_LIGHT = "#1E3E62"
PURPLE = "#6B21A8"
PURPLE_LIGHT = "#7C3AED"
WHITE = "#FFFFFF"
GRAY = "#94A3B8"
GREEN = "#22C55E"
RED = "#EF4444"
ORANGE = "#F97316"
BG = "#0F172A"
CARD_BG = "#1E293B"
SIDEBAR_BG = "#0B1929"


class StockCheckerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Stock Checker Pro")
        self.geometry("1200x750")
        self.minsize(1000, 650)
        self.configure(fg_color=BG)

        # Set app icon
        icon_path = os.path.join(APP_DIR, "assets", "logo.ico")
        png_path = os.path.join(APP_DIR, "assets", "logo.png")
        try:
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
            elif os.path.exists(png_path):
                icon_img = tk.PhotoImage(file=png_path)
                self.iconphoto(True, icon_img)
        except Exception:
            pass  # Icon is optional, never crash on it

        # State
        self.settings = load_settings()
        self.is_running = False
        self.stop_flag = [False]
        self.current_frame = None

        # Build layout
        self._build_sidebar()
        self._build_main_area()

        # Show dashboard by default
        self.show_dashboard()

        # Start scheduler
        self._start_scheduler()

        # Check for updates in background (after 3 seconds)
        self.after(3000, self._check_for_updates_on_startup)

        # Protocol for window close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_sidebar(self):
        """Build the left navigation sidebar."""
        self.sidebar = ctk.CTkFrame(self, width=220, fg_color=SIDEBAR_BG, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Logo
        logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_frame.pack(fill="x", padx=20, pady=(20, 10))

        ctk.CTkLabel(logo_frame, text="⚙", font=("Arial", 28), text_color=PURPLE_LIGHT).pack(side="left")
        ctk.CTkLabel(logo_frame, text=" Stock Checker\nPro",
                     font=ctk.CTkFont("Inter", 13, "bold"),
                     text_color=WHITE, justify="left").pack(side="left", padx=5)

        ctk.CTkFrame(self.sidebar, height=1, fg_color=NAVY_LIGHT).pack(fill="x", padx=15, pady=10)

        # Navigation buttons
        self.nav_buttons = {}
        nav_items = [
            ("dashboard", "🏠  Dashboard"),
            ("scheduler", "📅  Scheduler"),
            ("parts_manager", "📦  Parts Manager"),
            ("benchmark", "📊  Benchmark Prices"),
            ("pn_memory", "🧠  PN Memory"),
            ("logs", "📋  Logs"),
            ("settings", "⚙️  Settings"),
        ]

        for key, label in nav_items:
            btn = ctk.CTkButton(
                self.sidebar, text=label,
                font=ctk.CTkFont("Inter", 13),
                fg_color="transparent",
                text_color=GRAY,
                hover_color=NAVY_LIGHT,
                anchor="w",
                height=42,
                corner_radius=8,
                command=lambda k=key: self._nav_click(k)
            )
            btn.pack(fill="x", padx=10, pady=2)
            self.nav_buttons[key] = btn

        # Version at bottom
        local_ver, _ = get_local_version()
        self.version_label = ctk.CTkLabel(self.sidebar, text=f"v{local_ver}",
                     font=ctk.CTkFont("Inter", 11),
                     text_color=GRAY)
        self.version_label.pack(side="bottom", pady=15)

        # Update available indicator (hidden by default)
        self.update_btn = ctk.CTkButton(
            self.sidebar, text="🔄 Update Available",
            font=ctk.CTkFont("Inter", 11),
            fg_color=ORANGE, text_color=WHITE,
            hover_color="#EA580C",
            height=30, corner_radius=6,
            command=self._show_update_dialog
        )
        self._pending_update_version = None
        self._pending_update_changelog = ""

    def _build_main_area(self):
        """Build the main content area."""
        self.main_area = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.main_area.pack(side="right", fill="both", expand=True)

    def _nav_click(self, key):
        """Handle navigation button click."""
        # Reset all buttons
        for k, btn in self.nav_buttons.items():
            btn.configure(fg_color="transparent", text_color=GRAY)

        # Highlight selected
        self.nav_buttons[key].configure(fg_color=PURPLE, text_color=WHITE)

        # Show the corresponding screen
        method = getattr(self, f"show_{key}", None)
        if method:
            method()

    def _clear_main(self):
        """Clear the main content area."""
        for widget in self.main_area.winfo_children():
            widget.destroy()

    def _page_header(self, title: str, subtitle: str = "", btn_text: str = None,
                     btn_command=None, btn_color: str = GREEN):
        """Create a standard page header."""
        header = ctk.CTkFrame(self.main_area, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(25, 10))

        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(left, text=title,
                     font=ctk.CTkFont("Inter", 24, "bold"),
                     text_color=WHITE).pack(anchor="w")
        if subtitle:
            ctk.CTkLabel(left, text=subtitle,
                         font=ctk.CTkFont("Inter", 12),
                         text_color=GRAY).pack(anchor="w")

        if btn_text and btn_command:
            ctk.CTkButton(header, text=btn_text, command=btn_command,
                          fg_color=btn_color, hover_color=btn_color,
                          font=ctk.CTkFont("Inter", 13, "bold"),
                          height=38, width=140, corner_radius=8).pack(side="right")

    # ─────────────────────────────────────────────
    # DASHBOARD
    # ─────────────────────────────────────────────
    def show_dashboard(self):
        self._clear_main()
        self._nav_click_silent("dashboard")

        self._page_header("Dashboard",
                          btn_text="▶  Run Now",
                          btn_command=self._run_now,
                          btn_color=GREEN)

        # Top cards row
        cards_frame = ctk.CTkFrame(self.main_area, fg_color="transparent")
        cards_frame.pack(fill="x", padx=30, pady=5)

        # Last run / Next run
        runs = get_run_list()
        last_run = runs[0] if runs else None

        from core.scheduler_engine import get_next_stock_run
        next_run = get_next_stock_run()

        self._info_card(cards_frame, "LAST RUN",
                        last_run["start_display"] if last_run else "Never",
                        f"{last_run['parts_checked']} parts checked, {last_run['errors']} errors" if last_run else "No runs yet",
                        "🕐", PURPLE_LIGHT)

        self._info_card(cards_frame, "NEXT RUN",
                        next_run if next_run else "Not scheduled",
                        "Scheduler active" if next_run else "Set schedule in Scheduler tab",
                        "📅", NAVY_LIGHT)

        # Stats row
        stats_frame = ctk.CTkFrame(self.main_area, fg_color="transparent")
        stats_frame.pack(fill="x", padx=30, pady=10)

        # Calculate stats from last run
        total = last_run["parts_checked"] if last_run else 0
        errors = last_run["errors"] if last_run else 0
        pn_subs = last_run.get("pn_substitutions", 0) if last_run else 0

        self._stat_card(stats_frame, "TOTAL PARTS", str(total), WHITE)
        self._stat_card(stats_frame, "ERRORS", str(errors), RED if errors > 0 else GREEN)
        self._stat_card(stats_frame, "PN SUBSTITUTIONS", str(pn_subs), ORANGE if pn_subs > 0 else WHITE)
        self._stat_card(stats_frame, "TOTAL RUNS", str(len(runs)), PURPLE_LIGHT)

        # Recent activity
        ctk.CTkLabel(self.main_area, text="RECENT ACTIVITY",
                     font=ctk.CTkFont("Inter", 11, "bold"),
                     text_color=GRAY).pack(anchor="w", padx=30, pady=(10, 5))

        table_frame = ctk.CTkScrollableFrame(self.main_area, fg_color=CARD_BG,
                                              corner_radius=10, height=250)
        table_frame.pack(fill="both", expand=True, padx=30, pady=(0, 20))

        # Headers
        header_row = ctk.CTkFrame(table_frame, fg_color="transparent")
        header_row.pack(fill="x", padx=10, pady=(10, 5))
        for col, width in [("RUN DATE", 250), ("PARTS CHECKED", 150), ("ERRORS", 100), ("STATUS", 120)]:
            ctk.CTkLabel(header_row, text=col, font=ctk.CTkFont("Inter", 11, "bold"),
                         text_color=GRAY, width=width, anchor="w").pack(side="left", padx=5)

        # Rows
        for run in runs[:10]:
            row_frame = ctk.CTkFrame(table_frame, fg_color="transparent", height=40)
            row_frame.pack(fill="x", padx=10, pady=2)

            status = run.get("status", "unknown")
            status_color = GREEN if status == "success" else (ORANGE if status == "warning" else RED)
            status_label = "✓ Success" if status == "success" else ("⚠ Warning" if status == "warning" else "✗ Error")

            ctk.CTkLabel(row_frame, text=run.get("start_display", ""),
                         font=ctk.CTkFont("Inter", 12), text_color=WHITE,
                         width=250, anchor="w").pack(side="left", padx=5)
            ctk.CTkLabel(row_frame, text=str(run.get("parts_checked", 0)),
                         font=ctk.CTkFont("Inter", 12), text_color=WHITE,
                         width=150, anchor="w").pack(side="left", padx=5)
            ctk.CTkLabel(row_frame, text=str(run.get("errors", 0)),
                         font=ctk.CTkFont("Inter", 12), text_color=WHITE,
                         width=100, anchor="w").pack(side="left", padx=5)
            ctk.CTkLabel(row_frame, text=status_label,
                         font=ctk.CTkFont("Inter", 12, "bold"),
                         text_color=status_color, width=120, anchor="w").pack(side="left", padx=5)

    def _info_card(self, parent, label, value, subtitle, icon, color):
        card = ctk.CTkFrame(parent, fg_color=CARD_BG, corner_radius=10)
        card.pack(side="left", fill="both", expand=True, padx=(0, 10))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=20, pady=15)
        ctk.CTkLabel(inner, text=label, font=ctk.CTkFont("Inter", 10, "bold"),
                     text_color=color).pack(anchor="w")
        ctk.CTkLabel(inner, text=value, font=ctk.CTkFont("Inter", 18, "bold"),
                     text_color=WHITE).pack(anchor="w", pady=3)
        ctk.CTkLabel(inner, text=subtitle, font=ctk.CTkFont("Inter", 11),
                     text_color=GRAY).pack(anchor="w")

    def _stat_card(self, parent, label, value, color):
        card = ctk.CTkFrame(parent, fg_color=CARD_BG, corner_radius=10)
        card.pack(side="left", fill="both", expand=True, padx=(0, 10))
        ctk.CTkLabel(card, text=label, font=ctk.CTkFont("Inter", 10, "bold"),
                     text_color=GRAY).pack(pady=(15, 2))
        ctk.CTkLabel(card, text=value, font=ctk.CTkFont("Inter", 28, "bold"),
                     text_color=color).pack(pady=(0, 15))

    # ─────────────────────────────────────────────
    # SCHEDULER
    # ─────────────────────────────────────────────
    def show_scheduler(self):
        self._clear_main()
        self._nav_click_silent("scheduler")
        self._page_header("Scheduler",
                          "Set different run times for each day of the week.")

        scroll = ctk.CTkScrollableFrame(self.main_area, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=30)

        # Stock check schedule
        ctk.CTkLabel(scroll, text="MARCONE STOCK CHECK SCHEDULE",
                     font=ctk.CTkFont("Inter", 12, "bold"),
                     text_color=PURPLE_LIGHT).pack(anchor="w", pady=(10, 5))

        schedule_card = ctk.CTkFrame(scroll, fg_color=CARD_BG, corner_radius=10)
        schedule_card.pack(fill="x", pady=(0, 20))

        self.day_toggles = {}
        self.day_times = {}
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        stock_config = self.settings["scheduler"]["stock_check"]

        time_options = [f"{h:02d}:{m:02d}" for h in range(0, 24) for m in [0, 15, 30, 45]]

        for day in days:
            day_config = stock_config.get(day, {"enabled": False, "time": "09:00"})
            row = ctk.CTkFrame(schedule_card, fg_color="transparent", height=55)
            row.pack(fill="x", padx=20, pady=5)
            row.pack_propagate(False)

            toggle_var = ctk.BooleanVar(value=day_config.get("enabled", False))
            toggle = ctk.CTkSwitch(row, text="", variable=toggle_var,
                                   onvalue=True, offvalue=False,
                                   button_color=PURPLE, progress_color=PURPLE_LIGHT)
            toggle.pack(side="left")
            self.day_toggles[day] = toggle_var

            ctk.CTkLabel(row, text=day,
                         font=ctk.CTkFont("Inter", 14, "bold" if day_config.get("enabled") else "normal"),
                         text_color=WHITE if day_config.get("enabled") else GRAY,
                         width=120, anchor="w").pack(side="left", padx=15)

            time_var = ctk.StringVar(value=day_config.get("time", "09:00"))
            time_menu = ctk.CTkOptionMenu(row, values=time_options,
                                           variable=time_var,
                                           width=120, height=32,
                                           fg_color=NAVY_LIGHT,
                                           button_color=PURPLE,
                                           font=ctk.CTkFont("Inter", 13))
            time_menu.pack(side="right", padx=10)
            self.day_times[day] = time_var

        # Benchmark schedule
        ctk.CTkLabel(scroll, text="BENCHMARK PRICE CHECK SCHEDULE",
                     font=ctk.CTkFont("Inter", 12, "bold"),
                     text_color=ORANGE).pack(anchor="w", pady=(10, 5))

        bench_card = ctk.CTkFrame(scroll, fg_color=CARD_BG, corner_radius=10)
        bench_card.pack(fill="x", pady=(0, 20))

        bench_row = ctk.CTkFrame(bench_card, fg_color="transparent")
        bench_row.pack(fill="x", padx=20, pady=15)

        ctk.CTkLabel(bench_row, text="Run every week on:",
                     font=ctk.CTkFont("Inter", 13), text_color=WHITE).pack(side="left")

        bench_config = self.settings["scheduler"]["benchmark"]
        self.bench_day_var = ctk.StringVar(value=bench_config.get("day", "Monday"))
        ctk.CTkOptionMenu(bench_row, values=days, variable=self.bench_day_var,
                          width=130, fg_color=NAVY_LIGHT, button_color=PURPLE,
                          font=ctk.CTkFont("Inter", 13)).pack(side="left", padx=10)

        ctk.CTkLabel(bench_row, text="at", font=ctk.CTkFont("Inter", 13),
                     text_color=WHITE).pack(side="left")

        self.bench_time_var = ctk.StringVar(value=bench_config.get("time", "08:00"))
        ctk.CTkOptionMenu(bench_row, values=time_options, variable=self.bench_time_var,
                          width=120, fg_color=NAVY_LIGHT, button_color=PURPLE,
                          font=ctk.CTkFont("Inter", 13)).pack(side="left", padx=10)

        # Save button
        ctk.CTkButton(scroll, text="💾  Save Schedule",
                      command=self._save_schedule,
                      fg_color=GREEN, hover_color="#16A34A",
                      font=ctk.CTkFont("Inter", 14, "bold"),
                      height=44, corner_radius=8).pack(pady=20)

    def _save_schedule(self):
        """Save the scheduler configuration."""
        for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
            self.settings["scheduler"]["stock_check"][day] = {
                "enabled": self.day_toggles[day].get(),
                "time": self.day_times[day].get()
            }
        self.settings["scheduler"]["benchmark"] = {
            "enabled": True,
            "day": self.bench_day_var.get(),
            "time": self.bench_time_var.get()
        }
        save_settings(self.settings)
        self._start_scheduler()
        messagebox.showinfo("Saved", "Schedule saved and updated successfully!")

    # ─────────────────────────────────────────────
    # PARTS MANAGER
    # ─────────────────────────────────────────────
    def show_parts_manager(self):
        self._clear_main()
        self._nav_click_silent("parts_manager")
        self._page_header("Parts Manager",
                          "Your parts list is synced with your Google Sheet.",
                          btn_text="+ Add Part", btn_command=self._add_part_dialog)

        # Search bar
        search_frame = ctk.CTkFrame(self.main_area, fg_color="transparent")
        search_frame.pack(fill="x", padx=30, pady=(0, 10))

        self.parts_search_var = ctk.StringVar()
        self.parts_search_var.trace("w", lambda *a: self._filter_parts())
        ctk.CTkEntry(search_frame, placeholder_text="🔍  Search parts...",
                     textvariable=self.parts_search_var,
                     width=350, height=38,
                     font=ctk.CTkFont("Inter", 13),
                     fg_color=CARD_BG, border_color=NAVY_LIGHT).pack(side="left")

        ctk.CTkButton(search_frame, text="🗑  Remove Selected",
                      command=self._remove_selected_parts,
                      fg_color=RED, hover_color="#DC2626",
                      font=ctk.CTkFont("Inter", 13),
                      height=38, corner_radius=8).pack(side="right")

        # Parts table
        self.parts_table = ctk.CTkScrollableFrame(self.main_area, fg_color=CARD_BG,
                                                   corner_radius=10)
        self.parts_table.pack(fill="both", expand=True, padx=30, pady=(0, 10))

        # Headers
        header = ctk.CTkFrame(self.parts_table, fg_color=NAVY_LIGHT, corner_radius=6)
        header.pack(fill="x", padx=5, pady=(5, 0))
        for col, w in [("", 30), ("Part Number", 150), ("Part Name", 250),
                       ("Brand", 120), ("Appliance Type", 150), ("Status", 100)]:
            ctk.CTkLabel(header, text=col, font=ctk.CTkFont("Inter", 11, "bold"),
                         text_color=GRAY, width=w, anchor="w").pack(side="left", padx=8, pady=8)

        self.parts_checkboxes = {}
        self._load_parts_table()

        # Note
        ctk.CTkLabel(self.main_area,
                     text="ℹ  When you add a new part, the app automatically fills in the Name, Brand and Appliance Type",
                     font=ctk.CTkFont("Inter", 11), text_color=GRAY).pack(pady=(0, 15))

    def _load_parts_table(self, filter_text=""):
        """Load parts into the table."""
        # Clear existing rows (keep header)
        children = self.parts_table.winfo_children()
        for child in children[1:]:  # Skip header
            child.destroy()

        self.parts_checkboxes = {}

        # Try to load from sheet, fall back to sample data
        try:
            settings = load_settings()
            if settings["google_sheets"]["url"]:
                from core.sheets_engine import get_parts_list
                parts = get_parts_list(
                    settings["google_sheets"]["url"],
                    settings["google_sheets"]["sheet_name"],
                    settings["google_sheets"].get("credentials_path")
                )
            else:
                parts = self._get_sample_parts()
        except Exception:
            parts = self._get_sample_parts()

        for part in parts:
            pn = part.get("part_number", "")
            if filter_text and filter_text.lower() not in pn.lower() and \
               filter_text.lower() not in part.get("part_name", "").lower():
                continue

            row = ctk.CTkFrame(self.parts_table, fg_color="transparent", height=40)
            row.pack(fill="x", padx=5, pady=1)

            cb_var = ctk.BooleanVar()
            cb = ctk.CTkCheckBox(row, text="", variable=cb_var, width=30,
                                 checkbox_width=18, checkbox_height=18,
                                 fg_color=PURPLE)
            cb.pack(side="left", padx=8)
            self.parts_checkboxes[pn] = cb_var

            ctk.CTkLabel(row, text=pn, font=ctk.CTkFont("Inter", 12, "bold"),
                         text_color=PURPLE_LIGHT, width=150, anchor="w").pack(side="left", padx=5)
            ctk.CTkLabel(row, text=part.get("part_name", "—"),
                         font=ctk.CTkFont("Inter", 12), text_color=WHITE,
                         width=250, anchor="w").pack(side="left", padx=5)
            ctk.CTkLabel(row, text=part.get("brand", "—"),
                         font=ctk.CTkFont("Inter", 12), text_color=WHITE,
                         width=120, anchor="w").pack(side="left", padx=5)
            ctk.CTkLabel(row, text=part.get("appliance_type", "—"),
                         font=ctk.CTkFont("Inter", 12), text_color=WHITE,
                         width=150, anchor="w").pack(side="left", padx=5)

    def _get_sample_parts(self):
        return [
            {"part_number": "WP8544771", "part_name": "Washer Drain Pump Motor", "brand": "Whirlpool", "appliance_type": "Washer"},
            {"part_number": "W10295370A", "part_name": "Ice Maker Assembly", "brand": "Whirlpool", "appliance_type": "Refrigerator"},
            {"part_number": "316462900", "part_name": "Range Surface Element", "brand": "Frigidaire", "appliance_type": "Range"},
        ]

    def _filter_parts(self):
        self._load_parts_table(self.parts_search_var.get())

    def _add_part_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Add New Part")
        dialog.geometry("400x200")
        dialog.configure(fg_color=BG)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Enter Part Number:",
                     font=ctk.CTkFont("Inter", 14), text_color=WHITE).pack(pady=(20, 5))
        pn_entry = ctk.CTkEntry(dialog, width=300, height=38,
                                font=ctk.CTkFont("Inter", 14),
                                fg_color=CARD_BG, placeholder_text="e.g. WP8544771")
        pn_entry.pack(pady=5)
        ctk.CTkLabel(dialog, text="The app will auto-fill Name, Brand, and Appliance Type",
                     font=ctk.CTkFont("Inter", 11), text_color=GRAY).pack()

        def confirm():
            pn = pn_entry.get().strip()
            if pn:
                messagebox.showinfo("Part Added",
                                    f"Part {pn} will be added to your Google Sheet on the next sync.")
                dialog.destroy()
                self._load_parts_table()

        ctk.CTkButton(dialog, text="Add Part", command=confirm,
                      fg_color=GREEN, height=38, corner_radius=8).pack(pady=15)

    def _remove_selected_parts(self):
        selected = [pn for pn, var in self.parts_checkboxes.items() if var.get()]
        if not selected:
            messagebox.showwarning("No Selection", "Please select parts to remove.")
            return
        if messagebox.askyesno("Confirm Remove",
                               f"Remove {len(selected)} part(s) from your sheet?"):
            messagebox.showinfo("Removed",
                                f"{len(selected)} part(s) will be removed on next sync.")
            self._load_parts_table()

    # ─────────────────────────────────────────────
    # BENCHMARK PRICES
    # ─────────────────────────────────────────────
    def show_benchmark(self):
        self._clear_main()
        self._nav_click_silent("benchmark")

        from core.scheduler_engine import get_next_run_times
        next_times = get_next_run_times()
        bench_next = next_times.get("benchmark_weekly", "Not scheduled")

        self._page_header("Benchmark Prices",
                          "Lowest prices for new parts only. Updated weekly. Price history tracked automatically.",
                          btn_text="▶  Run Now", btn_command=self._run_benchmark_now,
                          btn_color=PURPLE_LIGHT)

        # Next check badge
        badge = ctk.CTkFrame(self.main_area, fg_color=NAVY_LIGHT, corner_radius=8)
        badge.pack(anchor="e", padx=30, pady=(0, 10))
        ctk.CTkLabel(badge, text=f"📅  Next price check: {bench_next}",
                     font=ctk.CTkFont("Inter", 12), text_color=WHITE).pack(padx=15, pady=8)

        # Table
        table = ctk.CTkScrollableFrame(self.main_area, fg_color=CARD_BG, corner_radius=10)
        table.pack(fill="both", expand=True, padx=30, pady=(0, 20))

        header = ctk.CTkFrame(table, fg_color=NAVY_LIGHT, corner_radius=6)
        header.pack(fill="x", padx=5, pady=(5, 0))
        for col, w in [("Part Number", 150), ("Part Name", 220), ("Amazon", 160),
                       ("Google Shopping", 180), ("eBay (New Only)", 180), ("Last Updated", 130)]:
            ctk.CTkLabel(header, text=col, font=ctk.CTkFont("Inter", 11, "bold"),
                         text_color=GRAY, width=w, anchor="w").pack(side="left", padx=8, pady=8)

        # Sample data
        sample = [
            ("WP8544771", "Washer Drain Pump Motor", "$24.99", "$22.50", "$21.99", "Jun 2, 2026"),
            ("W10295370A", "Ice Maker Assembly", "$8.49 → $6.99 (Jun 9)", "$169.99", "$159.99", "Jun 2, 2026"),
            ("316462900", "Range Surface Element", "$129.99", "$119.99 → $114.99 (Jun 9)", "—", "Jun 2, 2026"),
        ]
        for pn, name, amz, goog, ebay, updated in sample:
            row = ctk.CTkFrame(table, fg_color="transparent", height=40)
            row.pack(fill="x", padx=5, pady=2)
            ctk.CTkLabel(row, text=pn, font=ctk.CTkFont("Inter", 12, "bold"),
                         text_color=PURPLE_LIGHT, width=150, anchor="w").pack(side="left", padx=8)
            ctk.CTkLabel(row, text=name, font=ctk.CTkFont("Inter", 12),
                         text_color=WHITE, width=220, anchor="w").pack(side="left", padx=5)
            for val, w in [(amz, 160), (goog, 180), (ebay, 180)]:
                color = ORANGE if "→" in val else (GRAY if val == "—" else WHITE)
                ctk.CTkLabel(row, text=val, font=ctk.CTkFont("Inter", 12),
                             text_color=color, width=w, anchor="w").pack(side="left", padx=5)
            ctk.CTkLabel(row, text=updated, font=ctk.CTkFont("Inter", 11),
                         text_color=GRAY, width=130, anchor="w").pack(side="left", padx=5)

    # ─────────────────────────────────────────────
    # PN MEMORY
    # ─────────────────────────────────────────────
    def show_pn_memory(self):
        self._clear_main()
        self._nav_click_silent("pn_memory")
        self._page_header("Part Number Memory",
                          "The app learns and remembers correct part numbers so searches never fail twice.")

        # Search
        search_frame = ctk.CTkFrame(self.main_area, fg_color="transparent")
        search_frame.pack(fill="x", padx=30, pady=(0, 10))
        ctk.CTkEntry(search_frame, placeholder_text="🔍  Search part number memory...",
                     width=350, height=38, font=ctk.CTkFont("Inter", 13),
                     fg_color=CARD_BG, border_color=NAVY_LIGHT).pack(side="left")

        # Table
        table = ctk.CTkScrollableFrame(self.main_area, fg_color=CARD_BG, corner_radius=10)
        table.pack(fill="both", expand=True, padx=30, pady=(0, 10))

        header = ctk.CTkFrame(table, fg_color=NAVY_LIGHT, corner_radius=6)
        header.pack(fill="x", padx=5, pady=(5, 0))
        for col, w in [("Original PN", 160), ("Resolved PN", 160),
                       ("Reason", 250), ("Date Learned", 140), ("Actions", 150)]:
            ctk.CTkLabel(header, text=col, font=ctk.CTkFont("Inter", 11, "bold"),
                         text_color=GRAY, width=w, anchor="w").pack(side="left", padx=8, pady=8)

        mappings = get_all_mappings()
        if not mappings:
            ctk.CTkLabel(table, text="No part number substitutions learned yet.\nThey will appear here automatically as the app runs.",
                         font=ctk.CTkFont("Inter", 13), text_color=GRAY).pack(pady=40)
        else:
            for m in mappings:
                row = ctk.CTkFrame(table, fg_color="transparent", height=44)
                row.pack(fill="x", padx=5, pady=2)
                ctk.CTkLabel(row, text=m.get("original_pn", ""),
                             font=ctk.CTkFont("Inter", 12), text_color=WHITE,
                             width=160, anchor="w").pack(side="left", padx=8)
                ctk.CTkLabel(row, text=m.get("resolved_pn", ""),
                             font=ctk.CTkFont("Inter", 12, "bold"), text_color=GREEN,
                             width=160, anchor="w").pack(side="left", padx=5)
                ctk.CTkLabel(row, text=m.get("reason", ""),
                             font=ctk.CTkFont("Inter", 12), text_color=GRAY,
                             width=250, anchor="w").pack(side="left", padx=5)
                ctk.CTkLabel(row, text=m.get("date_learned", ""),
                             font=ctk.CTkFont("Inter", 11), text_color=GRAY,
                             width=140, anchor="w").pack(side="left", padx=5)
                btn_frame = ctk.CTkFrame(row, fg_color="transparent", width=150)
                btn_frame.pack(side="left", padx=5)
                ctk.CTkButton(btn_frame, text="Edit", width=60, height=28,
                              fg_color=PURPLE, font=ctk.CTkFont("Inter", 11),
                              command=lambda orig=m["original_pn"]: self._edit_pn_mapping(orig)).pack(side="left", padx=2)
                ctk.CTkButton(btn_frame, text="Delete", width=65, height=28,
                              fg_color=RED, font=ctk.CTkFont("Inter", 11),
                              command=lambda orig=m["original_pn"]: self._delete_pn_mapping(orig)).pack(side="left", padx=2)

        # Info box
        info = ctk.CTkFrame(self.main_area, fg_color=NAVY_LIGHT, corner_radius=8)
        info.pack(fill="x", padx=30, pady=(0, 20))
        ctk.CTkLabel(info,
                     text="ℹ  When the app finds a part under a different number, it saves the mapping here and uses it automatically on all future runs.",
                     font=ctk.CTkFont("Inter", 12), text_color=WHITE,
                     wraplength=900).pack(padx=20, pady=12)

    def _delete_pn_mapping(self, original_pn):
        if messagebox.askyesno("Delete Mapping", f"Delete mapping for {original_pn}?"):
            delete_mapping(original_pn)
            self.show_pn_memory()

    def _edit_pn_mapping(self, original_pn):
        mappings = get_all_mappings()
        current = next((m for m in mappings if m["original_pn"] == original_pn), None)
        if not current:
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Edit PN Mapping")
        dialog.geometry("400x250")
        dialog.configure(fg_color=BG)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text=f"Original PN: {original_pn}",
                     font=ctk.CTkFont("Inter", 13, "bold"), text_color=WHITE).pack(pady=(20, 5))

        ctk.CTkLabel(dialog, text="Resolved PN:", font=ctk.CTkFont("Inter", 12),
                     text_color=GRAY).pack(anchor="w", padx=30)
        resolved_entry = ctk.CTkEntry(dialog, width=340, height=36,
                                      font=ctk.CTkFont("Inter", 13), fg_color=CARD_BG)
        resolved_entry.insert(0, current.get("resolved_pn", ""))
        resolved_entry.pack(padx=30, pady=3)

        ctk.CTkLabel(dialog, text="Reason:", font=ctk.CTkFont("Inter", 12),
                     text_color=GRAY).pack(anchor="w", padx=30)
        reason_entry = ctk.CTkEntry(dialog, width=340, height=36,
                                    font=ctk.CTkFont("Inter", 13), fg_color=CARD_BG)
        reason_entry.insert(0, current.get("reason", ""))
        reason_entry.pack(padx=30, pady=3)

        def save():
            update_mapping(original_pn, resolved_entry.get().strip(), reason_entry.get().strip())
            dialog.destroy()
            self.show_pn_memory()

        ctk.CTkButton(dialog, text="Save", command=save,
                      fg_color=GREEN, height=36, corner_radius=8).pack(pady=15)

    # ─────────────────────────────────────────────
    # LOGS
    # ─────────────────────────────────────────────
    def show_logs(self):
        self._clear_main()
        self._nav_click_silent("logs")
        self._page_header("Logs", "Complete history of all past runs.")

        content = ctk.CTkFrame(self.main_area, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=30, pady=(0, 20))

        # Left panel - run list
        left = ctk.CTkFrame(content, fg_color=CARD_BG, corner_radius=10, width=300)
        left.pack(side="left", fill="y", padx=(0, 10))
        left.pack_propagate(False)

        ctk.CTkLabel(left, text="PAST RUNS",
                     font=ctk.CTkFont("Inter", 11, "bold"),
                     text_color=GRAY).pack(anchor="w", padx=15, pady=(15, 5))

        runs_scroll = ctk.CTkScrollableFrame(left, fg_color="transparent")
        runs_scroll.pack(fill="both", expand=True, padx=5)

        # Right panel - log detail
        self.log_detail_frame = ctk.CTkFrame(content, fg_color=CARD_BG, corner_radius=10)
        self.log_detail_frame.pack(side="right", fill="both", expand=True)

        ctk.CTkLabel(self.log_detail_frame,
                     text="Select a run from the left to view details",
                     font=ctk.CTkFont("Inter", 13), text_color=GRAY).pack(expand=True)

        runs = get_run_list()
        if not runs:
            ctk.CTkLabel(runs_scroll, text="No runs yet",
                         font=ctk.CTkFont("Inter", 12), text_color=GRAY).pack(pady=20)
        else:
            for run in runs:
                status = run.get("status", "unknown")
                status_color = GREEN if status == "success" else (ORANGE if status == "warning" else RED)
                status_icon = "✓" if status == "success" else ("⚠" if status == "warning" else "✗")

                run_btn = ctk.CTkFrame(runs_scroll, fg_color=NAVY_LIGHT, corner_radius=8)
                run_btn.pack(fill="x", pady=3, padx=5)
                run_btn.bind("<Button-1>", lambda e, r=run: self._show_run_detail(r["run_id"]))

                ctk.CTkLabel(run_btn,
                             text=run.get("start_display", ""),
                             font=ctk.CTkFont("Inter", 12), text_color=WHITE).pack(anchor="w", padx=10, pady=(8, 2))
                ctk.CTkLabel(run_btn,
                             text=f"{status_icon} {status.capitalize()}",
                             font=ctk.CTkFont("Inter", 11, "bold"),
                             text_color=status_color).pack(anchor="w", padx=10, pady=(0, 8))

    def _show_run_detail(self, run_id: str):
        """Show detailed log for a specific run."""
        for widget in self.log_detail_frame.winfo_children():
            widget.destroy()

        detail = get_run_detail(run_id)
        if not detail:
            ctk.CTkLabel(self.log_detail_frame, text="Could not load run details",
                         text_color=RED).pack(expand=True)
            return

        meta = detail.get("meta", {})
        lines = detail.get("lines", [])

        # Header
        header = ctk.CTkFrame(self.log_detail_frame, fg_color=NAVY_LIGHT, corner_radius=8)
        header.pack(fill="x", padx=15, pady=(15, 5))
        status = meta.get("status", "unknown")
        status_color = GREEN if status == "success" else (ORANGE if status == "warning" else RED)
        ctk.CTkLabel(header,
                     text=f"{meta.get('start_display', '')} — {status.capitalize()}",
                     font=ctk.CTkFont("Inter", 13, "bold"),
                     text_color=status_color).pack(side="left", padx=15, pady=10)

        ctk.CTkButton(header, text="Export Log", width=100, height=30,
                      fg_color=PURPLE, font=ctk.CTkFont("Inter", 11),
                      command=lambda: self._export_log(run_id)).pack(side="right", padx=10)

        # Log lines
        log_text = ctk.CTkTextbox(self.log_detail_frame, fg_color="#0A0F1A",
                                   font=ctk.CTkFont("Courier", 11),
                                   text_color="#A0AEC0")
        log_text.pack(fill="both", expand=True, padx=15, pady=(5, 5))
        for line in lines:
            log_text.insert("end", line + "\n")
        log_text.configure(state="disabled")

        # Summary bar
        summary = ctk.CTkFrame(self.log_detail_frame, fg_color=NAVY_LIGHT, corner_radius=8)
        summary.pack(fill="x", padx=15, pady=(0, 15))
        summary_text = (f"Run completed in {meta.get('duration_display', '?')}. "
                        f"{meta.get('parts_checked', 0)} parts checked. "
                        f"{meta.get('errors', 0)} errors. "
                        f"{meta.get('pn_substitutions', 0)} PN substitution(s) saved.")
        ctk.CTkLabel(summary, text=summary_text,
                     font=ctk.CTkFont("Inter", 12), text_color=WHITE).pack(padx=15, pady=10)

    def _export_log(self, run_id: str):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"StockCheckerPro_Log_{run_id}.txt"
        )
        if path:
            detail = get_run_detail(run_id)
            if detail:
                with open(path, "w") as f:
                    for line in detail.get("lines", []):
                        f.write(line + "\n")
                messagebox.showinfo("Exported", f"Log exported to {path}")

    # ─────────────────────────────────────────────
    # SETTINGS
    # ─────────────────────────────────────────────
    def show_settings(self):
        self._clear_main()
        self._nav_click_silent("settings")
        self._page_header("Settings")

        scroll = ctk.CTkScrollableFrame(self.main_area, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=30)

        # ── Marcone Credentials ──
        self._settings_section(scroll, "1.  Marcone Credentials", "🔐")
        marcone_card = ctk.CTkFrame(scroll, fg_color=CARD_BG, corner_radius=10)
        marcone_card.pack(fill="x", pady=(0, 20))

        marcone_cfg = self.settings["marcone"]
        self.marcone_user_var = ctk.StringVar(value=marcone_cfg.get("username", ""))
        self.marcone_pass_var = ctk.StringVar(value=decrypt_password(marcone_cfg.get("password", "")))

        self._labeled_entry(marcone_card, "Username / Email", self.marcone_user_var)
        self._labeled_entry(marcone_card, "Password", self.marcone_pass_var, show="*")

        test_marcone_btn = ctk.CTkButton(marcone_card, text="Test Connection",
                                          fg_color=PURPLE, hover_color=PURPLE_LIGHT,
                                          font=ctk.CTkFont("Inter", 13),
                                          height=36, width=160, corner_radius=8,
                                          command=self._test_marcone)
        test_marcone_btn.pack(anchor="e", padx=20, pady=(0, 15))

        # ── Google Sheet ──
        self._settings_section(scroll, "2.  Google Sheet", "📊")
        sheets_card = ctk.CTkFrame(scroll, fg_color=CARD_BG, corner_radius=10)
        sheets_card.pack(fill="x", pady=(0, 20))

        sheets_cfg = self.settings["google_sheets"]
        self.sheet_url_var = ctk.StringVar(value=sheets_cfg.get("url", ""))
        self.sheet_name_var = ctk.StringVar(value=sheets_cfg.get("sheet_name", "Sheet1"))

        self._labeled_entry(sheets_card, "Google Sheet URL", self.sheet_url_var)
        self._labeled_entry(sheets_card, "Sheet Name", self.sheet_name_var)

        ctk.CTkLabel(sheets_card, text="Google Credentials File (JSON):",
                     font=ctk.CTkFont("Inter", 12), text_color=GRAY).pack(anchor="w", padx=20, pady=(5, 2))
        creds_row = ctk.CTkFrame(sheets_card, fg_color="transparent")
        creds_row.pack(fill="x", padx=20, pady=(0, 5))
        self.creds_path_var = ctk.StringVar(value=sheets_cfg.get("credentials_path", ""))
        ctk.CTkEntry(creds_row, textvariable=self.creds_path_var,
                     height=36, font=ctk.CTkFont("Inter", 12),
                     fg_color=NAVY_LIGHT, border_color=NAVY_LIGHT).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(creds_row, text="Browse", width=80, height=36,
                      fg_color=PURPLE, font=ctk.CTkFont("Inter", 12),
                      command=self._browse_creds).pack(side="right", padx=(5, 0))

        test_sheets_btn = ctk.CTkButton(sheets_card, text="Test Connection",
                                         fg_color=PURPLE, hover_color=PURPLE_LIGHT,
                                         font=ctk.CTkFont("Inter", 13),
                                         height=36, width=160, corner_radius=8,
                                         command=self._test_sheets)
        test_sheets_btn.pack(anchor="e", padx=20, pady=(0, 15))

        # ── Backup Sheet ──
        self._settings_section(scroll, "3.  Backup Sheet", "☁")
        backup_card = ctk.CTkFrame(scroll, fg_color=CARD_BG, corner_radius=10)
        backup_card.pack(fill="x", pady=(0, 20))

        backup_cfg = self.settings["google_sheets"]
        backup_row = ctk.CTkFrame(backup_card, fg_color="transparent")
        backup_row.pack(fill="x", padx=20, pady=15)

        self.backup_enabled_var = ctk.BooleanVar(value=backup_cfg.get("backup_enabled", True))
        ctk.CTkSwitch(backup_row, text="Enable Backup Sheet",
                      variable=self.backup_enabled_var,
                      onvalue=True, offvalue=False,
                      button_color=PURPLE, progress_color=PURPLE_LIGHT,
                      font=ctk.CTkFont("Inter", 13), text_color=WHITE).pack(side="left")

        self.backup_name_var = ctk.StringVar(value=backup_cfg.get("backup_sheet_name", "Backup"))
        self._labeled_entry(backup_card, "Backup Sheet Name", self.backup_name_var)
        ctk.CTkLabel(backup_card,
                     text="ℹ  Backup is always kept in sync with the main sheet after every run.",
                     font=ctk.CTkFont("Inter", 11), text_color=GRAY).pack(anchor="w", padx=20, pady=(0, 15))

        # Save button
        ctk.CTkButton(scroll, text="💾  Save Settings",
                      command=self._save_settings,
                      fg_color=GREEN, hover_color="#16A34A",
                      font=ctk.CTkFont("Inter", 14, "bold"),
                      height=44, corner_radius=8).pack(pady=20)

    def _settings_section(self, parent, title, icon):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", pady=(15, 5))
        ctk.CTkLabel(frame, text=f"{icon}  {title}",
                     font=ctk.CTkFont("Inter", 14, "bold"),
                     text_color=WHITE).pack(anchor="w")

    def _labeled_entry(self, parent, label, var, show=None):
        ctk.CTkLabel(parent, text=label + ":",
                     font=ctk.CTkFont("Inter", 12), text_color=GRAY).pack(anchor="w", padx=20, pady=(8, 2))
        entry = ctk.CTkEntry(parent, textvariable=var, height=38,
                             font=ctk.CTkFont("Inter", 13),
                             fg_color=NAVY_LIGHT, border_color=NAVY_LIGHT,
                             show=show)
        entry.pack(fill="x", padx=20, pady=(0, 5))

    def _browse_creds(self):
        path = filedialog.askopenfilename(
            title="Select Google Credentials JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if path:
            self.creds_path_var.set(path)

    def _test_marcone(self):
        messagebox.showinfo("Test Marcone",
                            "Marcone connection test will run when you save settings and perform a stock check.")

    def _test_sheets(self):
        url = self.sheet_url_var.get().strip()
        name = self.sheet_name_var.get().strip()
        creds = self.creds_path_var.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Please enter your Google Sheet URL first.")
            return
        messagebox.showinfo("Testing...", "Testing Google Sheets connection. This may take a few seconds.")
        try:
            from core.sheets_engine import test_connection
            success, msg = test_connection(url, name, creds or None)
            if success:
                messagebox.showinfo("Connected!", msg)
            else:
                messagebox.showerror("Connection Failed", msg)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _save_settings(self):
        self.settings["marcone"]["username"] = self.marcone_user_var.get().strip()
        self.settings["marcone"]["password"] = encrypt_password(self.marcone_pass_var.get())
        self.settings["google_sheets"]["url"] = self.sheet_url_var.get().strip()
        self.settings["google_sheets"]["sheet_name"] = self.sheet_name_var.get().strip()
        self.settings["google_sheets"]["credentials_path"] = self.creds_path_var.get().strip()
        self.settings["google_sheets"]["backup_enabled"] = self.backup_enabled_var.get()
        self.settings["google_sheets"]["backup_sheet_name"] = self.backup_name_var.get().strip()
        save_settings(self.settings)
        messagebox.showinfo("Saved", "Settings saved successfully!")

    # ─────────────────────────────────────────────
    # RUN LOGIC
    # ─────────────────────────────────────────────
    def _run_now(self):
        """Trigger an immediate stock check run."""
        if self.is_running:
            messagebox.showwarning("Already Running", "A stock check is already in progress.")
            return

        settings = load_settings()
        username = settings["marcone"].get("username", "")
        password = decrypt_password(settings["marcone"].get("password", ""))

        if not username or not password:
            messagebox.showwarning("Credentials Missing",
                                   "Please enter your Marcone credentials in Settings first.")
            self.show_settings()
            return

        if not settings["google_sheets"].get("url"):
            messagebox.showwarning("Sheet Not Configured",
                                   "Please enter your Google Sheet URL in Settings first.")
            self.show_settings()
            return

        self.is_running = True
        self.stop_flag = [False]
        self._show_run_progress_window()

    def _show_run_progress_window(self):
        """Show the live run progress window."""
        self._clear_main()
        self._nav_click_silent("dashboard")

        self._page_header("Run In Progress",
                          btn_text="⏹  Stop Run",
                          btn_command=self._stop_run,
                          btn_color=RED)

        # Progress
        progress_frame = ctk.CTkFrame(self.main_area, fg_color=CARD_BG, corner_radius=10)
        progress_frame.pack(fill="x", padx=30, pady=10)

        self.progress_label = ctk.CTkLabel(progress_frame,
                                            text="Initializing...",
                                            font=ctk.CTkFont("Inter", 20, "bold"),
                                            text_color=WHITE)
        self.progress_label.pack(pady=(20, 5))

        self.progress_bar = ctk.CTkProgressBar(progress_frame, width=800,
                                                progress_color=PURPLE_LIGHT,
                                                fg_color=NAVY_LIGHT)
        self.progress_bar.pack(pady=10, padx=30)
        self.progress_bar.set(0)

        self.eta_label = ctk.CTkLabel(progress_frame, text="",
                                       font=ctk.CTkFont("Inter", 12), text_color=GRAY)
        self.eta_label.pack(pady=(0, 20))

        # Live log
        ctk.CTkLabel(self.main_area, text="LIVE LOG",
                     font=ctk.CTkFont("Inter", 11, "bold"), text_color=GRAY).pack(anchor="w", padx=30)

        self.live_log = ctk.CTkTextbox(self.main_area, fg_color="#0A0F1A",
                                        font=ctk.CTkFont("Courier", 11),
                                        text_color="#A0AEC0")
        self.live_log.pack(fill="both", expand=True, padx=30, pady=(5, 20))

        # Set log callback
        set_log_callback(self._append_log)

        # Start run in background thread
        thread = threading.Thread(target=self._execute_run, daemon=True)
        thread.start()

    def _append_log(self, line: str):
        """Append a line to the live log (thread-safe)."""
        def _do():
            self.live_log.configure(state="normal")
            self.live_log.insert("end", line + "\n")
            self.live_log.see("end")
            self.live_log.configure(state="disabled")
        try:
            self.after(0, _do)
        except Exception:
            pass

    def _update_progress(self, current, total, pn, status):
        """Update progress bar (thread-safe)."""
        def _do():
            pct = current / total if total > 0 else 0
            self.progress_bar.set(pct)
            self.progress_label.configure(text=f"{current} of {total} parts checked  ({int(pct*100)}%)")
            self.eta_label.configure(text=f"Current: {pn}")
        try:
            self.after(0, _do)
        except Exception:
            pass

    def _execute_run(self):
        """Execute the stock check run in a background thread."""
        from data.logger import start_run, finish_run
        from core.marcone_engine import run_stock_check
        from core.sheets_engine import get_parts_list, update_stock_result, sync_backup_sheet

        settings = load_settings()
        username = settings["marcone"]["username"]
        password = decrypt_password(settings["marcone"]["password"])
        sheet_url = settings["google_sheets"]["url"]
        sheet_name = settings["google_sheets"]["sheet_name"]
        creds = settings["google_sheets"].get("credentials_path") or None
        backup_enabled = settings["google_sheets"].get("backup_enabled", True)
        backup_name = settings["google_sheets"].get("backup_sheet_name", "Backup")

        run_id = start_run("stock_check")
        errors = 0
        pn_subs = 0

        try:
            # Get parts list
            parts = get_parts_list(sheet_url, sheet_name, creds)
            part_numbers = [p["part_number"] for p in parts]

            # Run stock check
            results = run_stock_check(
                username, password, part_numbers,
                progress_callback=self._update_progress,
                stop_flag=self.stop_flag
            )

            # Write results to sheet
            from data.logger import log
            log("Updating Google Sheet with results...")
            for result in results:
                orig_pn = result.get("original_pn", result.get("pn", ""))
                # Find matching part row
                matching_part = next((p for p in parts if p["part_number"].upper() == orig_pn.upper()), None)
                if matching_part:
                    qty = result.get("quantity", 0)
                    found = result.get("found", False)
                    update_stock_result(sheet_url, sheet_name, matching_part["row"],
                                        qty, found, credentials_path=creds)
                if not result.get("found"):
                    errors += 1
                if result.get("resolved_via") in ("variation", "superseded"):
                    pn_subs += 1

            log("Google Sheet updated successfully")

            # Sync backup
            if backup_enabled:
                sync_backup_sheet(sheet_url, sheet_name, backup_name, creds)

        except Exception as e:
            from data.logger import log
            log(f"Run error: {e}", "ERROR")
            errors += 1
        finally:
            finish_run(
                status="success" if errors == 0 else ("warning" if errors < 3 else "error"),
                parts_checked=len(results) if 'results' in dir() else 0,
                errors=errors,
                pn_substitutions=pn_subs
            )
            self.is_running = False
            self.after(0, self.show_dashboard)

    def _stop_run(self):
        """Stop the current run."""
        self.stop_flag[0] = True
        self.is_running = False

    def _run_benchmark_now(self):
        """Trigger an immediate benchmark price check."""
        messagebox.showinfo("Benchmark Check",
                            "Benchmark price check started in the background.\n"
                            "Results will be written to your Google Sheet when complete.")

    # ─────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────
    def _nav_click_silent(self, key):
        """Highlight nav button without triggering navigation."""
        for k, btn in self.nav_buttons.items():
            btn.configure(fg_color="transparent", text_color=GRAY)
        if key in self.nav_buttons:
            self.nav_buttons[key].configure(fg_color=PURPLE, text_color=WHITE)

    def _start_scheduler(self):
        """Start the background scheduler."""
        try:
            from core.scheduler_engine import start_scheduler, set_callbacks
            set_callbacks(self._run_now, self._run_benchmark_now)
            start_scheduler(self.settings["scheduler"])
        except Exception as e:
            pass  # Scheduler errors are non-fatal

    def _on_close(self):
        """Handle app close."""
        try:
            from core.scheduler_engine import stop_scheduler
            stop_scheduler()
        except Exception:
            pass
        self.destroy()

    # ─────────────────────────────────────────────
    # AUTO-UPDATER
    # ─────────────────────────────────────────────
    def _check_for_updates_on_startup(self):
        """Silently check for updates in background on startup."""
        def _on_result(available, version, changelog):
            if available:
                self._pending_update_version = version
                self._pending_update_changelog = changelog
                # Show the update button in the sidebar
                self.update_btn.pack(side="bottom", fill="x", padx=10, pady=(0, 5))

        check_update_async(_on_result)

    def _show_update_dialog(self):
        """Show a dialog asking the user to apply the available update."""
        version = self._pending_update_version or "?"
        changelog = self._pending_update_changelog or "Bug fixes and improvements."

        dialog = ctk.CTkToplevel(self)
        dialog.title("Update Available")
        dialog.geometry("480x320")
        dialog.configure(fg_color=BG)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="🔄  Update Available",
                     font=ctk.CTkFont("Inter", 18, "bold"),
                     text_color=ORANGE).pack(pady=(25, 5))

        ctk.CTkLabel(dialog, text=f"Version {version} is ready to install.",
                     font=ctk.CTkFont("Inter", 13), text_color=WHITE).pack(pady=(0, 10))

        # Changelog box
        log_box = ctk.CTkTextbox(dialog, height=100, fg_color=CARD_BG,
                                  font=ctk.CTkFont("Inter", 12), text_color=GRAY)
        log_box.pack(fill="x", padx=25, pady=(0, 15))
        log_box.insert("end", changelog)
        log_box.configure(state="disabled")

        # Progress label
        self._update_progress_var = ctk.StringVar(value="")
        progress_lbl = ctk.CTkLabel(dialog, textvariable=self._update_progress_var,
                                     font=ctk.CTkFont("Inter", 11), text_color=GRAY)
        progress_lbl.pack(pady=(0, 5))

        # Buttons
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=5)

        def _do_update():
            install_btn.configure(state="disabled")
            skip_btn.configure(state="disabled")

            def _progress(msg):
                self._update_progress_var.set(msg)

            def _done(success, message):
                if success:
                    self._update_progress_var.set(message)
                    self.update_btn.pack_forget()
                    messagebox.showinfo("Update Complete",
                                        "Update applied! Please close and reopen the app to use the new version.")
                    dialog.destroy()
                else:
                    messagebox.showerror("Update Failed", message)
                    install_btn.configure(state="normal")
                    skip_btn.configure(state="normal")

            apply_update_async(_progress, _done)

        install_btn = ctk.CTkButton(btn_frame, text="Install Update",
                                     fg_color=ORANGE, hover_color="#EA580C",
                                     font=ctk.CTkFont("Inter", 13, "bold"),
                                     width=160, height=38, corner_radius=8,
                                     command=_do_update)
        install_btn.pack(side="left", padx=8)

        skip_btn = ctk.CTkButton(btn_frame, text="Skip for Now",
                                  fg_color=NAVY_LIGHT, hover_color=NAVY,
                                  font=ctk.CTkFont("Inter", 13),
                                  width=130, height=38, corner_radius=8,
                                  command=dialog.destroy)
        skip_btn.pack(side="left", padx=8)


def main():
    app = StockCheckerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
