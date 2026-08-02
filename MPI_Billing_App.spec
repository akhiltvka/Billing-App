# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['run_desktop.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('static', 'static'),
        ('templates', 'templates'),
        ('logo.png', '.'),
        ('logo.ico', '.'),
    ],
    hiddenimports=[
        'app',
        'database',
        'license_manager',
        'license_sync',
        'backup_scheduler',
        'cloud_backup',
        'jinja2.ext',
        'webview',
        'openpyxl',
        'werkzeug.security',
        'werkzeug.serving',
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
    [],
    exclude_binaries=True,
    name='MPI_Billing_App',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='logo.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MPI_Billing_App',
)
