@echo off
echo ============================================================
echo   Building MPI Billing Software — Fresh Setup Installer
echo   Meat Products of India
echo ============================================================
echo.
echo   This script builds:
echo     1. App Program Payload : dist\MPI_Billing_App\
echo     2. Standalone Installer: dist\MPI_Billing_Software_Installer.exe
echo ============================================================
echo.

echo [1/4] Installing / upgrading dependencies...
python -m pip install -r requirements.txt --quiet
python -m pip install pyinstaller pywebview openpyxl flask flask-cors werkzeug pillow --quiet
if errorlevel 1 (
    echo [ERROR] Dependency installation failed.
    pause
    exit /b 1
)

echo.
echo [2/4] Converting logo.png to Windows icon logo.ico...
python -c "from PIL import Image; Image.open('logo.png').save('logo.ico', format='ICO', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"

echo.
echo [3/4] Compiling App Payload (dist\MPI_Billing_App\)...
echo        ^> This includes ALL latest updates and fixes
python -m PyInstaller --noconfirm MPI_Billing_App.spec
if errorlevel 1 (
    echo [ERROR] App payload build failed.
    pause
    exit /b 1
)

echo.
echo [4/4] Compiling Standalone Setup Wizard (dist\MPI_Billing_Software_Installer.exe)...
python -m PyInstaller --noconfirm MPI_Billing_Software_Installer.spec
if errorlevel 1 (
    echo [ERROR] Installer build failed.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   BUILD COMPLETE!
echo.
echo   Fresh Setup Installer : dist\MPI_Billing_Software_Installer.exe
echo   App Payload Directory : dist\MPI_Billing_App\
echo.
echo   Distribute "dist\MPI_Billing_Software_Installer.exe" to
echo   install the application fresh on any Windows machine.
echo ============================================================
pause
