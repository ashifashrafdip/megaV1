"""HTTPS client for PHP auth API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from auth_config import AuthSettings


class AuthError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class LoginResult:
    access_token: str
    refresh_token: str
    access_expires_in: int
    user: dict[str, Any]
    license: dict[str, Any] | None
    heartbeat_seconds: int


class AuthClient:
    def __init__(self, settings: AuthSettings):
        self.settings = settings
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})
        if settings.app_key:
            self._session.headers["X-App-Key"] = settings.app_key

    def _post(
        self,
        endpoint: str,
        payload: dict[str, Any] | None = None,
        *,
        access_token: str | None = None,
    ) -> dict[str, Any]:
        headers = {}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        try:
            response = self._session.post(
                self.settings.api_url(endpoint),
                json=payload or {},
                headers=headers,
                timeout=20,
                verify=self.settings.verify_ssl,
            )
        except requests.RequestException as exc:
            raise AuthError("network_error", f"Cannot reach auth server: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise AuthError("invalid_response", "Auth server returned non-JSON") from exc

        if not isinstance(data, dict):
            raise AuthError("invalid_response", "Unexpected auth response")

        if not data.get("ok"):
            raise AuthError(
                str(data.get("code", "error")),
                str(data.get("message", "Request failed")),
            )
        return data

    def login(self, username: str, password: str, device_id: str, pc_name: str) -> LoginResult:
        data = self._post(
            "login.php",
            {
                "username": username,
                "password": password,
                "device_id": device_id,
                "pc_name": pc_name,
            },
        )
        return LoginResult(
            access_token=str(data["access_token"]),
            refresh_token=str(data["refresh_token"]),
            access_expires_in=int(data.get("access_expires_in", 900)),
            user=dict(data.get("user") or {}),
            license=dict(data["license"]) if data.get("license") else None,
            heartbeat_seconds=int(data.get("heartbeat_interval", self.settings.heartbeat_seconds)),
        )

    def logout(self, access_token: str, device_id: str) -> None:
        try:
            self._post(
                "logout.php",
                {"device_id": device_id},
                access_token=access_token,
            )
        except AuthError:
            pass

    def heartbeat(
        self,
        access_token: str,
        device_id: str,
        pc_name: str,
    ) -> dict[str, Any]:
        return self._post(
            "heartbeat.php",
            {"device_id": device_id, "pc_name": pc_name},
            access_token=access_token,
        )

    def refresh(self, refresh_token: str, device_id: str) -> str:
        data = self._post(
            "refresh_token.php",
            {"refresh_token": refresh_token, "device_id": device_id},
        )
        return str(data["access_token"])

    def log_activity(
        self,
        access_token: str,
        action: str,
        device_id: str,
        pc_name: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        try:
            self._post(
                "activity_log.php",
                {
                    "action": action,
                    "device_id": device_id,
                    "pc_name": pc_name,
                    "details": details or {},
                },
                access_token=access_token,
            )
        except AuthError:
            pass

    def log_link(
        self,
        access_token: str,
        url: str,
        device_id: str,
        browser: str = "adspower",
    ) -> None:
        try:
            self._post(
                "link_log.php",
                {"url": url, "device_id": device_id, "browser": browser},
                access_token=access_token,
            )
        except AuthError:
            pass

    def fetch_payload(
        self,
        access_token: str,
        device_id: str,
    ) -> dict[str, Any]:
        data = self._post(
            "payload.php",
            {"device_id": device_id},
            access_token=access_token,
        )
        return dict(data.get("payload") or {})

