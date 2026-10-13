import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def test_morelogin_integration():
    print("Testing MoreLogin Unified Browser Integration (Problem 6)...")

    # 1. Test AppConfig and MoreLoginSettings
    from app_config import AppConfig, MoreLoginSettings
    ml_settings = MoreLoginSettings(
        api_base="http://127.0.0.1:40000",
        profile_id="env_998877",
        profile_name="Test Profile",
        cdp_evasion=True,
        close_on_stop=True,
    )
    assert ml_settings.identifier == "env_998877"

    cfg = AppConfig().with_browser_engine("morelogin").with_morelogin(ml_settings)
    assert cfg.browser_engine == "morelogin"
    assert cfg.morelogin.profile_id == "env_998877"

    # Test serialization round-trip
    dumped = cfg._to_dict()
    assert "morelogin" in dumped
    assert dumped["morelogin"]["profile_id"] == "env_998877"
    assert dumped["browser_engine"] == "morelogin"

    loaded_cfg = AppConfig(
        browser_engine=dumped["browser_engine"],
        morelogin=MoreLoginSettings.from_dict(dumped.get("morelogin")),
    )
    assert loaded_cfg.browser_engine == "morelogin"
    assert loaded_cfg.morelogin.profile_id == "env_998877"
    print("✓ AppConfig and MoreLoginSettings serialization verified.")

    # 2. Test MoreLogin Browser Manager and Profile Classes
    from morelogin_browser import (
        MoreLoginBrowserManager,
        MoreLoginLaunchSettings,
        MoreLoginProfile,
    )
    p = MoreLoginProfile(profile_id="p123", name="My Profile", group_name="Group A", proxy_info="1.2.3.4:8080")
    assert "My Profile" in p.label()
    assert "p123" in p.label()
    assert "Group A" in p.label()

    mgr = MoreLoginBrowserManager("http://127.0.0.1:40000")
    
    # Mock HTTP responses for MoreLogin API
    fake_list_resp = {
        "code": 0,
        "msg": "success",
        "data": {
            "total": 1,
            "dataList": [
                {
                    "id": "ml_profile_1",
                    "envName": "Browser Profile 1",
                    "groupName": "VIP",
                    "proxy": {"proxyName": "Proxy1", "proxyIp": "10.0.0.1", "proxyPort": "8080"}
                }
            ]
        }
    }

    with patch.object(mgr, "_post", return_value=fake_list_resp) as mock_post:
        profiles = mgr.list_profiles()
        assert len(profiles) == 1
        assert profiles[0].profile_id == "ml_profile_1"
        assert profiles[0].name == "Browser Profile 1"
        assert profiles[0].group_name == "VIP"
        mock_post.assert_called_with("/api/env/page", {"pageNo": 1, "pageSize": 50})

    # Test start_profile mock
    fake_start_resp = {
        "code": 0,
        "msg": "success",
        "data": {
            "debugPort": 9225
        }
    }
    with patch.object(mgr, "get_status", return_value={"status": "stopped"}):
        with patch.object(mgr, "_post", return_value=fake_start_resp) as mock_start:
            launch_s = MoreLoginLaunchSettings(profile_id="ml_profile_1", extra_args=["--arg1"])
            port = mgr.start_profile(launch_s)
            assert port == 9225
            assert mgr._active_env_id == "ml_profile_1"
            assert mgr._active_debug_port == 9225

    # Test stop mock
    with patch.object(mgr, "_post", return_value={"code": 0}) as mock_close:
        mgr.stop()
        mock_close.assert_called_with("/api/env/close", {"envId": "ml_profile_1"}, timeout_sec=10.0)
        assert mgr._active_env_id is None
    print("✓ MoreLoginBrowserManager API client & profile handling verified.")

    # 3. Test AutomationServices integration
    from main import AutomationServices
    services = AutomationServices.from_config(cfg)
    bm = services.create_browser_manager()
    assert isinstance(bm, MoreLoginBrowserManager)

    # Test build_morelogin_launch_settings with fake capture
    from camera_feed_service import VirtualCameraFeed
    fake_feed = VirtualCameraFeed(
        source_path=Path("test.mp4"),
        capture_path=Path("test.y4m"),
        converted=True,
    )
    launch_settings = services.build_morelogin_launch_settings(
        camera_feed=fake_feed,
        fake_capture_path=Path("custom.y4m"),
    )
    assert launch_settings.profile_id == "env_998877"
    assert any("--use-file-for-fake-video-capture=" in arg for arg in launch_settings.extra_args)
    assert any("--use-fake-ui-for-media-stream" in arg for arg in launch_settings.extra_args)
    assert any("--use-fake-device-for-media-stream" in arg for arg in launch_settings.extra_args)
    print("✓ AutomationServices browser manager factory and launch settings verified.")

    # 4. Test WorkerThread initialization with MoreLogin
    from main import WorkerThread
    worker = WorkerThread(services, ["file1.jpg", "file2.jpg", "file3.mp4"])
    assert worker.config.browser_engine == "morelogin"
    print("✓ WorkerThread initialization with MoreLogin engine verified.")

    # 5. Test MainWindow engine stack and selector options
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance()
    if not app:
        app = QApplication([])

    from main import MainWindow
    window = MainWindow()
    
    # Check that browser_engine_selector has all 3 engines
    engine_items = [window.browser_engine_selector.itemData(i) for i in range(window.browser_engine_selector.count())]
    assert "multilogin" in engine_items, "Multilogin missing in engine selector"
    assert "adspower" in engine_items, "AdsPower missing in engine selector"
    assert "morelogin" in engine_items, "MoreLogin missing in engine selector"

    # Check engine stack widget has 3 containers
    assert window.engine_stack.count() == 3, f"Expected 3 containers in engine_stack, found {window.engine_stack.count()}"
    assert hasattr(window, "morelogin_container")
    assert hasattr(window, "morelogin_profile_input")
    assert hasattr(window, "morelogin_refresh_button")

    # Test switching to MoreLogin
    ml_index = engine_items.index("morelogin")
    window.browser_engine_selector.setCurrentIndex(ml_index)
    assert window.engine_stack.currentIndex() == ml_index
    assert window.config.browser_engine == "morelogin"

    # Test set_running_state disables MoreLogin inputs
    window.set_running_state(True)
    assert not window.morelogin_profile_input.isEnabled()
    assert not window.morelogin_refresh_button.isEnabled()
    window.set_running_state(False)
    assert window.morelogin_profile_input.isEnabled()
    assert window.morelogin_refresh_button.isEnabled()

    print("✓ MainWindow UI controls and engine switching for MoreLogin verified.")
    print("\nALL MORELOGIN INTEGRATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_morelogin_integration()
