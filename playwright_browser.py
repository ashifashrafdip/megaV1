from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from playwright.sync_api import BrowserContext, Page, Playwright


class ChromiumBrowser:
    """Manage a persistent Chromium context with optional proxy and user agent."""

    def __init__(
        self,
        user_data_dir: str | Path = "browser_profile",
        *,
        headless: bool = False,
        proxy: str | dict[str, str] | None = None,
        user_agent: str | None = None,
        viewport: dict[str, int] | None = None,
        device_scale_factor: float | None = None,
        is_mobile: bool = False,
        has_touch: bool = False,
        locale: str = "en-US",
        timezone_id: str = "UTC",
        color_scheme: str = "light",
        permissions: list[str] | None = None,
        extra_http_headers: dict[str, str] | None = None,
        chromium_args: list[str] | None = None,
        launch_timeout_ms: int = 30000,
    ):
        self.user_data_dir = Path(user_data_dir)
        self.headless = headless
        self.proxy = self._normalize_proxy(proxy)
        self.user_agent = user_agent
        self.viewport = viewport or {"width": 1280, "height": 720}
        self.device_scale_factor = device_scale_factor
        self.is_mobile = is_mobile
        self.has_touch = has_touch
        self.locale = locale
        self.timezone_id = timezone_id
        self.color_scheme = color_scheme
        self.permissions = permissions or []
        self.extra_http_headers = extra_http_headers or {}
        self.chromium_args = chromium_args or []
        self.launch_timeout_ms = launch_timeout_ms

        self.playwright: Playwright | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    def start(self) -> Page:
        """Launch Chromium in a persistent context and return the first page."""
        if self.context and self.page:
            return self.page

        try:
            from playwright.sync_api import sync_playwright
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Playwright is not installed. Run: pip install playwright"
            ) from exc

        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        self.playwright = sync_playwright().start()

        launch_options: dict[str, Any] = {
            "headless": self.headless,
            "viewport": self.viewport,
            "is_mobile": self.is_mobile,
            "has_touch": self.has_touch,
            "locale": self.locale,
            "timezone_id": self.timezone_id,
            "color_scheme": self.color_scheme,
            "args": self.chromium_args,
            "timeout": self.launch_timeout_ms,
            "bypass_csp": True,
        }

        if self.device_scale_factor:
            launch_options["device_scale_factor"] = self.device_scale_factor

        if self.proxy:
            launch_options["proxy"] = self.proxy

        if self.user_agent:
            launch_options["user_agent"] = self.user_agent

        if self.extra_http_headers:
            launch_options["extra_http_headers"] = self.extra_http_headers

        try:
            self.context = self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.user_data_dir),
                **launch_options,
            )
        except Exception:
            self.playwright.stop()
            self.playwright = None
            raise

        if self.permissions:
            self.context.grant_permissions(self.permissions)

        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        return self.page

    def stop(self):
        """Close the persistent context and stop Playwright."""
        if self.context:
            self.context.close()
            self.context = None
            self.page = None

        if self.playwright:
            self.playwright.stop()
            self.playwright = None

    def __enter__(self) -> Page:
        return self.start()

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()

    @staticmethod
    def _normalize_proxy(proxy: str | dict[str, str] | None) -> dict[str, str] | None:
        if not proxy:
            return None

        if isinstance(proxy, str):
            return {"server": proxy}

        return proxy
