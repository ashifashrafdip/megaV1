from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from auth_config import AuthSettings
import sys


def get_default_config_path() -> Path:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        target = exe_dir / "config.json"
        if not target.exists():
            meipass_config = Path(getattr(sys, "_MEIPASS", "")) / "config.json"
            if meipass_config.is_file():
                try:
                    import shutil

                    shutil.copy2(meipass_config, target)
                    return target
                except Exception:
                    return meipass_config
        return target
    return Path(__file__).resolve().parent / "config.json"


CONFIG_FILE = get_default_config_path()
DEFAULT_PROXY_TYPE = "http"
DEFAULT_PROXY_PORTS = {"http": "8080", "socks5": "1080"}
SUPPORTED_PROXY_TYPES = {"http", "socks5"}


@dataclass(frozen=True)
class LivenessTimelineMark:
    start_ms: int
    position: str
    label: str = ""


def default_liveness_timeline() -> tuple[LivenessTimelineMark, ...]:
    return (
        LivenessTimelineMark(0, "center", "0-2.5s center"),
        LivenessTimelineMark(2500, "left", "2.5-5.5s center to left"),
        LivenessTimelineMark(5500, "center", "5.5-7s left to center"),
        LivenessTimelineMark(7000, "left", "7-10s center to left"),
        LivenessTimelineMark(10000, "center", "10-13s left to center"),
    )


def parse_liveness_timeline(raw: Any) -> tuple[LivenessTimelineMark, ...]:
    if not isinstance(raw, list) or not raw:
        return default_liveness_timeline()

    marks: list[LivenessTimelineMark] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        if "start_ms" in item:
            start_ms = max(0, int(item["start_ms"]))
        else:
            start_ms = max(0, int(float(item.get("start_sec", 0)) * 1000))
        position = str(item.get("position", "center")).strip().lower() or "center"
        label = str(item.get("label", "")).strip()
        marks.append(LivenessTimelineMark(start_ms, position, label))

    if not marks:
        return default_liveness_timeline()

    marks.sort(key=lambda mark: mark.start_ms)
    return tuple(marks)


def liveness_timeline_to_json(
    timeline: tuple[LivenessTimelineMark, ...],
) -> str:
    payload = [
        {
            "startMs": mark.start_ms,
            "position": mark.position,
            "label": mark.label,
        }
        for mark in timeline
    ]
    return json.dumps(payload, ensure_ascii=True)


def normalize_proxy_type(value: str | None) -> str:
    normalized = str(value or "").strip().lower().replace("-", "").replace("_", "")
    if normalized in {"socks", "socks5", "sock5", "shoks5"}:
        return "socks5"
    if normalized in SUPPORTED_PROXY_TYPES:
        return normalized
    return DEFAULT_PROXY_TYPE


def parse_proxy_server(server: str, fallback_type: str = DEFAULT_PROXY_TYPE) -> dict[str, str]:
    raw_server = server.strip()
    if not raw_server:
        return {
            "proxy_type": normalize_proxy_type(fallback_type),
            "host": "",
            "port": "",
            "username": "",
            "password": "",
        }

    parse_target = raw_server if "://" in raw_server else f"{fallback_type}://{raw_server}"
    parsed = urlparse(parse_target)

    try:
        port = str(parsed.port or "")
    except ValueError:
        port = ""

    return {
        "proxy_type": normalize_proxy_type(parsed.scheme or fallback_type),
        "host": parsed.hostname or "",
        "port": port,
        "username": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
    }


