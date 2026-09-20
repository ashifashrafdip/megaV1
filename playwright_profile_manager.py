from __future__ import annotations

import json
import shutil
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from playwright_browser import ChromiumBrowser

if TYPE_CHECKING:
    from playwright.sync_api import BrowserContext, Page


DEFAULT_PROFILE_ROOT = Path.home() / ".playwright_profiles"
SETTINGS_FILENAME = "settings.json"


@dataclass
class BrowserProfileSettings:
    """Launch and emulation settings kept with a persistent Playwright profile."""

    name: str
    headless: bool = False
    user_agent: str | None = None
    proxy: dict[str, str] | None = None
    viewport: dict[str, int] = field(default_factory=lambda: {"width": 1280, "height": 720})
    device_scale_factor: float | None = None
    is_mobile: bool = False
    has_touch: bool = False
    locale: str = "en-US"
    timezone_id: str = "UTC"
    color_scheme: str = "light"
    permissions: list[str] = field(default_factory=list)
    extra_http_headers: dict[str, str] = field(default_factory=dict)
    chromium_args: list[str] = field(default_factory=list)
    launch_timeout_ms: int = 30000

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "BrowserProfileSettings":
        device_scale_factor = raw.get("device_scale_factor")
        return cls(
            name=str(raw["name"]),
            headless=bool(raw.get("headless", False)),
            user_agent=raw.get("user_agent"),
            proxy=raw.get("proxy"),
            viewport=raw.get("viewport") or {"width": 1280, "height": 720},
            device_scale_factor=(
                float(device_scale_factor) if device_scale_factor is not None else None
            ),
            is_mobile=bool(raw.get("is_mobile", False)),
            has_touch=bool(raw.get("has_touch", False)),
            locale=raw.get("locale", "en-US"),
            timezone_id=raw.get("timezone_id", "UTC"),
            color_scheme=raw.get("color_scheme", "light"),
            permissions=raw.get("permissions") or [],
            extra_http_headers=raw.get("extra_http_headers") or {},
            chromium_args=raw.get("chromium_args") or [],
            launch_timeout_ms=int(raw.get("launch_timeout_ms", 30000)),
        )


class PlaywrightProfileManager:
    """Manage Chromium persistent contexts and profile settings on disk."""

    def __init__(self, profile_root: str | Path = DEFAULT_PROFILE_ROOT):
        self.profile_root = Path(profile_root)
        self.profile_root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._browser: ChromiumBrowser | None = None
        self._context: BrowserContext | None = None
        self._active_profile: BrowserProfileSettings | None = None

    @property
    def active_profile(self) -> BrowserProfileSettings | None:
        return self._active_profile

    @property
    def context(self) -> BrowserContext:
        if not self._context:
            raise RuntimeError("No active browser context. Call start() first.")
        return self._context

    def list_profiles(self) -> list[str]:
        with self._lock:
            return sorted(
                path.name
                for path in self.profile_root.iterdir()
                if path.is_dir() and (path / SETTINGS_FILENAME).exists()
            )

    def create_profile(
        self,
        name: str,
        *,
        overwrite: bool = False,
        **settings: Any,
    ) -> BrowserProfileSettings:
        with self._lock:
            safe_name = self._safe_profile_name(name)
            profile_dir = self.profile_dir(safe_name)
            if profile_dir.exists() and not overwrite:
                raise FileExistsError(f"Profile already exists: {safe_name}")

            profile_dir.mkdir(parents=True, exist_ok=True)
            profile_settings = BrowserProfileSettings(name=safe_name, **settings)
            self.save_settings(profile_settings)
            return profile_settings

    def load_settings(self, name: str) -> BrowserProfileSettings:
        with self._lock:
            settings_file = self.profile_dir(name) / SETTINGS_FILENAME
            if not settings_file.exists():
                raise FileNotFoundError(f"Profile settings not found: {settings_file}")

            with settings_file.open("r", encoding="utf-8") as settings_stream:
                return BrowserProfileSettings.from_dict(json.load(settings_stream))

    def save_settings(self, settings: BrowserProfileSettings):
        with self._lock:
            profile_dir = self.profile_dir(settings.name)
            profile_dir.mkdir(parents=True, exist_ok=True)
            settings_file = profile_dir / SETTINGS_FILENAME

            with settings_file.open("w", encoding="utf-8") as settings_stream:
                json.dump(asdict(settings), settings_stream, indent=2)

    def delete_profile(self, name: str):
        with self._lock:
            if self._active_profile and self._active_profile.name == name:
                self.stop()
            shutil.rmtree(self.profile_dir(name), ignore_errors=True)

    def start(self, name: str, *, start_url: str | None = None) -> Page:
        """Start a persistent Chromium context and return the first page."""
        with self._lock:
            if self._context:
                if self._active_profile and self._active_profile.name == name:
                    return self._first_page()
                self.stop()

            settings = self.load_settings(name)
            browser = ChromiumBrowser(
                user_data_dir=self.profile_dir(settings.name) / "user_data",
                headless=settings.headless,
                proxy=settings.proxy,
                user_agent=settings.user_agent,
                viewport=settings.viewport,
                device_scale_factor=settings.device_scale_factor,
                is_mobile=settings.is_mobile,
                has_touch=settings.has_touch,
                locale=settings.locale,
                timezone_id=settings.timezone_id,
                color_scheme=settings.color_scheme,
                permissions=settings.permissions,
                extra_http_headers=settings.extra_http_headers,
                chromium_args=settings.chromium_args,
                launch_timeout_ms=settings.launch_timeout_ms,
            )
            page = browser.start()
            self._browser = browser
            self._context = browser.context
            self._active_profile = settings

            if start_url:
                page.goto(start_url)

            return page

    def stop(self):
        with self._lock:
            if self._browser:
                self._browser.stop()
                self._browser = None
            elif self._context:
                self._context.close()

            self._context = None
            self._active_profile = None

    def storage_state(self, path: str | Path | None = None) -> dict[str, Any]:
        with self._lock:
            return self.context.storage_state(path=str(path) if path else None)

    def save_storage_state(self, path: str | Path | None = None) -> Path:
        with self._lock:
            if path:
                output_path = Path(path)
            elif self._active_profile:
                output_path = self.profile_dir(self._active_profile.name) / "storage_state.json"
            else:
                raise RuntimeError("No active profile to save storage state for.")

            output_path.parent.mkdir(parents=True, exist_ok=True)
            self.context.storage_state(path=str(output_path))
            return output_path

    def profile_dir(self, name: str) -> Path:
        return self.profile_root / self._safe_profile_name(name)

    def _first_page(self) -> Page:
        return self.context.pages[0] if self.context.pages else self.context.new_page()

    @staticmethod
    def _safe_profile_name(name: str) -> str:
        normalized = "".join(
            character if character.isalnum() or character in "._-" else "-"
            for character in name.strip()
        ).strip(".-_")
        if not normalized:
            raise ValueError("Profile name cannot be empty.")
        return normalized
