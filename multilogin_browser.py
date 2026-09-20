from __future__ import annotations

import base64
import json
import logging
import os
import re
import socket
import ssl
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

LOGGER = logging.getLogger("desktop_app.multilogin")

DEFAULT_MLX_API = "https://127.0.0.1:45001"
DEFAULT_MLA_API = "http://127.0.0.1:35000"


@dataclass(frozen=True)
class MultiloginProfile:
    profile_id: str
    folder_id: str = ""
    name: str = ""
    browser_type: str = "mimic"
    group_name: str = ""
    status: str = ""

    def label(self) -> str:
        title = self.name.strip() or self.profile_id
        details: list[str] = []
        if self.browser_type:
            details.append(self.browser_type.capitalize())
        if self.group_name:
            details.append(self.group_name)
        if details:
            return f"{title} ({', '.join(details)}) - {self.profile_id[:8]}..."
        return f"{title} ({self.profile_id})"


def extract_local_multilogin_token() -> str | None:
    """Attempt to find a valid active Multilogin JWT token from local app storage."""
    try:
        app_data = os.environ.get("APPDATA")
        if not app_data:
            return None
        leveldb_path = Path(app_data) / "Multilogin.exe" / "EBWebView" / "Default" / "Local Storage" / "leveldb"
        if not leveldb_path.is_dir():
            return None
        jwt_pattern = re.compile(rb'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}')
        candidates: list[str] = []
        for file_path in leveldb_path.glob("*"):
            if not file_path.is_file():
                continue
            try:
                content = file_path.read_bytes()
                for match in jwt_pattern.findall(content):
                    candidates.append(match.decode("utf-8", errors="ignore"))
            except Exception:
                continue
        if not candidates:
            return None

        ctx = _create_ssl_context()

        def get_exp(tok: str) -> int:
            try:
                parts = tok.split(".")
                if len(parts) >= 2:
                    padding = 4 - len(parts[1]) % 4
                    raw_payload = base64.urlsafe_b64decode(parts[1] + "=" * padding)
                    payload = json.loads(raw_payload.decode("utf-8"))
                    return int(payload.get("exp", 0))
            except Exception:
                pass
            return 0

        # Sort candidate tokens so freshest expiration is tried first
        sorted_tokens = sorted(set(candidates), key=get_exp, reverse=True)
        for tok in sorted_tokens:
            try:
                req = Request(
                    "https://127.0.0.1:45001/api/v1/profile/statuses",
                    headers={"Authorization": f"Bearer {tok}", "Accept": "application/json"}
                )
                with urlopen(req, context=ctx, timeout=1.5) as resp:
                    if resp.status == 200:
                        LOGGER.info("Auto-detected active Multilogin session token from local storage.")
                        return tok
            except Exception:
                continue
    except Exception:
        pass
    return None


@dataclass(frozen=True)
class MultiloginLaunchSettings:
    profile_id: str = ""
    folder_id: str = ""
    api_base: str = DEFAULT_MLX_API
    token: str = ""
    api_version: str = "auto"  # 'auto', 'mlx', 'mla' / 'v1'
    direct_cdp_url: str = ""
    headless: bool = False
    close_on_stop: bool = True
    launch_timeout_ms: int = 30000

    @classmethod
    def from_config(
        cls,
        settings: Any,
        *,
        headless: bool = False,
        launch_timeout_ms: int = 30000,
    ) -> "MultiloginLaunchSettings":
        token = str(getattr(settings, "token", "")).strip()
        if not token:
            local_tok = extract_local_multilogin_token()
            if local_tok:
                token = local_tok
        return cls(
            profile_id=str(getattr(settings, "profile_id", "")).strip(),
            folder_id=str(getattr(settings, "folder_id", "")).strip(),
            api_base=str(getattr(settings, "api_base", DEFAULT_MLX_API)).rstrip("/"),
            token=token,
            api_version=str(getattr(settings, "api_version", "auto")).lower(),
            direct_cdp_url=str(getattr(settings, "direct_cdp_url", "")).strip(),
            headless=headless,
            close_on_stop=bool(getattr(settings, "close_on_stop", True)),
            launch_timeout_ms=launch_timeout_ms,
        )

    @property
    def identifier(self) -> str:
        return self.profile_id or self.direct_cdp_url


