from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app_config import AdsPowerSettings


@dataclass(frozen=True)
class AdsPowerProfile:
    profile_id: str
    profile_no: str
    name: str
    group_name: str = ""
    remark: str = ""

    def label(self) -> str:
        title = self.name.strip() or self.profile_id or self.profile_no
        if self.profile_no and self.profile_id:
            return f"#{self.profile_no} - {title} ({self.profile_id})"
        if self.profile_no:
            return f"#{self.profile_no} - {title}"
        return title


@dataclass(frozen=True)
class AdsPowerLaunchSettings:
    profile_id: str
    profile_no: str = ""
    api_base: str = "http://local.adspower.net:50325"
    api_key: str = ""
    api_version: str = "v2"
    headless: bool = False
    close_on_stop: bool = True
    cdp_mask: bool = True
    proxy_detection: bool = False
    open_last_tabs: bool = False
    launch_args: list[str] = field(default_factory=list)
    launch_timeout_ms: int = 30000

    @classmethod
    def from_config(
        cls,
        settings: AdsPowerSettings,
        *,
        headless: bool,
        launch_args: list[str] | None = None,
        launch_timeout_ms: int = 30000,
    ) -> "AdsPowerLaunchSettings":
        return cls(
            profile_id=settings.profile_id.strip(),
            profile_no=settings.profile_no.strip(),
            api_base=settings.api_base.rstrip("/"),
            api_key=settings.api_key.strip(),
            api_version=settings.api_version.lower(),
            headless=headless,
            close_on_stop=settings.close_on_stop,
            cdp_mask=settings.cdp_mask,
            proxy_detection=settings.proxy_detection,
            open_last_tabs=settings.open_last_tabs,
            launch_args=launch_args or [],
            launch_timeout_ms=launch_timeout_ms,
        )

    @property
    def identifier(self) -> str:
        return self.profile_id or self.profile_no


class AdsPowerApiError(RuntimeError):
    pass


def list_adspower_profiles(
    settings: AdsPowerSettings,
    *,
    page: int = 1,
    limit: int = 100,
    timeout_ms: int = 30000,
) -> list[AdsPowerProfile]:
    """Fetch AdsPower browser profiles from the local API."""
    launch_settings = AdsPowerLaunchSettings.from_config(
        settings,
        headless=False,
        launch_timeout_ms=timeout_ms,
    )
    payload = {
        "page": max(1, page),
        "limit": min(max(1, limit), 100),
        "sort_type": "profile_no",
        "sort_order": "desc",
    }
    if settings.api_version == "v1":
        params = {
            "page": payload["page"],
            "page_size": payload["limit"],
        }
        response = _request_json(
            f"{launch_settings.api_base}/api/v1/user/list?{urlencode(params)}",
            "GET",
            launch_settings,
        )
    else:
        response = _request_json(
            f"{launch_settings.api_base}/api/v2/browser-profile/list",
            "POST",
            launch_settings,
            payload,
        )

    profiles: list[AdsPowerProfile] = []
    for item in (response.get("data") or {}).get("list") or []:
        profile_id = str(item.get("profile_id") or item.get("user_id") or "").strip()
        profile_no = str(item.get("profile_no") or item.get("serial_number") or "").strip()
        if not profile_id and not profile_no:
            continue
        profiles.append(
            AdsPowerProfile(
                profile_id=profile_id,
                profile_no=profile_no,
                name=str(item.get("name") or "").strip(),
                group_name=str(item.get("group_name") or "").strip(),
                remark=str(item.get("remark") or "").strip(),
            )
        )
    return profiles


