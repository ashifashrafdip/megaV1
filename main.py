from __future__ import annotations

import json
import logging
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from PyQt5.QtCore import QThread, QTimer, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app_config import (
    AdsPowerSettings,
    AppConfig,
    MultiloginSettings,
    liveness_timeline_to_json,
)
from theme import APP_QSS
from auth_client import AuthError
from auth_session import AuthSession
from login_dialog import require_login
from protection_stub import protection_checks
from adspower_browser import (
    AdsPowerApiError,
    AdsPowerBrowserManager,
    AdsPowerLaunchSettings,
    AdsPowerProfile,
    list_adspower_profiles,
)
from multilogin_browser import (
    MultiloginApiError,
    MultiloginBrowserManager,
    MultiloginLaunchSettings,
    MultiloginProfile,
    detect_active_cdp_endpoint,
    extract_local_multilogin_token,
    list_multilogin_profiles,
)
from camera_feed_service import VirtualCameraFeed, VirtualCameraService
from qt_logging import (
    install_exception_logger,
    remove_logging_handler,
    setup_text_edit_logging,
)
from video_step_automation import (
    VIDEO_STEP_RESULT_SCRIPT,
    VIDEO_STEP_TICK_SCRIPT,
    set_video_step_template,
    video_step_script,
)
from wizard_automation import (
    WIZARD_CAMERA_VIDEO_ID,
    WIZARD_PANEL_CAMERA,
    WIZARD_PANEL_REDACTING,
    WIZARD_VIDEO_WEBCAM_ID,
    set_liveness_template,
    wizard_finish_button_enabled_script,
    wizard_loader_idle_script,
    wizard_panel_visible_script,
    wizard_video_ready_script,
)

from temp_file_server import TemporaryFileServer


LOGGER = logging.getLogger("desktop_app")
EXECUTION_FLOW = (
    "QApplication -> MainWindow -> WorkerThread -> TemporaryFileServer -> "
    "Browser Manager (Multilogin / AdsPower) -> Playwright CDP page -> GUI log"
)
ID_BUTTON_ID = "btn-take-photo-id"
ID_BUTTON_TEXTS = ("I'm ready", "I'M READY", "Im ready", "Take photo of ID")
SELFIE_BUTTON_IDS = ("btn-take-photo-selfy", "btn-take-photo-selfie")
SELFIE_BUTTON_TEXTS = ("I AM READY", "TAKE SELFIE HOLDING ID")
CAMERA_BUTTON_ID = "btn-take-photo-camera"
CAMERA_BUTTON_TEXT = "TAKE PHOTO"
OK_BUTTON_ID = "btn-black-out-modal"
OK_BUTTON_TEXT = "OK"
FINISHED_BUTTON_ID = "btn-go-to-photo-id-redacting"
FINISHED_BUTTON_TEXT = "FINISHED"
LIVENESS_PROCEED_ID = "btn-video-instructions-proceed"
LIVENESS_PROCEED_TEXT = "PROCEED"
LIVENESS_SUBMIT_ID = "btn-video-submit-proceed"
MEDIA_PERMISSIONS = ("camera", "microphone")
CDP_MEDIA_PERMISSIONS = ("videoCapture", "audioCapture")
FAKE_MEDIA_STREAM_ARGS = (
    "--enable-media-stream",
    "--use-fake-ui-for-media-stream",
    "--use-fake-device-for-media-stream",
    "--autoplay-policy=no-user-gesture-required",
)
VIDEO_MIME_TYPES = {
    ".avi": "video/x-msvideo",
    ".m4v": "video/mp4",
    ".mkv": "video/x-matroska",
    ".mov": "video/quicktime",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".y4m": "video/y4m",
}
MAX_INLINE_BLOB_BYTES = 64 * 1024 * 1024
MAX_CAMERA_VIDEO_BYTES = 200 * 1024 * 1024
MIN_BLOB_FETCH_TIMEOUT_MS = 60_000
BLOB_FETCH_TIMEOUT_MS_PER_MB = 3_000
MAX_BLOB_FETCH_TIMEOUT_MS = 300_000


ServerFactory = Callable[[], TemporaryFileServer]
CameraServiceFactory = Callable[[], VirtualCameraService]


@dataclass(frozen=True)
class AutomationServices:
    """Factories and config used by the worker thread."""

    config: AppConfig
    server_factory: ServerFactory = TemporaryFileServer
    multilogin_browser_manager_factory: Callable[[], MultiloginBrowserManager] = MultiloginBrowserManager
    adspower_browser_manager_factory: Callable[[], AdsPowerBrowserManager] = AdsPowerBrowserManager
    camera_service_factory: CameraServiceFactory = VirtualCameraService

    @classmethod
    def from_config(cls, config: AppConfig) -> "AutomationServices":
        return cls(config=config)

    def create_server(self) -> TemporaryFileServer:
        return self.server_factory()

    def create_browser_manager(self) -> MultiloginBrowserManager | AdsPowerBrowserManager:
        if self.config.browser_engine == "adspower":
            return self.adspower_browser_manager_factory()
        return self.multilogin_browser_manager_factory()

    def create_camera_service(self) -> VirtualCameraService:
        output = self.config.camera_output_size
        return VirtualCameraService(
            output_width=output.width,
            output_height=output.height,
        )

    def build_multilogin_launch_settings(self) -> MultiloginLaunchSettings:
        return MultiloginLaunchSettings.from_config(
            self.config.multilogin,
            headless=self.config.headless,
            launch_timeout_ms=self.config.timeouts.browser_launch_ms,
        )

    def build_adspower_launch_settings(
        self,
        camera_feed: VirtualCameraFeed | None,
        media_origins: list[str] | None = None,
        fake_capture_path: Path | None = None,
    ) -> AdsPowerLaunchSettings:
        launch_args: list[str] = []

        if camera_feed:
            launch_args.extend(FAKE_MEDIA_STREAM_ARGS)
            capture_path = fake_capture_path or camera_feed.capture_path
            if capture_path:
                launch_args.append(
                    f"--use-file-for-fake-video-capture={capture_path.as_posix()}"
                )

        for origin in media_origins or []:
            if origin.startswith("http://") and "127.0.0.1" not in origin and "localhost" not in origin:
                launch_args.append(f"--unsafely-treat-insecure-origin-as-secure={origin}")

        return AdsPowerLaunchSettings.from_config(
            self.config.adspower,
            headless=self.config.headless,
            launch_args=launch_args,
            launch_timeout_ms=self.config.timeouts.browser_launch_ms,
        )

    def resolve_target_url(self, server: TemporaryFileServer) -> str:
        target_url = self.config.target_url.strip()
        if not target_url or target_url.lower() in {"local", "server", "{server_url}"}:
            return server.url_for("index.html")
        if "{server_url}" in target_url:
            # Check if target refers to a local file in Source file directory;
            # using file:// directly bypasses any browser proxy socket issues for mock tests
            rel = target_url.replace("{server_url}/", "").replace("{server_url}", "")
            for base in [
                Path(sys.executable).resolve().parent / "Source file",
                Path(getattr(sys, "_MEIPASS", "")) / "Source file",
                Path(__file__).resolve().parent / "Source file",
            ]:
                candidate = base / rel
                if candidate.is_file():
                    return candidate.resolve().as_uri()
            return target_url.replace("{server_url}", server.base_url)
        if target_url.startswith("/"):
            return f"{server.base_url}{target_url}"
        if not urlparse(target_url).scheme:
            return f"https://{target_url}"
        return target_url


class MultiloginProfileLoaderThread(QThread):
    profiles_loaded = pyqtSignal(list, str)

    def __init__(self, launch_settings: MultiloginLaunchSettings, parent=None):
        super().__init__(parent)
        self.launch_settings = launch_settings

    def run(self):
        try:
            profiles = list_multilogin_profiles(self.launch_settings)
            self.profiles_loaded.emit(profiles, "")
        except Exception as exc:
            self.profiles_loaded.emit([], str(exc))


class MultiloginCdpDetectorThread(QThread):
    detected = pyqtSignal(str)

    def run(self):
        try:
            endpoint = detect_active_cdp_endpoint(timeout_sec=0.25) or ""
            self.detected.emit(endpoint)
        except Exception:
            self.detected.emit("")