@dataclass(frozen=True)
class ProxySettings:
    enabled: bool = False
    proxy_type: str = DEFAULT_PROXY_TYPE
    host: str = "127.0.0.1"
    port: str = "8080"
    username: str = ""
    password: str = ""

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "ProxySettings":
        raw = raw or {}
        server = str(raw.get("server", "")).strip()
        explicit_type = raw.get("type") or raw.get("proxy_type")
        parsed_server = parse_proxy_server(
            server,
            normalize_proxy_type(explicit_type),
        )
        proxy_type = normalize_proxy_type(
            parsed_server["proxy_type"] if "://" in server else explicit_type or parsed_server["proxy_type"]
        )
        host = str(raw.get("host", "")).strip()
        port = str(raw.get("port", "")).strip()
        return cls(
            enabled=bool(raw.get("enabled", False)),
            proxy_type=proxy_type,
            host=host or parsed_server["host"] or "127.0.0.1",
            port=port or parsed_server["port"] or DEFAULT_PROXY_PORTS[proxy_type],
            username=str(raw.get("username", "")) or parsed_server["username"],
            password=str(raw.get("password", "")) or parsed_server["password"],
        )

    @property
    def server(self) -> str:
        host = self.host.strip()
        proxy_type = normalize_proxy_type(self.proxy_type)
        port = self.port.strip()

        if "://" in host:
            parsed_server = parse_proxy_server(host, proxy_type)
            proxy_type = parsed_server["proxy_type"]
            host = parsed_server["host"]
            port = port or parsed_server["port"]

        if ":" in host and not port and host.count(":") == 1:
            possible_host, possible_port = host.rsplit(":", 1)
            if possible_port.isdigit():
                host = possible_host
                port = possible_port

        if not host:
            return ""

        server_host = host
        if ":" in server_host and not server_host.startswith("[") and not server_host.endswith("]"):
            server_host = f"[{server_host}]"

        if port:
            return f"{proxy_type}://{server_host}:{port}"
        return f"{proxy_type}://{server_host}"

    def to_playwright_proxy(self) -> dict[str, str] | None:
        if not self.enabled or not self.host.strip():
            return None

        proxy = {
            "server": self.server,
            "bypass": "<-loopback>,127.0.0.1,localhost",
        }
        if self.username:
            proxy["username"] = self.username
        if self.password:
            proxy["password"] = self.password
        return proxy


@dataclass(frozen=True)
class WindowSize:
    width: int = 1280
    height: int = 720

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "WindowSize":
        raw = raw or {}
        return cls(
            width=max(320, int(raw.get("width", 1280))),
            height=max(240, int(raw.get("height", 720))),
        )

    def to_viewport(self) -> dict[str, int]:
        return {"width": self.width, "height": self.height}


@dataclass(frozen=True)
class CameraOutputSize:
    width: int = 1080
    height: int = 1980

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "CameraOutputSize":
        raw = raw or {}
        return cls(
            width=max(160, int(raw.get("width", 1080))),
            height=max(160, int(raw.get("height", 1980))),
        )


@dataclass(frozen=True)
class AutomationSettings:
    click_retries: int = 3
    camera_warmup_ms: int = 5000
    step_settle_ms: int = 2000
    capture_settle_ms: int = 2500
    post_capture_ms: int = 2000
    liveness_timeout_ms: int = 180000
    liveness_upload_mode: str = "live_recording"
    liveness_step_ms: int = 6000
    liveness_step_jitter_ms: int = 800
    liveness_retry_count: int = 1
    liveness_min_duration_seconds: int = 13
    human_delay_jitter_ms: int = 400
    liveness_timeline: tuple[LivenessTimelineMark, ...] = field(
        default_factory=default_liveness_timeline
    )

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "AutomationSettings":
        raw = raw or {}
        upload_mode = str(raw.get("liveness_upload_mode", "live_recording")).strip()
        if upload_mode not in {"live_recording", "file3_swap"}:
            upload_mode = "live_recording"
        timeline = parse_liveness_timeline(raw.get("liveness_timeline"))
        return cls(
            click_retries=max(1, int(raw.get("click_retries", 3))),
            camera_warmup_ms=max(500, int(raw.get("camera_warmup_ms", 5000))),
            step_settle_ms=max(250, int(raw.get("step_settle_ms", 2000))),
            capture_settle_ms=max(500, int(raw.get("capture_settle_ms", 2500))),
            post_capture_ms=max(500, int(raw.get("post_capture_ms", 2000))),
            liveness_timeout_ms=max(10000, int(raw.get("liveness_timeout_ms", 180000))),
            liveness_upload_mode=upload_mode,
            liveness_step_ms=max(3000, int(raw.get("liveness_step_ms", 6000))),
            liveness_step_jitter_ms=max(0, int(raw.get("liveness_step_jitter_ms", 800))),
            liveness_retry_count=max(0, int(raw.get("liveness_retry_count", 1))),
            liveness_min_duration_seconds=max(
                10, int(raw.get("liveness_min_duration_seconds", 13))
            ),
            human_delay_jitter_ms=max(0, int(raw.get("human_delay_jitter_ms", 400))),
            liveness_timeline=timeline,
        )


