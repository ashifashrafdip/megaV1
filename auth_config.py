"""Authentication settings strictly enforced for online licensing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AuthSettings:
    # Mandatory authentication — cannot be disabled by config file
    enabled: bool = True
    api_base: str = ""
    app_key: str = ""
    heartbeat_seconds: int = 45
    session_timeout_seconds: int = 3600
    verify_ssl: bool = True

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "AuthSettings":
        raw = raw or {}
        api_base = str(raw.get("api_base", "")).strip().rstrip("/")
        # Always enforce enabled = True (offline mode removed)
        return cls(
            enabled=True,
            api_base=api_base,
            app_key=str(raw.get("app_key", "")).strip(),
            heartbeat_seconds=max(30, int(raw.get("heartbeat_seconds", 45))),
            session_timeout_seconds=max(300, int(raw.get("session_timeout_seconds", 3600))),
            verify_ssl=bool(raw.get("verify_ssl", True)),
        )

    def api_url(self, endpoint: str) -> str:
        endpoint = endpoint.lstrip("/")
        return f"{self.api_base}/api/{endpoint}"
