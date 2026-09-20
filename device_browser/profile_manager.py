from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROFILE_FILE = Path(__file__).with_name("profiles.json")


@dataclass(frozen=True)
class Size:
    width: int
    height: int

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Size":
        return cls(width=int(raw["width"]), height=int(raw["height"]))

    def to_dict(self) -> dict[str, int]:
        return {"width": self.width, "height": self.height}


@dataclass(frozen=True)
class DeviceProfile:
    id: str
    device_name: str
    os_name: str
    os_version: str
    browser_name: str
    browser_version: str
    user_agent: str
    screen_resolution: Size
    device_pixel_ratio: float
    viewport_size: Size
    orientation: str
    language: str
    timezone: str
    color_scheme: str
    platform: str
    mobile: bool
    touch_points: int

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "DeviceProfile":
        required_keys = {
            "id",
            "device_name",
            "os_name",
            "os_version",
            "browser_name",
            "browser_version",
            "user_agent",
            "screen_resolution",
            "device_pixel_ratio",
            "viewport_size",
            "orientation",
            "language",
            "timezone",
            "color_scheme",
            "platform",
            "mobile",
            "touch_points",
        }
        missing = required_keys - raw.keys()
        if missing:
            raise ValueError(f"Profile {raw.get('id', '<unknown>')} is missing: {sorted(missing)}")

        profile = cls(
            id=str(raw["id"]),
            device_name=str(raw["device_name"]),
            os_name=str(raw["os_name"]),
            os_version=str(raw["os_version"]),
            browser_name=str(raw["browser_name"]),
            browser_version=str(raw["browser_version"]),
            user_agent=str(raw["user_agent"]),
            screen_resolution=Size.from_dict(raw["screen_resolution"]),
            device_pixel_ratio=float(raw["device_pixel_ratio"]),
            viewport_size=Size.from_dict(raw["viewport_size"]),
            orientation=str(raw["orientation"]),
            language=str(raw["language"]),
            timezone=str(raw["timezone"]),
            color_scheme=str(raw["color_scheme"]),
            platform=str(raw["platform"]),
            mobile=bool(raw["mobile"]),
            touch_points=int(raw["touch_points"]),
        )
        profile.validate()
        return profile

    def validate(self):
        if self.orientation not in {"portrait", "landscape"}:
            raise ValueError(f"{self.id}: orientation must be portrait or landscape")
        if self.color_scheme not in {"light", "dark"}:
            raise ValueError(f"{self.id}: color_scheme must be light or dark")
        if self.device_pixel_ratio <= 0:
            raise ValueError(f"{self.id}: device_pixel_ratio must be positive")
        if min(
            self.screen_resolution.width,
            self.screen_resolution.height,
            self.viewport_size.width,
            self.viewport_size.height,
        ) <= 0:
            raise ValueError(f"{self.id}: screen and viewport sizes must be positive")

    def label(self) -> str:
        return f"{self.device_name} - {self.os_name} {self.os_version} / {self.browser_name} {self.browser_version}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "device_name": self.device_name,
            "os_name": self.os_name,
            "os_version": self.os_version,
            "browser_name": self.browser_name,
            "browser_version": self.browser_version,
            "user_agent": self.user_agent,
            "screen_resolution": self.screen_resolution.to_dict(),
            "device_pixel_ratio": self.device_pixel_ratio,
            "viewport_size": self.viewport_size.to_dict(),
            "orientation": self.orientation,
            "language": self.language,
            "timezone": self.timezone,
            "color_scheme": self.color_scheme,
            "platform": self.platform,
            "mobile": self.mobile,
            "touch_points": self.touch_points,
        }


class ProfileManager:
    """Loads complete device profiles from a predefined JSON database."""

    def __init__(self, profile_file: Path = PROFILE_FILE):
        self.profile_file = profile_file
        self._profiles = self._load_profiles()

    def all_profiles(self) -> list[DeviceProfile]:
        return list(self._profiles.values())

    def default_profile(self) -> DeviceProfile:
        return next(iter(self._profiles.values()))

    def get(self, profile_id: str) -> DeviceProfile:
        try:
            return self._profiles[profile_id]
        except KeyError as exc:
            raise KeyError(f"Unknown device profile: {profile_id}") from exc

    def _load_profiles(self) -> dict[str, DeviceProfile]:
        with self.profile_file.open("r", encoding="utf-8") as profile_stream:
            raw_profiles = json.load(profile_stream)

        profiles = [DeviceProfile.from_dict(item) for item in raw_profiles]
        return {profile.id: profile for profile in profiles}

