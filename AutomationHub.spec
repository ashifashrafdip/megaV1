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
    (str(project_dir / 'device_browser' / 'profiles.json'), 'device_browser'),
    (str(project_dir / 'selfie.iife.js'), '.'),
    (str(project_dir / 'video.iife.js'), '.'),
]

hidden_imports = [
    'PyQt5',
    'PyQt5.QtCore',
    'PyQt5.QtGui',
    'PyQt5.QtWidgets',
    'PyQt5.QtNetwork',
    'PyQt5.sip',
    'playwright',
    'playwright.sync_api',
    'requests',
    'urllib3',
    'imageio_ffmpeg',
    'wmi',
    'jwt',
    'payload_defaults',
    'adspower_browser',
    'morelogin_browser',
    'multilogin_browser',
    'camera_feed_service',
    'video_step_automation',
    'wizard_automation',
    'auth_client',
    'auth_config',
    'auth_session',
    'device_fingerprint',
    'protection_stub',
    'playwright_browser',
    'playwright_profile_manager',
    'temp_file_server',
    'theme',
    'qt_logging',
    'login_dialog',
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
