"""Hardware fingerprint for device binding."""

from __future__ import annotations

import hashlib
import platform
import socket
import uuid


def _wmi_value(query: str, prop: str) -> str:
    try:
        import wmi  # type: ignore

        client = wmi.WMI()
        for item in client.query(query):
            value = getattr(item, prop, None)
            if value:
                return str(value).strip()
    except Exception:
        pass
    return ""


def collect_fingerprint_parts() -> dict[str, str]:
    parts = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or "",
        "node": platform.node(),
        "mac": hex(uuid.getnode()),
    }

    if platform.system().lower() == "windows":
        parts["cpu_id"] = _wmi_value("SELECT ProcessorId FROM Win32_Processor", "ProcessorId")
        parts["disk_serial"] = _wmi_value(
            "SELECT SerialNumber FROM Win32_DiskDrive WHERE Index=0",
            "SerialNumber",
        )
        parts["board_serial"] = _wmi_value(
            "SELECT SerialNumber FROM Win32_BaseBoard",
            "SerialNumber",
        )
    else:
        parts["cpu_id"] = platform.processor()
        parts["disk_serial"] = ""
        parts["board_serial"] = ""

    return parts


def device_id() -> str:
    parts = collect_fingerprint_parts()
    payload = "|".join(f"{key}={parts.get(key, '')}" for key in sorted(parts))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def pc_name() -> str:
    return platform.node() or socket.gethostname() or "unknown"
