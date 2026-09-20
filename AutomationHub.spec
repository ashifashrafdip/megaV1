# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import sys
import playwright

project_dir = Path(SPECPATH).resolve()
playwright_path = Path(playwright.__file__).resolve().parent
driver_dir = playwright_path / 'driver'

datas = [
    (str(driver_dir), 'playwright/driver'),
    (str(project_dir / 'config.json'), '.'),
    (str(project_dir / 'ffmpeg.exe'), '.'),
    (str(project_dir / 'Source file'), 'Source file'),
]

hidden_imports = [
    'PyQt5',
    'PyQt5.QtCore',
    'PyQt5.QtGui',
    'PyQt5.QtWidgets',
    'playwright',
    'playwright.sync_api',
    'requests',
    'urllib3',
    'imageio_ffmpeg',
    'wmi',
]

a = Analysis(
    [str(project_dir / 'main.py')],
    pathex=[str(project_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AutomationHub',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
