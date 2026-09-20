from __future__ import annotations

import os
import hashlib
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


VIDEO_SUFFIXES = {
    ".avi",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".webm",
    ".y4m",
}


@dataclass(frozen=True)
class VirtualCameraFeed:
    source_path: Path
    capture_path: Path | None
    converted: bool = False
    warning: str = ""


class VirtualCameraService:
    """Prepare Chromium-compatible fake webcam media at a fixed output resolution."""

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        *,
        output_width: int = 1080,
        output_height: int = 1980,
    ):
        self.cache_dir = Path(cache_dir or tempfile.gettempdir()) / "pyqt_fake_camera"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.output_width = max(160, int(output_width))
        self.output_height = max(160, int(output_height))

    def prepare(self, file_paths: list[str]) -> VirtualCameraFeed | None:
        source_path = self._select_video_file(file_paths)
        if not source_path:
            return None
        return self._prepare_source(source_path)

    def prepare_file(self, file_path: str) -> VirtualCameraFeed | None:
        if not file_path:
            return None

        path = Path(file_path).expanduser().resolve()
        if not path.is_file() or path.suffix.lower() not in VIDEO_SUFFIXES:
            return None
        return self._prepare_source(path)

    def prepare_automation_set(self, file_paths: list[str]) -> list[Path | None]:
        """Return a Chromium .y4m capture path for each of the first three file slots."""
        capture_paths: list[Path | None] = []
        for index in range(3):
            slot = file_paths[index] if index < len(file_paths) else ""
            feed = self.prepare_file(slot)
            capture_paths.append(feed.capture_path if feed else None)
        return capture_paths

    def prepare_blob_sources(self, file_paths: list[str]) -> list[Path | None]:
        """Return scaled MP4 paths for in-page blob camera switching."""
        blob_paths: list[Path | None] = []
        for index in range(3):
            slot = file_paths[index] if index < len(file_paths) else ""
            if not slot:
                blob_paths.append(None)
                continue

            path = Path(slot).expanduser().resolve()
            if not path.is_file() or path.suffix.lower() not in VIDEO_SUFFIXES:
                blob_paths.append(None)
                continue

            blob_paths.append(self._prepare_scaled_mp4(path))
        return blob_paths

    def runtime_capture_path(self) -> Path:
        return self.cache_dir / "active-capture.y4m"

    @staticmethod
    def stage_capture(source: Path, destination: Path) -> Path:
        """Stage capture for Chromium. Returns the path the browser should use."""
        source = source.expanduser().resolve()
        destination = destination.expanduser().resolve()
        if source == destination:
            return destination

        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            try:
                destination.unlink()
            except OSError:
                pass

        try:
            os.link(source, destination)
            return destination
        except OSError:
            pass

        try:
            shutil.copy2(source, destination)
            return destination
        except OSError:
            return source

    def output_label(self) -> str:
        return f"{self.output_width}x{self.output_height}"

    def _prepare_source(self, source_path: Path) -> VirtualCameraFeed:
        ffmpeg_path = self._find_ffmpeg()
        if not ffmpeg_path:
            if source_path.suffix.lower() == ".y4m":
                return VirtualCameraFeed(
                    source_path=source_path,
                    capture_path=source_path,
                    converted=False,
                    warning=(
                        "ffmpeg was not found; using the selected .y4m without "
                        f"resizing to {self.output_label()}."
                    ),
                )
            return VirtualCameraFeed(
                source_path=source_path,
                capture_path=None,
                warning=(
                    "ffmpeg was not found, so the selected video could not be converted "
                    "to .y4m. Chromium will open with its default fake camera feed."
                ),
            )

        capture_path = self._converted_path_for(source_path, ".y4m")
        if not capture_path.exists() or capture_path.stat().st_size == 0:
            try:
                self._convert_to_y4m(ffmpeg_path, source_path, capture_path)
            except RuntimeError as exc:
                return VirtualCameraFeed(
                    source_path=source_path,
                    capture_path=None,
                    warning=(
                        f"{exc} Chromium will open with its default fake camera feed."
                    ),
                )

        return VirtualCameraFeed(
            source_path=source_path,
            capture_path=capture_path,
            converted=source_path.suffix.lower() != ".y4m"
            or capture_path != source_path.resolve(),
        )

    def _prepare_scaled_mp4(self, source_path: Path) -> Path | None:
        ffmpeg_path = self._find_ffmpeg()
        if not ffmpeg_path:
            return source_path if source_path.suffix.lower() in {".mp4", ".m4v", ".mov", ".webm"} else None

        output_path = self._converted_path_for(source_path, ".mp4")
        if output_path.exists() and output_path.stat().st_size > 0:
            return output_path

        try:
            self._convert_to_mp4(ffmpeg_path, source_path, output_path)
        except RuntimeError:
            return source_path if source_path.suffix.lower() in {".mp4", ".m4v"} else None
        return output_path

    def _scale_filter(self) -> str:
        width = self.output_width
        height = self.output_height
        return (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease:flags=lanczos,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,fps=30,format=yuv420p"
        )

    @staticmethod
    def _select_video_file(file_paths: list[str]) -> Path | None:
        for file_path in file_paths:
            if not file_path:
                continue
            path = Path(file_path).expanduser().resolve()
            if path.is_file() and path.suffix.lower() in VIDEO_SUFFIXES:
                return path
        return None

    def _converted_path_for(self, source_path: Path, suffix: str) -> Path:
        fingerprint = hashlib.sha256(
            (
                f"{source_path}|{source_path.stat().st_size}|"
                f"{source_path.stat().st_mtime_ns}|{self.output_label()}|{suffix}|hq-v2"
            ).encode("utf-8")
        ).hexdigest()[:16]
        return self.cache_dir / f"{source_path.stem}-{fingerprint}{suffix}"

    @staticmethod
    def _find_ffmpeg() -> str | None:
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path:
            return ffmpeg_path

        try:
            import imageio_ffmpeg

            bundled_ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
            if bundled_ffmpeg and Path(bundled_ffmpeg).is_file():
                return bundled_ffmpeg
        except Exception:
            pass

        import sys

        candidates = [
            Path(getattr(sys, "_MEIPASS", "")) / "ffmpeg.exe",
            Path(getattr(sys, "_MEIPASS", "")) / "bin" / "ffmpeg.exe",
            Path(sys.executable).resolve().parent / "ffmpeg.exe",
            Path(sys.executable).resolve().parent / "bin" / "ffmpeg.exe",
            Path(__file__).with_name("ffmpeg.exe"),
            Path(__file__).with_name("bin") / "ffmpeg.exe",
            Path(__file__).with_name("tools") / "ffmpeg.exe",
            Path(__file__).with_name("ffmpeg") / "bin" / "ffmpeg.exe",
            Path.home()
            / ".cache"
            / "codex-runtimes"
            / "codex-primary-runtime"
            / "dependencies"
            / "bin"
            / "ffmpeg.exe",
            Path("C:/ffmpeg/bin/ffmpeg.exe"),
            Path("C:/Program Files/ffmpeg/bin/ffmpeg.exe"),
        ]
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)

        return None

    def _convert_to_y4m(self, ffmpeg_path: str, source_path: Path, capture_path: Path):
        capture_path.parent.mkdir(parents=True, exist_ok=True)
        command = [
            ffmpeg_path,
            "-y",
            "-i",
            str(source_path),
            "-vf",
            self._scale_filter(),
            "-pix_fmt",
            "yuv420p",
            "-f",
            "yuv4mpegpipe",
            str(capture_path),
        ]
        self._run_ffmpeg(command)

    def _convert_to_mp4(self, ffmpeg_path: str, source_path: Path, output_path: Path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        command = [
            ffmpeg_path,
            "-y",
            "-i",
            str(source_path),
            "-vf",
            self._scale_filter(),
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-profile:v",
            "high",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-an",
            str(output_path),
        ]
        self._run_ffmpeg(command)

    @staticmethod
    def _run_ffmpeg(command: list[str]):
        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
        )
        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip()
            raise RuntimeError(f"ffmpeg failed: {message}")

    @staticmethod
    def probe_duration_seconds(source_path: str | Path) -> float | None:
        source = Path(source_path).expanduser().resolve()
        if not source.is_file():
            return None
        try:
            completed = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(source),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            if completed.returncode != 0 or not completed.stdout.strip():
                return None
            return float(completed.stdout.strip())
        except Exception:
            return None
