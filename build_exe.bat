@echo off
echo ============================================================
echo   Building Standalone Windows Executable (.exe)
echo   Meat Products of India — Billing & Inventory App
echo ============================================================
echo.

echo [1/4] Installing dependencies...
python -m pip install -r requirements.txt
python -m pip install pyinstaller pywebview openpyxl flask flask-cors werkzeug pillow

echo.
echo [2/4] Converting logo.png to Windows icon logo.ico...
python -c "from PIL import Image; Image.open('logo.png').save('logo.ico', format='ICO', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"

echo.
echo [3/4] Building Program Payload Directory...
python -m PyInstaller --noconfirm MPI_Billing_App.spec

echo.
echo [4/4] Compiling Step-by-Step Graphical Windows Setup Installer...
python -m PyInstaller --noconfirm MPI_Billing_Software_Installer.spec

echo.
echo ============================================================
echo   BUILD COMPLETE!
echo   Step-by-step Installer: dist\MPI_Billing_Software_Installer.exe
echo ============================================================
pause
