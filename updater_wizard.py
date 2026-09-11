"""
updater_wizard.py — Standalone Application Updater + Installer Wizard
Meat Products of India — Billing & Inventory Management App

Two modes:
  1. UPDATE  — Safely updates an existing installation, preserving database,
               backups, settings and customer data.
  2. INSTALL — Fresh installation on a new machine (with shortcuts, registry).

Automatically detects whether the app is already installed and pre-selects
the appropriate mode.
"""

import sys
import os
import shutil
import winreg
import subprocess
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk

# ─── Configuration ─────────────────────────────────────────────────────────────
APP_NAME      = "MPI Billing Software"
APP_PUBLISHER = "Meat Products of India"
NEW_VERSION   = "2.0.0"          # <-- bump this with every release
REG_KEY_PATH  = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\MPI_Billing_Software"

# Files to NEVER overwrite during an update (user data preservation)
PRESERVE_PATTERNS = [
    r'data\meatshop.db',
]

# Payload source folders to skip entirely during update (user-generated)
SKIP_SOURCE_FOLDERS = {'backups'}

CHANGELOG = """\
v2.0.0 — Latest Release
───────────────────────────────────────────
• Discount now supports ₹ (flat cash) mode in addition to %
• Direct percentage input field added alongside slider
• Preset quick-discount buttons for both % and ₹ modes
• Bill summary popup shows accurate discount in both modes
• Held bills now preserve discount mode (% or ₹)
• Performance improvements across billing & inventory pages
• Minor UI polish and bug fixes throughout

v1.0.0 — Initial Release
───────────────────────────────────────────
• Full POS billing with thermal & A4 invoice printing
• Inventory & stock management with low-stock alerts
• Customer loyalty points system
• GST-ready billing (CGST/SGST/IGST)
• Cloud backup support
• Multi-user role management\
"""

C = {
    'bg':       '#0F172A',
    'card':     '#1E293B',
    'input':    '#334155',
    'accent':   '#0284C7',
    'gold':     '#F59E0B',
    'green':    '#10B981',
    'red':      '#EF4444',
    'text':     '#F8FAFC',
    'muted':    '#94A3B8',
    'sub':      '#CBD5E1',
    'border':   '#475569',
    'sel_bg':   '#1D4ED8',
}

# ─── Helpers ───────────────────────────────────────────────────────────────────

def get_bundle_dir():
    """Returns the directory that holds bundled assets (logo etc.) — _MEIPASS when frozen."""
    if getattr(sys, 'frozen', False):
        return getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.dirname(os.path.abspath(__file__))


def get_exe_dir():
    """
    Returns the directory of the running executable (or script when in dev).
    For the updater this is where MPI_Billing_App\\ payload folder lives,
    placed BESIDE the exe -- NOT inside the bundled _MEIPASS archive.
    """
    if getattr(sys, 'frozen', False):
        # sys.executable is the actual .exe path when frozen
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def detect_installed_path():
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, REG_KEY_PATH) as key:
                loc, _ = winreg.QueryValueEx(key, "InstallLocation")
                if loc and os.path.exists(loc):
                    return loc
        except Exception:
            pass
    user_appdata = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
    for candidate in [
        os.path.join(user_appdata, "Programs", "MPI Billing Software"),
        os.path.join(os.environ.get('ProgramFiles', r'C:\Program Files'), "MPI Billing Software"),
        os.path.join(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'), "MPI Billing Software"),
    ]:
        if os.path.exists(candidate):
            return candidate
    return os.path.join(user_appdata, "Programs", "MPI Billing Software")


def get_default_install_path():
    """Best-guess default path for a fresh install."""
    user_appdata = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
    return os.path.join(user_appdata, "Programs", "MPI Billing Software")


def get_installed_version(install_dir):
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, REG_KEY_PATH) as key:
                ver, _ = winreg.QueryValueEx(key, "DisplayVersion")
                if ver:
                    return ver
        except Exception:
            pass
    ver_file = os.path.join(install_dir, "version.txt")
    if os.path.exists(ver_file):
        try:
            with open(ver_file) as f:
                return f.read().strip()
        except Exception:
            pass
    if os.path.exists(os.path.join(install_dir, "MPI_Billing_App.exe")):
        return "1.x (unknown)"
    return None


def is_already_installed(install_dir):
    return os.path.exists(os.path.join(install_dir, "MPI_Billing_App.exe"))


def close_running_instances():
    try:
        subprocess.run(['taskkill', '/F', '/IM', 'MPI_Billing_App.exe'],
                       capture_output=True, timeout=5)
        time.sleep(0.8)
    except Exception:
        pass


