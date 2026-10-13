from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Ensure project root is in sys.path
PROJECT_DIR = Path(__file__).resolve().parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from app_config import AppConfig, AdsPowerSettings
from adspower_browser import (
    AdsPowerApiError,
    AdsPowerBrowserManager,
    AdsPowerLaunchSettings,
    AdsPowerProfile,
    check_adspower_active_profile,
    check_adspower_status,
    detect_local_adspower_base_url,
    detect_local_adspower_settings,
    detect_local_adspower_token,
    list_adspower_profiles,
)


class TestAdsPowerIntegration(unittest.TestCase):
    def test_01_config_and_settings(self):
        print("Testing AdsPower settings & AppConfig serialization...")
        settings = AdsPowerSettings(
            api_base="http://127.0.0.1:50325",
            profile_id="test_profile_id_123",
            profile_no="42",
            api_key="secret_token_abc",
            api_version="v2",
            close_on_stop=True,
            cdp_mask=True,
            proxy_detection=False,
            open_last_tabs=False,
        )
        self.assertEqual(settings.identifier, "test_profile_id_123")
        self.assertEqual(settings.api_base, "http://127.0.0.1:50325")

        cfg = AppConfig().with_browser_engine("adspower").with_adspower(settings)
        self.assertEqual(cfg.browser_engine == "adspower", True)
        self.assertEqual(cfg.adspower.profile_id, "test_profile_id_123")
        self.assertEqual(cfg.adspower.profile_no, "42")

        # Dict round-trip
        data = cfg._to_dict()
        self.assertIn("adspower", data)
        self.assertEqual(data["adspower"]["profile_id"], "test_profile_id_123")
        self.assertEqual(data["browser_engine"], "adspower")

        restored = AppConfig(
            browser_engine=data["browser_engine"],
            adspower=AdsPowerSettings.from_dict(data.get("adspower")),
        )
        self.assertEqual(restored.browser_engine, "adspower")
        self.assertEqual(restored.adspower.profile_id, "test_profile_id_123")
        self.assertEqual(restored.adspower.api_key, "secret_token_abc")
        print("  ✓ AdsPower configuration verified.")

    def test_02_adspower_profile_dataclass(self):
        print("Testing AdsPowerProfile label formatting...")
        p1 = AdsPowerProfile(profile_id="k1deidiv", profile_no="88", name="My Profile", group_name="Group1")
        self.assertIn("#88", p1.label())
        self.assertIn("My Profile", p1.label())
        self.assertIn("k1deidiv", p1.label())

        p2 = AdsPowerProfile(profile_id="k1deidiv", profile_no="", name="Only ID")
        self.assertEqual(p2.label(), "Only ID")

        p3 = AdsPowerProfile(profile_id="", profile_no="99", name="")
        self.assertEqual(p3.label(), "#99 - 99")
        print("  ✓ Profile labels verified.")

    def test_03_detect_local_settings(self):
        print("Testing local AdsPower detection...")
        base = detect_local_adspower_base_url()
        self.assertTrue(base.startswith("http"))

        token = detect_local_adspower_token()
        # On this machine, AdsPower is installed and running
        print(f"  Detected local token: {token[:6] if token else 'None'}... (len={len(token)})")
        
        base_url, detected_token, is_live = detect_local_adspower_settings()
        self.assertTrue(base_url.startswith("http"))
        print(f"  Detected settings: base={base_url}, live={is_live}")
        print("  ✓ Local settings detection verified.")

    def test_04_status_endpoint(self):
        print("Testing check_adspower_status...")
        # Mock status endpoint
        with patch("adspower_browser.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({"code": 0, "msg": "success"}).encode("utf-8")
            mock_resp.__enter__.return_value = mock_resp
            mock_urlopen.return_value = mock_resp

            status = check_adspower_status("http://127.0.0.1:50325")
            self.assertTrue(status)
        print("  ✓ Status check verified.")

    def test_05_list_profiles_mocked(self):
        print("Testing list_adspower_profiles with mock responses...")
        fake_v2_resp = {
            "code": 0,
            "msg": "Success",
            "data": {
                "list": [
                    {
                        "profile_id": "prof_001",
                        "profile_no": "10",
                        "name": "Profile Alpha",
                        "group_name": "VIP",
                        "remark": "Primary test profile",
                    },
                    {
                        "user_id": "prof_002",
                        "serial_number": "11",
                        "name": "Profile Beta",
                        "group_name": "Standard",
                        "remark": "",
                    },
                ]
            },
        }

        with patch("adspower_browser._request_json", return_value=fake_v2_resp) as mock_req:
            settings = AdsPowerSettings(api_base="http://127.0.0.1:50325", api_key="test_tok")
            profiles = list_adspower_profiles(settings)
            self.assertEqual(len(profiles), 2)
            self.assertEqual(profiles[0].profile_id, "prof_001")
            self.assertEqual(profiles[0].profile_no, "10")
            self.assertEqual(profiles[0].name, "Profile Alpha")
            self.assertEqual(profiles[1].profile_id, "prof_002")
            self.assertEqual(profiles[1].profile_no, "11")
            self.assertEqual(profiles[1].name, "Profile Beta")
        print("  ✓ Mocked profile listing verified.")

    def test_06_active_profile_and_browser_start(self):
        print("Testing AdsPowerBrowserManager start and active reuse...")
        mgr = AdsPowerBrowserManager()

        # Case A: Profile is already active -> reuse WebSocket directly
        active_resp = {
            "status": "Active",
            "ws": {"puppeteer": "ws://127.0.0.1:9999/devtools/browser/abc1234"},
            "debug_port": "9999",
        }

        launch_settings = AdsPowerLaunchSettings(
            profile_id="k1hnv9qa",
            profile_no="1",
            api_base="http://127.0.0.1:50325",
            api_key="token_xyz",
        )

        mock_playwright = MagicMock()
        mock_chromium = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_page.is_closed.return_value = False
        mock_context.pages = [mock_page]
        mock_browser.contexts = [mock_context]
        mock_chromium.connect_over_cdp.return_value = mock_browser
        mock_playwright.chromium = mock_chromium

        with patch("adspower_browser.check_adspower_active_profile", return_value=active_resp):
            with patch("playwright.sync_api.sync_playwright") as mock_pw_init:
                mock_pw_init.return_value.start.return_value = mock_playwright
                page = mgr.start(launch_settings)
                self.assertIsNotNone(page)
                mock_chromium.connect_over_cdp.assert_called_with(
                    "ws://127.0.0.1:9999/devtools/browser/abc1234",
                    timeout=15000,
                )

        # Stop manager
        with patch.object(mgr, "_stop_profile") as mock_stop:
            mgr.stop()
            self.assertIsNone(mgr._browser)
            mock_stop.assert_called_once()
        print("  ✓ Active profile reuse and manager stop verified.")

    def test_07_live_client_query_if_available(self):
        print("Testing query against live local AdsPower client if running...")
        base, token, is_live = detect_local_adspower_settings()
        if is_live:
            print(f"  AdsPower is currently running at {base}!")
            settings = AdsPowerSettings(api_base=base, api_key=token)
            profiles = list_adspower_profiles(settings)
            self.assertGreaterEqual(len(profiles), 1)
            print(f"  Successfully fetched {len(profiles)} live profile(s) from running AdsPower:")
            for p in profiles:
                print(f"    - {p.label()}")
        else:
            print("  AdsPower client not running, live query skipped.")
        print("  ✓ Live client check completed.")


    def test_08_worker_thread_adspower_execution(self):
        print("Testing WorkerThread execution with AdsPower engine...")
        from PyQt5.QtCore import QCoreApplication
        app = QCoreApplication.instance()
        if not app:
            app = QCoreApplication([])

        from main import WorkerThread, AutomationServices

        adspower_settings = AdsPowerSettings(
            api_base="http://127.0.0.1:50325",
            profile_id="k1hnv9qa",
            profile_no="1",
            api_key="mock_key",
        )
        cfg = AppConfig().with_browser_engine("adspower").with_adspower(adspower_settings)

        # Mock browser manager & page
        mock_mgr = MagicMock()
        mock_page = MagicMock()
        mock_context = MagicMock()
        mock_page.is_closed.return_value = False
        mock_page.title.return_value = "Verification Portal"
        mock_page.url = "https://example.com/verify"
        mock_page.context = mock_context
        mock_mgr.start.return_value = mock_page

        mock_camera_svc = MagicMock()
        mock_camera_svc.prepare.return_value = None
        mock_camera_svc.prepare_automation_set.return_value = [None, None, None]
        mock_camera_svc.prepare_blob_sources.return_value = []
        mock_camera_svc.output_label.return_value = "Virtual Cam"

        services = AutomationServices(
            config=cfg,
            adspower_browser_manager_factory=lambda: mock_mgr,
            camera_service_factory=lambda: mock_camera_svc,
        )

        worker = WorkerThread(
            services,
            files=["", "", ""],
        )

        # Request stop immediately after page load to allow run() to complete
        statuses = []
        worker.status.connect(lambda s: statuses.append(s))

        stop_calls = [0]
        def fake_stop():
            stop_calls[0] += 1
            return stop_calls[0] >= 5

        worker._stop_requested = fake_stop

        def fake_open(page, url):
            return page

        worker._open_target_page = fake_open

        worker.run()
        self.assertTrue(any("AdsPower" in s for s in statuses))
        mock_mgr.start.assert_called_once()
        print("  ✓ WorkerThread AdsPower execution verified.")


def run_all_tests():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestAdsPowerIntegration)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