@dataclass(frozen=True)
class MultiloginSettings:
    api_base: str = "https://launcher.mlx.yt:45001"
    profile_id: str = ""
    folder_id: str = ""
    token: str = ""
    api_version: str = "auto"
    direct_cdp_url: str = ""
    close_on_stop: bool = True

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "MultiloginSettings":
        raw = raw or {}
        return cls(
            api_base=str(raw.get("api_base", "https://launcher.mlx.yt:45001")).rstrip("/"),
            profile_id=str(raw.get("profile_id", "")).strip(),
            folder_id=str(raw.get("folder_id", "")).strip(),
            token=str(raw.get("token", "")).strip(),
            api_version=str(raw.get("api_version", "auto")).lower(),
            direct_cdp_url=str(raw.get("direct_cdp_url", "")).strip(),
            close_on_stop=bool(raw.get("close_on_stop", True)),
        )

    @property
    def identifier(self) -> str:
        return self.profile_id or self.direct_cdp_url


@dataclass(frozen=True)
class MoreLoginSettings:
    api_base: str = "http://127.0.0.1:40000"
    profile_id: str = ""
    profile_name: str = ""
    cdp_evasion: bool = True
    close_on_stop: bool = True

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "MoreLoginSettings":
        raw = raw or {}
        return cls(
            api_base=str(raw.get("api_base", "http://127.0.0.1:40000")).rstrip("/"),
            profile_id=str(raw.get("profile_id", "")).strip(),
            profile_name=str(raw.get("profile_name", "")).strip(),
            cdp_evasion=bool(raw.get("cdp_evasion", True)),
            close_on_stop=bool(raw.get("close_on_stop", True)),
        )

    @property
    def identifier(self) -> str:
        return self.profile_id or self.profile_name


@dataclass(frozen=True)
class AdsPowerSettings:
    api_base: str = "http://local.adspower.net:50325"
    profile_id: str = ""
    profile_no: str = ""
    api_key: str = ""
    api_version: str = "v2"
    close_on_stop: bool = True
    cdp_mask: bool = True
    proxy_detection: bool = False
    open_last_tabs: bool = False

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "AdsPowerSettings":
        raw = raw or {}
        return cls(
            api_base=str(raw.get("api_base", "http://local.adspower.net:50325")).rstrip("/"),
            profile_id=str(raw.get("profile_id", "")).strip(),
            profile_no=str(raw.get("profile_no", "")).strip(),
            api_key=str(raw.get("api_key", "")).strip(),
            api_version=str(raw.get("api_version", "v2")).lower(),
            close_on_stop=bool(raw.get("close_on_stop", True)),
            cdp_mask=bool(raw.get("cdp_mask", True)),
            proxy_detection=bool(raw.get("proxy_detection", False)),
            open_last_tabs=bool(raw.get("open_last_tabs", False)),
        )

    @property
    def identifier(self) -> str:
        return self.profile_id or self.profile_no


@dataclass(frozen=True)
class TimeoutSettings:
    browser_launch_ms: int = 30000
    page_load_ms: int = 45000
    script_ms: int = 30000
    shutdown_ms: int = 5000

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "TimeoutSettings":
        raw = raw or {}
        return cls(
            browser_launch_ms=max(1000, int(raw.get("browser_launch_ms", 30000))),
            page_load_ms=max(1000, int(raw.get("page_load_ms", 45000))),
            script_ms=max(1000, int(raw.get("script_ms", 30000))),
            shutdown_ms=max(1000, int(raw.get("shutdown_ms", 5000))),
        )