class MultiloginApiError(RuntimeError):
    pass


def _create_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _request_json(
    url: str,
    method: str = "GET",
    settings: MultiloginLaunchSettings | None = None,
    payload: dict[str, Any] | None = None,
    timeout_sec: float = 15.0,
    retry_auth: bool = True,
) -> dict[str, Any]:
    # Normalize launcher.mlx.yt and localhost to 127.0.0.1 to avoid Windows IPv6 NAT64 lookup delays
    if "://launcher.mlx.yt:" in url:
        url = url.replace("://launcher.mlx.yt:", "://127.0.0.1:")
    elif "://localhost:" in url:
        url = url.replace("://localhost:", "://127.0.0.1:")

    body = None
    headers = {"Accept": "application/json"}
    current_token = settings.token if settings else ""
    if current_token:
        headers["Authorization"] = f"Bearer {current_token}"

    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = Request(url, data=body, headers=headers, method=method)
    ssl_ctx = _create_ssl_context() if url.lower().startswith("https://") else None

    try:
        with urlopen(req, context=ssl_ctx, timeout=timeout_sec) as response:
            raw = response.read().decode("utf-8", errors="replace")
            if not raw.strip():
                return {}
            return json.loads(raw)
    except HTTPError as exc:
        raw_error = exc.read().decode("utf-8", errors="replace")
        detail = raw_error
        error_code = ""
        try:
            parsed = json.loads(raw_error)
            status_obj = parsed.get("status")
            if isinstance(status_obj, dict):
                error_code = str(status_obj.get("error_code") or "")
                msg = str(status_obj.get("message") or "")
                detail = f"{error_code}: {msg}" if error_code else (msg or raw_error)
            else:
                detail = parsed.get("message") or parsed.get("error") or raw_error
                error_code = str(parsed.get("error_code") or "")
        except Exception:
            pass

        # Check for expired or invalid token
        is_token_expired = (
            exc.code == 401
            or "EXPIRED_JWT_TOKEN" in error_code
            or "EXPIRED_JWT_TOKEN" in raw_error
            or "Authorization error" in detail
        )

        if is_token_expired and retry_auth and settings:
            fresh_token = extract_local_multilogin_token()
            if fresh_token and fresh_token != current_token:
                LOGGER.info("Multilogin token was expired. Automatically refreshed active token from local storage!")
                new_settings = MultiloginLaunchSettings(
                    profile_id=settings.profile_id,
                    folder_id=settings.folder_id,
                    api_base=settings.api_base,
                    token=fresh_token,
                    api_version=settings.api_version,
                    direct_cdp_url=settings.direct_cdp_url,
                    headless=settings.headless,
                    close_on_stop=settings.close_on_stop,
                    launch_timeout_ms=settings.launch_timeout_ms,
                )
                return _request_json(
                    url,
                    method=method,
                    settings=new_settings,
                    payload=payload,
                    timeout_sec=timeout_sec,
                    retry_auth=False,
                )

        if is_token_expired:
            raise MultiloginApiError(
                "Multilogin API token is expired or unauthorized (EXPIRED_JWT_TOKEN).\n"
                "Multilogin regular tokens expire after 30-60 minutes.\n\n"
                "How to fix:\n"
                "1. Open the Multilogin app on this PC (make sure you are signed in).\n"
                "2. Click 'Info' at the bottom-left corner -> Click 'Copy' next to 'API token'.\n"
                "3. In AutomationHub, paste the token into the 'API Token' field and start again."
            ) from exc

        if "PROFILE_ALREADY_RUNNING" in error_code or "PROFILE_ALREADY_RUNNING" in raw_error:
            raise MultiloginApiError(f"PROFILE_ALREADY_RUNNING: {detail}") from exc

        raise MultiloginApiError(f"HTTP {exc.code} from Multilogin: {detail}") from exc
    except URLError as exc:
        raise MultiloginApiError(f"Cannot reach Multilogin at {url}: {exc.reason}") from exc
    except Exception as exc:
        if isinstance(exc, MultiloginApiError):
            raise
        raise MultiloginApiError(f"Multilogin request failed ({url}): {exc}") from exc


