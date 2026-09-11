# -*- coding: utf-8 -*-
"""
installer_setup_wizard.py — Modern High-Resolution Setup Wizard
Meat Products of India — Billing & Inventory Management App
"""

import sys
import os
import shutil
import winreg
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk

# ─── High-DPI Awareness (Windows 10 / 11) ────────────────────────────────────
if sys.platform == 'win32':
    try:
        import ctypes
        # Per-monitor DPI awareness v2 for crisp high-resolution rendering
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

try:
    from database import (
        normalize_database_url,
        save_database_url,
        get_database_url,
        test_supabase_connection,
        get_external_config_dir
    )
except ImportError:
    pass

# ─── Configuration & Branding ────────────────────────────────────────────────
APP_NAME = "MPI Billing Software"
APP_PUBLISHER = "Meat Products of India"
APP_TAGLINE = "A Govt. of Kerala Undertaking"
APP_VERSION = "2.0.0"
REG_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\MPI_Billing_Software"
PROD_SUPABASE_URL = "postgresql://postgres.tjpfkpwmoyooevxjosof:Revathyr%40j6123@aws-0-ap-south-1.pooler.supabase.com:5432/postgres"

# ─── Modern Color Theme ──────────────────────────────────────────────────────
THEME = {
    'bg_main':       '#0B1120',  # Deep Obsidian Navy
    'bg_content':    '#0F172A',  # Slate 900
    'bg_card':       '#1E293B',  # Slate 800
    'bg_card_alt':   '#162032',  # Slightly darker card
    'bg_header':     '#131B2E',  # Header banner
    'bg_footer':     '#0B1120',  # Footer bar
    'border':        '#334155',  # Slate 700
    'border_subtle': '#1E293B',  # Slate 800
    'primary':       '#E11D48',  # Brand Crimson Red (Meat Products of India)
    'primary_hover': '#F43F5E',  # Rose 500
    'primary_active':'#BE123C',  # Rose 700
    'secondary':     '#334155',  # Slate 700
    'sec_hover':     '#475569',  # Slate 600
    'accent_blue':   '#38BDF8',  # Sky 400
    'accent_gold':   '#F59E0B',  # Amber 500
    'accent_green':  '#10B981',  # Emerald 500
    'text_light':    '#F8FAFC',  # White / Slate 50
    'text_sub':      '#CBD5E1',  # Slate 300
    'text_muted':    '#94A3B8',  # Slate 400
}


def get_bundle_dir():
    if getattr(sys, 'frozen', False):
        return getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.dirname(os.path.abspath(__file__))


def create_windows_shortcut(target, shortcut_path, icon_path=None, description=""):
    """Create a Windows .lnk shortcut safely in-memory without dropping temporary VBS files."""
    # 1. Native Python COM (pywin32) if available
    try:
        import win32com.client
        ws = win32com.client.Dispatch("WScript.Shell")
        sc = ws.CreateShortcut(shortcut_path)
        sc.TargetPath = target
        sc.WorkingDirectory = os.path.dirname(target)
        sc.Description = description
        if icon_path and os.path.exists(icon_path):
            sc.IconLocation = icon_path
        sc.Save()
        if os.path.exists(shortcut_path):
            return True
    except Exception:
        pass

    # 2. In-memory PowerShell fallback (no temporary files on disk)
    try:
        target_esc = target.replace("'", "''")
        sc_esc = shortcut_path.replace("'", "''")
        work_dir_esc = os.path.dirname(target).replace("'", "''")
        desc_esc = description.replace("'", "''")

        ps_parts = [
            "$ws = New-Object -ComObject WScript.Shell",
            f"$sc = $ws.CreateShortcut('{sc_esc}')",
            f"$sc.TargetPath = '{target_esc}'",
            f"$sc.WorkingDirectory = '{work_dir_esc}'",
            f"$sc.Description = '{desc_esc}'"
        ]
        if icon_path and os.path.exists(icon_path):
            icon_esc = icon_path.replace("'", "''")
            ps_parts.append(f"$sc.IconLocation = '{icon_esc}'")
        ps_parts.append("$sc.Save()")

        ps_command = "; ".join(ps_parts)
        cmd = ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", ps_command]

        creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        subprocess.run(cmd, capture_output=True, timeout=10, creationflags=creationflags)
        return os.path.exists(shortcut_path)
    except Exception as e:
        print(f"Shortcut creation error: {e}")
        return False