class WorkerThread(QThread):
    status = pyqtSignal(str)
    finished_successfully = pyqtSignal()
    stopped = pyqtSignal()
    failed = pyqtSignal(str)
    verification_passed = pyqtSignal(str)

    def __init__(self, services: AutomationServices, files: list[str], parent=None):
        super().__init__(parent)
        self.services = services
        self.config = services.config
        self.files = files
        self._automation_capture_paths: list[Path | None] = []
        self._active_capture_path: Path | None = None
        self._current_video_index: int | None = None
        self._staged_source_path: Path | None = None
        self._blob_camera_ready = False
        self._blob_source_paths: list[Path | None] = [None, None, None]
        self._blob_server_urls: list[str | None] = [None, None, None]
        self._blob_urls_cache: list[str | None] = [None, None, None]
        self._active_source_path: Path | None = None
        self._video_step_installed = False
        self._last_video_step_inject_at = 0.0
        self._automation = self.config.automation
        self._work_page = None
        self._verification_accepted_url: str | None = None

    def _bind_work_page(self, page):
        self._work_page = self._resolve_live_page(page)
        return self._work_page

    def _active_page(self, page=None):
        if page is not None:
            if page.is_closed():
                return self._resolve_live_page(None)
            return self._bind_work_page(page)
        if self._work_page and not self._work_page.is_closed():
            return self._work_page
        if self._work_page:
            return self._resolve_live_page(None)
        raise RuntimeError("No live browser page is available for automation.")

    def run(self):
        worker_logger = logging.getLogger("desktop_app.worker")
        server: TemporaryFileServer | None = None
        browser_manager: MultiloginBrowserManager | AdsPowerBrowserManager | None = None

        try:
            self._emit_status("Worker started.")
            self._emit_status(f"Loaded target URL: {self.config.target_url}")

            if self._stop_requested():
                return

            if self.config.browser_engine == "multilogin":
                self._emit_status("Step 1/5: Preparing Multilogin profile...")
                ml = self.config.multilogin
                if not ml.identifier:
                    raise ValueError(
                        "Select a Multilogin profile or specify a CDP URL before starting automation."
                    )
                if ml.direct_cdp_url:
                    self._emit_status(f"Multilogin Direct CDP target: {ml.direct_cdp_url}")
                else:
                    self._emit_status(f"Multilogin API: {ml.api_base}")
                    self._emit_status(f"Multilogin profile ID: {ml.profile_id}")
                    if ml.folder_id:
                        self._emit_status(f"Multilogin folder ID: {ml.folder_id}")
                self._emit_status(
                    "Browser, proxy, and fingerprint come from the Multilogin profile."
                )
            else:
                self._emit_status("Step 1/5: Preparing AdsPower profile...")
                adspower = self.config.adspower
                if not adspower.identifier:
                    raise ValueError(
                        "Select an AdsPower profile in the app before starting automation."
                    )

                self._emit_status(f"AdsPower API: {adspower.api_base}")
                if adspower.profile_id:
                    self._emit_status(f"AdsPower profile ID: {adspower.profile_id}")
                if adspower.profile_no:
                    self._emit_status(f"AdsPower profile No: {adspower.profile_no}")
                self._emit_status(
                    "Browser, proxy, and user agent come from the AdsPower profile."
                )
            self._emit_status(
                "This app only controls the virtual camera and automation script."
            )

            if self._stop_requested():
                return

            self._emit_status("Step 2/5: Setting up virtual camera feed...")
            camera_service = self.services.create_camera_service()
            output_label = camera_service.output_label()
            self._emit_status(f"Camera output target: {output_label}")
            camera_feed = camera_service.prepare(self.files)
            self._automation_capture_paths = camera_service.prepare_automation_set(self.files)
            self._blob_source_paths = camera_service.prepare_blob_sources(self.files)
            first_capture = next((path for path in self._automation_capture_paths if path), None)
            if first_capture:
                runtime_capture = camera_service.runtime_capture_path()
                self._active_capture_path = camera_service.stage_capture(
                    first_capture,
                    runtime_capture,
                )
                if self._active_capture_path != runtime_capture:
                    self._emit_status(
                        "Using source capture file directly (staging skipped due to disk space)."
                    )
                self._staged_source_path = first_capture
                self._current_video_index = 0
            else:
                self._active_capture_path = camera_feed.capture_path if camera_feed else None
                self._staged_source_path = None
                self._current_video_index = None
            if camera_feed:
                if camera_feed.warning:
                    self._emit_status(f"Virtual camera warning: {camera_feed.warning}")
                action = "converted to .y4m" if camera_feed.converted else "using .y4m directly"
                self._emit_status(f"Virtual camera source: {camera_feed.source_path}")
                if camera_feed.capture_path:
                    self._emit_status(
                        f"Virtual camera capture file: {camera_feed.capture_path} ({action})"
                    )
                else:
                    self._emit_status(
                        "Virtual camera capture file: Chromium default fake camera"
                    )
                self._emit_status(
                    "Chromium fake camera enabled: "
                    "--use-fake-ui-for-media-stream, --use-fake-device-for-media-stream"
                )
            else:
                self._emit_status("No video file selected for virtual camera.")

            for index, capture_path in enumerate(self._automation_capture_paths, start=1):
                if capture_path:
                    self._emit_status(
                        f"Automation camera video {index}: {capture_path} ({output_label})"
                    )
                elif self.files[index - 1] if index <= len(self.files) else "":
                    self._emit_status(
                        f"Automation camera video {index} unavailable: install ffmpeg or use .y4m"
                    )

            for index, blob_path in enumerate(self._blob_source_paths, start=1):
                if blob_path:
                    self._emit_status(f"Blob camera source {index}: {blob_path} ({output_label})")

            if self._stop_requested():
                return

            self._emit_status("Step 3/5: Starting local server...")
            server = self.services.create_server()
            server_url = server.start()
            self._emit_status(f"Local server started: {server_url}")
            self._publish_files(server)
            target_url = self.services.resolve_target_url(server)
            media_origins = self._media_permission_origins(target_url)

            if self._stop_requested():
                return

            browser_manager = self.services.create_browser_manager()
            if self.config.browser_engine == "multilogin":
                self._emit_status("Step 4/5: Launching Multilogin browser...")
                launch_settings = self.services.build_multilogin_launch_settings()
                page = browser_manager.start(launch_settings)
                page.context.set_default_timeout(self.config.timeouts.script_ms)
                page.context.set_default_navigation_timeout(self.config.timeouts.page_load_ms)
                self._emit_status(f"Multilogin browser attached: profile {launch_settings.identifier}")
            else:
                self._emit_status("Step 4/5: Launching AdsPower browser...")
                launch_settings = self.services.build_adspower_launch_settings(
                    camera_feed,
                    media_origins,
                    fake_capture_path=self._active_capture_path,
                )
                page = browser_manager.start(launch_settings)
                page.context.set_default_timeout(self.config.timeouts.script_ms)
                page.context.set_default_navigation_timeout(self.config.timeouts.page_load_ms)
                self._emit_status(f"AdsPower browser attached: profile {launch_settings.identifier}")

            if self._stop_requested():
                return

            self._emit_status(f"Step 5/5: Opening target URL: {target_url}")
            page = self._open_target_page(page, target_url)

            if self._stop_requested():
                return

            self._emit_status("Waiting for page load state...")
            page.wait_for_load_state("domcontentloaded", timeout=self.config.timeouts.page_load_ms)

            if camera_feed:
                self._grant_media_permissions(
                    page,
                    self._collect_media_origins(target_url, page, server_url),
                    reset_blocked=True,
                    skip_cdp=True,
                )

            if camera_feed and self._should_prepare_blob_camera():
                self._ensure_blob_camera_switcher(page)

            self._emit_status("Page loaded successfully.")
            self._emit_status(f"Page title: {page.title()}")
            self._emit_status(f"Current URL: {page.url}")

            if camera_feed or any(self.files[:3]):
                self._bind_work_page(page)
                self._run_capture_automation(self._work_page)
            else:
                self._emit_status("Capture automation skipped: File 1 video was not selected.")

            self._emit_status("Automation session ready. Click Stop when finished.")
            while not self._stop_requested():
                time.sleep(0.5)

            self._emit_status("Worker completed.")
            self.finished_successfully.emit()
        except Exception as exc:
            self._emit_status(f"Worker failed: {exc}")
            worker_logger.exception("Worker failed gracefully: %s", exc)
            self.failed.emit(str(exc))
            engine_title = "Multilogin" if self.config.browser_engine == "multilogin" else "AdsPower"
            self._emit_status(f"Automation paused. {engine_title} browser stays open so you can continue manually.")
        finally:
            self._emit_status("Cleaning up local server...")
            if server:
                try:
                    server.stop()
                except Exception:
                    worker_logger.exception("Failed to stop local server cleanly.")
            engine_title = "Multilogin" if self.config.browser_engine == "multilogin" else "AdsPower"
            if browser_manager and self.isInterruptionRequested():
                self._emit_status(f"Closing {engine_title} browser...")
                try:
                    browser_manager.stop()
                except Exception:
                    worker_logger.exception(f"Failed to stop {engine_title} browser cleanly.")
            elif browser_manager:
                self._emit_status(f"{engine_title} browser left open. Click Stop when finished.")

    def _open_target_page(self, page, target_url: str):
        context = page.context
        last_error: Exception | None = None

        for attempt in range(1, 4):
            try:
                if page.is_closed():
                    page = context.pages[-1] if context.pages else context.new_page()
                page.goto(
                    target_url,
                    wait_until="domcontentloaded",
                    timeout=self.config.timeouts.page_load_ms,
                )
                return page
            except Exception as exc:
                last_error = exc
                self._emit_status(f"Navigation attempt {attempt}/3 failed: {exc}")
                time.sleep(1.0)
                page = context.new_page()

        raise RuntimeError(f"Could not open target URL after 3 attempts: {last_error}")

    def _publish_files(self, server: TemporaryFileServer):
        source_dir = None
        for candidate in [
            Path(sys.executable).resolve().parent / "Source file",
            Path(getattr(sys, "_MEIPASS", "")) / "Source file",
            Path(__file__).resolve().parent / "Source file",
        ]:
            if candidate.is_dir():
                source_dir = candidate
                break

        if source_dir:
            try:
                server.copy_directory(source_dir)
                self._emit_status("Published mock verification assets from 'Source file' directory to local server.")
            except Exception as exc:
                logging.getLogger("desktop_app.worker").warning(
                    "Could not publish 'Source file' to local server: %s", exc
                )

        selected_files = [Path(file_path) for file_path in self.files if file_path]
        self._blob_server_urls = [None, None, None]

        for slot_index, blob_path in enumerate(self._blob_source_paths):
            if not blob_path or not blob_path.is_file():
                continue
            published_name = f"camera-slot-{slot_index + 1}{blob_path.suffix.lower()}"
            published_url = server.copy_file(blob_path, filename=published_name)
            self._blob_server_urls[slot_index] = published_url
            self._emit_status(
                f"Published camera slot {slot_index + 1}: {blob_path.name} -> {published_url}"
            )

        if not selected_files and not (server.directory and (server.directory / "index.html").exists()):
            index_url = server.write_text(
                "index.html",
                "<!doctype html><title>Local Server</title><h1>Local server is running</h1>",
            )
            self._emit_status(f"Published default local page: {index_url}")
            return

        for file_path in selected_files:
            published_url = server.copy_file(file_path)
            self._emit_status(f"Published file: {file_path} -> {published_url}")

    def _run_capture_automation(self, page):
        has_video_files = any(
            file_path and Path(file_path).is_file() for file_path in self.files[:3]
        )
        if not has_video_files:
            self._emit_status("Capture automation skipped: no video files selected.")
            return

        has_y4m = any(self._automation_capture_paths)
        if not has_y4m:
            self._emit_status(
                "No .y4m files ready; continuing with Chromium default fake camera feed."
            )

        self._emit_status("Automation started: ID document, selfie, then liveness.")
        self._validate_three_unique_videos()
        self._preflight_camera_sources()
        self._ensure_camera_permissions(page)
        self._wait_for_verification_ready(page)

        steps = (
            (0, self._step1_id_document, "File 1 / ID document"),
            (1, self._step2_selfie, "File 2 / selfie"),
            (2, self._step3_liveness, "File 3 / liveness"),
        )
        start_index = self._detect_start_step(page)
        if start_index > 0:
            self._emit_status(
                f"Resuming automation from step {start_index + 1} based on current page."
            )

        for slot_index, step_handler, label in steps[start_index:]:
            page = self._active_page()
            if slot_index == 2:
                attempts = 1 + self._automation.liveness_retry_count
                success = False
                for attempt in range(attempts):
                    if attempt > 0:
                        self._emit_status(
                            f"Retrying {label} ({attempt + 1}/{attempts})..."
                        )
                        self._verification_accepted_url = None
                        self._reset_liveness_step(page)
                    try:
                        success = step_handler(page)
                        if success:
                            break
                    except RuntimeError as exc:
                        self._emit_status(str(exc))
                        if attempt >= attempts - 1:
                            raise
                if not success:
                    raise RuntimeError(f"{label} automation failed.")
            elif not step_handler(page):
                raise RuntimeError(f"{label} automation failed.")
            self._bind_work_page(self._active_page())

        if self._verification_accepted_url:
            self.verification_passed.emit(self._verification_accepted_url)
            self._emit_status(
                f"VERIFICATION PASSED by agesmart.eu: {self._verification_accepted_url}"
            )
        else:
            self._emit_status(
                "Automation flow finished, but no site verification success was detected."
            )

        self._emit_status("Automation completed: ID document, selfie, and liveness.")

    def _resolve_live_page(self, page):
        if page and not page.is_closed():
            self._work_page = page
            return page

        context = None
        if page is not None:
            try:
                context = page.context
            except Exception:
                context = None
        if context is None and self._work_page is not None:
            try:
                context = self._work_page.context
            except Exception:
                context = None

        if context is not None:
            try:
                for candidate in reversed(context.pages):
                    if not candidate.is_closed():
                        if page is not None and page.is_closed():
                            self._emit_status("Switched to a live browser tab after navigation.")
                        self._work_page = candidate
                        return candidate
            except Exception as exc:
                raise RuntimeError(
                    f"Could not access AdsPower browser tabs: {exc}"
                ) from exc
            raise RuntimeError(
                "No live browser tab is open. AdsPower may have closed the verification page."
            )

        raise RuntimeError("No live browser page is available for automation.")

    def _detect_start_step(self, page) -> int:
        url = page.url.lower()
        if "btn-video-instructions-proceed" in self._visible_button_ids(page):
            return 2
        if "/verification/selfie/" in url or self._is_button_visible(page, "btn-take-photo-selfy"):
            return 1
        if self._is_button_visible(page, "btn-take-photo-id"):
            return 0
        if "/verification/selfie/" in url:
            return 1
        return 0

    def _visible_button_ids(self, page) -> set[str]:
        visible: set[str] = set()
        for element_id in (
            "btn-take-photo-id",
            "btn-take-photo-selfy",
            "btn-video-instructions-proceed",
            "btn-video-submit-proceed",
        ):
            if self._is_button_visible(page, element_id):
                visible.add(element_id)
        return visible

    @staticmethod
    def _is_button_visible(page, element_id: str) -> bool:
        for root in WorkerThread._page_roots(page):
            try:
                locator = root.locator(f"#{element_id}")
                if locator.count() > 0 and locator.first.is_visible():
                    return True
            except Exception:
                continue
        return False

    @staticmethod
    def _page_roots(page):
        roots = [page]
        for frame in page.frames:
            if frame not in roots:
                roots.append(frame)
        return roots

    def _locate_button(
        self,
        page,
        element_id: str,
        *,
        text: str | None = None,
    ):
        selectors = [f"#{element_id}"]
        if text:
            selectors.extend(
                [
                    f"button#{element_id}",
                    f"button:has-text('{text}')",
                    f"#{element_id}:has-text('{text}')",
                    f"text={text}",
                ]
            )
        elif element_id in SELFIE_BUTTON_IDS:
            for selfie_text in SELFIE_BUTTON_TEXTS:
                selectors.extend(
                    [
                        f"button:has-text('{selfie_text}')",
                        f"#{element_id}:has-text('{selfie_text}')",
                    ]
                )
        elif element_id == ID_BUTTON_ID:
            for id_text in ID_BUTTON_TEXTS:
                selectors.extend(
                    [
                        f"button:has-text('{id_text}')",
                        f"#{element_id}:has-text('{id_text}')",
                    ]
                )

        for root in self._page_roots(page):
            for selector in selectors:
                try:
                    locator = root.locator(selector)
                    if locator.count() > 0:
                        return locator.first, root
                except Exception:
                    continue
        return page.locator(f"#{element_id}").first, page

    def _open_camera_for_step(self, page, button_id: str, label: str) -> bool:
        if button_id in SELFIE_BUTTON_IDS:
            return self._click_selfie_ready(page)
        if button_id == ID_BUTTON_ID:
            return self._click_id_ready(page)

        opener_visible = self._is_button_visible(page, button_id)
        camera_visible = self._is_button_visible(page, CAMERA_BUTTON_ID)
        if camera_visible and not opener_visible:
            self._emit_status(f"{label}: camera view already open.")
            return True

        self._emit_status(f"Opening camera for {label} (#{button_id})...")
        for attempt in range(1, 4):
            self._emit_status(f"{label}: fast open attempt {attempt}/3")
            self._fast_click_element(page, button_id, label)
            if self._wait_for_camera_ready(page, timeout_ms=8000):
                return True
            if self._fast_click_only(page, button_id, label, text=None):
                if self._wait_for_camera_ready(page, timeout_ms=8000):
                    return True

        if self._is_button_visible(page, CAMERA_BUTTON_ID):
            self._emit_status(f"{label}: camera opened after retries.")
            return True

        self._emit_status(f"{label}: camera view did not open.")
        return False

    def _click_id_ready(self, page) -> bool:
        self._emit_status("Step 1: clicking I'm ready / Take photo of ID...")
        return self._click_opener_button(
            page,
            ID_BUTTON_ID,
            "ID Ready",
            ID_BUTTON_TEXTS,
            step_label="Step 1 opener",
            allow_playwright=False,
        )

    def _click_selfie_ready(self, page) -> bool:
        button_id = self._resolve_selfie_button_id(page)
        self._emit_status(
            f"Step 2: clicking I AM READY / TAKE SELFIE HOLDING ID (#{button_id})..."
        )
        return self._click_opener_button(
            page,
            button_id,
            "Selfie",
            SELFIE_BUTTON_TEXTS,
            step_label="Step 2 opener",
            allow_playwright=True,
            prefer_cdp=True,
        )

    def _click_opener_button(
        self,
        page,
        button_id: str,
        label: str,
        text_options: tuple[str, ...],
        *,
        step_label: str,
        allow_playwright: bool = False,
        prefer_cdp: bool = False,
    ) -> bool:
        for attempt in range(1, 6):
            page = self._active_page(page)
            self._emit_status(f"{step_label} click attempt {attempt}/5")
            self._scroll_button_into_view(page, button_id)

            if not self._is_button_visible(page, button_id):
                self._emit_status(f"{step_label}: button not visible yet, waiting...")
                if not self._wait_for_any_visible(page, [button_id], timeout_ms=5000):
                    time.sleep(0.8)
                    continue

            if prefer_cdp and allow_playwright and self._click_opener_cdp(page, button_id, label):
                time.sleep(1.0)
                if self._opener_camera_opened(page, button_id):
                    return True

            if self._fast_click_element(page, button_id, label):
                time.sleep(1.0)
                if self._opener_camera_opened(page, button_id):
                    return True

            for text in text_options:
                if self._fast_click_only(page, button_id, label, text=text):
                    time.sleep(1.0)
                    if self._opener_camera_opened(page, button_id):
                        return True

            if self._click_opener_js(page, button_id):
                time.sleep(1.0)
                if self._opener_camera_opened(page, button_id):
                    return True

            if allow_playwright and not prefer_cdp and self._click_opener_cdp(page, button_id, label):
                time.sleep(1.0)
                if self._opener_camera_opened(page, button_id):
                    return True

            if allow_playwright and self._click_opener_playwright(page, button_id, label):
                time.sleep(1.0)
                if self._opener_camera_opened(page, button_id):
                    return True

            time.sleep(0.8)

        self._emit_status(f"Could not click opener #{button_id}.")
        return False

    def _click_opener_playwright(
        self,
        page,
        button_id: str,
        label: str,
    ) -> bool:
        page = self._active_page(page)
        locator, click_root = self._locate_button(page, button_id)
        try:
            box = locator.bounding_box(timeout=2000)
            if not box:
                self._emit_status(f"Opener #{button_id} has no bounding box.")
                return False
            x = box["x"] + box["width"] / 2
            y = box["y"] + box["height"] / 2
            try:
                click_root.touchscreen.tap(x, y)
                tap_kind = "touch"
            except Exception:
                click_root.mouse.click(x, y)
                tap_kind = "mouse"
            self._emit_status(
                f"Opener tap on #{button_id} ({label}) via {tap_kind} at ({x:.0f}, {y:.0f})."
            )
            return True
        except Exception as exc:
            self._emit_status(f"Opener tap failed for #{button_id}: {exc}")
            return False

    def _derive_verification_token(self, page_url: str) -> str | None:
        parsed = urlparse(page_url)
        segments = [segment for segment in parsed.path.split("/") if segment]
        if len(segments) < 2:
            return None
        return segments[-1]

    def _verification_step_url(self, page_url: str, step: str) -> str | None:
        token = self._derive_verification_token(page_url)
        if not token:
            return None
        parsed = urlparse(page_url)
        return f"{parsed.scheme}://{parsed.netloc}/verification/{step}/{token}"

    def _reinstall_blob_camera(
        self,
        page,
        *,
        slot: int | None = None,
        slot_label: str = "",
    ) -> None:
        self._blob_camera_ready = False
        self._blob_urls_cache = [None, None, None]
        if self._should_prepare_blob_camera():
            self._ensure_blob_camera_switcher(page)
        if slot is not None:
            label = slot_label or f"File {slot + 1}"
            self._select_virtual_camera_video(page, slot, label, force=True)

    def _prepare_selfie_step(self, page) -> bool:
        page = self._active_page(page)
        if not self._wait_for_step_transition(
            page,
            expected_url_part="/verification/selfie/",
            button_ids=list(SELFIE_BUTTON_IDS),
            label="selfie step",
            timeout_ms=45000,
        ):
            return False
        if not self._wait_for_selfie_step_ready(page, timeout_ms=30000):
            return False

        page = self._active_page(page)
        self._reinstall_blob_camera(page)
        self._ensure_camera_permissions(page)
        try:
            page.wait_for_timeout(max(2000, self._automation.step_settle_ms))
        except Exception:
            time.sleep(max(2.0, self._automation.step_settle_ms / 1000))
        return True

    def _click_opener_cdp(self, page, button_id: str, label: str) -> bool:
        page = self._active_page(page)
        locator, _ = self._locate_button(page, button_id)
        try:
            box = locator.bounding_box(timeout=2000)
            if not box:
                self._emit_status(f"Opener #{button_id} has no bounding box for CDP tap.")
                return False
            x = box["x"] + box["width"] / 2
            y = box["y"] + box["height"] / 2
            client = page.context.new_cdp_session(page)
            try:
                client.send(
                    "Input.dispatchTouchEvent",
                    {
                        "type": "touchStart",
                        "touchPoints": [{"x": x, "y": y}],
                    },
                )
                client.send(
                    "Input.dispatchTouchEvent",
                    {
                        "type": "touchEnd",
                        "touchPoints": [],
                    },
                )
                tap_kind = "cdp-touch"
            except Exception:
                client.send(
                    "Input.dispatchMouseEvent",
                    {
                        "type": "mousePressed",
                        "x": x,
                        "y": y,
                        "button": "left",
                        "clickCount": 1,
                    },
                )
                client.send(
                    "Input.dispatchMouseEvent",
                    {
                        "type": "mouseReleased",
                        "x": x,
                        "y": y,
                        "button": "left",
                        "clickCount": 1,
                    },
                )
                tap_kind = "cdp-mouse"
            self._emit_status(
                f"Opener CDP tap on #{button_id} ({label}) via {tap_kind} at ({x:.0f}, {y:.0f})."
            )
            return True
        except Exception as exc:
            self._emit_status(f"Opener CDP tap failed for #{button_id}: {exc}")
            return False

    def _release_previous_camera_session(self, page) -> None:
        page = self._active_page(page)
        self._emit_status("Stopping in-page virtual camera before next step...")
        for root in self._page_roots(page):
            try:
                root.evaluate("() => { window.__stopVirtualCamera?.(); }")
            except Exception:
                continue
        try:
            page.wait_for_timeout(500)
        except Exception:
            time.sleep(0.5)

    def _opener_camera_opened(self, page, opener_id: str) -> bool:
        if not self._wait_for_camera_ready(page, timeout_ms=12000):
            return False

        if self._is_button_visible(page, opener_id):
            self._emit_status(
                f"TAKE PHOTO is visible but opener #{opener_id} is still on screen; retrying opener click."
            )
            return False

        self._emit_status(f"Opener #{opener_id} closed; camera session started.")
        return self._wait_for_camera_preview_stable(page)

    def _pause_ms(self, page, delay_ms: int) -> None:
        delay_ms = max(0, delay_ms)
        try:
            page = self._active_page(page)
            page.wait_for_timeout(delay_ms)
        except Exception:
            time.sleep(delay_ms / 1000)

    def _pause_ms_jitter(self, page, base_ms: int, *, jitter_ms: int | None = None) -> None:
        jitter = (
            self._automation.human_delay_jitter_ms
            if jitter_ms is None
            else max(0, jitter_ms)
        )
        extra = random.randint(0, jitter) if jitter else 0
        self._pause_ms(page, base_ms + extra)

    def _evaluate_on_page(self, page, script: str):
        page = self._active_page(page)
        for root in self._page_roots(page):
            try:
                return root.evaluate(script)
            except Exception:
                continue
        return page.evaluate(script)

    def _wait_for_wizard_loader_idle(
        self,
        page,
        *,
        timeout_ms: int | None = None,
        label: str = "wizard loader",
    ) -> bool:
        timeout_ms = timeout_ms or max(15000, self._automation.step_settle_ms * 4)
        self._emit_status(f"Waiting for {label} to finish...")
        deadline = time.monotonic() + (timeout_ms / 1000)
        while time.monotonic() < deadline:
            try:
                if self._evaluate_on_page(page, wizard_loader_idle_script()):
                    self._emit_status(f"{label.capitalize()} is idle.")
                    return True
            except Exception as exc:
                self._emit_status(f"Loader check retry: {exc}")
            self._pause_ms(page, 250)
        self._emit_status(f"{label.capitalize()} did not finish within {timeout_ms} ms.")
        return False

    def _wait_for_wizard_camera_video(
        self,
        page,
        *,
        timeout_ms: int | None = None,
    ) -> bool:
        timeout_ms = timeout_ms or max(20000, self._automation.camera_warmup_ms * 3)
        self._emit_status(
            f"Waiting for #{WIZARD_CAMERA_VIDEO_ID} stream to become ready..."
        )
        deadline = time.monotonic() + (timeout_ms / 1000)
        last_reason = ""
        while time.monotonic() < deadline:
            try:
                result = self._evaluate_on_page(page, wizard_video_ready_script())
                if isinstance(result, dict) and result.get("ok"):
                    self._emit_status(
                        "Wizard camera ready: "
                        f"{result.get('width')}x{result.get('height')}."
                    )
                    return True
                if isinstance(result, dict):
                    last_reason = str(result.get("reason", "unknown"))
            except Exception as exc:
                last_reason = str(exc)
            self._pause_ms(page, 300)
        self._emit_status(
            f"Wizard camera video not ready in time ({last_reason or 'timeout'})."
        )
        return False

    def _wait_for_finish_button_enabled(
        self,
        page,
        *,
        timeout_ms: int | None = None,
    ) -> bool:
        timeout_ms = timeout_ms or max(20000, self._automation.capture_settle_ms * 6)
        script = wizard_finish_button_enabled_script(FINISHED_BUTTON_ID)
        self._emit_status(
            f"Waiting for #{FINISHED_BUTTON_ID} to become enabled..."
        )
        deadline = time.monotonic() + (timeout_ms / 1000)
        while time.monotonic() < deadline:
            try:
                if self._evaluate_on_page(page, script):
                    self._emit_status("FINISHED button is enabled.")
                    return True
            except Exception:
                pass
            self._pause_ms(page, 400)
        self._emit_status("FINISHED button did not become enabled in time.")
        return False

    @staticmethod
    def _is_element_visible(page, element_id: str) -> bool:
        return WorkerThread._is_button_visible(page, element_id)

    def _wait_for_camera_preview_stable(self, page) -> bool:
        warmup_ms = max(4000, self._automation.camera_warmup_ms)
        self._emit_status(f"Warming up camera preview ({warmup_ms} ms before capture)...")
        page = self._active_page(page)

        if self._evaluate_on_page(
            page, wizard_panel_visible_script(WIZARD_PANEL_CAMERA)
        ):
            self._wait_for_wizard_loader_idle(page, label="camera loader")
            if not self._wait_for_wizard_camera_video(page):
                self._emit_status(
                    "Wizard camera element not ready; falling back to generic warmup."
                )

        deadline = time.monotonic() + min(warmup_ms / 1000, 10)
        while time.monotonic() < deadline:
            try:
                preview_ready = page.evaluate(
                    """
                    () => {
                      for (const video of document.querySelectorAll("video")) {
                        if (video.readyState >= 2 && video.videoWidth > 0) {
                          return true;
                        }
                      }
                      return false;
                    }
                    """
                )
                if preview_ready:
                    self._emit_status("Camera preview frames are ready.")
                    break
            except Exception:
                pass
            self._pause_ms(page, 300)

        self._pause_ms_jitter(page, warmup_ms)
        self._emit_status("Camera preview warmup complete.")
        return True

    def _click_opener_js(self, page, button_id: str) -> bool:
        for root in self._page_roots(page):
            try:
                clicked = root.evaluate(
                    """
                    (id) => {
                      const btn = document.getElementById(id);
                      if (!btn) return false;
                      btn.scrollIntoView({ block: "center", inline: "center" });
                      const targets = [btn, btn.querySelector("h4")].filter(Boolean);
                      for (const target of targets) {
                        if (typeof target.click === "function") target.click();
                      }
                      return true;
                    }
                    """,
                    button_id,
                )
                if clicked:
                    self._emit_status(f"JS click on #{button_id} (+ inner h4).")
                    return True
            except Exception:
                continue
        return False

    def _click_selfie_ready_js(self, page) -> bool:
        return self._click_opener_js(page, "btn-take-photo-selfy")

    def _scroll_button_into_view(self, page, element_id: str) -> None:
        for root in self._page_roots(page):
            try:
                root.evaluate(
                    """
                    (id) => {
                      const el = document.getElementById(id);
                      if (!el) return false;
                      el.scrollIntoView({ block: "center", inline: "center", behavior: "instant" });
                      return true;
                    }
                    """,
                    element_id,
                )
                return
            except Exception:
                continue

    def _run_photo_capture_step(
        self,
        page,
        *,
        video_slot: int,
        video_label: str,
        opener_call: Callable[[], bool],
        step_name: str,
    ) -> bool:
        self._emit_status(f"{step_name} started (4 buttons + video {video_slot + 1}).")

        if video_slot == 0:
            self._select_virtual_camera_video(page, video_slot, video_label)
            self._ensure_camera_permissions(page)
        else:
            self._select_virtual_camera_video(page, video_slot, video_label, force=True)
            self._ensure_camera_permissions(page)

        self._emit_status(f"{step_name} button 1/4: opener")
        if not opener_call():
            return False

        self._emit_status(f"{step_name} button 2/4: {CAMERA_BUTTON_TEXT}")
        if not self._click_take_photo(page):
            return False

        self._wait_for_wizard_loader_idle(page, label="photo upload loader")

        capture_settle_ms = max(1500, self._automation.capture_settle_ms)
        self._emit_status(
            f"Waiting {capture_settle_ms} ms for photo processing before OK..."
        )
        self._pause_ms(page, capture_settle_ms)

        if not self._wait_for_any_visible(
            page,
            [OK_BUTTON_ID, FINISHED_BUTTON_ID],
            timeout_ms=20000,
        ):
            self._emit_status(f"{step_name}: OK/FINISHED controls did not appear.")
            return False

        self._emit_status(f"{step_name} button 3/4: {OK_BUTTON_TEXT}")
        if not self._safe_click_target(
            page,
            OK_BUTTON_ID,
            OK_BUTTON_TEXT,
            text=OK_BUTTON_TEXT,
        ):
            return False

        self._wait_for_wizard_loader_idle(page, label="redacting loader")
        if self._evaluate_on_page(
            page, wizard_panel_visible_script(WIZARD_PANEL_REDACTING)
        ):
            self._emit_status("Redacting panel detected; waiting for FINISHED enable.")
            self._wait_for_finish_button_enabled(page)

        post_capture_ms = max(1000, self._automation.post_capture_ms)
        self._emit_status(
            f"Waiting {post_capture_ms} ms after OK before FINISHED..."
        )
        self._pause_ms(page, post_capture_ms)

        self._emit_status(f"{step_name} button 4/4: {FINISHED_BUTTON_TEXT}")
        if not self._safe_click_target(
            page,
            FINISHED_BUTTON_ID,
            FINISHED_BUTTON_TEXT,
            text=FINISHED_BUTTON_TEXT,
        ):
            return False

        self._emit_status(f"{step_name} completed.")
        self._wait_for_wizard_loader_idle(page, label="step transition loader")
        return True

    def _click_take_photo(self, page) -> bool:
        self._emit_status(f"Clicking #{CAMERA_BUTTON_ID} ({CAMERA_BUTTON_TEXT})...")
        page = self._active_page(page)
        self._wait_for_camera_preview_stable(page)

        for attempt in range(1, 4):
            self._emit_status(f"{CAMERA_BUTTON_TEXT} attempt {attempt}/3")
            self._fast_click_element(page, CAMERA_BUTTON_ID, "Capture")
            self._pause_ms(page, max(1200, self._automation.step_settle_ms))
            self._wait_for_wizard_loader_idle(page, label="capture loader", timeout_ms=25000)
            if self._wait_for_any_visible(
                page,
                [OK_BUTTON_ID, FINISHED_BUTTON_ID],
                timeout_ms=6000,
            ):
                self._emit_status("Photo captured; OK/FINISHED controls visible.")
                return True
            if self._fast_click_only(
                page,
                CAMERA_BUTTON_ID,
                "Capture",
                text=CAMERA_BUTTON_TEXT,
            ):
                self._pause_ms(page, max(1200, self._automation.step_settle_ms))
                if self._wait_for_any_visible(
                    page,
                    [OK_BUTTON_ID, FINISHED_BUTTON_ID],
                    timeout_ms=6000,
                ):
                    return True

            self._pause_ms(page, 1000)

        return self._safe_click_target(
            page,
            CAMERA_BUTTON_ID,
            "Capture",
            text=CAMERA_BUTTON_TEXT,
            timeout_ms=8000,
            allow_playwright_click=False,
        )

    def _resolve_selfie_button_id(self, page) -> str:
        for button_id in SELFIE_BUTTON_IDS:
            if self._is_button_visible(page, button_id):
                return button_id
        return SELFIE_BUTTON_IDS[0]

    def _wait_for_step_transition(
        self,
        page,
        *,
        expected_url_part: str,
        button_ids: list[str],
        label: str,
        timeout_ms: int = 45000,
    ) -> bool:
        self._emit_status(f"Waiting for {label}...")
        deadline = time.monotonic() + (timeout_ms / 1000)
        last_url = ""

        while time.monotonic() < deadline:
            page = self._active_page(page)
            try:
                current_url = page.url
                if current_url != last_url:
                    self._emit_status(f"Current URL: {current_url}")
                    last_url = current_url
                if expected_url_part and expected_url_part.lower() in current_url.lower():
                    self._emit_status(f"{label} page detected.")
                    try:
                        page.wait_for_load_state("domcontentloaded", timeout=5000)
                    except Exception:
                        pass
                    time.sleep(1.0)
                    return True
            except Exception as exc:
                self._emit_status(f"Waiting for {label}: {exc}")

            for button_id in button_ids:
                if self._is_button_visible(page, button_id):
                    self._emit_status(f"{label} control visible: #{button_id}")
                    return True

            try:
                page.wait_for_timeout(500)
            except Exception:
                time.sleep(0.5)

        self._emit_status(f"{label} did not appear within {timeout_ms} ms.")
        return False

    def _fast_click_element(self, page, element_id: str, label: str) -> bool:
        page = self._active_page(page)
        for root in self._page_roots(page):
            try:
                clicked = root.evaluate(
                    """
                    (id) => {
                      const el = document.getElementById(id);
                      if (!el) return false;
                      el.scrollIntoView({ block: "center", inline: "center" });
                      const events = [
                        "pointerdown", "touchstart", "mousedown",
                        "pointerup", "touchend", "mouseup", "click",
                      ];
                      for (const name of events) {
                        try {
                          let EventType = MouseEvent;
                          if (name.startsWith("pointer")) EventType = PointerEvent;
                          else if (name.startsWith("touch")) EventType = TouchEvent;
                          el.dispatchEvent(new EventType(name, {
                            bubbles: true,
                            cancelable: true,
                            view: window,
                          }));
                        } catch (_) {}
                      }
                      if (typeof el.click === "function") el.click();
                      return true;
                    }
                    """,
                    element_id,
                )
                if clicked:
                    self._emit_status(f"Fast DOM click on #{element_id} ({label}).")
                    return True
            except Exception:
                continue
        return False

    def _fast_click_only(
        self,
        page,
        element_id: str,
        label: str,
        *,
        text: str | None,
    ) -> bool:
        page = self._active_page(page)
        locator, click_root = self._locate_button(page, element_id, text=text)
        return self._click_with_fallbacks(
            click_root,
            locator,
            3000,
            element_id=element_id,
            allow_playwright_click=False,
        )

    def _wait_for_verification_ready(self, page, timeout_ms: int | None = None) -> bool:
        timeout_ms = timeout_ms or self.config.timeouts.page_load_ms
        self._emit_status("Waiting for verification page controls...")
        self._install_video_step_script(page)
        ready = self._wait_for_any_visible(
            page,
            [
                "btn-take-photo-id",
                "btn-take-photo-selfy",
                "btn-video-instructions-proceed",
                "btn-video-submit-proceed",
            ],
            timeout_ms=timeout_ms,
        )
        if ready:
            page.wait_for_timeout(self._automation.step_settle_ms)
            return True
        self._emit_status("Verification controls did not appear in time.")
        return False

    def _validate_three_unique_videos(self):
        slots = self.files[:3]
        missing = [
            str(index + 1)
            for index, file_path in enumerate(slots)
            if not file_path or not Path(file_path).is_file()
        ]
        if missing:
            raise RuntimeError(
                "File 1, File 2, and File 3 are all required for capture automation. "
                f"Missing slots: {', '.join(missing)}"
            )

        resolved = [Path(file_path).resolve() for file_path in slots]
        if len(set(resolved)) != 3:
            raise RuntimeError(
                "File 1, File 2, and File 3 must be three different videos. "
                "Using the same video in multiple slots will fail verification."
            )

        max_mb = MAX_CAMERA_VIDEO_BYTES // (1024 * 1024)
        oversized = [
            f"File {index + 1} ({path.name}, {path.stat().st_size // (1024 * 1024)} MB)"
            for index, path in enumerate(resolved)
            if path.stat().st_size > MAX_CAMERA_VIDEO_BYTES
        ]
        if oversized:
            raise RuntimeError(
                f"Each video must be {max_mb} MB or smaller. Oversized: {', '.join(oversized)}"
            )

    def _preflight_camera_sources(self) -> None:
        self._emit_status("Preflight: checking all 3 camera video slots...")
        missing_slots: list[str] = []
        missing_server: list[str] = []

        for index in range(3):
            label = f"File {index + 1}"
            raw_path = self.files[index] if index < len(self.files) else ""
            if not raw_path or not Path(raw_path).is_file():
                missing_slots.append(label)
                continue

            blob_path = (
                self._blob_source_paths[index]
                if index < len(self._blob_source_paths)
                else None
            )
            if not blob_path or not blob_path.is_file():
                missing_slots.append(f"{label} (ffmpeg/scaled output missing)")
                continue

            size_mb = blob_path.stat().st_size // (1024 * 1024)
            self._emit_status(
                f"Preflight OK: {label} -> {Path(raw_path).name} "
                f"({size_mb} MB prepared as {blob_path.name})"
            )

            server_url = (
                self._blob_server_urls[index]
                if index < len(self._blob_server_urls)
                else None
            )
            if not server_url:
                missing_server.append(label)

            if index == 2:
                min_seconds = self._automation.liveness_min_duration_seconds
                duration = VirtualCameraService.probe_duration_seconds(raw_path)
                if duration is None:
                    self._emit_status(
                        f"Preflight note: could not probe File 3 duration; "
                        f"recommended minimum is {min_seconds}s."
                    )
                elif duration < min_seconds:
                    self._emit_status(
                        f"Preflight warning: File 3 is only {duration:.1f}s; "
                        f"recommended minimum is {min_seconds}s for liveness."
                    )
                else:
                    self._emit_status(
                        f"Preflight OK: File 3 duration {duration:.1f}s "
                        f"(minimum recommended {min_seconds}s)."
                    )

        if missing_slots:
            raise RuntimeError(
                "Preflight failed. Missing or unreadable camera slots: "
                + ", ".join(missing_slots)
            )
        if missing_server:
            raise RuntimeError(
                "Preflight failed. Local server URLs missing for: "
                + ", ".join(missing_server)
            )

        self._emit_status("Preflight passed: Files 1, 2, and 3 are ready for automation.")

    def _reset_liveness_step(self, page) -> None:
        page = self._active_page(page)
        current_url = page.url
        self._video_step_installed = False
        try:
            page.goto(
                current_url,
                wait_until="domcontentloaded",
                timeout=self.config.timeouts.page_load_ms,
            )
        except Exception as exc:
            self._emit_status(f"Liveness retry page reload failed: {exc}")
        page = self._bind_work_page(self._active_page(page))
        self._reinstall_blob_camera(
            page,
            slot=2,
            slot_label="File 3 / liveness",
        )
        self._grant_media_permissions(
            page,
            self._collect_media_origins(page.url, page),
            reset_blocked=False,
        )
        self._install_video_step_script(page)
        self._pause_ms_jitter(page, 2000)

    def _should_prepare_blob_camera(self) -> bool:
        return any(
            file_path and Path(file_path).is_file()
            for file_path in self.files[:3]
        )

    def _needs_blob_camera_switcher(self) -> bool:
        return self._should_prepare_blob_camera()

    def _slot_source_path(self, index: int) -> Path | None:
        if index < len(self._blob_source_paths) and self._blob_source_paths[index]:
            return self._blob_source_paths[index]
        if index < len(self._automation_capture_paths):
            return self._automation_capture_paths[index]
        return None

    def _resolve_capture_source(self, index: int) -> Path | None:
        if index < len(self._automation_capture_paths):
            return self._automation_capture_paths[index]
        return None

    def _page_virtual_camera_index(self, page) -> int | None:
        try:
            return page.evaluate(
                "() => (typeof window.__getVirtualCameraIndex === 'function' "
                "? window.__getVirtualCameraIndex() : null)"
            )
        except Exception:
            return None

    def _select_virtual_camera_video(
        self,
        page,
        index: int,
        label: str,
        *,
        force: bool = False,
    ):
        if index >= len(self.files) or not self.files[index]:
            raise RuntimeError(f"{label} is missing a video file.")

        source_label = Path(self.files[index]).name
        blob_path = self._slot_source_path(index)
        if blob_path is None:
            raise RuntimeError(f"{label} could not be prepared for camera output.")

        if not force:
            page_index = self._page_virtual_camera_index(page)
            if (
                self._current_video_index == index
                and self._active_source_path == blob_path.resolve()
                and page_index == index
            ):
                self._emit_status(
                    f"Virtual camera already active for {label}: {source_label}"
                )
                return

        source_path = self._resolve_capture_source(index)
        if (
            self._staged_source_path
            and source_path
            and source_path.resolve() == self._staged_source_path.resolve()
            and index == 0
        ):
            self._current_video_index = index
            self._active_source_path = source_path.resolve()
            self._emit_status(
                f"Selected virtual camera video: {label} ({source_label})"
            )
            return

        if source_path and self._active_capture_path:
            try:
                staged_path = VirtualCameraService.stage_capture(
                    source_path,
                    self._active_capture_path,
                )
                self._active_capture_path = staged_path
                self._current_video_index = index
                self._active_source_path = source_path.resolve()
                self._emit_status(
                    f"Selected virtual camera video: {label} ({source_label})"
                )
                self._sync_blob_camera_slot(page, index, label)
                return
            except PermissionError:
                self._emit_status(
                    f"Capture file locked by Chromium; switching in-page camera for {label}."
                )

        if index < len(self._blob_source_paths) and self._blob_source_paths[index]:
            self._switch_blob_camera(page, index, label, self._blob_source_paths[index])
            self._active_source_path = self._blob_source_paths[index].resolve()
            self._current_video_index = index
            return

        if not source_path:
            raise RuntimeError(f"{label} does not have a prepared .y4m capture file.")

        self._switch_blob_camera(page, index, label, blob_path)
        self._active_source_path = blob_path.resolve()
        self._current_video_index = index

    def _verify_virtual_camera_slot(self, page, index: int, label: str) -> bool:
        page_index = self._page_virtual_camera_index(page)
        if page_index == index:
            return True
        self._emit_status(
            f"Camera slot mismatch for {label}: page has slot "
            f"{(page_index + 1) if page_index is not None else '?'}, expected {index + 1}. "
            "Re-switching..."
        )
        blob_path = self._slot_source_path(index)
        if blob_path is None:
            return False
        self._switch_blob_camera(page, index, label, blob_path)
        page_index = self._page_virtual_camera_index(page)
        if page_index == index:
            self._emit_status(f"Camera slot {index + 1} confirmed for {label}.")
            return True
        self._emit_status(
            f"Could not confirm camera slot {index + 1} for {label} "
            f"(page reports slot {(page_index + 1) if page_index is not None else '?'})."
        )
        return False

    def _restart_liveness_camera_stream(self, page) -> None:
        try:
            page.evaluate(
                """
                async () => {
                  const slot = window.__livenessUploadSlot ?? 2;
                  window.__stopVirtualCamera?.();
                  if (window.__setVirtualCameraVideo) {
                    await window.__setVirtualCameraVideo(slot);
                  }
                  const webcam = document.getElementById("webcam");
                  if (webcam?.srcObject) {
                    webcam.srcObject.getTracks().forEach((track) => track.stop());
                    webcam.srcObject = null;
                  }
                }
                """
            )
            self._emit_status("Liveness camera stream reset for File 3.")
        except Exception as exc:
            self._emit_status(f"Could not reset liveness camera stream: {exc}")

    def _sync_liveness_video_playback(self, page) -> None:
        auto = self._automation
        try:
            result = page.evaluate(
                """
                async () => {
                  if (typeof window.__resetVirtualCameraForLiveness !== "function") {
                    return { ok: false, reason: "no-playback-api" };
                  }
                  const reset = await window.__resetVirtualCameraForLiveness();
                  const playbackMs = window.__getVirtualCameraPlaybackMs?.() ?? 0;
                  const durationMs = window.__getVirtualCameraDurationMs?.() ?? 0;
                  return {
                    ok: reset,
                    playbackMs,
                    durationMs,
                  };
                }
                """
            )
        except Exception as exc:
            self._emit_status(f"Could not sync File 3 playback to start: {exc}")
            return

        if not result.get("ok"):
            self._emit_status(
                "File 3 playback sync skipped (camera stream not ready yet)."
            )
            return

        duration_ms = int(result.get("durationMs") or 0)
        duration_sec = duration_ms / 1000 if duration_ms else 0
        if duration_sec > 0:
            self._emit_status(
                f"File 3 synced to 0s (video duration {duration_sec:.1f}s, "
                f"timeline min {auto.liveness_min_duration_seconds}s)."
            )
        else:
            self._emit_status("File 3 playback synced to 0s for liveness timeline.")

    def _sync_blob_camera_slot(self, page, index: int, label: str) -> None:
        if not self._blob_camera_ready:
            return
        try:
            page.evaluate(
                """
                async (videoIndex) => {
                  window.__livenessUploadSlot = videoIndex;
                  if (window.__setVirtualCameraVideo) {
                    await window.__setVirtualCameraVideo(videoIndex);
                  }
                }
                """,
                index,
            )
            if self._verify_virtual_camera_slot(page, index, label):
                self._emit_status(f"In-page camera synced to slot {index + 1} for {label}.")
            else:
                self._emit_status(
                    f"In-page camera sync failed for slot {index + 1} ({label})."
                )
        except Exception as exc:
            self._emit_status(f"Could not sync in-page camera slot: {exc}")

    def _switch_blob_camera(self, page, index: int, label: str, source_path: Path):
        self._ensure_blob_camera_switcher(page)
        self._apply_blob_camera_patch(page)
        page.evaluate(
            """
            async (videoIndex) => {
              window.__livenessUploadSlot = videoIndex;
              if (window.__stopVirtualCamera) {
                window.__stopVirtualCamera();
              }
              if (window.__setVirtualCameraVideo) {
                return window.__setVirtualCameraVideo(videoIndex);
              }
              return null;
            }
            """,
            index,
        )
        self._current_video_index = index
        self._verify_virtual_camera_slot(page, index, label)
        self._emit_status(
            f"Camera slot {index + 1} ready for {label}: {source_path.name}"
        )

    def _apply_blob_camera_patch(self, page):
        if page.evaluate("() => Boolean(window.__setVirtualCameraVideo)"):
            return

        if not any(self._blob_urls_cache):
            raise RuntimeError("Blob camera URLs are not prepared.")

        output = self.config.camera_output_size
        page.evaluate(
            self._blob_camera_script(
                self._blob_urls_cache,
                output.width,
                output.height,
            )
        )
        self._emit_status(
            f"Applied in-page camera patch on current page ({output.width}x{output.height})."
        )

    def _ensure_blob_camera_switcher(self, page, *, force_refresh: bool = False):
        if self._blob_camera_ready and not force_refresh:
            return

        blob_urls: list[str | None] = [None, None, None]
        output = self.config.camera_output_size
        for slot_index in range(3):
            blob_path = (
                self._blob_source_paths[slot_index]
                if slot_index < len(self._blob_source_paths)
                else None
            )
            if not blob_path or not blob_path.is_file():
                continue

            blob_url = self._create_video_blob_url(page, blob_path, slot_index)
            if blob_url:
                blob_urls[slot_index] = blob_url
                self._emit_status(
                    f"In-page camera source {slot_index + 1} ready: "
                    f"{blob_path.name} ({output.width}x{output.height})"
                )
            else:
                self._emit_status(
                    f"In-page camera source {slot_index + 1} unavailable: {blob_path.name}"
                )

        if not any(blob_urls):
            raise RuntimeError(
                "Could not prepare in-page camera videos for switching."
            )

        self._blob_urls_cache = blob_urls

        try:
            refreshed = page.evaluate(
                """
                (urls) => {
                  if (typeof window.__updateVirtualCameraUrls === "function") {
                    window.__updateVirtualCameraUrls(urls);
                    return true;
                  }
                  return false;
                }
                """,
                blob_urls,
            )
            if refreshed:
                self._blob_camera_ready = True
                self._emit_status("In-page blob camera URLs refreshed.")
                return
        except Exception:
            pass

        script = self._blob_camera_script(blob_urls, output.width, output.height)
        page.context.add_init_script(script=script)
        page.evaluate(script)
        self._blob_camera_ready = True
        self._emit_status("In-page blob camera switcher installed.")

    @staticmethod
    def _blob_fetch_timeout_ms(file_size: int) -> int:
        size_mb = max(1, file_size // (1024 * 1024))
        return min(
            MAX_BLOB_FETCH_TIMEOUT_MS,
            max(MIN_BLOB_FETCH_TIMEOUT_MS, size_mb * BLOB_FETCH_TIMEOUT_MS_PER_MB),
        )

    def _create_video_blob_url_from_server(
        self,
        page,
        server_url: str,
        *,
        slot_index: int,
        source_path: Path,
    ) -> str | None:
        file_size = source_path.stat().st_size
        fetch_timeout_ms = self._blob_fetch_timeout_ms(file_size)
        self._emit_status(
            f"Loading camera source {slot_index + 1} from local server "
            f"({file_size // (1024 * 1024)} MB, timeout {fetch_timeout_ms // 1000}s): "
            f"{source_path.name}"
        )
        if page.is_closed():
            raise RuntimeError("Browser page closed while preparing camera video.")
        try:
            return page.evaluate(
                """
                async (url) => {
                  const response = await fetch(url);
                  if (!response.ok) {
                    throw new Error(`fetch failed: ${response.status}`);
                  }
                  const blob = await response.blob();
                  return URL.createObjectURL(blob);
                }
                """,
                server_url,
            )
        except Exception as exc:
            self._emit_status(
                f"Could not fetch camera source {slot_index + 1} from local server: {exc}"
            )
            return None

    def _create_video_blob_url(
        self,
        page,
        source_path: Path,
        slot_index: int,
    ) -> str | None:
        import base64

        mime_type = VIDEO_MIME_TYPES.get(source_path.suffix.lower())
        if not mime_type or source_path.suffix.lower() == ".y4m":
            return None

        file_size = source_path.stat().st_size
        if file_size > MAX_CAMERA_VIDEO_BYTES:
            max_mb = MAX_CAMERA_VIDEO_BYTES // (1024 * 1024)
            self._emit_status(
                f"Camera source {slot_index + 1} too large: {source_path.name} "
                f"({file_size // (1024 * 1024)} MB). Maximum supported size is {max_mb} MB."
            )
            return None

        server_url = (
            self._blob_server_urls[slot_index]
            if slot_index < len(self._blob_server_urls)
            else None
        )
        if server_url:
            blob_url = self._create_video_blob_url_from_server(
                page,
                server_url,
                slot_index=slot_index,
                source_path=source_path,
            )
            if blob_url:
                return blob_url
            self._emit_status(
                f"Falling back to direct inline blob injection for camera source {slot_index + 1}."
            )

        if file_size > MAX_INLINE_BLOB_BYTES:
            self._emit_status(
                f"Camera source {slot_index + 1} unavailable: {source_path.name} "
                f"({file_size // (1024 * 1024)} MB) requires the local file server."
            )
            return None

        payload = base64.b64encode(source_path.read_bytes()).decode("ascii")
        if page.is_closed():
            raise RuntimeError("Browser page closed while preparing camera video.")
        return page.evaluate(
            """
            ([encoded, mimeType]) => {
              const binary = atob(encoded);
              const bytes = new Uint8Array(binary.length);
              for (let index = 0; index < binary.length; index += 1) {
                bytes[index] = binary.charCodeAt(index);
              }
              return URL.createObjectURL(new Blob([bytes], { type: mimeType }));
            }
            """,
            [payload, mime_type],
        )

    @staticmethod
    def _blob_camera_script(
        video_urls: list[str | None],
        output_width: int,
        output_height: int,
    ) -> str:
        videos_json = json.dumps(video_urls, ensure_ascii=True)
        return f"""
(() => {{
  const videoUrls = {videos_json};
  const outputWidth = {output_width};
  const outputHeight = {output_height};
  let currentIndex = 0;
  let currentUrl = "";
  let activeVideo = null;
  let canvas = null;
  let context = null;
  let rafId = null;
  let rvfcId = null;
  let hiddenTimer = null;
  let livenessLoopRestore = null;

  const firstUrl = videoUrls.find((value) => Boolean(value)) || "";
  if (firstUrl) {{
    currentUrl = firstUrl;
    currentIndex = videoUrls.indexOf(firstUrl);
  }}

  const resolveUrl = (value) => {{
    if (typeof value === "number") {{
      if (videoUrls[value]) return {{ index: value, url: videoUrls[value] }};
      throw new Error(`Virtual camera slot ${{value + 1}} is not configured`);
    }}
    if (typeof value === "string" && value) {{
      const foundIndex = videoUrls.indexOf(value);
      return {{ index: foundIndex >= 0 ? foundIndex : currentIndex, url: value }};
    }}
    return {{ index: currentIndex, url: currentUrl }};
  }};

  const waitForVideo = (video) => new Promise((resolve) => {{
    if (video.readyState >= 2 && video.videoWidth) {{
      resolve();
      return;
    }}
    const done = () => resolve();
    video.addEventListener("loadeddata", done, {{ once: true }});
    video.addEventListener("canplay", done, {{ once: true }});
    video.addEventListener("error", done, {{ once: true }});
    setTimeout(done, 4000);
  }});

  // One persistent <video> element. Switching slots only swaps the source so
  // the captured MediaStream never tears down (which used to blank/white out).
  const ensureVideo = () => {{
    if (activeVideo) return activeVideo;
    const video = document.createElement("video");
    video.muted = true;
    video.defaultMuted = true;
    video.loop = true;
    video.playsInline = true;
    video.autoplay = true;
    video.setAttribute("playsinline", "true");
    video.setAttribute("muted", "true");
    video.width = outputWidth;
    video.height = outputHeight;
    video.style.position = "fixed";
    video.style.left = "-10000px";
    video.style.top = "0";
    video.style.width = `${{outputWidth}}px`;
    video.style.height = `${{outputHeight}}px`;
    video.style.opacity = "0.01";
    video.style.pointerEvents = "none";
    document.documentElement.appendChild(video);
    activeVideo = video;
    if (currentUrl) {{
      video.src = currentUrl;
      video.load();
    }}
    return video;
  }};

  // One persistent <canvas>. Created black so the feed is never white.
  const ensureCanvas = () => {{
    if (canvas) return canvas;
    canvas = document.createElement("canvas");
    canvas.width = outputWidth;
    canvas.height = outputHeight;
    canvas.style.position = "fixed";
    canvas.style.left = "-10000px";
    canvas.style.top = "0";
    canvas.style.width = `${{outputWidth}}px`;
    canvas.style.height = `${{outputHeight}}px`;
    canvas.style.opacity = "0.01";
    canvas.style.pointerEvents = "none";
    document.documentElement.appendChild(canvas);
    context = canvas.getContext("2d", {{ alpha: false }});
    context.imageSmoothingEnabled = true;
    context.imageSmoothingQuality = "high";
    context.fillStyle = "black";
    context.fillRect(0, 0, outputWidth, outputHeight);
    return canvas;
  }};

  const drawFrame = () => {{
    if (!context) return;
    const video = activeVideo;
    if (video && video.paused && !video.ended) {{
      video.play().catch(() => {{}});
    }}
    context.fillStyle = "black";
    context.fillRect(0, 0, outputWidth, outputHeight);
    if (video && video.readyState >= 2 && video.videoWidth) {{
      const sourceWidth = video.videoWidth;
      const sourceHeight = video.videoHeight;
      const scale = Math.min(outputWidth / sourceWidth, outputHeight / sourceHeight);
      const drawWidth = Math.max(1, Math.round(sourceWidth * scale));
      const drawHeight = Math.max(1, Math.round(sourceHeight * scale));
      const offsetX = Math.floor((outputWidth - drawWidth) / 2);
      const offsetY = Math.floor((outputHeight - drawHeight) / 2);
      try {{
        context.drawImage(video, offsetX, offsetY, drawWidth, drawHeight);
      }} catch (_) {{}}
    }}
  }};

  // Draw scheduling. To avoid CPU overload (which stalls/freezes video decode
  // at high resolution) we use a SINGLE active scheduler at a time:
  //  - foreground: requestVideoFrameCallback (per decoded frame, efficient)
  //    or requestAnimationFrame fallback;
  //  - background (tab hidden): a setInterval keep-alive, since rAF/rVFC pause.
  // The two are never run together.
  const stopRenderLoop = () => {{
    if (rafId) {{
      cancelAnimationFrame(rafId);
      rafId = null;
    }}
    if (rvfcId !== null && activeVideo && typeof activeVideo.cancelVideoFrameCallback === "function") {{
      try {{ activeVideo.cancelVideoFrameCallback(rvfcId); }} catch (_) {{}}
    }}
    rvfcId = null;
    if (hiddenTimer) {{
      clearInterval(hiddenTimer);
      hiddenTimer = null;
    }}
  }};

  const startForegroundLoop = () => {{
    if (activeVideo && typeof activeVideo.requestVideoFrameCallback === "function") {{
      const cb = () => {{
        drawFrame();
        if (activeVideo && typeof activeVideo.requestVideoFrameCallback === "function") {{
          rvfcId = activeVideo.requestVideoFrameCallback(cb);
        }}
      }};
      rvfcId = activeVideo.requestVideoFrameCallback(cb);
      return;
    }}
    const renderLoop = () => {{
      drawFrame();
      rafId = requestAnimationFrame(renderLoop);
    }};
    rafId = requestAnimationFrame(renderLoop);
  }};

  const applyVisibility = () => {{
    if (document.hidden) {{
      if (rafId) {{ cancelAnimationFrame(rafId); rafId = null; }}
      if (!hiddenTimer) hiddenTimer = setInterval(drawFrame, 33);
    }} else {{
      if (hiddenTimer) {{ clearInterval(hiddenTimer); hiddenTimer = null; }}
      if (rafId === null && rvfcId === null) startForegroundLoop();
    }}
  }};

  const startRenderLoop = () => {{
    stopRenderLoop();
    if (document.hidden) {{
      hiddenTimer = setInterval(drawFrame, 33);
    }} else {{
      startForegroundLoop();
    }}
  }};

  if (!window.__virtualCameraVisibilityHook) {{
    window.__virtualCameraVisibilityHook = true;
    document.addEventListener("visibilitychange", () => {{
      try {{ applyVisibility(); }} catch (_) {{}}
    }});
  }}

  const setCurrent = (value) => {{
    const resolved = resolveUrl(value);
    currentIndex = resolved.index;
    currentUrl = resolved.url || currentUrl;
    const video = ensureVideo();
    if (currentUrl && video.src !== currentUrl) {{
      video.src = currentUrl;
      video.load();
      video.play().catch(() => {{}});
    }}
    return currentUrl;
  }};

  const createStream = async () => {{
    if (!currentUrl) {{
      const fallback = videoUrls.find((value) => Boolean(value));
      if (fallback) {{
        currentUrl = fallback;
        currentIndex = videoUrls.indexOf(fallback);
      }}
    }}
    if (!currentUrl) throw new Error("No virtual camera video URL is configured");
    const video = ensureVideo();
    if (video.src !== currentUrl) {{
      video.src = currentUrl;
      video.load();
    }}
    await waitForVideo(video);
    await video.play().catch(() => {{}});
    ensureCanvas();
    drawFrame();
    startRenderLoop();
    // A fresh captureStream per call (from the SAME persistent canvas) so the
    // site can stop old tracks without killing our continuously-drawn feed.
    const stream = canvas.captureStream(30);
    if (!stream) throw new Error("This browser cannot capture a stream from canvas");
    return stream;
  }};

  const originalGetUserMedia = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
  navigator.mediaDevices.getUserMedia = async (constraints = {{}}) => {{
    if (constraints && constraints.video) {{
      return createStream();
    }}
    return originalGetUserMedia(constraints);
  }};

  // Soft stop: pause only. The canvas, render loop and captured stream stay
  // alive so switching videos never blanks the feed.
  window.__stopVirtualCamera = () => {{
    if (activeVideo) {{
      try {{ activeVideo.pause(); }} catch (_) {{}}
    }}
  }};

  // Full teardown (used only when the whole automation is torn down).
  window.__teardownVirtualCamera = () => {{
    stopRenderLoop();
    if (activeVideo) {{
      try {{
        activeVideo.pause();
        activeVideo.removeAttribute("src");
        activeVideo.load();
        activeVideo.remove();
      }} catch (_) {{}}
      activeVideo = null;
    }}
    if (canvas) {{
      try {{ canvas.remove(); }} catch (_) {{}}
      canvas = null;
      context = null;
    }}
  }};

  window.__setVirtualCameraVideo = async (value) => {{
    setCurrent(value);
    const video = ensureVideo();
    await waitForVideo(video);
    try {{ await video.play(); }} catch (_) {{}}
    if (canvas) {{
      drawFrame();
      if (rafId === null && rvfcId === null && hiddenTimer === null) startRenderLoop();
    }}
    return currentUrl;
  }};

  window.__getVirtualCameraIndex = () => currentIndex;

  window.__getVirtualCameraPlaybackMs = () => {{
    if (!activeVideo) return 0;
    return Math.max(0, Math.floor((activeVideo.currentTime || 0) * 1000));
  }};

  window.__getVirtualCameraDurationMs = () => {{
    if (!activeVideo || !Number.isFinite(activeVideo.duration)) return 0;
    return Math.max(0, Math.floor(activeVideo.duration * 1000));
  }};

  window.__setVirtualCameraLoop = (enabled) => {{
    if (!activeVideo) return false;
    activeVideo.loop = Boolean(enabled);
    return true;
  }};

  window.__resetVirtualCameraForLiveness = async () => {{
    const video = ensureVideo();
    await waitForVideo(video);
    livenessLoopRestore = video.loop;
    video.loop = false;
    try {{ video.currentTime = 0; }} catch (_) {{}}
    await new Promise((resolve) => {{
      const done = () => resolve();
      video.addEventListener("seeked", done, {{ once: true }});
      setTimeout(done, 400);
    }});
    try {{ await video.play(); }} catch (_) {{}}
    if (canvas && rafId === null && rvfcId === null && hiddenTimer === null) startRenderLoop();
    return true;
  }};

  window.__restoreVirtualCameraLoop = () => {{
    if (!activeVideo || livenessLoopRestore === null) return false;
    activeVideo.loop = livenessLoopRestore;
    livenessLoopRestore = null;
    return true;
  }};

  window.__fetchVirtualCameraFile = async (index) => {{
    const url = videoUrls[index];
    if (!url) return null;
    const response = await fetch(url);
    const blob = await response.blob();
    const ext = (blob.type || "").includes("mp4") ? "mp4" : "webm";
    return new File([blob], `virtual-camera-${{index + 1}}.${{ext}}`, {{
      type: blob.type || "video/mp4",
    }});
  }};

  window.__updateVirtualCameraUrls = (urls) => {{
    for (let index = 0; index < urls.length; index += 1) {{
      videoUrls[index] = urls[index] || null;
    }}
  }};
}})();
"""

    def _ensure_camera_permissions(self, page):
        origins = self._collect_media_origins(page.url, page)
        self._grant_media_permissions(page, origins)

    def _collect_media_origins(
        self,
        target_url: str,
        page=None,
        server_url: str | None = None,
    ) -> list[str]:
        origins: list[str] = []
        origins.extend(self._media_permission_origins(target_url))
        if server_url:
            origins.extend(self._media_permission_origins(server_url))
        if page is not None:
            origins.extend(self._media_permission_origins(page.url))
            origins.extend(self._page_frame_origins(page))
        return self._unique_origins(origins)

    def _grant_media_permissions(
        self,
        page,
        origins: list[str],
        *,
        reset_blocked: bool = False,
        skip_cdp: bool = False,
    ):
        context = page.context

        if reset_blocked:
            try:
                context.clear_permissions()
                self._emit_status("Cleared blocked media permission overrides.")
            except Exception as exc:
                self._emit_status(f"Could not clear old media permissions: {exc}")

        try:
            context.grant_permissions(list(MEDIA_PERMISSIONS))
            self._emit_status("Media permissions granted globally.")
        except Exception as exc:
            self._emit_status(f"Could not grant global media permissions: {exc}")

        for origin in origins:
            try:
                context.grant_permissions(list(MEDIA_PERMISSIONS), origin=origin)
                self._emit_status(f"Media permissions granted for {origin}.")
            except Exception as exc:
                self._emit_status(f"Could not grant media permissions for {origin}: {exc}")

        if not skip_cdp:
            self._grant_media_permissions_via_cdp(page, origins)

    def _grant_media_permissions_via_cdp(self, page, origins: list[str]):
        try:
            client = page.context.new_cdp_session(page)
        except Exception as exc:
            self._emit_status(f"CDP session unavailable for media permissions: {exc}")
            return

        try:
            client.send(
                "Browser.grantPermissions",
                {"permissions": list(CDP_MEDIA_PERMISSIONS)},
            )
        except Exception as exc:
            self._emit_status(f"CDP global media permission grant failed: {exc}")

        for origin in origins:
            try:
                client.send(
                    "Browser.grantPermissions",
                    {
                        "origin": origin,
                        "permissions": list(CDP_MEDIA_PERMISSIONS),
                    },
                )
            except Exception as exc:
                self._emit_status(f"CDP media permission grant failed for {origin}: {exc}")

    @staticmethod
    def _media_permission_origins(target_url: str) -> list[str]:
        parsed = urlparse(target_url)
        if not parsed.scheme or not parsed.netloc:
            return []
        return [f"{parsed.scheme}://{parsed.netloc}"]

    def _page_frame_origins(self, page) -> list[str]:
        origins: list[str] = []
        try:
            frames = page.frames
        except Exception as exc:
            self._emit_status(f"Could not read page frame origins: {exc}")
            return origins

        for frame in frames:
            origins.extend(self._media_permission_origins(frame.url))
        return self._unique_origins(origins)

    @staticmethod
    def _unique_origins(origins: list[str]) -> list[str]:
        unique: list[str] = []
        for origin in origins:
            if origin and origin not in unique:
                unique.append(origin)
        return unique

    def _step1_id_document(self, page) -> bool:
        if not self._run_photo_capture_step(
            page,
            video_slot=0,
            video_label="File 1 / ID document",
            opener_call=lambda: self._click_id_ready(page),
            step_name="Step 1 / ID document",
        ):
            return False
        return self._prepare_selfie_step(page)

    def _wait_for_selfie_step_ready(self, page, timeout_ms: int = 20000) -> bool:
        self._emit_status("Waiting for selfie step UI to become ready...")
        deadline = time.monotonic() + (timeout_ms / 1000)
        while time.monotonic() < deadline:
            page = self._active_page(page)
            selfie_visible = any(
                self._is_button_visible(page, button_id) for button_id in SELFIE_BUTTON_IDS
            )
            if not selfie_visible:
                try:
                    page.wait_for_timeout(400)
                except Exception:
                    time.sleep(0.4)
                continue

            blocking_ids = (OK_BUTTON_ID, FINISHED_BUTTON_ID, ID_BUTTON_ID)
            if any(self._is_button_visible(page, element_id) for element_id in blocking_ids):
                try:
                    page.wait_for_timeout(400)
                except Exception:
                    time.sleep(0.4)
                continue

            self._emit_status("Selfie step UI is ready.")
            try:
                page.wait_for_timeout(max(2000, self._automation.step_settle_ms))
            except Exception:
                time.sleep(max(2.0, self._automation.step_settle_ms / 1000))
            return True

        return self._wait_for_selfie_button(page, timeout_ms=5000)

    def _wait_for_selfie_button(self, page, timeout_ms: int = 15000) -> bool:
        self._emit_status("Waiting for #btn-take-photo-selfy to appear...")
        if self._wait_for_any_visible(page, list(SELFIE_BUTTON_IDS), timeout_ms=timeout_ms):
            try:
                page = self._active_page(page)
                page.wait_for_timeout(self._automation.step_settle_ms)
            except Exception:
                time.sleep(self._automation.step_settle_ms / 1000)
            return True
        return False

    def _step2_selfie(self, page) -> bool:
        page = self._active_page(page)
        if not any(
            self._is_button_visible(page, button_id) for button_id in SELFIE_BUTTON_IDS
        ):
            if not self._prepare_selfie_step(page):
                self._emit_status("Selfie step did not become ready.")
                return False

        page = self._active_page(page)
        if self._is_button_visible(page, CAMERA_BUTTON_ID) and any(
            self._is_button_visible(page, button_id) for button_id in SELFIE_BUTTON_IDS
        ):
            self._emit_status(
                "Selfie page loaded with stale camera controls; waiting for a clean selfie opener..."
            )
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline:
                page = self._active_page(page)
                if not self._is_button_visible(page, CAMERA_BUTTON_ID):
                    break
                try:
                    page.wait_for_timeout(500)
                except Exception:
                    time.sleep(0.5)

        if not self._run_photo_capture_step(
            page,
            video_slot=1,
            video_label="File 2 / selfie",
            opener_call=lambda: self._click_selfie_ready(page),
            step_name="Step 2 / selfie",
        ):
            return False

        return self._wait_for_step_transition(
            page,
            expected_url_part="/verification/",
            button_ids=[LIVENESS_PROCEED_ID, LIVENESS_SUBMIT_ID],
            label="liveness step",
            timeout_ms=45000,
        )

    def _step3_liveness(self, page) -> bool:
        auto = self._automation
        timeline_summary = " | ".join(
            mark.label or f"{mark.start_ms // 1000}s {mark.position}"
            for mark in auto.liveness_timeline
        )
        self._emit_status(
            "Step 3 / liveness started "
            f"(upload={auto.liveness_upload_mode}, "
            f"min={auto.liveness_min_duration_seconds}s, "
            f"retries={auto.liveness_retry_count}). "
            f"Timeline: {timeline_summary}"
        )
        if not self._wait_for_any_visible(page, [LIVENESS_PROCEED_ID], timeout_ms=45000):
            self._emit_status("Liveness PROCEED button did not appear.")
            return False

        self._ensure_blob_camera_switcher(page, force_refresh=True)
        if not self._blob_urls_cache[2]:
            raise RuntimeError(
                "File 3 / liveness could not be loaded into the in-page camera. "
                "Ensure the video file is valid and the local server is running."
            )
        self._ensure_camera_permissions(page)
        self._select_virtual_camera_video(page, 2, "File 3 / liveness", force=True)
        self._verify_virtual_camera_slot(page, 2, "File 3 / liveness")
        self._restart_liveness_camera_stream(page)
        self._install_video_step_script(page)
        self._sync_liveness_video_playback(page)
        self._pause_ms(page, max(2000, self._automation.camera_warmup_ms))

        timeout_seconds = max(60, self._automation.liveness_timeout_ms // 1000)
        deadline = time.monotonic() + timeout_seconds
        last_status = ""
        reinject_at = time.monotonic()

        while time.monotonic() < deadline:
            if self._stop_requested():
                return False

            if time.monotonic() - reinject_at >= 15:
                self._install_video_step_script(page, reinject=True)
                reinject_at = time.monotonic()

            page = self._active_page(page)
            try:
                tick = page.evaluate(VIDEO_STEP_TICK_SCRIPT)
                if isinstance(tick, dict):
                    phase = tick.get("phase", "unknown")
                    if tick.get("result") == "success":
                        accepted_url = tick.get("url") or page.url
                        self._verification_accepted_url = accepted_url
                        self._emit_status(f"Verification accepted: {accepted_url}")
                        self._emit_status("Process Completed!")
                        return True
                    if tick.get("result") == "error":
                        message = tick.get("message", "Submission failed")
                        raise RuntimeError(
                            f"Site rejected liveness verification: {message}"
                        )

                    status = (
                        f"phase={phase} "
                        f"proceeded={tick.get('proceeded')} "
                        f"recording={tick.get('recording')} "
                        f"finished={tick.get('finished')} "
                        f"elapsed={(tick.get('elapsedMs') or 0) // 1000}s"
                    )
                    if status != last_status:
                        self._emit_status(f"Liveness: {status}")
                        last_status = status

                result = self._evaluate_on_page(page, VIDEO_STEP_RESULT_SCRIPT)
                if isinstance(result, dict):
                    if result.get("status") == "success":
                        accepted_url = result.get("url", page.url)
                        self._verification_accepted_url = accepted_url
                        self._emit_status(f"Verification accepted: {accepted_url}")
                        self._emit_status("Process Completed!")
                        return True
                    if result.get("status") == "error":
                        raise RuntimeError(
                            "Site rejected liveness verification: "
                            f"{result.get('message', 'failed')}"
                        )
            except RuntimeError:
                raise
            except Exception as exc:
                self._emit_status(f"Liveness tick: {exc}")

            self._pause_ms(page, 800)

        self._emit_status("Liveness automation timed out.")
        return False

    def _video_step_script(self) -> str:
        auto = self._automation
        return video_step_script(
            upload_mode=auto.liveness_upload_mode,
            timeline_json=liveness_timeline_to_json(auto.liveness_timeline),
        )

    def _install_video_step_script(self, page, *, reinject: bool = False):
        script = self._video_step_script()
        if not self._video_step_installed:
            page.context.add_init_script(script=script)
            self._video_step_installed = True
            self._emit_status("Video step script registered (native cascade).")
            self._inject_video_step_script(page, script)
        elif reinject:
            self._inject_video_step_script(page, script)

    def _inject_video_step_script(
        self,
        page,
        script: str | None = None,
        *,
        force: bool = False,
    ):
        now = time.monotonic()
        if not force and (now - self._last_video_step_inject_at) < 4.0:
            return
        self._last_video_step_inject_at = now
        script = script or self._video_step_script()
        injected = 0
        for frame in page.frames:
            try:
                frame.evaluate(script)
                injected += 1
            except Exception:
                continue

        if injected:
            self._emit_status(
                f"Video step script injected into {injected} frame(s)."
            )

    def _wait_for_camera_ready(self, page, timeout_ms: int | None = None) -> bool:
        timeout_ms = timeout_ms or max(self._automation.camera_warmup_ms, 8000)
        self._emit_status(f"Waiting for TAKE PHOTO button (timeout {timeout_ms} ms)...")
        if self._wait_for_any_visible(page, ["btn-take-photo-camera"], timeout_ms=timeout_ms):
            page.wait_for_timeout(self._automation.step_settle_ms)
            return True
        self._emit_status("TAKE PHOTO button did not appear in time.")
        return False

    def _wait_for_any_visible(
        self,
        page,
        element_ids: list[str],
        timeout_ms: int | None = None,
    ) -> bool:
        timeout_ms = timeout_ms or self.config.timeouts.script_ms
        deadline = time.monotonic() + (timeout_ms / 1000)
        while time.monotonic() < deadline:
            try:
                page = self._active_page(page if page is not None and not page.is_closed() else None)
            except RuntimeError as exc:
                self._emit_status(f"Waiting for controls: {exc}")
                time.sleep(0.5)
                continue
            for element_id in element_ids:
                if self._is_button_visible(page, element_id):
                    return True
            try:
                page.wait_for_timeout(250)
            except Exception:
                time.sleep(0.25)
        return False

    def _safe_click(
        self,
        page,
        element_id: str,
        label: str,
        timeout_ms: int | None = None,
        *,
        required: bool = True,
    ) -> bool:
        return self._safe_click_target(
            page,
            element_id,
            label,
            timeout_ms=timeout_ms,
            required=required,
        )

    def _safe_click_target(
        self,
        page,
        element_id: str,
        label: str,
        timeout_ms: int | None = None,
        *,
        text: str | None = None,
        required: bool = True,
        allow_playwright_click: bool = True,
    ) -> bool:
        timeout_ms = timeout_ms or min(self.config.timeouts.script_ms, 8000)
        retries = self._automation.click_retries

        for attempt in range(1, retries + 1):
            page = self._active_page(page)
            self._emit_status(f"Clicking {label}: #{element_id} (attempt {attempt}/{retries})")

            if self._fast_click_element(page, element_id, label):
                time.sleep(0.6)

            locator, click_root = self._locate_button(page, element_id, text=text)
            if self._click_with_fallbacks(
                click_root,
                locator,
                timeout_ms,
                element_id=element_id,
                allow_playwright_click=allow_playwright_click,
            ):
                page = self._active_page(page)
                try:
                    page.wait_for_timeout(self._automation.step_settle_ms)
                except Exception:
                    time.sleep(self._automation.step_settle_ms / 1000)
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=3000)
                except Exception:
                    pass
                self._bind_work_page(page)
                return True

            if attempt >= retries:
                message = f"Could not click {label} (#{element_id})."
                if required:
                    self._emit_status(message)
                    return False
                self._emit_status(f"Optional click skipped for {label}.")
                return True
            self._emit_status(f"Retrying {label}...")
            time.sleep(0.8)

        return False

    def _click_with_fallbacks(
        self,
        page,
        locator,
        timeout_ms: int,
        *,
        element_id: str | None = None,
        allow_playwright_click: bool = True,
    ) -> bool:
        per_strategy_ms = min(2500, max(1500, timeout_ms // 3))
        strategies: list[tuple[str, Callable[[], None]]] = [
            ("attached-js", lambda: self._click_locator_js_attached(locator, per_strategy_ms)),
            ("touch", lambda: self._click_locator_touch(page, locator, per_strategy_ms)),
            ("javascript", lambda: self._click_locator_js(locator, per_strategy_ms)),
            ("center", lambda: self._click_locator_center(page, locator, per_strategy_ms)),
        ]
        if allow_playwright_click:
            strategies.append(
                ("force", lambda: self._click_locator(locator, 1500, force=True)),
            )

        last_error: Exception | None = None
        for strategy_name, click_action in strategies:
            try:
                click_action()
                self._emit_status(f"Click succeeded using {strategy_name} strategy.")
                return True
            except Exception as exc:
                last_error = exc
                self._emit_status(f"{strategy_name} click failed: {exc}")

        if last_error:
            self._emit_status(f"All click strategies failed: {last_error}")
        return False

    @staticmethod
    def _click_locator(locator, timeout_ms: int, *, force: bool) -> None:
        locator.wait_for(state="visible", timeout=timeout_ms)
        locator.scroll_into_view_if_needed(timeout=timeout_ms)
        locator.click(timeout=timeout_ms, force=force, no_wait_after=True)

    @staticmethod
    def _click_locator_js(locator, timeout_ms: int) -> None:
        locator.wait_for(state="visible", timeout=timeout_ms)
        locator.evaluate(
            """
            (element) => {
              element.scrollIntoView({ block: "center", inline: "center" });
              element.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
              if (typeof element.click === "function") {
                element.click();
              }
            }
            """
        )

    @staticmethod
    def _click_locator_js_attached(locator, timeout_ms: int) -> None:
        locator.wait_for(state="attached", timeout=timeout_ms)
        locator.evaluate(
            """
            (element) => {
              element.scrollIntoView({ block: "center", inline: "center" });
              const events = ["pointerdown", "mousedown", "pointerup", "mouseup", "click"];
              for (const name of events) {
                const EventType = name.startsWith("pointer") ? PointerEvent : MouseEvent;
                element.dispatchEvent(new EventType(name, { bubbles: true, cancelable: true, view: window }));
              }
              if (typeof element.click === "function") {
                element.click();
              }
            }
            """
        )

    @staticmethod
    def _click_locator_touch(page, locator, timeout_ms: int) -> None:
        locator.wait_for(state="attached", timeout=timeout_ms)
        locator.scroll_into_view_if_needed(timeout=timeout_ms)
        box = locator.bounding_box(timeout=timeout_ms)
        if not box:
            raise RuntimeError("Element has no clickable bounding box.")
        x = box["x"] + box["width"] / 2
        y = box["y"] + box["height"] / 2
        try:
            page.touchscreen.tap(x, y)
        except Exception:
            page.mouse.click(x, y)

    @staticmethod
    def _click_locator_center(page, locator, timeout_ms: int) -> None:
        box = locator.bounding_box(timeout=timeout_ms)
        if not box:
            raise RuntimeError("Element has no clickable bounding box.")
        x = box["x"] + box["width"] / 2
        y = box["y"] + box["height"] / 2
        page.mouse.click(x, y)

    def _stop_requested(self) -> bool:
        if self.isInterruptionRequested():
            self._emit_status("Stop requested. Cleaning up...")
            self.stopped.emit()
            return True
        return False

    def _emit_status(self, message: str):
        self.status.emit(message)


class MainWindow(QMainWindow):
    def __init__(self, auth_session: AuthSession | None = None):
        super().__init__()
        self.worker: WorkerThread | None = None
        self.device_browser_window: QMainWindow | None = None
        self.file_inputs: list[QLineEdit] = []
        self.auth_session = auth_session
        self._auth_locked = False
        if self.auth_session:
            if not self.auth_session.payload:
                try:
                    self.auth_session.load_payload()
                except Exception as exc:
                    LOGGER.warning("Could not load initial payload: %s", exc)
            payload = self.auth_session.payload or {}
            if "liveness_template" in payload:
                set_liveness_template(payload["liveness_template"])
            if "video_step_template" in payload:
                set_video_step_template(payload["video_step_template"])
        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.timeout.connect(self._on_heartbeat_tick)
        self.config = AppConfig.load()
        self.services = AutomationServices.from_config(self.config)


        self.setWindowTitle("Automation Hub")
        self.resize(960, 680)
        self.setMinimumSize(760, 560)

        self.url_input = QLineEdit()
        self.url_input.setText(self.config.target_url)
        self.url_input.setPlaceholderText("https://example.com")

        self.browser_engine_selector = QComboBox()
        self.browser_engine_selector.addItem("Multilogin (MLX / MLA / CDP)", "multilogin")
        self.browser_engine_selector.addItem("AdsPower", "adspower")
        if self.config.browser_engine == "adspower":
            self.browser_engine_selector.setCurrentIndex(1)
        else:
            self.browser_engine_selector.setCurrentIndex(0)

        self.multilogin_profile_input = QComboBox()
        self.multilogin_profile_input.setEditable(True)
        if self.multilogin_profile_input.lineEdit():
            self.multilogin_profile_input.lineEdit().setPlaceholderText("Select profile or paste Multilogin Profile ID...")
        self.multilogin_profile_input.setMinimumWidth(360)
        self.multilogin_refresh_button = QPushButton("Refresh")
        self.multilogin_refresh_button.setObjectName("ghostBtn")
        self.multilogin_refresh_button.setCursor(Qt.PointingHandCursor)

        initial_token = self.config.multilogin.token
        if not initial_token:
            auto_tok = extract_local_multilogin_token()
            if auto_tok:
                initial_token = auto_tok
                self.config = self.config.with_multilogin(
                    self.config.multilogin.__class__(
                        api_base=self.config.multilogin.api_base,
                        profile_id=self.config.multilogin.profile_id,
                        folder_id=self.config.multilogin.folder_id,
                        token=initial_token,
                        api_version=self.config.multilogin.api_version,
                        direct_cdp_url=self.config.multilogin.direct_cdp_url,
                        close_on_stop=self.config.multilogin.close_on_stop,
                    )
                )

        self.multilogin_token_input = QLineEdit()
        self.multilogin_token_input.setPlaceholderText("Multilogin API / Bearer Token...")
        self.multilogin_token_input.setText(initial_token)
        self.multilogin_token_input.setEchoMode(QLineEdit.PasswordEchoOnEdit)

        self.multilogin_cdp_input = QLineEdit()
        self.multilogin_cdp_input.setPlaceholderText("Active CDP Port / URL e.g. 127.0.0.1:9222 (or click Auto-Detect)")
        self.multilogin_cdp_input.setText(self.config.multilogin.direct_cdp_url)

        self.multilogin_auto_detect_button = QPushButton("Auto-Detect")
        self.multilogin_auto_detect_button.setObjectName("ghostBtn")
        self.multilogin_auto_detect_button.setCursor(Qt.PointingHandCursor)
        self.multilogin_auto_detect_button.setToolTip("Scan local ports to detect any running Multilogin / Chromium browser")

        self.adspower_profile_input = QComboBox()
        self.adspower_profile_input.setMinimumWidth(360)
        self.adspower_refresh_button = QPushButton("Refresh")
        self.adspower_refresh_button.setObjectName("ghostBtn")
        self.adspower_refresh_button.setCursor(Qt.PointingHandCursor)

        self.start_button = QPushButton("Start Automation")
        self.start_button.setObjectName("primaryBtn")
        self.start_button.setCursor(Qt.PointingHandCursor)
        self.start_button.setMinimumHeight(40)
        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("dangerBtn")
        self.stop_button.setCursor(Qt.PointingHandCursor)
        self.stop_button.setMinimumHeight(40)
        self.stop_button.setEnabled(False)

        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setLineWrapMode(QTextEdit.NoWrap)

        self.file_buttons: list[QPushButton] = []
        self._build_ui()
        self.logger, self.log_handler = setup_text_edit_logging(
            self.log_console,
            logger_name="desktop_app",
            level=logging.INFO,
        )
        self._connect_signals()
        if self.config.browser_engine == "adspower":
            self._populate_adspower_profiles()
        else:
            self._populate_multilogin_profiles()
        self._build_auth_status_bar()
        self._start_heartbeat()
        if self.auth_session and self.config.auth.enabled:
            self._log_app_activity("app_start")
        LOGGER.info("Application initialized.")
        LOGGER.info("Execution flow: %s", EXECUTION_FLOW)

    def _build_auth_status_bar(self) -> None:
        if not self.config.auth.enabled:
            return
        status = self.statusBar()
        self.auth_user_label = QLabel("User: -")
        self.auth_license_label = QLabel("License: -")
        self.auth_online_label = QLabel("Status: connecting")
        status.addPermanentWidget(self.auth_user_label)
        status.addPermanentWidget(self.auth_license_label)
        status.addPermanentWidget(self.auth_online_label)
        self._update_auth_status_labels()

    def _update_auth_status_labels(self) -> None:
        if not self.config.auth.enabled or not hasattr(self, "auth_user_label"):
            return
        if not self.auth_session or self._auth_locked:
            self.auth_user_label.setText("User: locked")
            self.auth_license_label.setText("License: -")
            self.auth_online_label.setText("● Locked")
            self.auth_online_label.setStyleSheet("color: #ff5c7a; font-weight: 600;")
            return
        days = self.auth_session.license_days_left
        license_text = f"{days} days left" if days is not None else "active"
        self.auth_user_label.setText(f"User: {self.auth_session.username}")
        self.auth_license_label.setText(f"License: {license_text}")
        self.auth_online_label.setText("● Online")
        self.auth_online_label.setStyleSheet("color: #2ee6a6; font-weight: 600;")

    def _start_heartbeat(self) -> None:
        if not self.config.auth.enabled or not self.auth_session:
            return
        interval_ms = max(30000, self.auth_session.heartbeat_seconds * 1000)
        self._heartbeat_timer.start(interval_ms)
        QTimer.singleShot(2000, self._on_heartbeat_tick)

    def _on_heartbeat_tick(self) -> None:
        if not self.auth_session or self._auth_locked or not self.config.auth.enabled:
            return
        try:
            self.auth_session.heartbeat_check()
            self._update_auth_status_labels()
        except AuthError as exc:
            self._lock_application(exc.message)

    def _lock_application(self, reason: str) -> None:
        if self._auth_locked:
            return
        self._auth_locked = True
        if self.auth_session:
            self.auth_session.lock(reason)
        self._heartbeat_timer.stop()
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
        self.set_running_state(False)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self._update_auth_status_labels()
        LOGGER.error("Application locked: %s", reason)
        QMessageBox.critical(
            self,
            "Application Locked",
            reason,
        )

    def _log_app_activity(self, action: str) -> None:
        if not self.auth_session or not self.config.auth.enabled:
            return
        try:
            token = self.auth_session.ensure_access_token()
            self.auth_session.client.log_activity(
                token,
                action,
                self.auth_session.device_id,
                self.auth_session.pc_name,

            )
        except AuthError:
            pass

    def _build_ui(self):
        tools_menu = self.menuBar().addMenu("Tools")
        self.open_device_browser_action = QAction("Open Device Profile Browser", self)
        tools_menu.addAction(self.open_device_browser_action)

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(22, 18, 22, 18)
        root_layout.setSpacing(16)

        root_layout.addWidget(self._build_header())

        input_group = QGroupBox("Configuration")
        input_layout = QGridLayout(input_group)
        input_layout.setColumnStretch(1, 1)
        input_layout.setHorizontalSpacing(12)
        input_layout.setVerticalSpacing(12)

        input_layout.addWidget(QLabel("Target URL"), 0, 0)
        input_layout.addWidget(self.url_input, 0, 1, 1, 2)

        input_layout.addWidget(QLabel("Browser Engine"), 1, 0)
        input_layout.addWidget(self.browser_engine_selector, 1, 1, 1, 2)

        # Multilogin Container
        self.multilogin_container = QWidget()
        multilogin_layout = QGridLayout(self.multilogin_container)
        multilogin_layout.setContentsMargins(0, 0, 0, 0)
        multilogin_layout.setHorizontalSpacing(12)
        multilogin_layout.setVerticalSpacing(8)
        multilogin_layout.setColumnStretch(1, 1)

        multilogin_row = QHBoxLayout()
        multilogin_row.addWidget(self.multilogin_profile_input, 1)
        multilogin_row.addWidget(self.multilogin_refresh_button)

        cdp_row = QHBoxLayout()
        cdp_row.addWidget(self.multilogin_cdp_input, 1)
        cdp_row.addWidget(self.multilogin_auto_detect_button)

        multilogin_layout.addWidget(QLabel("Multilogin Profile"), 0, 0)
        multilogin_layout.addLayout(multilogin_row, 0, 1, 1, 2)

        multilogin_layout.addWidget(QLabel("API Token"), 1, 0)
        multilogin_layout.addWidget(self.multilogin_token_input, 1, 1, 1, 2)

        multilogin_layout.addWidget(QLabel("Direct CDP / Port"), 2, 0)
        multilogin_layout.addLayout(cdp_row, 2, 1, 1, 2)

        multilogin_hint = QLabel(
            "Connects to Multilogin X (port 45001), Multilogin 6 (port 35000), or active browser port. "
            "Tip: Enter your API Token and click Refresh to load profiles, or launch in Multilogin and click 'Auto-Detect'."
        )
        multilogin_hint.setWordWrap(True)
        multilogin_hint.setStyleSheet("color: #8fa0b5; font-size: 11px;")
        multilogin_layout.addWidget(multilogin_hint, 3, 1, 1, 2)

        # AdsPower Container
        self.adspower_container = QWidget()
        adspower_layout = QGridLayout(self.adspower_container)
        adspower_layout.setContentsMargins(0, 0, 0, 0)
        adspower_layout.setHorizontalSpacing(12)
        adspower_layout.setVerticalSpacing(8)
        adspower_layout.setColumnStretch(1, 1)

        adspower_row = QHBoxLayout()
        adspower_row.addWidget(self.adspower_profile_input, 1)
        adspower_row.addWidget(self.adspower_refresh_button)

        adspower_layout.addWidget(QLabel("AdsPower Profile"), 0, 0)
        adspower_layout.addLayout(adspower_row, 0, 1, 1, 2)

        adspower_hint = QLabel(
            "Browser, proxy, and user agent come from the selected AdsPower profile. "
            "This app only injects the virtual camera and automation script."
        )
        adspower_hint.setWordWrap(True)
        adspower_hint.setStyleSheet("color: #8fa0b5; font-size: 11px;")
        adspower_layout.addWidget(adspower_hint, 1, 1, 1, 2)

        self.engine_stack = QStackedWidget()
        self.engine_stack.addWidget(self.multilogin_container)
        self.engine_stack.addWidget(self.adspower_container)
        if self.config.browser_engine == "adspower":
            self.engine_stack.setCurrentIndex(1)
        else:
            self.engine_stack.setCurrentIndex(0)

        input_layout.addWidget(self.engine_stack, 2, 0, 1, 3)

        for row in range(3, 6):
            file_number = row - 2
            file_input = QLineEdit()
            file_input.setReadOnly(True)
            file_input.setPlaceholderText(f"Choose file {file_number}")
            file_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

            picker_button = QPushButton(f"Browse {file_number}")
            picker_button.clicked.connect(
                lambda checked=False, line_edit=file_input: self.pick_file(line_edit)
            )

            self.file_inputs.append(file_input)
            self.file_buttons.append(picker_button)
            input_layout.addWidget(QLabel(f"File {file_number}"), row, 0)
            input_layout.addWidget(file_input, row, 1)
            input_layout.addWidget(picker_button, row, 2)

        # Pre-populate default video paths if found on disk
        default_video_candidates = [
            Path(r"C:\Users\ASHIF\Downloads\New folder\New folder\New folder (2)\0729(12).mp4"),
            Path(r"C:\Users\ASHIF\Downloads\New folder\New folder\New folder (2)\0729(13).mp4"),
            Path(r"C:\Users\ASHIF\Downloads\New folder\New folder\New folder (2)\0729(14).mp4"),
        ]
        for idx, file_in in enumerate(self.file_inputs):
            if idx < len(default_video_candidates) and default_video_candidates[idx].is_file():
                file_in.setText(str(default_video_candidates[idx]))

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.stop_button)

        log_group = QGroupBox("Activity Log")
        log_layout = QVBoxLayout(log_group)
        log_layout.addWidget(self.log_console)

        root_layout.addWidget(input_group)
        root_layout.addLayout(button_row)
        root_layout.addWidget(log_group, 1)

        self.setCentralWidget(root)

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("headerBar")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(14)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        title = QLabel("Automation Hub")
        title.setObjectName("appTitle")
        subtitle = QLabel("Multilogin & AdsPower verification automation suite")
        subtitle.setObjectName("appSubtitle")
        text_col.addWidget(title)
        text_col.addWidget(subtitle)

        badge = QLabel("PRO")
        badge.setObjectName("appBadge")
        badge.setAlignment(Qt.AlignCenter)

        layout.addLayout(text_col)
        layout.addStretch(1)
        layout.addWidget(badge, 0, Qt.AlignVCenter)
        return header

    def _connect_signals(self):
        self.start_button.clicked.connect(self.start_work)
        self.stop_button.clicked.connect(self.stop_work)
        self.browser_engine_selector.currentIndexChanged.connect(self.on_browser_engine_changed)
        self.multilogin_refresh_button.clicked.connect(self.refresh_multilogin_profiles)
        self.multilogin_auto_detect_button.clicked.connect(self.detect_active_multilogin_browser)
        self.multilogin_profile_input.currentIndexChanged.connect(self.on_multilogin_profile_selected)
        self.multilogin_profile_input.currentTextChanged.connect(self.on_multilogin_profile_text_changed)
        self.multilogin_token_input.textChanged.connect(self.on_multilogin_token_changed)
        self.multilogin_cdp_input.textChanged.connect(self.on_multilogin_cdp_changed)
        self.adspower_refresh_button.clicked.connect(self.refresh_adspower_profiles)
        self.open_device_browser_action.triggered.connect(self.open_device_browser)
        self.adspower_profile_input.currentIndexChanged.connect(self.on_adspower_profile_selected)

    def pick_file(self, line_edit: QLineEdit):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select File",
            "",
            "Video files (*.y4m *.mp4 *.mov *.webm *.mkv *.avi *.m4v);;All files (*.*)",
        )
        if file_path:
            line_edit.setText(file_path)

    def start_work(self):
        if self._auth_locked:
            QMessageBox.warning(self, "Locked", "Application is locked. Contact your administrator.")
            return

        if not self.auth_session or not self.auth_session.is_authenticated:
            QMessageBox.critical(self, "Unauthorized", "Active authenticated server session required.")
            return

        try:
            self.auth_session.heartbeat_check()
            if not self.auth_session.payload:
                self.auth_session.load_payload()
            payload = self.auth_session.payload or {}
            if "liveness_template" in payload:
                set_liveness_template(payload["liveness_template"])
            if "video_step_template" in payload:
                set_video_step_template(payload["video_step_template"])
        except AuthError as exc:
            self._lock_application(exc.message)
            return
        except Exception as exc:
            QMessageBox.critical(self, "Security Error", f"Failed to retrieve remote payload: {exc}")
            return

        target_url = self.url_input.text().strip() or self.config.target_url
        files = [line_edit.text().strip() for line_edit in self.file_inputs]
        browser_engine = self.browser_engine_selector.currentData() or self.config.browser_engine

        missing_paths = [path for path in files if path and not Path(path).is_file()]
        if missing_paths:
            QMessageBox.warning(
                self,
                "Invalid Files",
                "These file paths do not exist:\n" + "\n".join(missing_paths),
            )
            return

        multilogin_settings = self._selected_multilogin_settings()
        adspower_settings = self._selected_adspower_settings()

        if browser_engine == "multilogin":
            if not multilogin_settings.token:
                auto_tok = extract_local_multilogin_token()
                if auto_tok:
                    self.multilogin_token_input.setText(auto_tok)
                    multilogin_settings = self._selected_multilogin_settings()
            if (not multilogin_settings.profile_id or multilogin_settings.profile_id in ("mlx-agent", "mla-agent")) and not multilogin_settings.direct_cdp_url:
                endpoint = detect_active_cdp_endpoint(timeout_sec=0.25)
                if endpoint:
                    self.multilogin_cdp_input.setText(endpoint)
                    multilogin_settings = self._selected_multilogin_settings()
                    LOGGER.info("Auto-detected active Multilogin browser at %s", endpoint)
                else:
                    QMessageBox.warning(
                        self,
                        "Multilogin Profile Required",
                        "Please paste your Multilogin Profile ID into the profile box,\n"
                        "or start your profile inside Multilogin and click 'Auto-Detect'.",
                    )
                    return
        else:
            if not adspower_settings.identifier:
                QMessageBox.warning(
                    self,
                    "AdsPower Profile Required",
                    "Select an AdsPower profile from the dropdown, or click Refresh Profiles "
                    "after opening AdsPower.",
                )
                return

        if not self._validate_automation_videos(files):
            return

        self.log_console.clear()
        LOGGER.info("Starting background task...")
        LOGGER.info("Execution flow: %s", EXECUTION_FLOW)
        LOGGER.info("Browser engine: %s", browser_engine)
        self.set_running_state(True)

        if self.auth_session and self.config.auth.enabled:
            try:
                token = self.auth_session.ensure_access_token()
                self.auth_session.client.log_link(
                    token,
                    target_url,
                    self.auth_session.device_id,
                )
                self._log_app_activity("automation_start")
            except AuthError as exc:
                self._lock_application(exc.message)
                return


        self.config = (
            AppConfig.load()
            .with_target_url(target_url)
            .with_browser_engine(browser_engine)
            .with_multilogin(multilogin_settings)
            .with_adspower(adspower_settings)
        )
        self.config.save()
        self.services = AutomationServices.from_config(self.config)
        self.worker = WorkerThread(self.services, files, self)
        self.worker.status.connect(self.on_worker_status)
        self.worker.finished_successfully.connect(self.on_worker_finished)
        self.worker.stopped.connect(self.on_worker_stopped)
        self.worker.failed.connect(self.on_worker_failed)
        self.worker.verification_passed.connect(self.on_verification_passed)
        self.worker.finished.connect(self.on_thread_finished)
        self.worker.start()

    def stop_work(self):
        if self.worker and self.worker.isRunning():
            LOGGER.info("Requesting stop...")
            self.stop_button.setEnabled(False)
            self.worker.requestInterruption()

    def on_worker_finished(self):
        LOGGER.info("Finished successfully.")

    def on_worker_stopped(self):
        LOGGER.info("Stopped by user.")

    def on_worker_failed(self, message: str):
        LOGGER.error("Worker failed: %s", message)
        QMessageBox.critical(
            self,
            "Automation Failed",
            message,
        )

    def on_verification_passed(self, url: str):
        QMessageBox.information(
            self,
            "Verification Passed",
            "agesmart.eu accepted the verification.\n\n"
            f"Result URL:\n{url}",
        )

    def on_worker_status(self, message: str):
        LOGGER.info(message)

    def on_thread_finished(self):
        self.set_running_state(False)
        self.worker = None

    def open_device_browser(self):
        if self.device_browser_window:
            self.device_browser_window.show()
            self.device_browser_window.raise_()
            self.device_browser_window.activateWindow()
            return

        try:
            from device_browser.ui import MainWindow as DeviceBrowserWindow
        except ModuleNotFoundError as exc:
            LOGGER.exception("Device browser dependency is missing.")
            QMessageBox.critical(
                self,
                "Device Browser Unavailable",
                "The device browser requires PyQtWebEngine.\n\n"
                "Install dependencies with:\n"
                "pip install -r requirements.txt",
            )
            return
        except Exception as exc:
            LOGGER.exception("Failed to initialize device browser.")
            QMessageBox.critical(
                self,
                "Device Browser Error",
                f"Could not initialize the device browser:\n{exc}",
            )
            return

        self.device_browser_window = DeviceBrowserWindow()
        self.device_browser_window.setAttribute(Qt.WA_DeleteOnClose, True)
        self.device_browser_window.destroyed.connect(self.on_device_browser_closed)
        self.device_browser_window.show()
        LOGGER.info(
            "Device browser initialized: ProfileManager -> AppSettings -> DeviceBrowser -> QWebEngineView"
        )

    def on_device_browser_closed(self, _object=None):
        self.device_browser_window = None

    def set_running_state(self, running: bool):
        self.start_button.setEnabled(not running and not self._auth_locked)
        self.stop_button.setEnabled(running)
        self.url_input.setEnabled(not running)
        self.browser_engine_selector.setEnabled(not running)
        self.adspower_profile_input.setEnabled(not running)
        self.adspower_refresh_button.setEnabled(not running)
        self.multilogin_profile_input.setEnabled(not running)
        self.multilogin_refresh_button.setEnabled(not running)
        self.multilogin_token_input.setEnabled(not running)
        self.multilogin_cdp_input.setEnabled(not running)
        self.multilogin_auto_detect_button.setEnabled(not running)
        for line_edit in self.file_inputs:
            line_edit.setEnabled(not running)
        for file_button in self.file_buttons:
            file_button.setEnabled(not running)

    def _populate_multilogin_profiles(self, *, show_errors: bool = False):
        self.multilogin_refresh_button.setEnabled(False)
        self.multilogin_refresh_button.setText("Loading...")
        if not self.multilogin_token_input.text().strip():
            auto_tok = extract_local_multilogin_token()
            if auto_tok:
                self.multilogin_token_input.setText(auto_tok)
        selected = self._selected_multilogin_settings()
        launch_settings = MultiloginLaunchSettings.from_config(selected)

        self._multilogin_loader_thread = MultiloginProfileLoaderThread(launch_settings, self)
        self._multilogin_loader_thread.profiles_loaded.connect(
            lambda profiles, err: self._on_multilogin_profiles_loaded(profiles, err, show_errors=show_errors)
        )
        self._multilogin_loader_thread.start()

    def _on_multilogin_profiles_loaded(self, profiles: list[MultiloginProfile], err: str, show_errors: bool = False):
        self.multilogin_refresh_button.setEnabled(True)
        self.multilogin_refresh_button.setText("Refresh")

        selected = self.config.multilogin
        current_text = self.multilogin_profile_input.currentText().strip()

        if err and show_errors:
            LOGGER.warning("Could not load Multilogin profiles: %s", err)
            QMessageBox.warning(
                self,
                "Multilogin Profiles",
                f"Could not load profiles from Multilogin.\n\n{err}\n\n"
                "Tip: You can paste your Multilogin Profile ID directly into the box, "
                "or launch your profile in Multilogin and click 'Auto-Detect'.",
            )

        self.multilogin_profile_input.blockSignals(True)
        self.multilogin_profile_input.clear()

        if not profiles and (selected.profile_id or current_text):
            pid = current_text or selected.profile_id
            if pid not in ("mlx-agent", "mla-agent", "direct-cdp"):
                profiles = [
                    MultiloginProfile(
                        profile_id=pid,
                        folder_id=selected.folder_id,
                        name="Saved profile",
                    )
                ]

        selected_index = 0
        for i, profile in enumerate(profiles):
            self.multilogin_profile_input.addItem(profile.label(), profile)
            if (selected.profile_id and profile.profile_id == selected.profile_id) or (current_text and profile.profile_id == current_text):
                selected_index = i
            elif not selected.profile_id and profile.profile_id not in ("mlx-agent", "mla-agent", "direct-cdp") and selected_index == 0:
                selected_index = i

        if profiles:
            self.multilogin_profile_input.setCurrentIndex(selected_index)
        elif current_text:
            self.multilogin_profile_input.setEditText(current_text)

        self.multilogin_profile_input.blockSignals(False)

    def refresh_multilogin_profiles(self):
        self._populate_multilogin_profiles(show_errors=True)
        LOGGER.info("Refreshing Multilogin profiles in background...")

    def detect_active_multilogin_browser(self):
        LOGGER.info("Scanning for active Multilogin browser...")
        self.multilogin_auto_detect_button.setEnabled(False)
        self.multilogin_auto_detect_button.setText("Scanning...")

        self._multilogin_detector_thread = MultiloginCdpDetectorThread(self)
        self._multilogin_detector_thread.detected.connect(self._on_cdp_detected)
        self._multilogin_detector_thread.start()

    def _on_cdp_detected(self, endpoint: str):
        self.multilogin_auto_detect_button.setEnabled(True)
        self.multilogin_auto_detect_button.setText("Auto-Detect")
        if endpoint:
            self.multilogin_cdp_input.setText(endpoint)
            LOGGER.info("Detected running Multilogin browser at %s", endpoint)
            QMessageBox.information(
                self,
                "Active Browser Detected",
                f"Successfully connected to active Multilogin browser at:\n{endpoint}\n\n"
                "The automation will now run through this active browser session.",
            )
        else:
            LOGGER.warning("No running Multilogin browser detected.")
            QMessageBox.information(
                self,
                "No Running Browser Found",
                "No active Multilogin browser was detected on local ports.\n\n"
                "Please start your profile inside Multilogin first,\n"
                "or paste your Multilogin Profile ID in the box above.",
            )

    def _selected_multilogin_profile(self) -> MultiloginProfile | None:
        data = self.multilogin_profile_input.currentData()
        if isinstance(data, MultiloginProfile):
            return data
        return None

    def _selected_multilogin_settings(self) -> MultiloginSettings:
        profile = self._selected_multilogin_profile()
        base = self.config.multilogin
        cdp_override = self.multilogin_cdp_input.text().strip()
        text_val = self.multilogin_profile_input.currentText().strip()

        profile_id = profile.profile_id if profile else ""
        if not profile_id or profile_id in ("mlx-agent", "mla-agent", "direct-cdp"):
            if text_val and not text_val.startswith("---"):
                import re
                m = re.search(r'\(([^)]+)\)$', text_val)
                if m:
                    extracted = m.group(1).strip()
                    if extracted not in ("mlx-agent", "mla-agent", "direct-cdp", "Online", "Ready"):
                        profile_id = extracted
                    else:
                        profile_id = base.profile_id
                else:
                    profile_id = text_val
            else:
                profile_id = base.profile_id

        folder_id = profile.folder_id if profile else base.folder_id
        token_val = self.multilogin_token_input.text().strip() if hasattr(self, "multilogin_token_input") else base.token
        return MultiloginSettings(
            api_base=base.api_base,
            profile_id=profile_id,
            folder_id=folder_id,
            token=token_val or base.token,
            api_version=base.api_version,
            direct_cdp_url=cdp_override,
            close_on_stop=base.close_on_stop,
        )

    def on_multilogin_token_changed(self, _text: str):
        multilogin_settings = self._selected_multilogin_settings()
        self.config = AppConfig.load().with_multilogin(multilogin_settings)
        self.config.save()

    def on_multilogin_profile_selected(self, _index: int):
        profile = self._selected_multilogin_profile()
        if not profile:
            return
        LOGGER.info("Multilogin profile selected: %s", profile.label())
        multilogin_settings = self._selected_multilogin_settings()
        if multilogin_settings.profile_id and multilogin_settings.profile_id not in ("mlx-agent", "mla-agent", "direct-cdp"):
            self.config = AppConfig.load().with_multilogin(multilogin_settings)
            self.config.save()

    def on_multilogin_profile_text_changed(self, _text: str):
        multilogin_settings = self._selected_multilogin_settings()
        if multilogin_settings.profile_id and multilogin_settings.profile_id not in ("mlx-agent", "mla-agent", "direct-cdp"):
            self.config = AppConfig.load().with_multilogin(multilogin_settings)
            self.config.save()

    def on_multilogin_cdp_changed(self, text: str):
        multilogin_settings = self._selected_multilogin_settings()
        self.config = AppConfig.load().with_multilogin(multilogin_settings)
        self.config.save()

    def on_browser_engine_changed(self, index: int):
        engine = self.browser_engine_selector.itemData(index) or ("adspower" if index == 1 else "multilogin")
        self.engine_stack.setCurrentIndex(index)
        self.config = AppConfig.load().with_browser_engine(engine)
        self.config.save()
        LOGGER.info("Browser engine switched to: %s", engine)
        if engine == "multilogin":
            if self.multilogin_profile_input.count() == 0:
                self._populate_multilogin_profiles()
        else:
            if self.adspower_profile_input.count() == 0:
                self._populate_adspower_profiles()

    def _populate_adspower_profiles(self, *, show_errors: bool = False):
        selected = self.config.adspower
        self.adspower_profile_input.blockSignals(True)
        self.adspower_profile_input.clear()

        profiles: list[AdsPowerProfile] = []
        try:
            profiles = list_adspower_profiles(selected, limit=100)
        except AdsPowerApiError as exc:
            LOGGER.warning("Could not load AdsPower profiles: %s", exc)
            if show_errors:
                QMessageBox.warning(
                    self,
                    "AdsPower Profiles",
                    f"Could not load profiles from AdsPower.\n\n{exc}\n\n"
                    "Make sure AdsPower is open and the Local API is enabled.",
                )

        if not profiles and selected.identifier:
            profiles = [
                AdsPowerProfile(
                    profile_id=selected.profile_id,
                    profile_no=selected.profile_no,
                    name="Saved profile",
                )
            ]

        selected_index = 0
        for profile in profiles:
            self.adspower_profile_input.addItem(profile.label(), profile)
            if selected.profile_id and profile.profile_id == selected.profile_id:
                selected_index = self.adspower_profile_input.count() - 1
            elif (
                not selected.profile_id
                and selected.profile_no
                and profile.profile_no == selected.profile_no
            ):
                selected_index = self.adspower_profile_input.count() - 1

        if profiles:
            self.adspower_profile_input.setCurrentIndex(selected_index)
        self.adspower_profile_input.blockSignals(False)

    def refresh_adspower_profiles(self):
        self._populate_adspower_profiles(show_errors=True)
        LOGGER.info("AdsPower profiles refreshed.")

    def _selected_adspower_profile(self) -> AdsPowerProfile | None:
        data = self.adspower_profile_input.currentData()
        if isinstance(data, AdsPowerProfile):
            return data
        return None

    def _selected_adspower_settings(self) -> AdsPowerSettings:
        profile = self._selected_adspower_profile()
        base = self.config.adspower
        if not profile:
            return base
        return AdsPowerSettings(
            api_base=base.api_base,
            profile_id=profile.profile_id,
            profile_no=profile.profile_no,
            api_key=base.api_key,
            api_version=base.api_version,
            close_on_stop=base.close_on_stop,
            cdp_mask=base.cdp_mask,
            proxy_detection=base.proxy_detection,
            open_last_tabs=base.open_last_tabs,
        )

    def on_adspower_profile_selected(self, _index: int):
        profile = self._selected_adspower_profile()
        if not profile:
            return
        LOGGER.info("AdsPower profile selected: %s", profile.label())
        adspower_settings = self._selected_adspower_settings()
        if adspower_settings.identifier:
            self.config = AppConfig.load().with_adspower(adspower_settings)
            self.config.save()

    def _validate_automation_videos(self, files: list[str]) -> bool:
        labels = ("File 1 / ID document", "File 2 / selfie", "File 3 / liveness")
        missing = [
            labels[index]
            for index, file_path in enumerate(files[:3])
            if not file_path or not Path(file_path).is_file()
        ]
        if missing:
            QMessageBox.warning(
                self,
                "Missing Videos",
                "All three videos are required:\n" + "\n".join(missing),
            )
            return False

        resolved = [Path(file_path).resolve() for file_path in files[:3]]
        if len(set(resolved)) != 3:
            QMessageBox.warning(
                self,
                "Duplicate Videos",
                "File 1, File 2, and File 3 must be three different videos.\n"
                "Using the same video in two slots will fail verification.",
            )
            return False

        return True

    def closeEvent(self, event):
        if self.auth_session and self.config.auth.enabled and not self._auth_locked:
            self._log_app_activity("app_close")
            try:
                self.auth_session.logout()
            except Exception:
                pass
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            self.worker.wait(self.config.timeouts.shutdown_ms)
        if self.device_browser_window:
            self.device_browser_window.close()
            self.device_browser_window = None
        remove_logging_handler(self.logger, self.log_handler)
        event.accept()


def ensure_local_auth_server(auth_settings: AuthSettings) -> None:
    """Ensure local auth server is running if api_base points to localhost."""
    if not auth_settings or not auth_settings.api_base:
        return
    api_base = auth_settings.api_base.lower()
    if "localhost" not in api_base and "127.0.0.1" not in api_base:
        return

    import urllib.request
    try:
        req = urllib.request.Request(f"{auth_settings.api_base}/api/login.php", method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, data=b"{}", timeout=1.0) as resp:
            return
    except urllib.error.HTTPError:
        return
    except Exception:
        pass

    import subprocess
    import shutil
    base_dir = Path(__file__).resolve().parent
    server_dir = base_dir / "server-vercel"
    if not server_dir.is_dir():
        server_dir = Path(sys.executable).resolve().parent / "server-vercel"
    if not server_dir.is_dir():
        return

    from urllib.parse import urlparse
    parsed = urlparse(auth_settings.api_base)
    port = parsed.port or 3015

    flags = 0
    if sys.platform == "win32":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

    npx = shutil.which("npx") or "npx.cmd"
    try:
        subprocess.Popen(
            [npx, "next", "start", "-p", str(port)],
            cwd=str(server_dir),
            creationflags=flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1.5)
    except Exception as exc:
        LOGGER.warning("Could not auto-start local auth server: %s", exc)


def main() -> int:
    import os

    if sys.stdout is None:
        try:
            sys.stdout = open(os.devnull, "w")
        except Exception:
            pass
    if sys.stderr is None:
        try:
            sys.stderr = open(os.devnull, "w")
        except Exception:
            pass

    if getattr(sys, "frozen", False):
        driver_dir = Path(getattr(sys, "_MEIPASS", "")) / "playwright" / "driver"
        if driver_dir.is_dir():
            node_exe = driver_dir / "node.exe"
            if node_exe.is_file():
                os.environ["PLAYWRIGHT_NODEJS_PATH"] = str(node_exe)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
    app = QApplication(sys.argv)
    app.setApplicationName("Automation Hub")
    app.setStyle("Fusion")
    app.setStyleSheet(APP_QSS)
    install_exception_logger(LOGGER)

    config = AppConfig.load()
    ok, reason = protection_checks()
    if not ok:
        LOGGER.error("Protection check failed: %s", reason)
        return 1

    ensure_local_auth_server(config.auth)

    auth_session = require_login(config.auth)
    if not auth_session or not auth_session.is_authenticated:
        return 1


    window = MainWindow(auth_session=auth_session)
    window.show()

    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