def create_windows_shortcut(target, shortcut_path, icon_path=None, description=""):
    """Create a Windows .lnk shortcut safely in-memory without dropping temporary VBS files into %TEMP%."""
    # 1. Native Python COM (pywin32) if available (100% in-process COM)
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

    # 2. In-memory PowerShell (no temporary files created on disk, avoids AV heuristics)
    try:
        target_esc = target.replace("'", "''")
        sc_esc = shortcut_path.replace("'", "''")
        work_dir_esc = os.path.dirname(target).replace("'", "''")
        desc_esc = description.replace("'", "''")
        
        ps_parts = [
            f"$ws = New-Object -ComObject WScript.Shell",
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
        print(f"Shortcut error: {e}")
        return False


def write_uninstaller(target_dir):
    uninstaller_cmd = os.path.join(target_dir, "Uninstall.cmd")
    with open(uninstaller_cmd, "w", encoding="utf-8") as u:
        u.write(f'@echo off\ntitle Uninstall {APP_NAME}\n')
        u.write(f'echo Uninstalling {APP_NAME}...\n')
        u.write(f'reg delete "HKCU\\{REG_KEY_PATH}" /f >nul 2>&1\n')
        u.write(f'reg delete "HKLM\\{REG_KEY_PATH}" /f >nul 2>&1\n')
        u.write(f'set DS="%USERPROFILE%\\Desktop\\{APP_NAME}.lnk"\n')
        u.write(f'if exist %DS% del /f /q %DS%\n')
        u.write(f'set SM="%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\{APP_NAME}.lnk"\n')
        u.write(f'if exist %SM% del /f /q %SM%\n')
        u.write('echo Done! Close this window.\npause\n')
    return uninstaller_cmd


def register_in_windows(target_dir, uninstaller_cmd=None):
    exe_path = os.path.join(target_dir, "MPI_Billing_App.exe")
    icon_path = os.path.join(target_dir, "logo.ico")
    if uninstaller_cmd is None:
        uninstaller_cmd = os.path.join(target_dir, "Uninstall.cmd")
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_KEY_PATH) as key:
            winreg.SetValueEx(key, "DisplayName",    0, winreg.REG_SZ, APP_NAME)
            winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, NEW_VERSION)
            winreg.SetValueEx(key, "Publisher",      0, winreg.REG_SZ, APP_PUBLISHER)
            winreg.SetValueEx(key, "InstallLocation",0, winreg.REG_SZ, target_dir)
            winreg.SetValueEx(key, "DisplayIcon",    0, winreg.REG_SZ,
                              icon_path if os.path.exists(icon_path) else exe_path)
            if os.path.exists(uninstaller_cmd):
                winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ,
                                  f'"{uninstaller_cmd}"')
            winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
    except Exception as e:
        print(f"Registry error: {e}")
    try:
        with open(os.path.join(target_dir, "version.txt"), 'w') as f:
            f.write(NEW_VERSION)
    except Exception:
        pass


def should_preserve(rel_path):
    norm = rel_path.lower().replace('/', '\\')
    return any(norm.endswith(p.lower()) for p in PRESERVE_PATTERNS)


# ─── Main Wizard Window ────────────────────────────────────────────────────────

