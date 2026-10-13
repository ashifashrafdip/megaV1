from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
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
    api_base: str = "http://127.0.0.1:50325"
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
        key = settings.api_key.strip()
        if not key:
            key = detect_local_adspower_token()

        base = settings.api_base.rstrip("/")
        if not base:
            base = detect_local_adspower_base_url()

        return cls(
            profile_id=settings.profile_id.strip(),
            profile_no=settings.profile_no.strip(),
            api_base=base,
            api_key=key,
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


def detect_local_adspower_token() -> str:
    """Auto-detect AdsPower login token or API key from local user data."""
    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        appdata = str(Path.home() / "AppData" / "Roaming")

    cfg_file = Path(appdata) / "adspower_global" / "config.json"
    if not cfg_file.is_file():
        return ""
    try:
        raw_text = cfg_file.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r'loginToken[^\w]*([a-fA-F0-9]{32,64})', raw_text)
        if m:
            return m.group(1).strip()
        m_api = re.search(r'apiKey[^\w]*([a-zA-Z0-9_\-]{16,64})', raw_text)
        if m_api:
            return m_api.group(1).strip()
        data = json.loads(raw_text)
        snapshot = data.get("AI_AGENT_STORE_SNAPSHOT")
        if isinstance(snapshot, str):
            snapshot = json.loads(snapshot)
        if isinstance(snapshot, dict):
            user = snapshot.get("state", {}).get("user", {})
            tok = user.get("loginToken") or user.get("apiKey") or snapshot.get("token")
            if tok:
                return str(tok).strip()
    except Exception:
        pass
    return ""



def detect_local_adspower_base_url() -> str:
    """Auto-detect AdsPower local API base URL from local configuration."""
    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        appdata = str(Path.home() / "AppData" / "Roaming")
    
    local_api_file = Path(appdata) / "adspower_global" / "cwd_global" / "source" / "local_api"
    if local_api_file.is_file():
        try:
            url = local_api_file.read_text(encoding="utf-8").strip().rstrip("/")
            if url:
                # Prefer 127.0.0.1 for high reliability if local domain
                if "local.adspower." in url:
                    m = re.search(r":(\d+)$", url)
                    port = m.group(1) if m else "50325"
                    return f"http://127.0.0.1:{port}"
                return url
        except Exception:
            pass
    return "http://127.0.0.1:50325"


def check_adspower_status(api_base: str = "http://127.0.0.1:50325", timeout_s: float = 3.0) -> bool:
    """Check if AdsPower Local API service is alive via /status endpoint."""
    urls = [api_base.rstrip("/")]
    if "127.0.0.1" not in api_base:
        urls.append("http://127.0.0.1:50325")
    if "localhost" not in api_base:
        urls.append("http://localhost:50325")

    for base in urls:
        try:
            req = Request(f"{base}/status", headers={"Accept": "application/json"})
            with urlopen(req, timeout=timeout_s) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if int(data.get("code", -1)) == 0:
                    return True
        except Exception:
            continue
    return False


def detect_local_adspower_settings() -> tuple[str, str, bool]:
    """Auto-detect AdsPower base URL, token, and running status."""
    base_url = detect_local_adspower_base_url()
    token = detect_local_adspower_token()
    is_live = check_adspower_status(base_url, timeout_s=1.5)
    return base_url, token, is_live


def check_adspower_active_profile(settings: AdsPowerLaunchSettings) -> dict[str, Any] | None:
    """Check if the designated profile is currently active in AdsPower."""
    if not settings.identifier:
        return None

    # Try v2 active endpoint first
    try:
        params: dict[str, Any] = {}
        if settings.profile_id:
            params["profile_id"] = settings.profile_id
        if settings.profile_no:
            params["profile_no"] = settings.profile_no
        url = f"{settings.api_base}/api/v2/browser-profile/active?{urlencode(params)}"
        resp = _request_json(url, "GET", settings)
        data = resp.get("data") or {}
        if str(data.get("status", "")).lower() == "active":
            return data
    except Exception:
        pass

    # Try v1 active endpoint
    try:
        params1: dict[str, Any] = {}
        if settings.profile_id:
            params1["user_id"] = settings.profile_id
        if settings.profile_no:
            params1["serial_number"] = settings.profile_no
        url1 = f"{settings.api_base}/api/v1/browser/active?{urlencode(params1)}"
        resp1 = _request_json(url1, "GET", settings)
        data1 = resp1.get("data") or {}
        if str(data1.get("status", "")).lower() == "active":
            return data1
    except Exception:
        pass

    return None