@dataclass(frozen=True)
class AppConfig:
    browser_engine: str = "morelogin"
    morelogin: MoreLoginSettings = field(default_factory=MoreLoginSettings)
    multilogin: MultiloginSettings = field(default_factory=MultiloginSettings)
    proxy: ProxySettings = field(default_factory=ProxySettings)
    adspower: AdsPowerSettings = field(default_factory=AdsPowerSettings)
    user_agent: str = ""
    window_size: WindowSize = field(default_factory=WindowSize)
    camera_output_size: CameraOutputSize = field(default_factory=CameraOutputSize)
    automation: AutomationSettings = field(default_factory=AutomationSettings)
    target_url: str = "https://example.com"
    timeouts: TimeoutSettings = field(default_factory=TimeoutSettings)
    profile_name: str = "default"
    device_profile_id: str = ""
    headless: bool = False
    auth: AuthSettings = field(default_factory=AuthSettings)

    @classmethod
    def load(cls, config_file: str | Path = CONFIG_FILE) -> "AppConfig":
        path = Path(config_file)
        if not path.exists():
            default_config = cls()
            default_config.save(path)
            return default_config

        with path.open("r", encoding="utf-8") as config_stream:
            raw = json.load(config_stream)

        return cls(
            browser_engine=str(raw.get("browser_engine", "morelogin")).lower(),
            morelogin=MoreLoginSettings.from_dict(raw.get("morelogin")),
            multilogin=MultiloginSettings.from_dict(raw.get("multilogin")),
            proxy=ProxySettings.from_dict(raw.get("proxy")),
            adspower=AdsPowerSettings.from_dict(raw.get("adspower")),
            user_agent=str(raw.get("user_agent", "")),
            window_size=WindowSize.from_dict(raw.get("window_size")),
            camera_output_size=CameraOutputSize.from_dict(raw.get("camera_output_size")),
            automation=AutomationSettings.from_dict(raw.get("automation")),
            target_url=str(raw.get("target_url", "https://example.com")),
            timeouts=TimeoutSettings.from_dict(raw.get("timeouts")),
            profile_name=str(raw.get("profile_name", "default")),
            device_profile_id=str(raw.get("device_profile_id", "")),
            headless=bool(raw.get("headless", False)),
            auth=AuthSettings.from_dict(raw.get("auth")),
        )

    def save(self, config_file: str | Path = CONFIG_FILE):
        path = Path(config_file)
        payload = self._to_dict()
        if path.exists():
            with path.open("r", encoding="utf-8") as config_stream:
                existing = json.load(config_stream)
            for key, value in existing.items():
                if key not in payload:
                    payload[key] = value

        with path.open("w", encoding="utf-8") as config_stream:
            json.dump(payload, config_stream, indent=2)

    def _to_dict(self) -> dict[str, Any]:
        return {
            "browser_engine": self.browser_engine,
            "morelogin": {
                "api_base": self.morelogin.api_base,
                "profile_id": self.morelogin.profile_id,
                "profile_name": self.morelogin.profile_name,
                "cdp_evasion": self.morelogin.cdp_evasion,
                "close_on_stop": self.morelogin.close_on_stop,
            },
            "multilogin": {
                "api_base": self.multilogin.api_base,
                "profile_id": self.multilogin.profile_id,
                "folder_id": self.multilogin.folder_id,
                "token": self.multilogin.token,
                "api_version": self.multilogin.api_version,
                "direct_cdp_url": self.multilogin.direct_cdp_url,
                "close_on_stop": self.multilogin.close_on_stop,
            },
            "proxy": {
                "enabled": self.proxy.enabled,
                "type": self.proxy.proxy_type,
                "host": self.proxy.host,
                "port": self.proxy.port,
                "server": self.proxy.server,
                "username": self.proxy.username,
                "password": self.proxy.password,
            },
            "adspower": {
                "api_base": self.adspower.api_base,
                "profile_id": self.adspower.profile_id,
                "profile_no": self.adspower.profile_no,
                "api_key": self.adspower.api_key,
                "api_version": self.adspower.api_version,
                "close_on_stop": self.adspower.close_on_stop,
                "cdp_mask": self.adspower.cdp_mask,
                "proxy_detection": self.adspower.proxy_detection,
                "open_last_tabs": self.adspower.open_last_tabs,
            },
            "user_agent": self.user_agent,
            "window_size": {
                "width": self.window_size.width,
                "height": self.window_size.height,
            },
            "camera_output_size": {
                "width": self.camera_output_size.width,
                "height": self.camera_output_size.height,
            },
            "automation": {
                "click_retries": self.automation.click_retries,
                "camera_warmup_ms": self.automation.camera_warmup_ms,
                "step_settle_ms": self.automation.step_settle_ms,
                "capture_settle_ms": self.automation.capture_settle_ms,
                "post_capture_ms": self.automation.post_capture_ms,
                "liveness_timeout_ms": self.automation.liveness_timeout_ms,
                "liveness_upload_mode": self.automation.liveness_upload_mode,
                "liveness_step_ms": self.automation.liveness_step_ms,
                "liveness_step_jitter_ms": self.automation.liveness_step_jitter_ms,
                "liveness_retry_count": self.automation.liveness_retry_count,
                "liveness_min_duration_seconds": self.automation.liveness_min_duration_seconds,
                "human_delay_jitter_ms": self.automation.human_delay_jitter_ms,
                "liveness_timeline": [
                    {
                        "start_sec": mark.start_ms / 1000,
                        "position": mark.position,
                        **({"label": mark.label} if mark.label else {}),
                    }
                    for mark in self.automation.liveness_timeline
                ],
            },
            "target_url": self.target_url,
            "timeouts": {
                "browser_launch_ms": self.timeouts.browser_launch_ms,
                "page_load_ms": self.timeouts.page_load_ms,
                "script_ms": self.timeouts.script_ms,
                "shutdown_ms": self.timeouts.shutdown_ms,
            },
            "profile_name": self.profile_name,
            "device_profile_id": self.device_profile_id,
            "headless": self.headless,
            "auth": {
                "enabled": self.auth.enabled,
                "api_base": self.auth.api_base,
                "app_key": self.auth.app_key,
                "heartbeat_seconds": self.auth.heartbeat_seconds,
                "session_timeout_seconds": self.auth.session_timeout_seconds,
                "verify_ssl": self.auth.verify_ssl,
                "offline_mode": self.auth.offline_mode,
                "local_username": self.auth.local_username,
                "local_password_hash": self.auth.local_password_hash,
            },
        }

    def with_browser_engine(self, browser_engine: str) -> "AppConfig":
        import dataclasses
        return dataclasses.replace(self, browser_engine=browser_engine)

    def with_morelogin(self, morelogin: MoreLoginSettings) -> "AppConfig":
        import dataclasses
        return dataclasses.replace(self, morelogin=morelogin)

    def with_multilogin(self, multilogin: MultiloginSettings) -> "AppConfig":
        import dataclasses
        return dataclasses.replace(self, multilogin=multilogin)

    def with_target_url(self, target_url: str) -> "AppConfig":
        import dataclasses
        return dataclasses.replace(self, target_url=target_url)

    def with_proxy(self, proxy: ProxySettings) -> "AppConfig":
        import dataclasses
        return dataclasses.replace(self, proxy=proxy)

    def with_adspower(self, adspower: AdsPowerSettings) -> "AppConfig":
        import dataclasses
        return dataclasses.replace(self, adspower=adspower)

    def with_user_agent(self, user_agent: str) -> "AppConfig":
        import dataclasses
        return dataclasses.replace(self, user_agent=user_agent)

    def with_window_size(self, window_size: WindowSize) -> "AppConfig":
        import dataclasses
        return dataclasses.replace(self, window_size=window_size)

    def with_device_profile_id(self, device_profile_id: str) -> "AppConfig":
        import dataclasses
        return dataclasses.replace(self, device_profile_id=device_profile_id)
