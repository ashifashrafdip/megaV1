"""Local auth session state and token refresh."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from auth_client import AuthClient, AuthError, LoginResult
from auth_config import AuthSettings
from device_fingerprint import device_id, pc_name


@dataclass
class AuthSession:
    settings: AuthSettings
    client: AuthClient
    access_token: str = ""
    refresh_token: str = ""
    access_expires_at: float = 0.0
    user: dict[str, Any] = field(default_factory=dict)
    license: dict[str, Any] | None = None
    heartbeat_seconds: int = 45
    device_id: str = ""
    pc_name: str = ""
    locked: bool = False
    lock_reason: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.device_id:
            self.device_id = device_id()
        if not self.pc_name:
            self.pc_name = pc_name()

    @property
    def is_authenticated(self) -> bool:
        return bool(self.access_token) and not self.locked

    @property
    def username(self) -> str:
        return str(self.user.get("username", ""))

    @property
    def license_days_left(self) -> int | None:
        if not self.license:
            return None
        days = self.license.get("days_left")
        return int(days) if days is not None else None

    def apply_login(self, result: LoginResult) -> None:
        self.access_token = result.access_token
        self.refresh_token = result.refresh_token
        self.access_expires_at = time.time() + result.access_expires_in - 30
        self.user = result.user
        self.license = result.license
        self.heartbeat_seconds = result.heartbeat_seconds
        self.locked = False
        self.lock_reason = ""
        self.save_cache()
        try:
            self.load_payload()
        except Exception:
            pass

    def load_payload(self) -> dict[str, Any]:
        token = self.ensure_access_token()
        data = self.client.fetch_payload(token, self.device_id)
        self.payload = data
        return self.payload

    def lock(self, reason: str) -> None:
        self.locked = True
        self.lock_reason = reason
        self.payload = {}

    def ensure_access_token(self) -> str:
        if self.locked:
            raise AuthError("locked", self.lock_reason or "Application locked")
        if self.access_token and time.time() < self.access_expires_at:
            return self.access_token
        if not self.refresh_token:
            raise AuthError("session_revoked", "Session expired")
        try:
            self.access_token = self.client.refresh(self.refresh_token, self.device_id)
            self.access_expires_at = time.time() + max(60, self.settings.session_timeout_seconds // 4)
            self.save_cache()
            return self.access_token
        except AuthError as exc:
            self.lock(exc.message)
            raise

    def heartbeat_check(self) -> None:
        token = self.ensure_access_token()
        try:
            data = self.client.heartbeat(token, self.device_id, self.pc_name)
            if data.get("license"):
                self.license = dict(data["license"])
            self.heartbeat_seconds = int(
                data.get("heartbeat_interval", self.heartbeat_seconds)
            )
            self.save_cache()
        except AuthError as exc:
            self.lock(exc.message)
            raise

    def logout(self) -> None:
        if self.access_token:
            self.client.logout(self.access_token, self.device_id)
        self.clear_cache()

    def cache_path(self) -> Path:
        base = Path.home() / ".automation_hub"
        base.mkdir(parents=True, exist_ok=True)
        return base / "auth_session.json"

    def save_cache(self) -> None:
        payload = {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "access_expires_at": self.access_expires_at,
            "user": self.user,
            "license": self.license,
            "heartbeat_seconds": self.heartbeat_seconds,
            "device_id": self.device_id,
            "pc_name": self.pc_name,
        }
        self.cache_path().write_text(json.dumps(payload), encoding="utf-8")

    def load_cache(self) -> bool:
        path = self.cache_path()
        if not path.is_file():
            return False
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        self.access_token = str(payload.get("access_token", ""))
        self.refresh_token = str(payload.get("refresh_token", ""))
        self.access_expires_at = float(payload.get("access_expires_at", 0))
        self.user = dict(payload.get("user") or {})
        self.license = payload.get("license")
        self.heartbeat_seconds = int(payload.get("heartbeat_seconds", self.heartbeat_seconds))
        self.device_id = str(payload.get("device_id", self.device_id))
        self.pc_name = str(payload.get("pc_name", self.pc_name))
        return bool(self.refresh_token)

    def clear_cache(self) -> None:
        self.access_token = ""
        self.refresh_token = ""
        self.user = {}
        self.license = None
        path = self.cache_path()
        if path.is_file():
            try:
                path.unlink()
            except OSError:
                pass
