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
import webview

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
        self._window.minimize()

    def toggle_maximize(self):
        if self._maximized:
            self._window.restore()
            self._maximized = False
        else:
            self._window.maximize()
            self._maximized = True

    def close_window(self):
        self._window.destroy()


# ─── Main Entry Point ────────────────────────────────────────────────────────
if __name__ == '__main__':
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

    print("[3/3] Launching desktop window...")

    # Fetch shop name from settings to use as window title
    shop_title = "Meat Products of India"
    try:
        import urllib.request, json
        with urllib.request.urlopen(f"{URL}/api/settings", timeout=3) as r:
            data = json.loads(r.read())
            shop_title = data.get('data', {}).get('shop_name', shop_title)
    except Exception:
        pass

    window = webview.create_window(
        title            = f"{shop_title} — Billing & Inventory",
        url              = URL,
        width            = 1400,
        height           = 860,
        min_size         = (900, 600),
        resizable        = True,
        frameless        = True,    # ← Remove native OS title bar; use our custom one
        easy_drag        = False,   # ← We handle drag via CSS -webkit-app-region:drag
        background_color = '#0f0f0f',
    )

    api = DesktopApi(window)
    window.expose(api.minimize_window, api.toggle_maximize, api.close_window)

    def on_loaded():
        """Maximize the window once the page finishes loading."""
        try:
            window.maximize()
        except Exception:
            pass

    # Set MPI_DEBUG=1 in the environment only for internal development/testing, never in the customer build.
    DEBUG_MODE = os.environ.get('MPI_DEBUG', '0') == '1'
    webview.start(on_loaded, debug=DEBUG_MODE)
    print("[OK] Desktop window closed. Goodbye!")
