@echo off
echo ============================================================
echo   Building Windows 7 (32-bit x86) Standalone Installer (.exe)
echo   Meat Products of India — Billing & Inventory App
echo ============================================================
echo.

:: Detect Python environment
set PY_CMD=python
py -3.8-32 --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set PY_CMD=py -3.8-32
    echo [Environment] Found Python 3.8 32-bit via PyLauncher.
) else (
    echo [Environment] Using default python command...
)

echo.
echo [1/4] Installing 32-bit dependencies...
%PY_CMD% -m pip install -r requirements.txt
%PY_CMD% -m pip install pyinstaller pywebview openpyxl flask flask-cors werkzeug pillow

echo.
echo [2/4] Generating Windows icon logo.ico...
%PY_CMD% -c "from PIL import Image; Image.open('logo.png').save('logo.ico', format='ICO', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"

echo.
echo.
echo [3/4] Building Windows 7 32-bit Program Payload Directory...
tools\py38_x86\tools\python.exe -m PyInstaller --noconfirm MPI_Billing_App_Win7_32bit.spec

echo.
echo [4/4] Compiling Windows 7 32-bit Native Setup Installer (.exe)...
powershell -Command "if (Test-Path 'payload_win7_x86.zip') { Remove-Item -Force 'payload_win7_x86.zip' }; Compress-Archive -Path 'dist\MPI_Billing_App_Win7_32bit\*' -DestinationPath 'payload_win7_x86.zip' -CompressionLevel Optimal"
C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe /target:winexe /platform:x86 /win32icon:logo.ico /r:System.IO.Compression.dll /r:System.IO.Compression.FileSystem.dll /resource:payload_win7_x86.zip,payload.zip /out:dist\MPI_Billing_Software_Installer_Win7_32bit.exe SetupWizardWin7.cs

echo.
echo ============================================================
echo   BUILD COMPLETE!
echo   Windows 7 32-bit Native Installer: 
echo   dist\MPI_Billing_Software_Installer_Win7_32bit.exe
echo ============================================================
pause
