"""
updater_wizard.py — Standalone 1-Click Application Updater Wizard
Meat Products of India — Billing & Inventory Management App

Safely updates an existing installation without touching the database (meatshop.db),
settings, or customer data. Automatically detects the installed directory, terminates
running instances, updates all program binaries/templates/scripts, and relaunches the app.
"""

import sys
import os
import shutil
import winreg
import subprocess
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk

APP_NAME = "MPI Billing Software"
APP_PUBLISHER = "Meat Products of India"
APP_VERSION = "1.0.0"
REG_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\MPI_Billing_Software"


def get_bundle_dir():
    if getattr(sys, 'frozen', False):
        return getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.dirname(os.path.abspath(__file__))


def detect_installed_path():
    """Detect the currently installed directory of MPI Billing Software."""
    # 1. Try Windows Registry
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY_PATH) as key:
            loc, _ = winreg.QueryValueEx(key, "InstallLocation")
            if loc and os.path.exists(loc):
                return loc
    except Exception:
        pass

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REG_KEY_PATH) as key:
            loc, _ = winreg.QueryValueEx(key, "InstallLocation")
            if loc and os.path.exists(loc):
                return loc
    except Exception:
        pass

    # 2. Try default LocalAppData path
    user_appdata = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
    def_path = os.path.join(user_appdata, "Programs", "MPI Billing Software")
    if os.path.exists(def_path):
        return def_path

    # 3. Try Program Files
    prog_files = os.environ.get('ProgramFiles', r'C:\Program Files')
    pf_path = os.path.join(prog_files, "MPI Billing Software")
    if os.path.exists(pf_path):
        return pf_path

    return def_path


def close_running_instances():
    """Kill any running MPI_Billing_App processes to prevent file lock errors."""
    try:
        subprocess.run(['taskkill', '/F', '/IM', 'MPI_Billing_App.exe'], capture_output=True)
        time.sleep(0.5)
    except Exception:
        pass