def is_port_open(host: str, port: int, timeout: float = 0.2) -> bool:
    if host.lower() in {"launcher.mlx.yt", "localhost"}:
        host = "127.0.0.1"
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def unlock_multilogin_profile_cloud(profile_id: str, folder_id: str = "", token: str = "") -> bool:
    """Removes active session lock from Multilogin Cloud backend."""
    if not token:
        token = extract_local_multilogin_token() or ""
    if not token:
        return False
    if not folder_id:
        folder_id = find_mlx_folder_id(profile_id)

    url = "https://api.multilogin.com/bpds/profile/lock"
    payload = json.dumps({"folder_id": folder_id, "profile_id": profile_id}).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    }
    req = Request(url, data=payload, headers=headers, method="DELETE")
    ctx = _create_ssl_context()
    try:
        with urlopen(req, context=ctx, timeout=8.0) as resp:
            if resp.status == 200:
                LOGGER.info("Successfully unlocked Multilogin profile %s in cloud.", profile_id)
                return True
    except Exception as exc:
        LOGGER.warning("Auto-unlock request for profile %s returned: %s", profile_id, exc)
    return False


def _sanitize_cdp_endpoint_tabs(cdp_endpoint: str) -> None:
    """Ensure browser has a responsive tab ready and close any stuck proxy checking tabs (e.g. whoer.net)."""
    try:
        http_base = cdp_endpoint
        if http_base.startswith("ws://"):
            p = urlparse(http_base)
            http_base = f"http://{p.netloc}"
        elif not http_base.startswith("http://") and not http_base.startswith("https://"):
            http_base = f"http://{http_base}"

        list_url = f"{http_base}/json/list"
        req = Request(list_url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=1.5) as resp:
            targets = json.loads(resp.read().decode("utf-8"))

        has_whoer = any("whoer.net" in (t.get("url") or "") for t in targets)
        if has_whoer:
            # Create a clean blank tab first
            try:
                new_req = Request(f"{http_base}/json/new", method="PUT")
                with urlopen(new_req, timeout=1.5):
                    pass
            except Exception:
                pass
            # Close the blocking proxy check tab
            for t in targets:
                if "whoer.net" in (t.get("url") or ""):
                    tid = t.get("id")
                    if tid:
                        try:
                            close_req = Request(f"{http_base}/json/close/{tid}", method="PUT")
                            with urlopen(close_req, timeout=1.5):
                                pass
                        except Exception:
                            pass
    except Exception as exc:
        LOGGER.debug("Could not sanitize CDP tabs: %s", exc)


def detect_active_cdp_endpoint(timeout_sec: float = 0.25) -> str | None:
    """Scan common and active local remote debugging ports to find an already active browser."""
    candidate_ports: list[int] = [9222, 9223, 9224, 9225, 9333, 35100, 35101, 35102, 45100, 45101, 45102]
    # Dynamically discover listening TCP ports on 127.0.0.1
    try:
        import subprocess
        out = subprocess.check_output(["netstat", "-ano", "-p", "tcp"], text=True, errors="ignore")
        for line in out.splitlines():
            if "LISTENING" in line and "127.0.0.1:" in line:
                m = re.search(r"127\.0\.0\.1:(\d+)", line)
                if m:
                    p = int(m.group(1))
                    if 1024 < p < 65535 and p not in (45001, 35000, 50325) and p not in candidate_ports:
                        candidate_ports.append(p)
    except Exception:
        pass

    for port in candidate_ports:
        if not is_port_open("127.0.0.1", port, timeout=0.08):
            continue
        try:
            url = f"http://127.0.0.1:{port}/json/version"
            req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req, timeout=timeout_sec) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("webSocketDebuggerUrl") or data.get("Browser"):
                    return f"127.0.0.1:{port}"
        except Exception:
            continue
    return None


