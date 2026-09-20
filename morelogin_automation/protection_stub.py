"""
Phase 2 application protection stubs.

Planned enhancements:
- Anti-debugging checks (Windows IsDebuggerPresent)
- Binary integrity hash verification
- Offline grace period using cached heartbeat timestamp
- PyInstaller packaging + obfuscation
- Windows DPAPI for local token encryption

Enable incrementally; MVP auth uses server heartbeat only.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path


def runtime_integrity_ok() -> bool:
    """Placeholder integrity check — extend with packaged binary hash."""
    return True


def anti_debug_ok() -> bool:
    """Basic anti-debug stub for Windows."""
    if not sys.platform.startswith("win"):
        return True
    try:
        import ctypes

        if ctypes.windll.kernel32.IsDebuggerPresent():
            return False
    except Exception:
        pass
    return True


def file_fingerprint(path: Path) -> str:
    if not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def protection_checks() -> tuple[bool, str]:
    if not anti_debug_ok():
        return False, "Debugger detected"
    if not runtime_integrity_ok():
        return False, "Application integrity check failed"
    return True, ""