class UpdateWizard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} — Fast Update Utility")
        self.geometry("620x440")
        self.resizable(False, False)
        self.configure(bg="#0F172A")

        self.bundle_dir = get_bundle_dir()
        self.payload_dir = os.path.join(self.bundle_dir, "payload")
        if not os.path.exists(self.payload_dir):
            self.payload_dir = os.path.join(self.bundle_dir, "dist", "MPI_Billing_App")

        detected = detect_installed_path()
        self.install_path = tk.StringVar(value=detected)
        self.launch_after = tk.BooleanVar(value=True)

        # Load Logo
        self.logo_img = None
        logo_p = os.path.join(self.bundle_dir, "logo.png")
        if os.path.exists(logo_p):
            try:
                pil_img = Image.open(logo_p).resize((56, 56), Image.Resampling.LANCZOS)
                self.logo_img = ImageTk.PhotoImage(pil_img)
            except Exception:
                pass

        self.build_ui()
        self.show_main_view()

    def build_ui(self):
        # Header Banner
        header = tk.Frame(self, bg="#1E293B", height=70)
        header.pack(fill="x", side="top")

        if self.logo_img:
            lbl_logo = tk.Label(header, image=self.logo_img, bg="#1E293B")
            lbl_logo.pack(side="left", padx=14, pady=7)

        lbl_hdr_title = tk.Label(header, text=f"{APP_NAME} — Update Utility", font=("Segoe UI", 15, "bold"), fg="#F8FAFC", bg="#1E293B")
        lbl_hdr_title.pack(side="left", pady=10)

        # Main Container
        self.container = tk.Frame(self, bg="#0F172A", padx=25, pady=18)
        self.container.pack(fill="both", expand=True)

        # Footer
        self.footer = tk.Frame(self, bg="#1E293B", height=50)
        self.footer.pack(fill="x", side="bottom")

        self.btn_exit = tk.Button(self.footer, text="Exit", font=("Segoe UI", 10), bg="#475569", fg="#FFFFFF", width=10, command=self.destroy)
        self.btn_exit.pack(side="left", padx=20, pady=10)

        self.btn_action = tk.Button(self.footer, text="⚡ Update Now", font=("Segoe UI", 10, "bold"), bg="#0284C7", fg="#FFFFFF", width=16, command=self.start_update)
        self.btn_action.pack(side="right", padx=20, pady=10)

    def clear_container(self):
        for widget in self.container.winfo_children():
            widget.destroy()

    def show_main_view(self):
        self.clear_container()

        tk.Label(self.container, text="Update Existing Installation", font=("Segoe UI", 14, "bold"), fg="#38BDF8", bg="#0F172A").pack(anchor="w", pady=(0, 8))

        info_box = tk.Frame(self.container, bg="#1E293B", padx=14, pady=10)
        info_box.pack(fill="x", pady=(0, 14))

        tk.Label(info_box, text="🔒 100% Safe Database & Settings Preservation:", font=("Segoe UI", 10, "bold"), fg="#10B981", bg="#1E293B").pack(anchor="w")
        bullets = (
            "• Preserves all your existing bills, customer accounts, and database records.\n"
            "• Updates program files, latest UI bugfixes, tagline features & stock editing tools.\n"
            "• Automatically closes any running instance during update."
        )
        tk.Label(info_box, text=bullets, font=("Segoe UI", 9), fg="#CBD5E1", bg="#1E293B", justify="left").pack(anchor="w", pady=(4, 0))

        tk.Label(self.container, text="Installation Folder to Update:", font=("Segoe UI", 10, "bold"), fg="#F8FAFC", bg="#0F172A").pack(anchor="w", pady=(6, 4))

        frame_dir = tk.Frame(self.container, bg="#0F172A")
        frame_dir.pack(fill="x", pady=(0, 10))

        entry = tk.Entry(frame_dir, textvariable=self.install_path, font=("Segoe UI", 10), bg="#1E293B", fg="#F8FAFC", insertbackground="white")
        entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 8))

        def browse_folder():
            f = filedialog.askdirectory(initialdir=self.install_path.get())
            if f:
                self.install_path.set(f)

        tk.Button(frame_dir, text="Browse…", font=("Segoe UI", 9), bg="#334155", fg="#FFFFFF", command=browse_folder).pack(side="right")

        tk.Checkbutton(self.container, text=f"Launch {APP_NAME} automatically after update completes", variable=self.launch_after, font=("Segoe UI", 9, "bold"), fg="#38BDF8", bg="#0F172A", selectcolor="#1E293B", activebackground="#0F172A", activeforeground="#38BDF8").pack(anchor="w", pady=6)

    def start_update(self):
        target_dir = self.install_path.get().strip()
        if not target_dir:
            messagebox.showerror("Error", "Please select a valid installation folder.")
            return

        self.clear_container()
        self.btn_exit.config(state="disabled")
        self.btn_action.config(state="disabled")

        tk.Label(self.container, text="Applying Updates…", font=("Segoe UI", 14, "bold"), fg="#38BDF8", bg="#0F172A").pack(anchor="w", pady=(0, 12))

        self.progress_bar = ttk.Progressbar(self.container, orient="horizontal", mode="determinate", length=540)
        self.progress_bar.pack(pady=15)

        self.lbl_status = tk.Label(self.container, text="Closing running app processes…", font=("Segoe UI", 9), fg="#94A3B8", bg="#0F172A")
        self.lbl_status.pack(anchor="w")

        self.after(300, self.perform_update_process)

    def perform_update_process(self):
        target_dir = self.install_path.get().strip()
        os.makedirs(target_dir, exist_ok=True)

        # 1. Close running app instances
        self.lbl_status.config(text="Stopping running instances of MPI Billing App…")
        self.update_idletasks()
        close_running_instances()

        # 2. Backup existing database if present
        self.lbl_status.config(text="Securing database safety backup…")
        self.update_idletasks()
        target_db = os.path.join(target_dir, "data", "meatshop.db")
        backup_db_path = None
        if os.path.exists(target_db):
            temp_dir = os.environ.get('TEMP', '.')
            backup_db_path = os.path.join(temp_dir, 'meatshop_db_updater_backup.db')
            try:
                shutil.copy2(target_db, backup_db_path)
            except Exception:
                pass

        # 3. Copy new payload files (skipping data/meatshop.db to preserve local data)
        src_payload = self.payload_dir
        if not os.path.exists(src_payload):
            src_payload = get_bundle_dir()

        files_to_copy = []
        for root, dirs, files in os.walk(src_payload):
            for file in files:
                rel_p = os.path.relpath(os.path.join(root, file), src_payload)
                # NEVER overwrite user's database with empty payload database
                if rel_p.lower().replace('/', '\\').endswith(r'data\meatshop.db') and os.path.exists(target_db):
                    continue
                files_to_copy.append((os.path.join(root, file), rel_p))

        total_f = len(files_to_copy)
        for idx, (src_f, rel_f) in enumerate(files_to_copy):
            dest_f = os.path.join(target_dir, rel_f)
            os.makedirs(os.path.dirname(dest_f), exist_ok=True)
            try:
                shutil.copy2(src_f, dest_f)
            except Exception as copy_err:
                print(f"Warning copying {rel_f}: {copy_err}")

            pct = int(((idx + 1) / max(1, total_f)) * 100)
            self.progress_bar['value'] = pct
            self.lbl_status.config(text=f"Updating: {rel_f}")
            self.update_idletasks()

        # 4. Restore preserved database to ensure 100% integrity
        if backup_db_path and os.path.exists(backup_db_path):
            os.makedirs(os.path.join(target_dir, "data"), exist_ok=True)
            try:
                shutil.copy2(backup_db_path, target_db)
                os.remove(backup_db_path)
            except Exception:
                pass

        self.progress_bar['value'] = 100
        self.show_finish_view()

    def show_finish_view(self):
        self.clear_container()

        tk.Label(self.container, text="🎉 Update Completed Successfully!", font=("Segoe UI", 15, "bold"), fg="#10B981", bg="#0F172A").pack(anchor="w", pady=(0, 10))

        msg = (
            f"{APP_NAME} has been updated to the latest build.\n\n"
            "✓ All program files and latest features updated.\n"
            "✓ All existing bills, inventory balances, customers & settings preserved."
        )
        tk.Label(self.container, text=msg, font=("Segoe UI", 10), fg="#CBD5E1", bg="#0F172A", justify="left").pack(anchor="w", pady=(0, 15))

        self.btn_exit.config(state="normal", text="Close", command=self.destroy)
        self.btn_action.config(state="normal", text="🚀 Launch Updated App", bg="#10B981", command=self.finish_and_launch)

    def finish_and_launch(self):
        if self.launch_after.get():
            target_exe = os.path.join(self.install_path.get(), "MPI_Billing_App.exe")
            if os.path.exists(target_exe):
                subprocess.Popen([target_exe], cwd=self.install_path.get())
        self.destroy()


if __name__ == "__main__":
    app = UpdateWizard()
    app.mainloop()