def list_multilogin_profiles(
    settings: Any,
    *,
    timeout_ms: int = 1000,
) -> list[MultiloginProfile]:
    """Discover profiles from Multilogin (detecting MLX on port 45001 or MLA on port 35000)."""
    launch_settings = MultiloginLaunchSettings.from_config(
        settings,
        launch_timeout_ms=timeout_ms,
    )
    timeout_sec = min(1.0, max(0.3, timeout_ms / 1000.0))

    # If direct CDP url is configured, synthesize a profile
    if launch_settings.direct_cdp_url:
        return [
            MultiloginProfile(
                profile_id="direct-cdp",
                name=f"Direct CDP ({launch_settings.direct_cdp_url})",
                browser_type="cdp",
            )
        ]

    # Multilogin X / MLA status quick detection
    mlx_open = is_port_open("127.0.0.1", 45001, timeout=0.1)
    mla_open = is_port_open("127.0.0.1", 35000, timeout=0.1)

    if mlx_open:
        mlx_profiles = _fetch_mlx_profiles(launch_settings, timeout_sec=timeout_sec)
        if mlx_profiles:
            return mlx_profiles

    # Classic MLA (port 35000) supports /api/v1/profile/list
    if mla_open:
        try:
            profiles = _try_fetch_profiles_from_base("http://127.0.0.1:35000", launch_settings, timeout_sec)
            if profiles:
                return profiles
        except Exception:
            pass

    profiles: list[MultiloginProfile] = []
    if launch_settings.profile_id and launch_settings.profile_id not in {"mlx-agent", "mla-agent", "direct-cdp"}:
        profiles.append(
            MultiloginProfile(
                profile_id=launch_settings.profile_id,
                folder_id=launch_settings.folder_id,
                name="Current Saved Profile",
                status="Saved",
            )
        )

    if mlx_open:
        profiles.append(
            MultiloginProfile(
                profile_id="mlx-agent",
                name="Multilogin X Ready (Enter Profile ID or click Auto-Detect)",
                status="Online",
            )
        )
    elif mla_open:
        profiles.append(
            MultiloginProfile(
                profile_id="mla-agent",
                name="Multilogin MLA Ready (Enter Profile ID or click Auto-Detect)",
                status="Online",
            )
        )

    return profiles


def find_mlx_folder_id(profile_id: str) -> str:
    """Find folder_id for a given profile_id from local disk or default."""
    try:
        user_home = Path.home()
        mlx_profiles_root = user_home / "mlx" / "profiles"
        if mlx_profiles_root.is_dir():
            for user_id_dir in mlx_profiles_root.iterdir():
                if not user_id_dir.is_dir():
                    continue
                for folder_dir in user_id_dir.iterdir():
                    if not folder_dir.is_dir():
                        continue
                    target = folder_dir / profile_id
                    if target.is_dir():
                        return folder_dir.name
    except Exception:
        pass
    return "default"


def _fetch_mlx_profiles(settings: MultiloginLaunchSettings, timeout_sec: float = 1.0) -> list[MultiloginProfile]:
    profiles: list[MultiloginProfile] = []
    seen_ids = set()

    # 1. Try local launcher profile/statuses with token
    for base in ("https://launcher.mlx.yt:45001", "http://127.0.0.1:45001"):
        try:
            url = f"{base}/api/v1/profile/statuses"
            res = _request_json(url, "GET", settings, timeout_sec=timeout_sec)
            states = (res.get("data") or {}).get("states") or {}
            for pid, info in states.items():
                if isinstance(info, dict):
                    actual_id = str(info.get("profile_id") or pid).strip()
                    if actual_id and actual_id not in seen_ids:
                        seen_ids.add(actual_id)
                        profiles.append(
                            MultiloginProfile(
                                profile_id=actual_id,
                                folder_id=str(info.get("folder_id") or "").strip(),
                                name=str(info.get("name") or f"Profile {actual_id[:8]}").strip(),
                                browser_type=str(info.get("browser_type") or "mimic").lower(),
                                status=str(info.get("status") or "Ready").strip(),
                            )
                        )
        except Exception:
            continue

    # 2. Check local disk for profiles under %USERPROFILE%/mlx/profiles/*/*/*
    try:
        user_home = Path.home()
        mlx_profiles_root = user_home / "mlx" / "profiles"
        if mlx_profiles_root.is_dir():
            for user_id_dir in mlx_profiles_root.iterdir():
                if not user_id_dir.is_dir():
                    continue
                for folder_dir in user_id_dir.iterdir():
                    if not folder_dir.is_dir():
                        continue
                    folder_id = folder_dir.name
                    for prof_dir in folder_dir.iterdir():
                        if not prof_dir.is_dir():
                            continue
                        prof_id = prof_dir.name
                        if len(prof_id) >= 32 and "-" in prof_id and prof_id not in seen_ids:
                            seen_ids.add(prof_id)
                            profiles.append(
                                MultiloginProfile(
                                    profile_id=prof_id,
                                    folder_id=folder_id,
                                    name=f"Multilogin Profile ({prof_id[:8]}...)",
                                    browser_type="mimic",
                                    status="Ready",
                                )
                            )
    except Exception:
        pass

    return profiles