class AdsPowerBrowserManager:
    """Start an existing AdsPower profile and attach Playwright over CDP."""

    def __init__(self):
        self._settings: AdsPowerLaunchSettings | None = None
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    @property
    def context(self):
        if not self._context:
            raise RuntimeError("No active AdsPower browser context. Call start() first.")
        return self._context

    def start(self, settings: AdsPowerLaunchSettings, *, start_url: str | None = None):
        if not settings.identifier:
            raise ValueError("AdsPower profile ID or profile No is required.")

        if self._page:
            return self._page

        try:
            from playwright.sync_api import sync_playwright
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Playwright is not installed. Run: pip install playwright"
            ) from exc

        response = self._start_profile(settings)
        ws_url = self._extract_puppeteer_ws(response)

        self._playwright = sync_playwright().start()
        try:
            self._browser = self._playwright.chromium.connect_over_cdp(
                ws_url,
                timeout=settings.launch_timeout_ms,
            )
        except Exception:
            self._playwright.stop()
            self._playwright = None
            raise

        self._context = self._browser.contexts[0] if self._browser.contexts else self._browser.new_context()
        self._page = self._pick_work_page(self._context)
        self._settings = settings

        if start_url:
            self._page.goto(start_url, wait_until="domcontentloaded")

        return self._page

    @staticmethod
    def _pick_work_page(context):
        import time

        time.sleep(1.5)
        for page in reversed(context.pages):
            if not page.is_closed():
                return page
        return context.new_page()

    def active_page(self):
        if self._page and not self._page.is_closed():
            return self._page
        if self._context:
            for page in reversed(self._context.pages):
                if not page.is_closed():
                    self._page = page
                    return page
            self._page = self._context.new_page()
            return self._page
        raise RuntimeError("No active AdsPower browser page.")

    def stop(self):
        settings = self._settings

        if self._browser:
            self._browser = None
            self._context = None
            self._page = None

        if self._playwright:
            self._playwright.stop()
            self._playwright = None

        if settings and settings.close_on_stop:
            self._stop_profile(settings)

        self._settings = None

    def _start_profile(self, settings: AdsPowerLaunchSettings) -> dict[str, Any]:
        if settings.api_version == "v1":
            params: dict[str, Any] = {
                "headless": "1" if settings.headless else "0",
                "open_tabs": "1" if settings.open_last_tabs else "0",
                "ip_tab": "1" if settings.proxy_detection else "0",
                "cdp_mask": "1" if settings.cdp_mask else "0",
            }
            if settings.profile_id:
                params["user_id"] = settings.profile_id
            if settings.profile_no:
                params["serial_number"] = settings.profile_no
            if settings.launch_args:
                params["launch_args"] = json.dumps(settings.launch_args)
            return _request_json(
                f"{settings.api_base}/api/v1/browser/start?{urlencode(params)}",
                "GET",
                settings,
            )

        payload: dict[str, Any] = {
            "headless": "1" if settings.headless else "0",
            "last_opened_tabs": "1" if settings.open_last_tabs else "0",
            "proxy_detection": "1" if settings.proxy_detection else "0",
            "cdp_mask": "1" if settings.cdp_mask else "0",
        }
        if settings.profile_id:
            payload["profile_id"] = settings.profile_id
        if settings.profile_no:
            payload["profile_no"] = settings.profile_no
        if settings.launch_args:
            payload["launch_args"] = settings.launch_args
        return _request_json(
            f"{settings.api_base}/api/v2/browser-profile/start",
            "POST",
            settings,
            payload,
        )

    def _stop_profile(self, settings: AdsPowerLaunchSettings):
        try:
            if settings.api_version == "v1":
                params: dict[str, Any] = {}
                if settings.profile_id:
                    params["user_id"] = settings.profile_id
                if settings.profile_no:
                    params["serial_number"] = settings.profile_no
                _request_json(
                    f"{settings.api_base}/api/v1/browser/stop?{urlencode(params)}",
                    "GET",
                    settings,
                )
                return

            payload: dict[str, Any] = {}
            if settings.profile_id:
                payload["profile_id"] = settings.profile_id
            if settings.profile_no:
                payload["profile_no"] = settings.profile_no
            _request_json(
                f"{settings.api_base}/api/v2/browser-profile/stop",
                "POST",
                settings,
                payload,
            )
        except AdsPowerApiError:
            pass

    @staticmethod
    def _extract_puppeteer_ws(response: dict[str, Any]) -> str:
        data = response.get("data") or {}
        ws = data.get("ws") or {}
        puppeteer_ws = ws.get("puppeteer")
        if not puppeteer_ws:
            raise AdsPowerApiError("AdsPower did not return data.ws.puppeteer.")
        return str(puppeteer_ws)


def _request_json(
    url: str,
    method: str,
    settings: AdsPowerLaunchSettings,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    body: bytes | None = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if settings.api_key:
        headers["Authorization"] = f"Bearer {settings.api_key}"

    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=max(1, settings.launch_timeout_ms / 1000)) as response:
            raw_body = response.read().decode("utf-8")
    except HTTPError as exc:
        raise AdsPowerApiError(f"AdsPower HTTP {exc.code}: {exc.reason}") from exc
    except URLError as exc:
        raise AdsPowerApiError(
            f"Cannot reach AdsPower Local API at {settings.api_base}: {exc.reason}"
        ) from exc

    try:
        result = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise AdsPowerApiError(f"AdsPower returned non-JSON response: {raw_body[:200]}") from exc

    if int(result.get("code", -1)) != 0:
        raise AdsPowerApiError(result.get("msg") or "AdsPower API request failed.")
    return result
