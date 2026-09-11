"""
run_desktop.py — Desktop Application Launcher
Meat Products of India — Billing & Inventory Management App

Starts the Flask server in a background thread, then opens the app
in a dedicated pywebview window (Edge WebView2) — frameless, maximized,
with our own custom in-page Windows 11-style title bar.
"""

import threading
import time
import sys
import os
import webbrowser

# Safely attempt webview import so legacy OS without compatible CLR/webview doesn't crash on startup
try:
    import webview
    HAS_WEBVIEW = True
except Exception as e:
    webview = None
    HAS_WEBVIEW = False
    print(f"[Desktop App Notice] Native pywebview import failed ({e}). Defaulting to browser mode.")

# Set AppUserModelID so Windows Taskbar displays official logo.ico / logo.png icon
try:
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("MeatProductsOfIndia.BillingApp.1.0")
except Exception:
    pass

# ─── Load Environment Variables ─────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ─── Start Flask Server in Background Thread ────────────────────────────────
def start_flask():
    """Starts Flask on 127.0.0.1:5173 (desktop-only port to avoid conflicts)."""
    os.environ.setdefault('FLASK_DESKTOP', '1')
    try:
        from database import init_db
        init_db()
    except Exception as e:
        print(f"[Desktop DB Init Error] {e}")
    try:
        from sync_worker import start_sync_scheduler
        start_sync_scheduler()
    except Exception as e:
        print(f"[Desktop Sync Init Error] {e}")
    from app import app
    app.run(host='127.0.0.1', port=5173, debug=False, use_reloader=False)


def wait_for_server(url, timeout=15):
    """Polls until Flask is ready to serve requests."""
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(0.25)
    return False


# ─── pywebview Window Controls API ──────────────────────────────────────────
class DesktopApi:
    """
    JavaScript ↔ Python bridge for window control actions.
    Called by the frontend via window.pywebview.api.<method>().
    """

    def __init__(self, window):
        self._window = window
        self._maximized = True  # start maximized

    def minimize_window(self):
        try:
            self._window.minimize()
        except Exception:
            pass

    def toggle_maximize(self):
        try:
            if self._maximized:
                self._window.restore()
                self._maximized = False
            else:
                self._window.maximize()
                self._maximized = True
        except Exception:
            pass

    def close_window(self):
        try:
            self._window.destroy()
        except Exception:
            pass

    def select_folder(self):
        """Opens native OS folder picker dialog and returns selected directory path."""
        try:
            res = self._window.create_file_dialog(webview.FOLDER_DIALOG)
            if res and len(res) > 0:
                return res[0]
        except Exception as e:
            print(f"[Desktop Folder Picker Error] {e}")
        return None

    def save_file(self, base64_data, default_filename='export.xlsx'):
        """Opens native OS save file dialog and saves base64 data to selected path."""
        try:
            import base64
            file_types = ('Excel Files (*.xlsx)', 'All Files (*.*)')
            res = self._window.create_file_dialog(webview.SAVE_FILENAME_DIALOG, save_filename=default_filename, file_types=file_types)
            if res:
                save_path = res if isinstance(res, str) else res[0]
                if save_path:
                    data = base64.b64decode(base64_data)
                    with open(save_path, 'wb') as f:
                        f.write(data)
                    return save_path
        except Exception as e:
            print(f"[Desktop Save File Error] {e}")
        return None


# ─── Main Entry Point ────────────────────────────────────────────────────────
if __name__ == '__main__':
    from database import get_database_url, get_external_config_dir
    db_url = get_database_url()
    if not db_url:
        config_dir = get_external_config_dir()
        err_msg = (
            "Supabase cloud sync connection string (DATABASE_URL) is not configured!\n\n"
            "This application requires an external DATABASE_URL to support cloud synchronization.\n\n"
            "Please run the Setup Wizard (installer_setup_wizard.py) or set the DATABASE_URL environment "
            "variable before starting the application.\n\n"
            f"Expected configuration file:\n{os.path.join(config_dir, 'database_url.txt')}"
        )
        print("\n" + "=" * 70, file=sys.stderr)
        print(f"[CRITICAL CONFIG ERROR]\n{err_msg}", file=sys.stderr)
        print("=" * 70 + "\n", file=sys.stderr)
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("MPI Billing Software — Setup Required", err_msg)
            root.destroy()
        except Exception:
            pass
        sys.exit(1)

    PORT = 5173
    URL  = f'http://127.0.0.1:{PORT}'

    print("=" * 60)
    print("  Meat Products of India — Desktop App")
    print("=" * 60)
    print("[1/3] Starting Flask server...")

    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()

    print("[2/3] Waiting for server to be ready...")
    if not wait_for_server(URL):
        print("[ERROR] Flask server did not start in time. Exiting.")
        sys.exit(1)

    print("[3/3] Launching application interface...")

    # Fetch shop name from settings to use as window title
    shop_title = "Meat Products of India"
    try:
        import urllib.request, json
        with urllib.request.urlopen(f"{URL}/api/settings", timeout=3) as r:
            data = json.loads(r.read())
            shop_title = data.get('data', {}).get('shop_name', shop_title)
    except Exception:
        pass

    use_native_window = HAS_WEBVIEW
    if use_native_window:
        try:
            window = webview.create_window(
                title            = f"{shop_title} — Billing & Inventory",
                url              = URL,
                width            = 1400,
                height           = 860,
                min_size         = (900, 600),
                resizable        = True,
                frameless        = True,    # Remove native OS title bar; use custom title bar
                easy_drag        = False,   # Handle drag via CSS -webkit-app-region:drag
                background_color = '#0f0f0f',
            )

            api = DesktopApi(window)
            window.expose(api.minimize_window, api.toggle_maximize, api.close_window, api.select_folder, api.save_file)

            def on_loaded():
                try:
                    window.maximize()
                except Exception:
                    pass

            DEBUG_MODE = os.environ.get('MPI_DEBUG', '0') == '1'
            webview.start(on_loaded, debug=DEBUG_MODE)
        except Exception as e:
            print(f"[Desktop App Notice] Native pywebview window failed ({e}). Falling back to system browser mode...")
            use_native_window = False

    if not use_native_window:
        print(f"[Desktop App] Opening application in default system browser: {URL}")
        webbrowser.open(URL)
        try:
            while True:
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            pass

    print("[OK] Desktop session ended. Goodbye!")