def _try_fetch_profiles_from_base(
    base: str,
    settings: MultiloginLaunchSettings,
    timeout_sec: float,
) -> list[MultiloginProfile]:
    profiles: list[MultiloginProfile] = []

    # Try MLX endpoints first
    for endpoint in ("/api/v2/profile/list", "/api/v1/profile/list", "/api/v3/profile/list"):
        try:
            res = _request_json(f"{base}{endpoint}", "GET", settings, timeout_sec=timeout_sec)
            items = res.get("data") or res.get("profiles") or res.get("value") or []
            if isinstance(items, dict) and "list" in items:
                items = items["list"]
            if isinstance(items, list) and items:
                for item in items:
                    p_id = str(item.get("id") or item.get("uuid") or item.get("profile_id") or "").strip()
                    if not p_id:
                        continue
                    profiles.append(
                        MultiloginProfile(
                            profile_id=p_id,
                            folder_id=str(item.get("folder_id") or item.get("folder") or "").strip(),
                            name=str(item.get("name") or "").strip(),
                            browser_type=str(item.get("browser_type") or item.get("browser") or "mimic").lower(),
                            group_name=str(item.get("group_name") or item.get("group") or "").strip(),
                            status=str(item.get("status") or "").strip(),
                        )
                    )
                if profiles:
                    return profiles
        except Exception:
            pass

    # Try MLA v1 endpoints (classic MLA)
    try:
        res = _request_json(f"{base}/api/v1/profile/list", "GET", settings, timeout_sec=timeout_sec)
        items = res.get("value") or res.get("data") or []
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    p_id = str(item.get("id") or item.get("uuid") or item.get("profile_id") or "").strip()
                    if not p_id:
                        continue
                    profiles.append(
                        MultiloginProfile(
                            profile_id=p_id,
                            name=str(item.get("name") or "").strip(),
                            browser_type=str(item.get("browser_type") or "mimic").lower(),
                            group_name=str(item.get("group_name") or "").strip(),
                        )
                    )
            if profiles:
                return profiles
    except Exception:
        pass

    return profiles