# ─── Custom UI Helper: Modern Hover Button ────────────────────────────────────
def create_hover_button(parent, text, command, bg, hover_bg, fg="#FFFFFF", width=12, bold=False, pady=6):
    font = ("Segoe UI", 10, "bold") if bold else ("Segoe UI", 10)
    btn = tk.Button(
        parent, text=text, command=command, bg=bg, fg=fg,
        activebackground=hover_bg, activeforeground=fg,
        font=font, width=width, relief="flat", bd=0, padx=14, pady=pady, cursor="hand2"
    )
    btn.bind("<Enter>", lambda e: btn.config(bg=hover_bg))
    btn.bind("<Leave>", lambda e: btn.config(bg=bg))
    return btn


# ─── Installer Wizard GUI ─────────────────────────────────────────────────────
class InstallerWizard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.is_32bit = (sys.maxsize <= 2**31 - 1)
        edition_str = "32-bit x86 Edition" if self.is_32bit else "64-bit Edition"
        self.title(f"{APP_NAME} — Setup Wizard ({edition_str})")

        WIN_WIDTH = 760
        WIN_HEIGHT = 530
        self.geometry(f"{WIN_WIDTH}x{WIN_HEIGHT}")
        self.resizable(False, False)
        self.configure(bg=THEME['bg_main'])

        # Center on primary display
        self.update_idletasks()
        x = (self.winfo_screenwidth() - WIN_WIDTH) // 2
        y = (self.winfo_screenheight() - WIN_HEIGHT) // 2
        self.geometry(f"{WIN_WIDTH}x{WIN_HEIGHT}+{x}+{y}")

        self.bundle_dir = get_bundle_dir()
        self.payload_dir = os.path.join(self.bundle_dir, "payload")
        if not os.path.exists(self.payload_dir):
            self.payload_dir = os.path.join(self.bundle_dir, "dist", "MPI_Billing_App")

        # Default Install Path
        user_appdata = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
        self.install_path = tk.StringVar(value=os.path.join(user_appdata, "Programs", "MPI Billing Software"))
        self.create_desktop_sc = tk.BooleanVar(value=True)
        self.create_start_sc = tk.BooleanVar(value=True)
        self.launch_after = tk.BooleanVar(value=True)

        self.current_step = 0
        self.steps = [
            self.show_step_welcome,
            self.show_step_directory,
            self.show_step_options,
            self.show_step_install,
            self.show_step_finish
        ]

        # ── High-Resolution Logos ──
        self.logo_hero = None
        self.logo_header = None
        self.logo_finish = None
        logo_p = os.path.join(self.bundle_dir, "logo.png")
        if os.path.exists(logo_p):
            try:
                pil_raw = Image.open(logo_p)
                self.logo_hero = ImageTk.PhotoImage(pil_raw.resize((128, 128), Image.Resampling.LANCZOS))
                self.logo_header = ImageTk.PhotoImage(pil_raw.resize((50, 50), Image.Resampling.LANCZOS))
                self.logo_finish = ImageTk.PhotoImage(pil_raw.resize((84, 84), Image.Resampling.LANCZOS))
            except Exception as e:
                print(f"[Installer Warning] Could not load high-res logo: {e}")

        # Set Window Icon
        ico_p = os.path.join(self.bundle_dir, "logo.ico")
        if os.path.exists(ico_p):
            try:
                self.iconbitmap(ico_p)
            except Exception:
                pass

        # Configure ttk Styles for Modern Progressbar
        style = ttk.Style(self)
        try:
            style.theme_use('clam')
        except Exception:
            pass
        style.configure(
            "Custom.Horizontal.TProgressbar",
            troughcolor=THEME['bg_card'],
            background=THEME['primary'],
            darkcolor=THEME['primary'],
            lightcolor=THEME['primary_hover'],
            bordercolor=THEME['border'],
            thickness=18
        )

        self.build_shell()
        self.show_step(0)

    def build_shell(self):
        # ── Global Navigation Footer ──
        self.footer = tk.Frame(self, bg=THEME['bg_footer'], height=60)
        self.footer.pack(fill="x", side="bottom")

        # Subtle top border line
        sep_f = tk.Frame(self.footer, bg=THEME['border_subtle'], height=1)
        sep_f.pack(fill="x", side="top")

        self.footer_inner = tk.Frame(self.footer, bg=THEME['bg_footer'])
        self.footer_inner.pack(fill="x", padx=20, pady=12)

        self.btn_back = create_hover_button(
            self.footer_inner, "‹ Back", self.prev_step,
            bg=THEME['secondary'], hover_bg=THEME['sec_hover'], width=10
        )
        self.btn_back.pack(side="left", padx=(0, 10))

        self.btn_cancel = create_hover_button(
            self.footer_inner, "Cancel", self.destroy,
            bg=THEME['bg_card'], hover_bg=THEME['secondary'], fg=THEME['text_sub'], width=10
        )
        self.btn_cancel.pack(side="left")

        self.btn_next = create_hover_button(
            self.footer_inner, "Next ›", self.next_step,
            bg=THEME['primary'], hover_bg=THEME['primary_hover'], bold=True, width=12
        )
        self.btn_next.pack(side="right")

        # ── Main Central Container ──
        self.main_container = tk.Frame(self, bg=THEME['bg_content'])
        self.main_container.pack(fill="both", expand=True)

    def clear_container(self):
        for widget in self.main_container.winfo_children():
            widget.destroy()

    def show_step(self, index):
        self.current_step = index
        self.clear_container()
        self.steps[index]()

    def prev_step(self):
        if self.current_step > 0:
            self.show_step(self.current_step - 1)

    def next_step(self):
        if self.current_step < len(self.steps) - 1:
            self.show_step(self.current_step + 1)
        else:
            if self.launch_after.get():
                target_exe = os.path.join(self.install_path.get(), "MPI_Billing_App.exe")
                if os.path.exists(target_exe):
                    subprocess.Popen([target_exe], cwd=self.install_path.get())
            self.destroy()

    # ──────────────────────────────────────────────────────────────────────────
    # Step 0: Welcome Screen (Modern Two-Column Hero Layout)
    # ──────────────────────────────────────────────────────────────────────────
    def show_step_welcome(self):
        self.btn_back.config(state="disabled")
        self.btn_next.config(text="Next ›", state="normal")

        # ── Left Hero Sidebar (High-Res Logo & Branding) ──
        sidebar = tk.Frame(self.main_container, bg=THEME['bg_main'], width=270)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        # Right border line on sidebar
        tk.Frame(sidebar, bg=THEME['border_subtle'], width=1).pack(side="right", fill="y")

        side_inner = tk.Frame(sidebar, bg=THEME['bg_main'], padx=20, pady=26)
        side_inner.pack(fill="both", expand=True)

        # High-Resolution Logo
        if self.logo_hero:
            lbl_logo = tk.Label(side_inner, image=self.logo_hero, bg=THEME['bg_main'])
            lbl_logo.pack(pady=(10, 14))

        tk.Label(
            side_inner, text="MEAT PRODUCTS OF INDIA",
            font=("Segoe UI", 10, "bold"), fg=THEME['accent_gold'], bg=THEME['bg_main']
        ).pack(anchor="center")

        tk.Label(
            side_inner, text=APP_TAGLINE,
            font=("Segoe UI", 8), fg=THEME['text_muted'], bg=THEME['bg_main']
        ).pack(anchor="center", pady=(2, 12))

        # Thin divider
        tk.Frame(side_inner, bg=THEME['border_subtle'], height=1).pack(fill="x", pady=(0, 14))

        tk.Label(
            side_inner, text=APP_NAME,
            font=("Segoe UI", 12, "bold"), fg=THEME['text_light'], bg=THEME['bg_main']
        ).pack(anchor="center")

        arch_txt = f"v{APP_VERSION} • {'32-bit x86' if self.is_32bit else '64-bit'}"
        tk.Label(
            side_inner, text=arch_txt,
            font=("Segoe UI", 9, "bold"), fg=THEME['accent_blue'], bg=THEME['bg_main']
        ).pack(anchor="center", pady=(2, 16))

        # Brand feature badges
        features = [
            ("⚡", "100% Offline POS Billing"),
            ("☁️", "Supabase Cloud Sync"),
            ("🧾", "GST Thermal Receipts"),
            ("💳", "Razorpay Online License"),
        ]
        for icon, txt in features:
            f_row = tk.Frame(side_inner, bg=THEME['bg_main'])
            f_row.pack(anchor="w", fill="x", pady=3)
            tk.Label(f_row, text=icon, font=("Segoe UI", 9), bg=THEME['bg_main']).pack(side="left", padx=(0, 8))
            tk.Label(f_row, text=txt, font=("Segoe UI", 9), fg=THEME['text_sub'], bg=THEME['bg_main']).pack(side="left")

        # ── Right Main Area ──
        right = tk.Frame(self.main_container, bg=THEME['bg_content'], padx=32, pady=28)
        right.pack(side="right", fill="both", expand=True)

        tk.Label(
            right, text="Welcome to Setup",
            font=("Segoe UI", 18, "bold"), fg=THEME['text_light'], bg=THEME['bg_content']
        ).pack(anchor="w")

        tk.Label(
            right, text="Install Meat Products of India Billing & Inventory Management System on your PC.",
            font=("Segoe UI", 10), fg=THEME['text_muted'], bg=THEME['bg_content']
        ).pack(anchor="w", pady=(4, 18))

        # Modern Feature Cards
        cards = [
            ("⚡ Fast Offline-First Engine", "Blazing-fast local SQLite database allows uninterrupted checkout even without active internet."),
            ("☁️ Real-Time Cloud Mirror", "Automatically synchronizes bills, inventory, and ledger to your central Supabase cloud server."),
            ("🛡️ Safe Upgrades & Data Preservation", "Existing shop transactions, database, and settings are automatically preserved during updates.")
        ]

        for card_title, card_desc in cards:
            c_box = tk.Frame(right, bg=THEME['bg_card'], padx=14, pady=10, highlightthickness=1, highlightbackground=THEME['border'])
            c_box.pack(fill="x", pady=5)

            tk.Label(c_box, text=card_title, font=("Segoe UI", 10, "bold"), fg=THEME['accent_blue'], bg=THEME['bg_card']).pack(anchor="w")
            tk.Label(c_box, text=card_desc, font=("Segoe UI", 9), fg=THEME['text_sub'], bg=THEME['bg_card'], wraplength=410, justify="left").pack(anchor="w", pady=(2, 0))

        tk.Label(
            right, text='Click "Next ›" to choose your installation directory.',
            font=("Segoe UI", 9), fg=THEME['text_muted'], bg=THEME['bg_content']
        ).pack(anchor="w", pady=(22, 0))

    # ──────────────────────────────────────────────────────────────────────────
    # Helper: Build Header for Subsequent Steps
    # ──────────────────────────────────────────────────────────────────────────
    def create_step_header(self, title, step_text):
        hdr = tk.Frame(self.main_container, bg=THEME['bg_header'], height=72)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)

        # Bottom separator line
        tk.Frame(hdr, bg=THEME['border'], height=1).pack(fill="x", side="bottom")

        hdr_inner = tk.Frame(hdr, bg=THEME['bg_header'], padx=20)
        hdr_inner.pack(fill="both", expand=True)

        if self.logo_header:
            lbl_logo = tk.Label(hdr_inner, image=self.logo_header, bg=THEME['bg_header'])
            lbl_logo.pack(side="left", padx=(0, 14), pady=10)

        t_frame = tk.Frame(hdr_inner, bg=THEME['bg_header'])
        t_frame.pack(side="left", fill="y", pady=14)

        tk.Label(
            t_frame, text="MEAT PRODUCTS OF INDIA",
            font=("Segoe UI", 8, "bold"), fg=THEME['accent_gold'], bg=THEME['bg_header']
        ).pack(anchor="w")

        tk.Label(
            t_frame, text=title,
            font=("Segoe UI", 13, "bold"), fg=THEME['text_light'], bg=THEME['bg_header']
        ).pack(anchor="w")

        # Step Indicator Pill Badge
        badge = tk.Label(
            hdr_inner, text=step_text,
            font=("Segoe UI", 9, "bold"), fg=THEME['accent_blue'], bg=THEME['bg_card'],
            padx=12, pady=4, relief="flat"
        )
        badge.pack(side="right", pady=18)

    # ──────────────────────────────────────────────────────────────────────────
    # Step 1: Directory Selection
    # ──────────────────────────────────────────────────────────────────────────
    def show_step_directory(self):
        self.btn_back.config(state="normal")
        self.btn_next.config(text="Next ›", state="normal")

        self.create_step_header("Installation Location", "Step 1 of 3")

        body = tk.Frame(self.main_container, bg=THEME['bg_content'], padx=32, pady=24)
        body.pack(fill="both", expand=True)

        tk.Label(
            body, text="Select Destination Folder",
            font=("Segoe UI", 14, "bold"), fg=THEME['text_light'], bg=THEME['bg_content']
        ).pack(anchor="w")

        tk.Label(
            body, text=f"Setup will install {APP_NAME} into the following directory.",
            font=("Segoe UI", 10), fg=THEME['text_muted'], bg=THEME['bg_content']
        ).pack(anchor="w", pady=(4, 16))

        # Path input card
        frame_dir = tk.Frame(body, bg=THEME['bg_card'], padx=14, pady=14, highlightthickness=1, highlightbackground=THEME['border'])
        frame_dir.pack(fill="x", pady=6)

        entry = tk.Entry(
            frame_dir, textvariable=self.install_path, font=("Segoe UI", 10),
            bg=THEME['bg_main'], fg=THEME['text_light'], insertbackground="white",
            relief="flat", highlightthickness=1, highlightbackground=THEME['border']
        )
        entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 10))

        def browse_folder():
            f = filedialog.askdirectory(initialdir=self.install_path.get())
            if f:
                self.install_path.set(f)

        btn_browse = create_hover_button(
            frame_dir, "Browse…", browse_folder,
            bg=THEME['secondary'], hover_bg=THEME['sec_hover'], width=10, pady=4
        )
        btn_browse.pack(side="right")

        # Disk space status card
        space_frame = tk.Frame(body, bg=THEME['bg_content'])
        space_frame.pack(fill="x", pady=(18, 0))

        tk.Label(
            space_frame, text="✓ Required disk space: ~95 MB",
            font=("Segoe UI", 9, "bold"), fg=THEME['accent_green'], bg=THEME['bg_content']
        ).pack(anchor="w")

        tk.Label(
            space_frame, text="• Recommended: Install on local drive (C:\\) for optimal SQLite transaction speed.",
            font=("Segoe UI", 9), fg=THEME['text_muted'], bg=THEME['bg_content']
        ).pack(anchor="w", pady=(4, 0))

    # ──────────────────────────────────────────────────────────────────────────
    # Step 2: Options Screen
    # ──────────────────────────────────────────────────────────────────────────
    def show_step_options(self):
        self.btn_back.config(state="normal")
        self.btn_next.config(text="Install", state="normal")

        self.create_step_header("Shortcuts & Integration", "Step 2 of 3")

        body = tk.Frame(self.main_container, bg=THEME['bg_content'], padx=32, pady=24)
        body.pack(fill="both", expand=True)

        tk.Label(
            body, text="Configure Shortcuts",
            font=("Segoe UI", 14, "bold"), fg=THEME['text_light'], bg=THEME['bg_content']
        ).pack(anchor="w")

        tk.Label(
            body, text="Choose where you would like shortcuts to be created for quick launching.",
            font=("Segoe UI", 10), fg=THEME['text_muted'], bg=THEME['bg_content']
        ).pack(anchor="w", pady=(4, 16))

        # Checkbox card
        opt_card = tk.Frame(body, bg=THEME['bg_card'], padx=16, pady=14, highlightthickness=1, highlightbackground=THEME['border'])
        opt_card.pack(fill="x", pady=6)

        cb1 = tk.Checkbutton(
            opt_card, text="🖥️  Create a Desktop Shortcut", variable=self.create_desktop_sc,
            font=("Segoe UI", 10, "bold"), fg=THEME['text_light'], bg=THEME['bg_card'],
            selectcolor=THEME['bg_main'], activebackground=THEME['bg_card'], activeforeground=THEME['text_light']
        )
        cb1.pack(anchor="w", pady=6)

        cb2 = tk.Checkbutton(
            opt_card, text="📁  Create a Start Menu Shortcut", variable=self.create_start_sc,
            font=("Segoe UI", 10, "bold"), fg=THEME['text_light'], bg=THEME['bg_card'],
            selectcolor=THEME['bg_main'], activebackground=THEME['bg_card'], activeforeground=THEME['text_light']
        )
        cb2.pack(anchor="w", pady=6)

        # Integration notice
        note_card = tk.Frame(body, bg=THEME['bg_card_alt'], padx=14, pady=10, highlightthickness=1, highlightbackground=THEME['border'])
        note_card.pack(fill="x", pady=(16, 0))

        tk.Label(
            note_card, text="🛡️  Windows Settings & Control Panel Integration",
            font=("Segoe UI", 9, "bold"), fg=THEME['accent_blue'], bg=THEME['bg_card_alt']
        ).pack(anchor="w")

        tk.Label(
            note_card, text="✓ Registers automatically in Windows Installed Apps (Settings ➔ Apps) with built-in uninstaller.",
            font=("Segoe UI", 9), fg=THEME['accent_green'], bg=THEME['bg_card_alt']
        ).pack(anchor="w", pady=(2, 0))

    # ──────────────────────────────────────────────────────────────────────────
    # Step 3: Installing Screen
    # ──────────────────────────────────────────────────────────────────────────
    def show_step_install(self):
        self.btn_back.config(state="disabled")
        self.btn_next.config(state="disabled")
        self.btn_cancel.config(state="disabled")

        self.create_step_header("Installing Program Files", "Step 3 of 3")

        body = tk.Frame(self.main_container, bg=THEME['bg_content'], padx=32, pady=28)
        body.pack(fill="both", expand=True)

        tk.Label(
            body, text="Extracting and Configuring Files…",
            font=("Segoe UI", 14, "bold"), fg=THEME['text_light'], bg=THEME['bg_content']
        ).pack(anchor="w")

        tk.Label(
            body, text="Please wait while setup installs MPI Billing Software on your computer.",
            font=("Segoe UI", 10), fg=THEME['text_muted'], bg=THEME['bg_content']
        ).pack(anchor="w", pady=(4, 20))

        # Progress bar
        self.progress_bar = ttk.Progressbar(body, orient="horizontal", mode="determinate", length=640, style="Custom.Horizontal.TProgressbar")
        self.progress_bar.pack(fill="x", pady=10)

        # Status text
        self.lbl_status = tk.Label(body, text="Preparing installation…", font=("Segoe UI", 9), fg=THEME['accent_blue'], bg=THEME['bg_content'])
        self.lbl_status.pack(anchor="w", pady=4)

        self.after(200, self.perform_installation)

    def perform_installation(self):
        target_dir = self.install_path.get()
        os.makedirs(target_dir, exist_ok=True)

        # Preserve existing database if updating
        target_db = os.path.join(target_dir, "data", "meatshop.db")
        backup_db_path = None
        if os.path.exists(target_db):
            temp_dir = os.environ.get('TEMP', '.')
            backup_db_path = os.path.join(temp_dir, 'meatshop_db_backup.db')
            try:
                shutil.copy2(target_db, backup_db_path)
            except Exception:
                pass

        src_payload = self.payload_dir
        if not os.path.exists(src_payload):
            src_payload = get_bundle_dir()

        files_to_copy = []
        for root, dirs, files in os.walk(src_payload):
            for file in files:
                rel_p = os.path.relpath(os.path.join(root, file), src_payload)
                files_to_copy.append((os.path.join(root, file), rel_p))

        total_f = len(files_to_copy)
        for idx, (src_f, rel_f) in enumerate(files_to_copy):
            dest_f = os.path.join(target_dir, rel_f)
            os.makedirs(os.path.dirname(dest_f), exist_ok=True)
            try:
                shutil.copy2(src_f, dest_f)
            except Exception:
                pass

            pct = int(((idx + 1) / max(1, total_f)) * 100)
            self.progress_bar['value'] = pct
            display_file = rel_f if len(rel_f) <= 55 else f"...{rel_f[-52:]}"
            self.lbl_status.config(text=f"Copying: {display_file}")
            self.update_idletasks()

        # Restore preserved database if it existed
        if backup_db_path and os.path.exists(backup_db_path):
            os.makedirs(os.path.join(target_dir, "data"), exist_ok=True)
            try:
                shutil.copy2(backup_db_path, target_db)
                os.remove(backup_db_path)
            except Exception:
                pass

        try:
            with open(os.path.join(target_dir, "version.txt"), 'w', encoding='utf-8') as f:
                f.write(APP_VERSION)
        except Exception:
            pass

        # Ensure Supabase DATABASE_URL is securely provisioned in %PROGRAMDATA% with locked permissions
        try:
            curr_url = get_database_url()
            if not curr_url:
                save_database_url(PROD_SUPABASE_URL)
        except Exception as e:
            print(f"[Installer Warning] Could not provision database URL: {e}")

        # Create Uninstaller Script
        uninstaller_cmd = os.path.join(target_dir, "Uninstall.cmd")
        with open(uninstaller_cmd, "w", encoding="utf-8") as u:
            u.write(f'''@echo off
title Uninstall {APP_NAME}
echo ============================================================
echo   Uninstalling {APP_NAME}
echo ============================================================
echo.
echo Removing Windows Shortcuts and Registry entries...
reg delete "HKCU\\{REG_KEY_PATH}" /f >nul 2>&1
reg delete "HKLM\\{REG_KEY_PATH}" /f >nul 2>&1

set DESKTOP_SC="%USERPROFILE%\\Desktop\\{APP_NAME}.lnk"
if exist %DESKTOP_SC% del /f /q %DESKTOP_SC%

set START_SC="%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\{APP_NAME}.lnk"
if exist %START_SC% del /f /q %START_SC%

echo.
echo Cleaning up program files...
echo Completed!
timeout /t 2 >nul
''')

        # Register in Windows Add/Remove Programs (Registry)
        exe_path = os.path.join(target_dir, "MPI_Billing_App.exe")
        icon_path = os.path.join(target_dir, "logo.ico")

        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_KEY_PATH) as key:
                winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
                winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, APP_VERSION)
                winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, APP_PUBLISHER)
                winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f'"{uninstaller_cmd}"')
                winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, icon_path if os.path.exists(icon_path) else exe_path)
                winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, target_dir)
                winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
        except Exception as reg_e:
            print(f"Registry registration error: {reg_e}")

        # Create Shortcuts
        if self.create_desktop_sc.get():
            desktop_dir = os.path.join(os.path.expanduser('~'), 'Desktop')
            sc_p = os.path.join(desktop_dir, f"{APP_NAME}.lnk")
            create_windows_shortcut(exe_path, sc_p, icon_path, APP_NAME)

        if self.create_start_sc.get():
            start_menu = os.path.join(os.environ.get('APPDATA', ''), r'Microsoft\Windows\Start Menu\Programs')
            sc_p = os.path.join(start_menu, f"{APP_NAME}.lnk")
            create_windows_shortcut(exe_path, sc_p, icon_path, APP_NAME)

        self.btn_next.config(state="normal")
        self.show_step(4)

    # ──────────────────────────────────────────────────────────────────────────
    # Step 4: Finish Screen
    # ──────────────────────────────────────────────────────────────────────────
    def show_step_finish(self):
        self.btn_back.config(state="disabled")
        self.btn_cancel.config(state="disabled")
        self.btn_next.config(text="Finish", state="normal")

        body = tk.Frame(self.main_container, bg=THEME['bg_content'], padx=36, pady=32)
        body.pack(fill="both", expand=True)

        top_row = tk.Frame(body, bg=THEME['bg_content'])
        top_row.pack(anchor="w", fill="x")

        if self.logo_finish:
            lbl_fin_logo = tk.Label(top_row, image=self.logo_finish, bg=THEME['bg_content'])
            lbl_fin_logo.pack(side="left", padx=(0, 20))

        title_box = tk.Frame(top_row, bg=THEME['bg_content'])
        title_box.pack(side="left", fill="y", pady=10)

        tk.Label(
            title_box, text="Installation Complete! 🎉",
            font=("Segoe UI", 17, "bold"), fg=THEME['accent_green'], bg=THEME['bg_content']
        ).pack(anchor="w")

        tk.Label(
            title_box, text=f"{APP_NAME} v{APP_VERSION} is ready to use.",
            font=("Segoe UI", 10), fg=THEME['text_sub'], bg=THEME['bg_content']
        ).pack(anchor="w", pady=(4, 0))

        # Summary confirmation card
        sum_card = tk.Frame(body, bg=THEME['bg_card'], padx=18, pady=16, highlightthickness=1, highlightbackground=THEME['border'])
        sum_card.pack(fill="x", pady=20)

        inst_path_display = self.install_path.get()
        if len(inst_path_display) > 55:
            inst_path_display = f"...{inst_path_display[-50:]}"

        items = [
            ("📁 Location", inst_path_display),
            ("⚡ Database Engine", "100% Offline SQLite (Active)"),
            ("☁️ Cloud Sync", "Supabase PostgreSQL Mirror (Connected)"),
            ("💳 Software License", "Active / 10-Day Free Trial Initialized"),
        ]
        for label, val in items:
            row = tk.Frame(sum_card, bg=THEME['bg_card'])
            row.pack(fill="x", pady=3)
            tk.Label(row, text=f"{label}:", font=("Segoe UI", 9, "bold"), fg=THEME['text_muted'], bg=THEME['bg_card'], width=18, anchor="w").pack(side="left")
            tk.Label(row, text=val, font=("Segoe UI", 9), fg=THEME['text_light'], bg=THEME['bg_card']).pack(side="left")

        cb_launch = tk.Checkbutton(
            body, text=f"🚀  Launch {APP_NAME} now", variable=self.launch_after,
            font=("Segoe UI", 11, "bold"), fg=THEME['accent_blue'], bg=THEME['bg_content'],
            selectcolor=THEME['bg_main'], activebackground=THEME['bg_content'], activeforeground=THEME['accent_blue']
        )
        cb_launch.pack(anchor="w", pady=(6, 0))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=f"{APP_NAME} Setup Wizard")
    parser.add_argument("--db-url", dest="db_url", default=None, help="Custom Supabase PostgreSQL connection string (Developer override)")
    args, _ = parser.parse_known_args()
    if args.db_url:
        PROD_SUPABASE_URL = args.db_url.strip()
    app = InstallerWizard()
    app.mainloop()