class UpdaterInstaller(tk.Tk):
    MODE_SELECT  = "select"
    MODE_UPDATE  = "update"
    MODE_INSTALL = "install"

    def __init__(self):
        super().__init__()

        self.bundle_dir  = get_bundle_dir()   # for logo/assets (inside _MEIPASS)
        self.exe_dir     = get_exe_dir()       # for payload folder beside the exe

        # Payload search order:
        #   1. MPI_Billing_App\  beside the exe      (production updater package)
        #   2. payload\          beside the exe       (legacy bundled layout)
        #   3. dist\MPI_Billing_App\  in project dir  (dev / build environment)
        for _candidate in [
            os.path.join(self.exe_dir,    "MPI_Billing_App"),
            os.path.join(self.exe_dir,    "payload"),
            os.path.join(self.exe_dir,    "dist", "MPI_Billing_App"),
            os.path.join(self.bundle_dir, "payload"),
            os.path.join(self.bundle_dir, "dist", "MPI_Billing_App"),
        ]:
            if os.path.exists(_candidate):
                self.payload_dir = _candidate
                break
        else:
            self.payload_dir = os.path.join(self.exe_dir, "MPI_Billing_App")

        self.detected_path  = detect_installed_path()
        self.already_inst   = is_already_installed(self.detected_path)

        self.install_path   = tk.StringVar(value=self.detected_path)
        self.fresh_path     = tk.StringVar(value=get_default_install_path())
        self.launch_after   = tk.BooleanVar(value=True)
        self.desktop_sc     = tk.BooleanVar(value=True)
        self.start_sc       = tk.BooleanVar(value=True)
        self._mode          = None
        self._update_error  = None
        self._files_updated = 0
        self._files_skipped = 0

        # Window
        self.title(f"{APP_NAME} — Setup & Update Wizard  v{NEW_VERSION}")
        self.geometry("700x560")
        self.resizable(False, False)
        self.configure(bg=C['bg'])
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        # Logo
        self.logo_img = None
        logo_p = os.path.join(self.bundle_dir, "logo.png")
        if os.path.exists(logo_p):
            try:
                img = Image.open(logo_p).resize((52, 52), Image.Resampling.LANCZOS)
                self.logo_img = ImageTk.PhotoImage(img)
            except Exception:
                pass

        self._build_chrome()
        self._show_mode_select()

    # ── Chrome (header + container + footer) ──────────────────────────────────

    def _build_chrome(self):
        # Header
        hdr = tk.Frame(self, bg=C['card'], height=72)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)

        if self.logo_img:
            tk.Label(hdr, image=self.logo_img, bg=C['card']).pack(
                side="left", padx=14, pady=10)

        hdr_txt = tk.Frame(hdr, bg=C['card'])
        hdr_txt.pack(side="left", fill="y", pady=10)
        tk.Label(hdr_txt, text=f"{APP_NAME} — Setup & Update Wizard",
                 font=("Segoe UI", 13, "bold"), fg=C['text'], bg=C['card']).pack(anchor="w")
        tk.Label(hdr_txt, text=f"Version {NEW_VERSION}  |  {APP_PUBLISHER}",
                 font=("Segoe UI", 9), fg=C['muted'], bg=C['card']).pack(anchor="w")

        # Container
        self.container = tk.Frame(self, bg=C['bg'], padx=22, pady=14)
        self.container.pack(fill="both", expand=True)

        # Footer
        self.footer = tk.Frame(self, bg=C['card'], height=52)
        self.footer.pack(fill="x", side="bottom")
        self.footer.pack_propagate(False)

        self.btn_back = tk.Button(
            self.footer, text="‹ Back", font=("Segoe UI", 10),
            bg=C['border'], fg=C['text'], width=10,
            relief="flat", cursor="hand2", command=self._show_mode_select)
        self.btn_back.pack(side="left", padx=16, pady=10)

        self.btn_exit = tk.Button(
            self.footer, text="Exit", font=("Segoe UI", 10),
            bg=C['border'], fg=C['text'], width=9,
            relief="flat", cursor="hand2", command=self.destroy)
        self.btn_exit.pack(side="left", padx=6, pady=10)

        self.btn_action = tk.Button(
            self.footer, text="Continue ›", font=("Segoe UI", 10, "bold"),
            bg=C['accent'], fg=C['text'], width=18,
            relief="flat", cursor="hand2", command=self._noop)
        self.btn_action.pack(side="right", padx=16, pady=10)

    def _noop(self): pass

    def _clear(self):
        for w in self.container.winfo_children():
            w.destroy()

    def _set_footer(self, back_visible=True, action_text="Continue ›",
                    action_cmd=None, action_color=None, exit_visible=True):
        self.btn_back.config(state="normal" if back_visible else "disabled")
        self.btn_exit.config(state="normal" if exit_visible else "disabled")
        self.btn_action.config(
            text=action_text,
            command=action_cmd or self._noop,
            bg=action_color or C['accent'])

    # ── SCREEN 1: Mode Selection ───────────────────────────────────────────────

    def _show_mode_select(self):
        self._clear()
        self._mode = self.MODE_SELECT
        self._set_footer(back_visible=False, action_text="Continue ›",
                         action_cmd=self._on_mode_continue)

        tk.Label(self.container, text="What would you like to do?",
                 font=("Segoe UI", 14, "bold"), fg=C['text'],
                 bg=C['bg']).pack(anchor="w", pady=(0, 14))

        self._mode_var = tk.StringVar(
            value="update" if self.already_inst else "install")

        # ── Update card ──
        upd_border_c = C['accent'] if self.already_inst else C['border']
        upd_card = tk.Frame(self.container, bg=C['card'],
                            highlightbackground=upd_border_c,
                            highlightthickness=2, padx=0, pady=0)
        upd_card.pack(fill="x", pady=(0, 10))
        upd_card.bind("<Button-1>", lambda e: self._mode_var.set("update"))

        upd_inner = tk.Frame(upd_card, bg=C['card'], padx=14, pady=12)
        upd_inner.pack(fill="x")

        rb_upd = tk.Radiobutton(
            upd_inner, text="", variable=self._mode_var, value="update",
            bg=C['card'], activebackground=C['card'],
            command=lambda: self._refresh_mode_cards(
                upd_card, inst_card, upd_border_lbl, inst_border_lbl))
        rb_upd.pack(side="left")

        upd_txt = tk.Frame(upd_inner, bg=C['card'])
        upd_txt.pack(side="left", fill="x", expand=True)
        upd_border_lbl = tk.Label(
            upd_txt,
            text="⚡ Update Existing Installation",
            font=("Segoe UI", 12, "bold"),
            fg=C['accent'], bg=C['card'])
        upd_border_lbl.pack(anchor="w")

        inst_ver = get_installed_version(self.detected_path) or "Not found"
        status_txt = (
            f"Detected installation: {self.detected_path}\n"
            f"Installed version: v{inst_ver}  →  New version: v{NEW_VERSION}\n"
            "Updates program files only — database, backups & settings are preserved."
        ) if self.already_inst else (
            "No existing installation detected on this computer.\n"
            "Use this option if you know the installation folder path."
        )
        tk.Label(upd_txt, text=status_txt,
                 font=("Segoe UI", 9), fg=C['sub'] if self.already_inst else C['muted'],
                 bg=C['card'], justify="left").pack(anchor="w", pady=(3, 0))

        if self.already_inst:
            badge = tk.Label(upd_inner, text=" DETECTED ", font=("Segoe UI", 8, "bold"),
                             fg='#fff', bg=C['accent'], padx=4)
            badge.pack(side="right", padx=6)

        # ── Install card ──
        inst_border_c = C['green'] if not self.already_inst else C['border']
        inst_card = tk.Frame(self.container, bg=C['card'],
                             highlightbackground=inst_border_c,
                             highlightthickness=2)
        inst_card.pack(fill="x", pady=(0, 10))
        inst_card.bind("<Button-1>", lambda e: self._mode_var.set("install"))

        inst_inner = tk.Frame(inst_card, bg=C['card'], padx=14, pady=12)
        inst_inner.pack(fill="x")

        rb_inst = tk.Radiobutton(
            inst_inner, text="", variable=self._mode_var, value="install",
            bg=C['card'], activebackground=C['card'],
            command=lambda: self._refresh_mode_cards(
                upd_card, inst_card, upd_border_lbl, inst_border_lbl))
        rb_inst.pack(side="left")

        inst_txt = tk.Frame(inst_inner, bg=C['card'])
        inst_txt.pack(side="left", fill="x", expand=True)
        inst_border_lbl = tk.Label(
            inst_txt,
            text="🆕 Fresh Install (New Machine)",
            font=("Segoe UI", 12, "bold"),
            fg=C['green'], bg=C['card'])
        inst_border_lbl.pack(anchor="w")
        tk.Label(inst_txt,
                 text=(
                     "Install MPI Billing Software for the first time on this computer.\n"
                     "Creates desktop & Start Menu shortcuts, registers in Windows Apps."
                 ),
                 font=("Segoe UI", 9), fg=C['sub'], bg=C['card'],
                 justify="left").pack(anchor="w", pady=(3, 0))

        if not self.already_inst:
            badge2 = tk.Label(inst_inner, text=" RECOMMENDED ", font=("Segoe UI", 8, "bold"),
                              fg='#fff', bg=C['green'], padx=4)
            badge2.pack(side="right", padx=6)

        # Changelog preview
        tk.Label(self.container, text="What's New in v" + NEW_VERSION + ":",
                 font=("Segoe UI", 9, "bold"), fg=C['muted'],
                 bg=C['bg']).pack(anchor="w", pady=(8, 4))

        log_frame = tk.Frame(self.container, bg=C['card'], padx=2, pady=2)
        log_frame.pack(fill="both", expand=True)
        sb = tk.Scrollbar(log_frame)
        sb.pack(side="right", fill="y")
        lt = tk.Text(log_frame, font=("Consolas", 8), bg=C['card'],
                     fg=C['sub'], relief="flat", wrap="word",
                     yscrollcommand=sb.set, height=5)
        lt.insert("1.0", CHANGELOG)
        lt.config(state="disabled")
        lt.pack(side="left", fill="both", expand=True)
        sb.config(command=lt.yview)

    def _refresh_mode_cards(self, upd_card, inst_card, upd_lbl, inst_lbl):
        v = self._mode_var.get()
        upd_card.config(highlightbackground=C['accent'] if v == 'update' else C['border'])
        inst_card.config(highlightbackground=C['green'] if v == 'install' else C['border'])

    def _on_mode_continue(self):
        mode = self._mode_var.get()
        if mode == "update":
            self._show_update_view()
        else:
            self._show_install_view()

    # ══════════════════════════════════════════════════════════════════════════
    # UPDATE FLOW
    # ══════════════════════════════════════════════════════════════════════════

    def _show_update_view(self):
        self._clear()
        self._mode = self.MODE_UPDATE
        self._set_footer(back_visible=True, action_text="⚡ Update Now",
                         action_cmd=self._start_update, action_color=C['accent'])

        inst_dir  = self.install_path.get()
        inst_ver  = get_installed_version(inst_dir) or "Not Found"
        is_fresh  = not is_already_installed(inst_dir)

        tk.Label(self.container, text="Update Existing Installation",
                 font=("Segoe UI", 13, "bold"), fg=C['accent'],
                 bg=C['bg']).pack(anchor="w", pady=(0, 10))

        # Version comparison
        ver_frame = tk.Frame(self.container, bg=C['card'], padx=14, pady=10)
        ver_frame.pack(fill="x", pady=(0, 10))
        tk.Label(ver_frame, text="Version Comparison",
                 font=("Segoe UI", 9, "bold"), fg=C['muted'],
                 bg=C['card']).pack(anchor="w")
        vr = tk.Frame(ver_frame, bg=C['card'])
        vr.pack(fill="x", pady=(6, 0))

        _b1 = tk.Frame(vr, bg=C['input'], padx=12, pady=6)
        _b1.pack(side="left", fill="both", expand=True)
        tk.Label(_b1, text="Installed", font=("Segoe UI", 8), fg=C['muted'], bg=C['input']).pack(anchor="w")
        tk.Label(_b1, text=f"v{inst_ver}", font=("Segoe UI", 14, "bold"),
                 fg=C['red'] if is_fresh else C['sub'], bg=C['input']).pack(anchor="w")

        tk.Label(vr, text="  →  ", font=("Segoe UI", 14, "bold"),
                 fg=C['muted'], bg=C['card']).pack(side="left")

        _b2 = tk.Frame(vr, bg=C['input'], padx=12, pady=6)
        _b2.pack(side="left", fill="both", expand=True)
        tk.Label(_b2, text="New (this package)", font=("Segoe UI", 8), fg=C['muted'], bg=C['input']).pack(anchor="w")
        tk.Label(_b2, text=f"v{NEW_VERSION}", font=("Segoe UI", 14, "bold"),
                 fg=C['green'], bg=C['input']).pack(anchor="w")

        # Path selector
        tk.Label(self.container, text="Installation Folder to Update:",
                 font=("Segoe UI", 10, "bold"), fg=C['text'],
                 bg=C['bg']).pack(anchor="w", pady=(6, 3))

        pf = tk.Frame(self.container, bg=C['bg'])
        pf.pack(fill="x", pady=(0, 8))
        tk.Entry(pf, textvariable=self.install_path, font=("Segoe UI", 10),
                 bg=C['input'], fg=C['text'], insertbackground="white",
                 relief="flat").pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 8))
        tk.Button(pf, text="Browse…", font=("Segoe UI", 9),
                  bg=C['border'], fg=C['text'], relief="flat", cursor="hand2",
                  command=lambda: (
                      f := filedialog.askdirectory(initialdir=self.install_path.get()),
                      self.install_path.set(f) if f else None)
                  ).pack(side="right")

        # Safety notice
        sb_f = tk.Frame(self.container, bg="#064E3B", padx=12, pady=7)
        sb_f.pack(fill="x", pady=(0, 10))
        tk.Label(sb_f, text="🔒 100% Safe — Database & Data Preserved",
                 font=("Segoe UI", 9, "bold"), fg="#6EE7B7", bg="#064E3B").pack(anchor="w")
        tk.Label(sb_f,
                 text="Bills, customers, backups & settings are NEVER overwritten.",
                 font=("Segoe UI", 9), fg="#A7F3D0", bg="#064E3B").pack(anchor="w")

        # Changelog
        tk.Label(self.container, text="Changelog:",
                 font=("Segoe UI", 9, "bold"), fg=C['muted'],
                 bg=C['bg']).pack(anchor="w", pady=(0, 3))
        lf = tk.Frame(self.container, bg=C['card'], padx=2, pady=2)
        lf.pack(fill="both", expand=True)
        sb2 = tk.Scrollbar(lf)
        sb2.pack(side="right", fill="y")
        lt = tk.Text(lf, font=("Consolas", 8), bg=C['card'],
                     fg=C['sub'], relief="flat", wrap="word",
                     yscrollcommand=sb2.set, height=7)
        lt.insert("1.0", CHANGELOG)
        lt.config(state="disabled")
        lt.pack(side="left", fill="both", expand=True)
        sb2.config(command=lt.yview)

        # Launch checkbox
        tk.Checkbutton(
            self.container,
            text=f"Launch {APP_NAME} automatically after update",
            variable=self.launch_after,
            font=("Segoe UI", 9, "bold"), fg=C['accent'],
            bg=C['bg'], selectcolor=C['card'],
            activebackground=C['bg'], activeforeground=C['accent']
        ).pack(anchor="w", pady=(8, 0))

    def _start_update(self):
        target_dir = self.install_path.get().strip()
        if not target_dir:
            messagebox.showerror("Error", "Please enter the installation folder path.")
            return
        if not os.path.exists(self.payload_dir):
            messagebox.showerror("Payload Missing",
                                 f"Update payload not found at:\n{self.payload_dir}")
            return
        self._run_progress(target_dir, mode="update")

    # ══════════════════════════════════════════════════════════════════════════
    # INSTALL FLOW
    # ══════════════════════════════════════════════════════════════════════════

    def _show_install_view(self):
        self._clear()
        self._mode = self.MODE_INSTALL
        self._set_footer(back_visible=True, action_text="🆕 Install Now",
                         action_cmd=self._start_install, action_color=C['green'])

        tk.Label(self.container, text="Fresh Installation",
                 font=("Segoe UI", 13, "bold"), fg=C['green'],
                 bg=C['bg']).pack(anchor="w", pady=(0, 6))
        tk.Label(self.container,
                 text=f"Install {APP_NAME} v{NEW_VERSION} on this computer for the first time.",
                 font=("Segoe UI", 10), fg=C['sub'], bg=C['bg']).pack(anchor="w", pady=(0, 12))

        # Destination
        tk.Label(self.container, text="Install to Folder:",
                 font=("Segoe UI", 10, "bold"), fg=C['text'],
                 bg=C['bg']).pack(anchor="w", pady=(0, 3))
        pf = tk.Frame(self.container, bg=C['bg'])
        pf.pack(fill="x", pady=(0, 4))
        tk.Entry(pf, textvariable=self.fresh_path, font=("Segoe UI", 10),
                 bg=C['input'], fg=C['text'], insertbackground="white",
                 relief="flat").pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 8))
        tk.Button(pf, text="Browse…", font=("Segoe UI", 9),
                  bg=C['border'], fg=C['text'], relief="flat", cursor="hand2",
                  command=lambda: (
                      f := filedialog.askdirectory(initialdir=self.fresh_path.get()),
                      self.fresh_path.set(f) if f else None)
                  ).pack(side="right")
        tk.Label(self.container, text="Required disk space: ~85 MB",
                 font=("Segoe UI", 9), fg=C['muted'],
                 bg=C['bg']).pack(anchor="w", pady=(0, 10))

        # Options
        opts_frame = tk.Frame(self.container, bg=C['card'], padx=14, pady=12)
        opts_frame.pack(fill="x", pady=(0, 10))
        tk.Label(opts_frame, text="Shortcuts & Integration",
                 font=("Segoe UI", 9, "bold"), fg=C['muted'],
                 bg=C['card']).pack(anchor="w", pady=(0, 6))

        for var, label in [
            (self.desktop_sc,  "Create a Desktop shortcut"),
            (self.start_sc,    "Create a Start Menu shortcut"),
        ]:
            tk.Checkbutton(opts_frame, text=label, variable=var,
                           font=("Segoe UI", 10), fg=C['text'],
                           bg=C['card'], selectcolor=C['input'],
                           activebackground=C['card'], activeforeground=C['text']
                           ).pack(anchor="w", pady=2)

        tk.Label(opts_frame,
                 text="✓ Automatically registers in Windows Settings → Apps & Features (with Uninstaller)",
                 font=("Segoe UI", 9), fg=C['green'], bg=C['card']).pack(anchor="w", pady=(8, 0))

        # Feature list
        feat_frame = tk.Frame(self.container, bg=C['card'], padx=14, pady=10)
        feat_frame.pack(fill="x", pady=(0, 10))
        tk.Label(feat_frame, text="Included in this release:",
                 font=("Segoe UI", 9, "bold"), fg=C['muted'],
                 bg=C['card']).pack(anchor="w", pady=(0, 4))
        features = [
            "Full POS Billing — Thermal & A4 Invoices",
            "Inventory, Stock Management & Low-Stock Alerts",
            "Discount by % or flat ₹ Cash Amount",
            "GST-Ready (CGST / SGST / IGST)",
            "Customer Loyalty Points System",
            "Multi-user Role Management",
        ]
        for feat in features:
            tk.Label(feat_frame, text=f"  • {feat}", font=("Segoe UI", 9),
                     fg=C['sub'], bg=C['card']).pack(anchor="w")

        # Launch checkbox
        tk.Checkbutton(
            self.container,
            text=f"Launch {APP_NAME} after installation",
            variable=self.launch_after,
            font=("Segoe UI", 9, "bold"), fg=C['green'],
            bg=C['bg'], selectcolor=C['card'],
            activebackground=C['bg'], activeforeground=C['green']
        ).pack(anchor="w", pady=(4, 0))

    def _start_install(self):
        target_dir = self.fresh_path.get().strip()
        if not target_dir:
            messagebox.showerror("Error", "Please select a destination folder.")
            return
        if not os.path.exists(self.payload_dir):
            messagebox.showerror("Payload Missing",
                                 f"Installation payload not found at:\n{self.payload_dir}")
            return
        self._run_progress(target_dir, mode="install")

    # ══════════════════════════════════════════════════════════════════════════
    # SHARED PROGRESS VIEW (Update & Install)
    # ══════════════════════════════════════════════════════════════════════════

    def _run_progress(self, target_dir, mode):
        self._clear()
        self._set_footer(back_visible=False, exit_visible=False,
                         action_text="Working…", action_color=C['border'])
        self.btn_action.config(state="disabled")

        verb = "Installing" if mode == "install" else "Updating"
        tk.Label(self.container, text=f"{verb}…",
                 font=("Segoe UI", 13, "bold"), fg=C['accent'],
                 bg=C['bg']).pack(anchor="w", pady=(0, 10))

        self.progress_bar = ttk.Progressbar(
            self.container, orient="horizontal",
            mode="determinate", length=630)
        self.progress_bar.pack(pady=(0, 6))

        self.lbl_step = tk.Label(self.container, text="Preparing…",
                                 font=("Segoe UI", 9, "bold"), fg=C['text'],
                                 bg=C['bg'])
        self.lbl_step.pack(anchor="w")
        self.lbl_file = tk.Label(self.container, text="",
                                 font=("Consolas", 8), fg=C['muted'],
                                 bg=C['bg'], wraplength=640, justify="left")
        self.lbl_file.pack(anchor="w", pady=(2, 0))

        lf = tk.Frame(self.container, bg=C['card'], padx=2, pady=2)
        lf.pack(fill="both", expand=True, pady=(12, 0))
        sb = tk.Scrollbar(lf)
        sb.pack(side="right", fill="y")
        self.log_box = tk.Text(lf, font=("Consolas", 8), bg=C['card'],
                               fg=C['sub'], relief="flat", wrap="word",
                               yscrollcommand=sb.set, height=14)
        self.log_box.pack(side="left", fill="both", expand=True)
        sb.config(command=self.log_box.yview)

        thread = threading.Thread(
            target=self._perform_update if mode == "update" else self._perform_install,
            args=(target_dir,), daemon=True)
        thread.start()

    def _log(self, msg):
        def _do():
            self.log_box.config(state="normal")
            self.log_box.insert("end", msg + "\n")
            self.log_box.see("end")
            self.log_box.config(state="disabled")
        self.after(0, _do)

    def _setstep(self, t): self.after(0, lambda: self.lbl_step.config(text=t))
    def _setfile(self, t): self.after(0, lambda: self.lbl_file.config(text=t))
    def _setpct(self, p):  self.after(0, lambda: self.progress_bar.config(value=p))

    # ── Update worker ──────────────────────────────────────────────────────────

    def _perform_update(self, target_dir):
        os.makedirs(target_dir, exist_ok=True)
        try:
            self._setstep("Step 1 of 4: Stopping running instances…")
            self._log("⏹  Stopping MPI Billing App processes…")
            close_running_instances()
            self._log("✓  Stopped."); self._setpct(5)

            self._setstep("Step 2 of 4: Backing up database…")
            self._log("🔒  Backing up database…")
            target_db = os.path.join(target_dir, "data", "meatshop.db")
            bak = None
            if os.path.exists(target_db):
                bak = os.path.join(os.environ.get('TEMP', '.'), 'mpi_upd_db.db')
                try:
                    shutil.copy2(target_db, bak)
                    self._log(f"✓  Backed up: {bak}")
                except Exception as e:
                    self._log(f"⚠  Backup failed: {e}")
            else:
                self._log("ℹ  No existing database found.")
            self._setpct(15)

            self._setstep("Step 3 of 4: Copying updated files…")
            files, upd, skp, errs = self._copy_payload(target_dir, preserve_db=True)
            self._files_updated = upd; self._files_skipped = skp

            self._setstep("Step 4 of 4: Restoring database & finalising…")
            if bak and os.path.exists(bak):
                os.makedirs(os.path.join(target_dir, "data"), exist_ok=True)
                try:
                    shutil.copy2(bak, target_db)
                    os.remove(bak)
                    self._log("✓  Database restored.")
                except Exception as e:
                    self._log(f"⚠  Restore error: {e}")
            register_in_windows(target_dir)
            self._log(f"✓  Registry updated to v{NEW_VERSION}")
            self._setpct(100)
            self.after(0, lambda: self._show_finish(target_dir, errs, mode="update"))
        except Exception as ex:
            self._update_error = str(ex)
            self._log(f"❌  FATAL: {ex}")
            self.after(0, self._show_error)

    # ── Install worker ─────────────────────────────────────────────────────────

    def _perform_install(self, target_dir):
        os.makedirs(target_dir, exist_ok=True)
        try:
            self._setstep("Step 1 of 4: Preparing installation directory…")
            self._log(f"📁  Installing to: {target_dir}")
            self._setpct(5)

            self._setstep("Step 2 of 4: Copying program files…")
            _, upd, skp, errs = self._copy_payload(target_dir, preserve_db=False)
            self._files_updated = upd; self._files_skipped = skp

            self._setstep("Step 3 of 4: Creating shortcuts & registering…")
            exe_path  = os.path.join(target_dir, "MPI_Billing_App.exe")
            icon_path = os.path.join(target_dir, "logo.ico")
            uninstaller_cmd = write_uninstaller(target_dir)
            self._log("✓  Uninstaller created.")

            register_in_windows(target_dir, uninstaller_cmd)
            self._log("✓  Registered in Windows Apps & Features.")

            if self.desktop_sc.get():
                desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
                create_windows_shortcut(exe_path,
                                        os.path.join(desktop, f"{APP_NAME}.lnk"),
                                        icon_path, APP_NAME)
                self._log("✓  Desktop shortcut created.")

            if self.start_sc.get():
                start = os.path.join(os.environ.get('APPDATA', ''),
                                     r'Microsoft\Windows\Start Menu\Programs')
                create_windows_shortcut(exe_path,
                                        os.path.join(start, f"{APP_NAME}.lnk"),
                                        icon_path, APP_NAME)
                self._log("✓  Start Menu shortcut created.")

            self._setstep("Step 4 of 4: Finalising…")
            self._log(f"✅  Installation complete. v{NEW_VERSION}")
            self._setpct(100)
            self.after(0, lambda: self._show_finish(target_dir, errs, mode="install"))
        except Exception as ex:
            self._update_error = str(ex)
            self._log(f"❌  FATAL: {ex}")
            self.after(0, self._show_error)

    # ── Shared file copy helper ────────────────────────────────────────────────

    def _copy_payload(self, target_dir, preserve_db):
        files_to_copy = []
        for root, dirs, files in os.walk(self.payload_dir):
            dirs[:] = [d for d in dirs
                       if d.lower() not in SKIP_SOURCE_FOLDERS]
            for f in files:
                src = os.path.join(root, f)
                rel = os.path.relpath(src, self.payload_dir)
                files_to_copy.append((src, rel))

        total = len(files_to_copy)
        self._log(f"ℹ  Payload: {total} files")
        upd = skp = 0; errs = []
        target_db = os.path.join(target_dir, "data", "meatshop.db")

        for idx, (src, rel) in enumerate(files_to_copy):
            pct = 15 + int(((idx + 1) / max(1, total)) * 75)
            self._setpct(pct)
            self._setfile(f"Copying: {rel}")

            if preserve_db and should_preserve(rel) and os.path.exists(target_db):
                self._log(f"  [SKIP]  {rel}  (preserved)")
                skp += 1; continue

            dest = os.path.join(target_dir, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            try:
                shutil.copy2(src, dest)
                upd += 1
                if upd <= 15 or upd % 50 == 0:
                    self._log(f"  [OK]    {rel}")
            except Exception as e:
                errs.append(rel)
                self._log(f"  [ERR]   {rel} — {e}")

        self._log(f"✅  Done: {upd} copied, {skp} preserved, {len(errs)} errors")
        return files_to_copy, upd, skp, errs

    # ── Finish Screen ──────────────────────────────────────────────────────────

    def _show_finish(self, target_dir, errors, mode):
        self._clear()
        has_err = bool(errors)
        verb = "Installation" if mode == "install" else "Update"

        if has_err:
            tk.Label(self.container,
                     text=f"✓ {verb} Complete  ({len(errors)} warning(s))",
                     font=("Segoe UI", 14, "bold"), fg=C['gold'],
                     bg=C['bg']).pack(anchor="w", pady=(0, 10))
        else:
            emoji = "🎉" if mode == "install" else "✅"
            tk.Label(self.container,
                     text=f"{emoji} {verb} Completed Successfully!",
                     font=("Segoe UI", 14, "bold"), fg=C['green'],
                     bg=C['bg']).pack(anchor="w", pady=(0, 10))

        # Summary
        sf = tk.Frame(self.container, bg=C['card'], padx=14, pady=10)
        sf.pack(fill="x", pady=(0, 12))

        rows = [
            ("✓ Version",        f"v{NEW_VERSION}"),
            ("✓ Location",       target_dir),
            ("✓ Files Copied",   str(self._files_updated)),
        ]
        if mode == "update":
            rows += [
                ("✓ Files Preserved", str(self._files_skipped)),
                ("✓ Database",        "Preserved — all bills & records intact"),
            ]
        else:
            rows += [
                ("✓ Desktop Shortcut",  "Created" if self.desktop_sc.get() else "Skipped"),
                ("✓ Start Menu",        "Created" if self.start_sc.get() else "Skipped"),
                ("✓ Windows Apps",      "Registered with Uninstaller"),
            ]
        if has_err:
            rows.append(("⚠ Errors", str(len(errors))))

        for label, value in rows:
            row = tk.Frame(sf, bg=C['card'])
            row.pack(fill="x", pady=1)
            tk.Label(row, text=label, font=("Segoe UI", 9), fg=C['muted'],
                     bg=C['card'], width=26, anchor="w").pack(side="left")
            tk.Label(row, text=value, font=("Segoe UI", 9, "bold"),
                     fg=C['gold'] if label.startswith("⚠") else C['green'],
                     bg=C['card']).pack(side="left")

        if has_err:
            tk.Label(self.container,
                     text="Some files could not be replaced (possibly in use). The app will still work correctly.",
                     font=("Segoe UI", 9), fg=C['gold'],
                     bg=C['bg'], wraplength=640, justify="left").pack(anchor="w", pady=(0, 8))

        tk.Checkbutton(
            self.container,
            text=f"Launch {APP_NAME} now",
            variable=self.launch_after,
            font=("Segoe UI", 10, "bold"),
            fg=C['green'] if mode == "install" else C['accent'],
            bg=C['bg'], selectcolor=C['card'],
            activebackground=C['bg']
        ).pack(anchor="w", pady=6)

        self._set_footer(back_visible=False, exit_visible=True,
                         action_text="🚀 Launch App",
                         action_cmd=lambda: self._finish_launch(target_dir),
                         action_color=C['green'])
        self.btn_exit.config(text="Close")

    def _show_error(self):
        self._clear()
        tk.Label(self.container, text="❌ Operation Failed",
                 font=("Segoe UI", 14, "bold"), fg=C['red'],
                 bg=C['bg']).pack(anchor="w", pady=(0, 10))
        tk.Label(self.container,
                 text=f"An unexpected error occurred:\n\n{self._update_error}\n\n"
                      "Your database and existing data are safe.\n"
                      "Try running as Administrator or close the app first.",
                 font=("Segoe UI", 10), fg=C['sub'],
                 bg=C['bg'], justify="left", wraplength=640).pack(anchor="w")
        self._set_footer(back_visible=True, action_text="⟳ Retry",
                         action_cmd=self._show_mode_select, action_color=C['accent'])

    def _finish_launch(self, target_dir):
        if self.launch_after.get():
            exe = os.path.join(target_dir, "MPI_Billing_App.exe")
            if os.path.exists(exe):
                subprocess.Popen([exe], cwd=target_dir)
            else:
                messagebox.showwarning("Not Found",
                                       f"Could not find:\n{exe}\n\nLaunch manually.")
        self.destroy()


# ─── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = UpdaterInstaller()
    app.mainloop()
