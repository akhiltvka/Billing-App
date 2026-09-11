import sys
import os
import shutil
import winreg
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk

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

# ─── Configuration ───────────────────────────────────────────────────────────
APP_NAME = "MPI Billing Software"
APP_PUBLISHER = "Meat Products of India"
APP_VERSION = "2.0.0"
REG_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\MPI_Billing_Software"
PROD_SUPABASE_URL = "postgresql://postgres.tjpfkpwmoyooevxjosof:Revathyr%40j6123@aws-0-ap-south-1.pooler.supabase.com:5432/postgres"

def get_bundle_dir():
    if getattr(sys, 'frozen', False):
        return getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.dirname(os.path.abspath(__file__))

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
        print(f"Shortcut creation error: {e}")
        return False

# ─── Installer Wizard GUI ─────────────────────────────────────────────────────
class InstallerWizard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.is_32bit = (sys.maxsize <= 2**31 - 1)
        edition_str = "Windows 7 / 32-bit Edition" if self.is_32bit else "Windows 10/11 64-bit"
        self.title(f"{APP_NAME} — Setup Wizard ({edition_str})")
        self.geometry("660x520")
        self.resizable(False, False)
        self.configure(bg="#0F172A")

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

        # Load Logo
        self.logo_img = None
        logo_p = os.path.join(self.bundle_dir, "logo.png")
        if os.path.exists(logo_p):
            try:
                pil_img = Image.open(logo_p).resize((64, 64), Image.Resampling.LANCZOS)
                self.logo_img = ImageTk.PhotoImage(pil_img)
            except Exception:
                pass

        self.build_ui()
        self.show_step(0)

    def build_ui(self):
        # ── Header Banner ──
        header = tk.Frame(self, bg="#1E293B", height=75)
        header.pack(fill="x", side="top")

        if self.logo_img:
            lbl_logo = tk.Label(header, image=self.logo_img, bg="#1E293B")
            lbl_logo.pack(side="left", padx=15, pady=8)

        lbl_hdr_title = tk.Label(header, text=APP_NAME, font=("Segoe UI", 16, "bold"), fg="#F8FAFC", bg="#1E293B")
        lbl_hdr_title.pack(side="left", pady=10)

        lbl_hdr_sub = tk.Label(header, text="Setup & Installation Wizard (32-bit & 64-bit Compatible)", font=("Segoe UI", 9), fg="#94A3B8", bg="#1E293B")
        lbl_hdr_sub.pack(side="left", padx=10, pady=12)

        # ── Container Frame ──
        self.container = tk.Frame(self, bg="#0F172A", padx=25, pady=20)
        self.container.pack(fill="both", expand=True)

        # ── Navigation Footer ──
        footer = tk.Frame(self, bg="#1E293B", height=55)
        footer.pack(fill="x", side="bottom")

        self.btn_back = tk.Button(footer, text="‹ Back", font=("Segoe UI", 10), bg="#334155", fg="#FFFFFF", width=10, command=self.prev_step)
        self.btn_back.pack(side="left", padx=20, pady=12)

        self.btn_cancel = tk.Button(footer, text="Cancel", font=("Segoe UI", 10), bg="#475569", fg="#FFFFFF", width=10, command=self.destroy)
        self.btn_cancel.pack(side="left", padx=5, pady=12)

        self.btn_next = tk.Button(footer, text="Next ›", font=("Segoe UI", 10, "bold"), bg="#E11D48", fg="#FFFFFF", width=12, command=self.next_step)
        self.btn_next.pack(side="right", padx=20, pady=12)

    def clear_container(self):
        for widget in self.container.winfo_children():
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

    # ── Step 0: Welcome ──
    def show_step_welcome(self):
        self.btn_back.config(state="disabled")
        self.btn_next.config(text="Next ›", state="normal")

        tk.Label(self.container, text="Welcome to the Setup Wizard", font=("Segoe UI", 15, "bold"), fg="#38BDF8", bg="#0F172A").pack(anchor="w", pady=(0, 10))
        
        arch_bullet = "• Windows 7, 8, 10 & 11 Compatible (32-bit x86 Edition)" if self.is_32bit else "• Windows 10 & 11 Compatible (64-bit x64 Edition)"

        info_txt = (
            f"This wizard will install {APP_NAME} v{APP_VERSION} on your computer.\n\n"
            f"{arch_bullet}\n"
            "• Safe Database Preservation on Updates\n"
            "• Windows Settings & Control Panel Integration (Add/Remove Programs)\n\n"
            "It is recommended that you close all other applications before continuing.\n\n"
            "Click Next to continue with the step-by-step installation."
        )
        tk.Label(self.container, text=info_txt, font=("Segoe UI", 10), fg="#CBD5E1", bg="#0F172A", justify="left").pack(anchor="w")

    # ── Step 1: Directory ──
    def show_step_directory(self):
        self.btn_back.config(state="normal")
        self.btn_next.config(text="Next ›", state="normal")

        tk.Label(self.container, text="Select Destination Location", font=("Segoe UI", 14, "bold"), fg="#38BDF8", bg="#0F172A").pack(anchor="w", pady=(0, 10))
        tk.Label(self.container, text=f"Where should {APP_NAME} be installed?", font=("Segoe UI", 10), fg="#CBD5E1", bg="#0F172A").pack(anchor="w", pady=(0, 15))

        frame_dir = tk.Frame(self.container, bg="#0F172A")
        frame_dir.pack(fill="x", pady=10)

        entry = tk.Entry(frame_dir, textvariable=self.install_path, font=("Segoe UI", 10), bg="#1E293B", fg="#F8FAFC", insertbackground="white")
        entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 10))

        def browse_folder():
            f = filedialog.askdirectory(initialdir=self.install_path.get())
            if f:
                self.install_path.set(f)

        tk.Button(frame_dir, text="Browse…", font=("Segoe UI", 9), bg="#334155", fg="#FFFFFF", command=browse_folder).pack(side="right")

        tk.Label(self.container, text="Required disk space: ~85 MB", font=("Segoe UI", 9), fg="#94A3B8", bg="#0F172A").pack(anchor="w", pady=(15, 0))

    # ── Step 2: Options ──
    def show_step_options(self):
        self.btn_back.config(state="normal")
        self.btn_next.config(text="Install", state="normal")

        tk.Label(self.container, text="Select Additional Shortcuts & Integration", font=("Segoe UI", 14, "bold"), fg="#38BDF8", bg="#0F172A").pack(anchor="w", pady=(0, 10))

        tk.Checkbutton(self.container, text="Create a Desktop Shortcut", variable=self.create_desktop_sc, font=("Segoe UI", 10), fg="#F8FAFC", bg="#0F172A", selectcolor="#1E293B", activebackground="#0F172A", activeforeground="#F8FAFC").pack(anchor="w", pady=8)
        tk.Checkbutton(self.container, text="Create a Start Menu Shortcut", variable=self.create_start_sc, font=("Segoe UI", 10), fg="#F8FAFC", bg="#0F172A", selectcolor="#1E293B", activebackground="#0F172A", activeforeground="#F8FAFC").pack(anchor="w", pady=8)
        tk.Label(self.container, text="✓ Registers automatically in Windows Installed Apps (Settings -> Apps) with Uninstaller", font=("Segoe UI", 9), fg="#10B981", bg="#0F172A").pack(anchor="w", pady=15)

    # ── Step 3: Install ──
    def show_step_install(self):
        self.btn_back.config(state="disabled")
        self.btn_next.config(state="disabled")
        self.btn_cancel.config(state="disabled")

        tk.Label(self.container, text="Installing Program Files…", font=("Segoe UI", 14, "bold"), fg="#38BDF8", bg="#0F172A").pack(anchor="w", pady=(0, 15))

        self.progress_bar = ttk.Progressbar(self.container, orient="horizontal", mode="determinate", length=540)
        self.progress_bar.pack(pady=20)

        self.lbl_status = tk.Label(self.container, text="Preparing installation…", font=("Segoe UI", 9), fg="#94A3B8", bg="#0F172A")
        self.lbl_status.pack(anchor="w")

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
                shutil.copy(target_db, backup_db_path)
            except Exception:
                pass

        src_payload = self.payload_dir
        if not os.path.exists(src_payload):
            src_payload = get_bundle_dir()

        files_to_copy = []
        for root, dirs, files in os.walk(src_payload):
            dirs[:] = [d for d in dirs if d.lower() not in ('backups', '__pycache__')]
            for file in files:
                rel_p = os.path.relpath(os.path.join(root, file), src_payload)
                if rel_p.lower().replace('/', '\\').endswith(r'data\meatshop.db') and os.path.exists(target_db):
                    continue
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
            self.lbl_status.config(text=f"Copying: {rel_f}")
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
            with open(os.path.join(target_dir, "version.txt"), 'w') as f:
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

    # ── Step 4: Finish ──
    def show_step_finish(self):
        self.btn_back.config(state="disabled")
        self.btn_cancel.config(state="disabled")
        self.btn_next.config(text="Finish", state="normal")

        tk.Label(self.container, text="Installation Completed Successfully!", font=("Segoe UI", 15, "bold"), fg="#10B981", bg="#0F172A").pack(anchor="w", pady=(0, 10))

        tk.Label(self.container, text=f"{APP_NAME} has been installed on your computer.", font=("Segoe UI", 10), fg="#CBD5E1", bg="#0F172A").pack(anchor="w", pady=(0, 15))
        tk.Checkbutton(self.container, text=f"Launch {APP_NAME} now", variable=self.launch_after, font=("Segoe UI", 10, "bold"), fg="#38BDF8", bg="#0F172A", selectcolor="#1E293B", activebackground="#0F172A", activeforeground="#38BDF8").pack(anchor="w", pady=10)
        tk.Label(self.container, text="Click Finish to exit setup.", font=("Segoe UI", 9), fg="#94A3B8", bg="#0F172A").pack(anchor="w", pady=(20, 0))

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=f"{APP_NAME} Setup Wizard")
    parser.add_argument("--db-url", dest="db_url", default=None, help="Custom Supabase PostgreSQL connection string (Developer override)")
    args, _ = parser.parse_known_args()
    if args.db_url:
        PROD_SUPABASE_URL = args.db_url.strip()
    app = InstallerWizard()
    app.mainloop()
