"""PyArmor obfuscation and protection build script for Automation Hub.

This script obfuscates core proprietary application modules into encrypted bytecode
preventing reverse engineering, tampering, and unauthorized offline execution.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT_DIR / "dist_protected"

CORE_MODULES = [
    "auth_client.py",
    "auth_config.py",
    "auth_session.py",
    "device_fingerprint.py",
    "protection_stub.py",
    "stealth_bridge.py",
    "wizard_automation.py",
    "video_step_automation.py",
]

ASSETS_TO_COPY = [
    "main.py",
    "config.json",
    "selfie.iife.js",
    "video.iife.js",
    "theme.py",
    "qt_logging.py",
    "app_config.py",
    "temp_file_server.py",
    "camera_feed_service.py",
    "adspower_browser.py",
    "multilogin_browser.py",
    "playwright_browser.py",
    "playwright_profile_manager.py",
    "login_dialog.py",
    "device_browser",
]



def clean_output_dir(target_dir: Path) -> None:
    if target_dir.exists():
        print(f"[*] Cleaning existing build directory: {target_dir}")
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)


def run_pyarmor_obfuscation(target_dir: Path) -> bool:
    print(f"[*] Starting PyArmor obfuscation into: {target_dir}")
    clean_output_dir(target_dir)

    # Build pyarmor command
    # Uses pyarmor.cli gen to produce protected files
    cmd = [
        sys.executable,
        "-m",
        "pyarmor.cli",
        "gen",
        "-O",
        str(target_dir),
    ]

    for mod in CORE_MODULES:
        p = ROOT_DIR / mod
        if p.is_file():
            cmd.append(str(p))

    print(f"[*] Executing command: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(ROOT_DIR))
    if result.returncode != 0:
        print("[-] PyArmor obfuscation failed.")
        return False

    print("[+] Core modules obfuscated successfully.")

    # Copy accompanying assets
    print("[*] Copying assets and non-obfuscated files...")
    for item in ASSETS_TO_COPY:
        src = ROOT_DIR / item
        dst = target_dir / item
        if not src.exists():
            continue
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
        print(f"    Copied: {item}")

    print(f"[+] Protected build ready in: {target_dir}")
    return True


def run_pyinstaller_build(target_dir: Path) -> bool:
    spec_file = ROOT_DIR / "AutomationHub.spec"
    if not spec_file.is_file():
        print("[-] AutomationHub.spec not found, skipping PyInstaller executable generation.")
        return False

    try:
        import PyInstaller  # type: ignore # noqa
    except ImportError:
        print("[-] PyInstaller not installed in current Python environment.")
        print("    Install it via: pip install pyinstaller")
        return False

    print("[*] Running PyInstaller with AutomationHub.spec...")
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--distpath",
        str(target_dir / "bin"),
        "--workpath",
        str(ROOT_DIR / "build" / "pyinstaller_work"),
        "-y",
        str(spec_file),
    ]
    res = subprocess.run(cmd, cwd=str(ROOT_DIR))
    return res.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Automation Hub Security Build Script")
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=str(OUTPUT_DIR),
        help="Destination directory for protected output",
    )
    parser.add_argument(
        "--exe",
        action="store_true",
        help="Also build binary executable via PyInstaller",
    )
    args = parser.parse_args()

    out_path = Path(args.output).resolve()
    success = run_pyarmor_obfuscation(out_path)
    if not success:
        return 1

    if args.exe:
        run_pyinstaller_build(out_path)

    print("\n" + "=" * 60)
    print("Build complete! Protected deployment generated in:")
    print(f"  {out_path}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
