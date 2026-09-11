@echo off
echo ============================================================
echo   Building MPI Billing Software — Updater Package
echo   Meat Products of India
echo ============================================================
echo.
echo   This script does everything in one go:
echo     1. Recompiles the app from latest source code
echo     2. Builds the small updater wizard exe
echo     3. Assembles the distribution package
echo.
echo   OUTPUT:
echo     dist\MPI_Update_Package\
echo       MPI_Billing_App_Updater.exe   (~5-10 MB wizard)
echo       MPI_Billing_App\              (~80 MB app files)
echo       README_Update.txt
echo ============================================================
echo.

echo [1/5] Installing / upgrading dependencies...
python -m pip install -r requirements.txt --quiet
python -m pip install pyinstaller pywebview openpyxl flask flask-cors werkzeug pillow --quiet
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo [2/5] Converting logo.png to Windows icon logo.ico...
python -c "from PIL import Image; Image.open('logo.png').save('logo.ico', format='ICO', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"

echo.
echo [3/5] Compiling app from latest source code (dist\MPI_Billing_App\)...
echo        ^> This picks up ALL your latest changes (billing.js, app.py, templates, etc.)
python -m PyInstaller --noconfirm MPI_Billing_App.spec
if errorlevel 1 (
    echo [ERROR] App build failed. Check output above.
    pause
    exit /b 1
)
echo        Done. New build in dist\MPI_Billing_App\

echo.
echo [4/5] Building small Updater wizard executable...
python -m PyInstaller --noconfirm MPI_Billing_App_Updater.spec
if errorlevel 1 (
    echo [ERROR] Updater exe build failed. Check output above.
    pause
    exit /b 1
)

echo.
echo [5/5] Assembling update distribution package...

set OUT=dist\MPI_Update_Package
if exist "%OUT%" rmdir /s /q "%OUT%"
mkdir "%OUT%"

copy /y "dist\MPI_Billing_App_Updater.exe" "%OUT%\MPI_Billing_App_Updater.exe" >nul
echo   Copied: MPI_Billing_App_Updater.exe

xcopy /e /i /q "dist\MPI_Billing_App" "%OUT%\MPI_Billing_App" >nul
echo   Copied: MPI_Billing_App\ (app payload)

(
echo MPI Billing Software — Update Package
echo ======================================
echo.
echo HOW TO UPDATE:
echo   1. Run:  MPI_Billing_App_Updater.exe
echo   2. Select "Update Existing Installation"
echo   3. Confirm the detected installation folder
echo   4. Click "Update Now"
echo.
echo HOW TO INSTALL ON A NEW MACHINE:
echo   1. Run:  MPI_Billing_App_Updater.exe
echo   2. Select "Fresh Install (New Machine)"
echo   3. Choose your destination folder
echo   4. Click "Install Now"
echo.
echo IMPORTANT:
echo   - Do NOT move or delete the MPI_Billing_App\ folder.
echo   - MPI_Billing_App_Updater.exe and MPI_Billing_App\ must stay together.
echo   - Your database, bills, customers and backups are NEVER overwritten.
) > "%OUT%\README_Update.txt"
echo   Written: README_Update.txt

echo.
echo ============================================================
echo   BUILD COMPLETE!
echo.
echo   Your update package is ready at:
echo     dist\MPI_Update_Package\
echo.
echo   Share the entire MPI_Update_Package\ folder (or zip it)
echo   with your customers to deploy the latest update.
echo ============================================================
pause