class MultiloginBrowserManager:
    """Manage a Multilogin profile launch and connect Playwright Chromium over CDP."""

    def __init__(self):
        self._settings: MultiloginLaunchSettings | None = None
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._started_profile_id: str | None = None

    @property
    def context(self):
        if not self._context:
            raise RuntimeError("No active Multilogin browser context. Call start() first.")
        return self._context

    def start(
        self,
        settings: MultiloginLaunchSettings,
        *,
        start_url: str | None = None,
    ):
        if self._page and not self._page.is_closed():
            return self._page

        try:
            from playwright.sync_api import sync_playwright
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Playwright is not installed. Run: pip install playwright"
            ) from exc

        # 1. Direct CDP mode
        if settings.direct_cdp_url:
            cdp_url = settings.direct_cdp_url
            if not cdp_url.startswith("ws://") and not cdp_url.startswith("http://"):
                cdp_url = f"http://{cdp_url}"
            _sanitize_cdp_endpoint_tabs(cdp_url)
            LOGGER.info("Connecting directly to CDP at %s", cdp_url)
            self._playwright = sync_playwright().start()
            try:
                self._browser = self._playwright.chromium.connect_over_cdp(
                    cdp_url,
                    timeout=settings.launch_timeout_ms,
                )
            except Exception:
                self._playwright.stop()
                self._playwright = None
                raise
            self._context = (
                self._browser.contexts[0]
                if self._browser.contexts
                else self._browser.new_context()
            )
            self._page = self._pick_work_page(self._context)
            self._settings = settings
            if start_url:
                self._page.goto(start_url, wait_until="domcontentloaded")
            return self._page

        if not settings.profile_id:
            raise ValueError("Multilogin profile ID is required.")

        # 2. Launch profile via Multilogin API
        cdp_endpoint = self._start_profile(settings)
        _sanitize_cdp_endpoint_tabs(cdp_endpoint)
        LOGGER.info("Multilogin browser launched. CDP endpoint: %s", cdp_endpoint)

        self._playwright = sync_playwright().start()
        try:
            self._browser = self._playwright.chromium.connect_over_cdp(
                cdp_endpoint,
                timeout=settings.launch_timeout_ms,
            )
        except Exception:
            self._playwright.stop()
            self._playwright = None
            raise

        self._context = (
            self._browser.contexts[0]
            if self._browser.contexts
            else self._browser.new_context()
        )
        self._page = self._pick_work_page(self._context)
        self._settings = settings
        self._started_profile_id = settings.profile_id

        if start_url:
            self._page.goto(start_url, wait_until="domcontentloaded")

        return self._page

    @staticmethod
    def _pick_work_page(context):
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
        raise RuntimeError("No active Multilogin browser page.")

    def stop(self):
        settings = self._settings
        profile_id = self._started_profile_id

        if self._browser:
            self._browser = None
            self._context = None
            self._page = None

        if self._playwright:
            self._playwright.stop()
            self._playwright = None

        if settings and settings.close_on_stop and profile_id:
            self._stop_profile(settings, profile_id)

        self._settings = None
        self._started_profile_id = None

    def _start_profile(self, settings: MultiloginLaunchSettings) -> str:
        base = settings.api_base.rstrip("/")
        timeout_sec = max(10.0, settings.launch_timeout_ms / 1000.0)
        p_id = settings.profile_id
        f_id = settings.folder_id or find_mlx_folder_id(p_id)

        # Check if browser is already running on a CDP port before launching
        detected_early = detect_active_cdp_endpoint(timeout_sec=0.2)
        if detected_early:
            if settings.direct_cdp_url:
                return settings.direct_cdp_url
            if p_id in ("mlx-agent", "mla-agent", "", None):
                LOGGER.info("Active Multilogin browser detected on %s - connecting directly.", detected_early)
                return detected_early

        candidate_bases = [base]
        for fb in ("http://127.0.0.1:45001", DEFAULT_MLX_API, DEFAULT_MLA_API):
            if fb not in candidate_bases:
                candidate_bases.append(fb)

        # Prioritize bases with open TCP ports
        open_bases = []
        for b in candidate_bases:
            try:
                p = urlparse(b)
                host = p.hostname or "127.0.0.1"
                port = p.port or (443 if p.scheme == "https" else 80)
                if is_port_open(host, port, timeout=0.2):
                    open_bases.append(b)
            except Exception:
                continue
        if not open_bases:
            open_bases = candidate_bases

        start_urls = []
        for b in open_bases:
            start_urls.extend([
                f"{b}/api/v2/profile/f/{quote(f_id)}/p/{quote(p_id)}/start?automation_type=playwright&headless_mode={'true' if settings.headless else 'false'}",
                f"{b}/api/v2/profile/f/{quote(f_id)}/p/{quote(p_id)}/start?automation_type=selenium&headless_mode={'true' if settings.headless else 'false'}",
                f"{b}/api/v1/profile/start?profileId={quote(p_id)}&automation=true",
                f"{b}/api/v1/profile/start?profile_id={quote(p_id)}&automation_type=playwright",
                f"{b}/api/v2/profile/start?profile_id={quote(p_id)}&automation_type=playwright",
                f"{b}/api/v1/profile/start?profileId={quote(p_id)}",
            ])

        last_error = None
        for url in start_urls:
            try:
                LOGGER.info("Attempting Multilogin start: %s", url)
                res = _request_json(url, "GET", settings, timeout_sec=timeout_sec)
                endpoint = self._extract_cdp_endpoint(res)
                if endpoint:
                    return endpoint
            except MultiloginApiError as exc:
                err_str = str(exc)
                if "EXPIRED_JWT_TOKEN" in err_str or "unauthorized" in err_str.lower():
                    # Fast-fail so we don't crash socket and mask error with WinError 10054
                    raise
                if "can't lock profile" in err_str.lower() or "lock_profile_error" in err_str.lower():
                    LOGGER.info("Profile %s is locked in Multilogin cloud. Attempting automatic unlock...", p_id)
                    unlock_multilogin_profile_cloud(p_id, f_id, settings.token)
                    time.sleep(1.5)
                    try:
                        res = _request_json(url, "GET", settings, timeout_sec=timeout_sec)
                        endpoint = self._extract_cdp_endpoint(res)
                        if endpoint:
                            return endpoint
                    except Exception as retry_exc:
                        last_error = retry_exc
                        continue
                if "PROFILE_ALREADY_RUNNING" in err_str:
                    LOGGER.info("Multilogin profile %s is already running without automation port. Stopping and restarting...", p_id)
                    self._stop_profile(settings, p_id)
                    time.sleep(2.0)
                    try:
                        res = _request_json(url, "GET", settings, timeout_sec=timeout_sec)
                        endpoint = self._extract_cdp_endpoint(res)
                        if endpoint:
                            return endpoint
                    except Exception as retry_exc:
                        last_error = retry_exc
                        continue
                last_error = exc
                continue
            except Exception as exc:
                last_error = exc
                continue

        # Check if browser was started on a local CDP port
        time.sleep(1.0)
        detected = detect_active_cdp_endpoint(timeout_sec=0.5)
        if detected:
            LOGGER.info("Detected running Multilogin browser on CDP port %s", detected)
            return detected

        raise MultiloginApiError(
            f"Failed to start Multilogin profile '{p_id}'.\n"
            f"Make sure Multilogin X (port 45001) or Multilogin 6 / MLA (port 35000) is running, "
            f"or start the profile inside Multilogin and click 'Auto-Detect Active Browser'.\n"
            f"Details: {last_error}"
        )

    def _stop_profile(self, settings: MultiloginLaunchSettings, profile_id: str):
        base = settings.api_base.rstrip("/")
        stop_urls = [
            f"{base}/api/v1/profile/stop/p/{quote(profile_id)}",
            f"{base}/api/v1/profile/stop_all?type=all",
            f"{base}/api/v2/profile/stop?profile_id={quote(profile_id)}",
            f"{base}/api/v1/profile/stop?profileId={quote(profile_id)}",
        ]
        for url in stop_urls:
            try:
                _request_json(url, "GET", settings, timeout_sec=10.0)
                LOGGER.info("Multilogin profile %s stopped via %s", profile_id, url)
                return
            except Exception:
                pass

    @staticmethod
    def _extract_cdp_endpoint(response: dict[str, Any]) -> str:
        """Extract WebSocket URL or http endpoint from Multilogin API response."""
        # 1. Check value directly
        value = response.get("value")
        if isinstance(value, str) and value.strip():
            val = value.strip()
            if val.startswith("ws://") or val.startswith("http://"):
                return val
            if ":" in val:
                return f"http://{val}"
            if val.isdigit():
                return f"http://127.0.0.1:{val}"

        # 2. Check value as dictionary
        if isinstance(value, dict):
            port = value.get("port")
            ws = value.get("ws") or value.get("puppeteer")
            if ws:
                return str(ws)
            if port:
                return f"http://127.0.0.1:{port}"

        # 3. Check data dictionary (common in MLX)
        data = response.get("data")
        if isinstance(data, dict):
            ws = data.get("ws") or data.get("value")
            port = data.get("port")
            if isinstance(ws, dict):
                ws_val = ws.get("puppeteer") or ws.get("playwright")
                if ws_val:
                    return str(ws_val)
            if isinstance(ws, str) and ws:
                return ws
            if port:
                return f"http://127.0.0.1:{port}"

        # 4. Check port field directly
        port = response.get("port")
        if port:
            return f"http://127.0.0.1:{port}"

        raise MultiloginApiError(
            f"Unexpected Multilogin response format, could not extract CDP address: {response}"
        )