def list_adspower_profiles(
    settings: AdsPowerSettings,
    *,
    page: int = 1,
    limit: int = 100,
    timeout_ms: int = 30000,
) -> list[AdsPowerProfile]:
    """Fetch AdsPower browser profiles from the local API with v2/v1 fallback."""
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

    response: dict[str, Any] | None = None
    last_exc: Exception | None = None

    # Primary attempt based on settings.api_version
    if settings.api_version.lower() != "v1":
        try:
            response = _request_json(
                f"{launch_settings.api_base}/api/v2/browser-profile/list",
                "POST",
                launch_settings,
                payload,
            )
        except Exception as exc:
            last_exc = exc

    # Fallback to v1 if v2 failed or settings requested v1
    if response is None or int(response.get("code", -1)) != 0:
        try:
            params = {
                "page": payload["page"],
                "page_size": payload["limit"],
            }
            response = _request_json(
                f"{launch_settings.api_base}/api/v1/user/list?{urlencode(params)}",
                "GET",
                launch_settings,
            )
        except Exception as exc:
            if last_exc is None:
                last_exc = exc
            if response is None:
                raise last_exc

    profiles: list[AdsPowerProfile] = []
    data_list = (response.get("data") or {}).get("list") or []
    for item in data_list:
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

        if self._page and not self._page.is_closed():
            return self._page

        try:
            from playwright.sync_api import sync_playwright
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Playwright is not installed. Run: pip install playwright"
            ) from exc

        # 1. Check if profile is already active
        ws_url = ""
        active_info = check_adspower_active_profile(settings)
        if active_info:
            ws_url = self._extract_puppeteer_ws({"data": active_info})

        # 2. If not active, start the profile
        if not ws_url:
            try:
                response = self._start_profile(settings)
                ws_url = self._extract_puppeteer_ws(response)
            except Exception as exc:
                # If start fails because it was already open, check active status
                active_fallback = check_adspower_active_profile(settings)
                if active_fallback:
                    ws_url = self._extract_puppeteer_ws({"data": active_fallback})
                else:
                    raise exc

        # 3. Connect Playwright over CDP with retry loop
        self._playwright = sync_playwright().start()
        connected_browser = None
        last_connect_exc = None

        for attempt in range(1, 4):
            try:
                connected_browser = self._playwright.chromium.connect_over_cdp(
                    ws_url,
                    timeout=min(settings.launch_timeout_ms, 15000),
                )
                break
            except Exception as exc:
                last_connect_exc = exc
                time.sleep(1.5)

        if not connected_browser:
            self._playwright.stop()
            self._playwright = None
            raise last_connect_exc or RuntimeError(f"Failed to connect to AdsPower CDP at {ws_url}")

        self._browser = connected_browser
        self._context = self._browser.contexts[0] if self._browser.contexts else self._browser.new_context()
        self._page = self._pick_work_page(self._context)
        self._settings = settings

        if start_url:
            try:
                self._page.goto(start_url, wait_until="domcontentloaded")
            except Exception:
                pass

        return self._page

    @staticmethod
    def _pick_work_page(context):
        time.sleep(1.0)
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
            try:
                self._browser = None
            except Exception:
                pass
            self._context = None
            self._page = None

        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass
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
        if puppeteer_ws:
            return str(puppeteer_ws)
        
        debug_port = data.get("debug_port")
        if debug_port:
            return f"http://127.0.0.1:{debug_port}"
            
        selenium = ws.get("selenium")
        if selenium:
            return f"http://{selenium}"

        raise AdsPowerApiError("AdsPower did not return WebSocket or CDP debug address.")


def _request_json(
    url: str,
    method: str,
    settings: AdsPowerLaunchSettings,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute JSON request to AdsPower API with intelligent auth header fallback and rate-limiting retry."""
    body_bytes = json.dumps(payload).encode("utf-8") if payload is not None else None
    token = settings.api_key.strip()
    if not token:
        token = detect_local_adspower_token()

    is_hex_token = bool(token and len(token) == 48 and all(c in "0123456789abcdefABCDEF" for c in token))

    # Determine auth header attempts
    if token:
        if is_hex_token:
            auth_modes = [
                {"login-token": token},
                {"api-key": token, "Authorization": f"Bearer {token}"},
            ]
        else:
            auth_modes = [
                {"api-key": token, "Authorization": f"Bearer {token}"},
                {"login-token": token},
            ]
    else:
        auth_modes = [{}]

    timeout_sec = max(2.0, settings.launch_timeout_ms / 1000.0)
    last_error: Exception | None = None

    # Base URL fallbacks if local DNS resolution fails
    candidate_urls = [url]
    if "local.adspower." in url:
        m = re.match(r"^(https?://)local\.adspower\.[^:/]+(?::(\d+))?(.*)$", url)
        if m:
            scheme = m.group(1)
            port = f":{m.group(2)}" if m.group(2) else ":50325"
            path = m.group(3)
            candidate_urls.append(f"{scheme}127.0.0.1{port}{path}")
            candidate_urls.append(f"{scheme}localhost{port}{path}")

    for target_url in candidate_urls:
        for auth_headers in auth_modes:
            for retry in range(3):
                headers = {"Accept": "application/json"}
                if payload is not None:
                    headers["Content-Type"] = "application/json"
                headers.update(auth_headers)

                request = Request(target_url, data=body_bytes, headers=headers, method=method)
                try:
                    with urlopen(request, timeout=timeout_sec) as response:
                        raw_body = response.read().decode("utf-8")
                except HTTPError as exc:
                    last_error = AdsPowerApiError(f"AdsPower HTTP {exc.code}: {exc.reason}")
                    time.sleep(1.1)
                    continue
                except URLError as exc:
                    last_error = AdsPowerApiError(
                        f"Cannot reach AdsPower Local API at {settings.api_base}: {exc.reason}"
                    )
                    break  # Try next candidate URL

                try:
                    result = json.loads(raw_body)
                except json.JSONDecodeError as exc:
                    last_error = AdsPowerApiError(f"AdsPower returned non-JSON response: {raw_body[:200]}")
                    break

                code = int(result.get("code", -1))
                if code == 0:
                    return result

                msg = str(result.get("msg") or "AdsPower API request failed.")
                
                # Rate limit encountered -> wait 1.2s and retry
                if "too many request" in msg.lower():
                    time.sleep(1.2)
                    continue

                # Header mismatch or require api-key -> try next auth mode
                if "mismatch" in msg.lower() or "require api-key" in msg.lower():
                    time.sleep(1.1)
                    break

                # Other application error
                raise AdsPowerApiError(msg)

    if last_error:
        raise last_error
    raise AdsPowerApiError("AdsPower request failed after all attempts.")
