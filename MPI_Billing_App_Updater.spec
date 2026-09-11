# -*- mode: python ; coding: utf-8 -*-
#
# MPI_Billing_App_Updater.spec
#
# Builds a SMALL updater executable — the app payload (MPI_Billing_App\)
# is NOT bundled inside the exe. Instead, place the exe alongside the
# MPI_Billing_App\ folder when distributing.
#
# Distribution package layout:
#   MPI_Update_v2.0.0\
#     MPI_Billing_App_Updater.exe   <-- this output (~5-10 MB)
#     MPI_Billing_App\              <-- copied from dist\MPI_Billing_App\
#     logo.png
#
# Use build_updater.bat to build and package this automatically.

block_cipher = None

a = Analysis(
    ['updater_wizard.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # Only bundle the logo assets — NOT the full app payload
        ('logo.png', '.'),
        ('logo.ico', '.'),
    ],
    hiddenimports=[
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'winreg',
        'tkinter',
        'tkinter.ttk',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='MPI_Billing_App_Updater',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='logo.ico',
)
