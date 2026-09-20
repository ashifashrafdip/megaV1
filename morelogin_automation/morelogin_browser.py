from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

LOGGER = logging.getLogger("morelogin_automation.browser")
DEFAULT_MORELOGIN_API = "http://127.0.0.1:40000"


@dataclass(frozen=True)
class MoreLoginProfile:
    profile_id: str
    name: str = ""
    group_name: str = ""
    proxy_info: str = ""
    status: str = "stopped"

    def label(self) -> str:
        title = self.name.strip() or self.profile_id
        details: list[str] = []
        if self.group_name:
            details.append(self.group_name)
        if self.proxy_info:
            details.append(self.proxy_info)
        if details:
            return f"{title} ({', '.join(details)}) [{self.profile_id}]"
        return f"{title} [{self.profile_id}]"


@dataclass(frozen=True)
class MoreLoginLaunchSettings:
    profile_id: str = ""
    api_base: str = DEFAULT_MORELOGIN_API
    extra_args: list[str] = field(default_factory=list)
    headless: bool = False
    cdp_evasion: bool = True
    close_on_stop: bool = True
    launch_timeout_ms: int = 35000

    @property
    def identifier(self) -> str:
        return self.profile_id


class MoreLoginApiError(RuntimeError):
    pass


class MoreLoginBrowserManager:
    """Manages MoreLogin browser profiles, starts them with camera injection args, and connects Playwright via CDP."""

    def __init__(self, api_base: str = DEFAULT_MORELOGIN_API):
        self.api_base = api_base.rstrip("/")
        self._active_env_id: str | None = None
        self._active_debug_port: int | None = None
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._page: Any = None
        self._settings: MoreLoginLaunchSettings | None = None

    def _post(self, endpoint: str, payload: dict[str, Any], timeout_sec: float = 15.0) -> dict[str, Any]:
        url = f"{self.api_base}{endpoint}"
        body = json.dumps(payload).encode("utf-8")
        req = Request(
            url,
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urlopen(req, timeout=timeout_sec) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("code") != 0 and data.get("code") is not None:
                    msg = data.get("msg") or f"API error code {data.get('code')}"
                    raise MoreLoginApiError(f"MoreLogin API error on {endpoint}: {msg}")
                return data
        except HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            raise MoreLoginApiError(f"MoreLogin HTTP {e.code} error on {endpoint}: {err_body}") from e
        except URLError as e:
            raise MoreLoginApiError(
                f"Could not connect to MoreLogin Local API at {self.api_base}. "
                f"Ensure MoreLogin Client is running. Error: {e}"
            ) from e

    def check_health(self) -> bool:
        """Check if MoreLogin Local API is accessible."""
        try:
            res = self._post("/api/env/page", {"pageNo": 1, "pageSize": 1}, timeout_sec=3.0)
            return res.get("code") == 0
        except Exception:
            return False

    def list_profiles(self, page_no: int = 1, page_size: int = 50) -> list[MoreLoginProfile]:
        """Fetch all browser profiles from MoreLogin."""
        res = self._post("/api/env/page", {"pageNo": page_no, "pageSize": page_size})
        data = res.get("data") or {}
        raw_list = data.get("dataList") or []
        profiles: list[MoreLoginProfile] = []
        for item in raw_list:
            p_id = str(item.get("id") or "")
            if not p_id:
                continue
            name = str(item.get("envName") or "")
            group_name = str(item.get("groupName") or "")
            proxy_data = item.get("proxy") or {}
            proxy_str = ""
            if proxy_data and isinstance(proxy_data, dict):
                proxy_str = proxy_data.get("proxyName") or f"{proxy_data.get('proxyIp')}:{proxy_data.get('proxyPort')}"
            profiles.append(
                MoreLoginProfile(
                    profile_id=p_id,
                    name=name,
                    group_name=group_name,
                    proxy_info=proxy_str,
                )
            )
        return profiles

    def get_status(self, env_id: str) -> dict[str, Any]:
        """Get running status and debug port for a profile."""
        res = self._post("/api/env/status", {"envId": env_id})
        return res.get("data") or {}

    def start_profile(
        self,
        settings: MoreLoginLaunchSettings,
    ) -> int:
        """Starts a MoreLogin browser profile and returns its CDP debug port."""
        env_id = settings.profile_id
        if not env_id:
            raise ValueError("Profile ID must not be empty.")

        # Check if already running
        status_info = self.get_status(env_id)
        if status_info.get("status") in {"started", "running"}:
            port = status_info.get("debugPort")
            if port:
                try:
                    self._active_env_id = env_id
                    self._active_debug_port = int(port)
                    LOGGER.info("Profile %s is already running on port %d", env_id, self._active_debug_port)
                    return self._active_debug_port
                except ValueError:
                    pass

        payload: dict[str, Any] = {
            "envId": env_id,
            "isHeadless": settings.headless,
            "cdpEvasion": settings.cdp_evasion,
        }
        if settings.extra_args:
            payload["args"] = settings.extra_args

        LOGGER.info("Starting MoreLogin profile %s with args: %s", env_id, settings.extra_args)
        start_res = self._post("/api/env/start", payload, timeout_sec=settings.launch_timeout_ms / 1000.0)
        data = start_res.get("data") or {}

        debug_port_raw = data.get("debugPort")
        if not debug_port_raw:
            deadline = time.time() + 10.0
            while time.time() < deadline:
                time.sleep(1.0)
                st = self.get_status(env_id)
                if st.get("debugPort"):
                    debug_port_raw = st.get("debugPort")
                    break

        if not debug_port_raw:
            raise MoreLoginApiError(f"MoreLogin started profile {env_id} but did not return a debugPort: {start_res}")

        debug_port = int(debug_port_raw)
        self._active_env_id = env_id
        self._active_debug_port = debug_port
        LOGGER.info("MoreLogin profile %s started successfully on debugPort %d", env_id, debug_port)
        return debug_port

    def start(
        self,
        settings: MoreLoginLaunchSettings,
        start_url: str | None = None,
    ) -> Any:
        """High-level launcher: starts profile, connects Playwright over CDP, selects work page, and returns it."""
        if not settings.profile_id:
            raise ValueError("MoreLogin profile ID is required.")

        if self._page and not self._page.is_closed():
            return self._page

        from playwright.sync_api import sync_playwright

        debug_port = self.start_profile(settings)
        ws_url = f"http://127.0.0.1:{debug_port}"

        self._playwright = sync_playwright().start()
        try:
            self._browser = self._playwright.chromium.connect_over_cdp(
                ws_url,
                timeout=settings.launch_timeout_ms,
            )
        except Exception:
            if self._playwright:
                self._playwright.stop()
                self._playwright = None
            raise

        self._context = (
            self._browser.contexts[0] if self._browser.contexts else self._browser.new_context()
        )
        self._page = self._pick_work_page(self._context)
        self._settings = settings

        if start_url:
            self._page.goto(start_url, wait_until="domcontentloaded")

        return self._page

    @staticmethod
    def _pick_work_page(context: Any) -> Any:
        """Finds a content page, filtering out internal DevTools and extension background pages."""
        time.sleep(1.5)
        # Search backwards for a non-devtools, non-extension page
        for page in reversed(context.pages):
            if not page.is_closed():
                url = page.url.lower()
                if not url.startswith(("devtools://", "chrome-extension://", "about:blank#blocked")):
                    try:
                        page.bring_to_front()
                    except Exception:
                        pass
                    return page

        # If all existing tabs are devtools/extensions, create a fresh one
        new_page = context.new_page()
        try:
            new_page.bring_to_front()
        except Exception:
            pass
        return new_page

    def active_page(self) -> Any:
        if self._page and not self._page.is_closed():
            return self._page
        if self._context:
            for page in reversed(self._context.pages):
                if not page.is_closed():
                    url = page.url.lower()
                    if not url.startswith(("devtools://", "chrome-extension://")):
                        self._page = page
                        return page
        return self._page

    def stop(self) -> None:
        """Stops Playwright and closes MoreLogin profile."""
        target_id = self._active_env_id
        if self._browser:
            try:
                self._browser.close()
            except Exception as e:
                LOGGER.debug("Error closing Playwright browser: %s", e)
            self._browser = None

        if self._playwright:
            try:
                self._playwright.stop()
            except Exception as e:
                LOGGER.debug("Error stopping Playwright: %s", e)
            self._playwright = None

        if target_id:
            LOGGER.info("Closing MoreLogin profile %s via API", target_id)
            try:
                self._post("/api/env/close", {"envId": target_id}, timeout_sec=10.0)
            except Exception as e:
                LOGGER.warning("Could not close profile %s cleanly: %s", target_id, e)

        self._active_env_id = None
        self._active_debug_port = None
        self._context = None
        self._page = None

    def close_profile(self, env_id: str | None = None) -> None:
        self.stop()

    def close(self, *args: Any, **kwargs: Any) -> None:
        self.stop()
