import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from device_browser.profile_manager import ProfileManager
from app_config import AppConfig

def test_profile_definitions():
    print("Testing device profiles in profiles.json...")
    mgr = ProfileManager()
    profiles = mgr.all_profiles()
    assert len(profiles) >= 4, f"Expected at least 4 profiles, found {len(profiles)}"
    
    # Check samsung-galaxy-s25-ultra
    s25 = mgr.get("samsung-galaxy-s25-ultra")
    assert s25.os_name == "Android"
    assert s25.browser_name == "Chrome"
    assert "Chrome/" in s25.user_agent
    assert s25.orientation == "portrait"
    assert s25.mobile is True
    assert s25.touch_points == 5
    print(f"  ✅ S25 Ultra profile verified: {s25.label()}")

    # Check windows-11-desktop
    win11 = mgr.get("windows-11-desktop")
    assert win11.os_name == "Windows"
    assert win11.browser_name == "Chrome"
    assert win11.orientation == "landscape"
    assert win11.mobile is False
    print(f"  ✅ Windows 11 profile verified: {win11.label()}")

def test_config_alignment():
    print("Testing config.json profile and viewport alignment...")
    cfg = AppConfig.load()
    assert cfg.device_profile_id == "samsung-galaxy-s25-ultra"
    assert cfg.profile_name == "samsung-galaxy-s25-ultra"
    assert "Chrome" in cfg.user_agent and "Android" in cfg.user_agent
    assert cfg.window_size.width == 384
    assert cfg.window_size.height == 832
    assert cfg.camera_output_size.width == 720
    assert cfg.camera_output_size.height == 1280
    assert cfg.automation.liveness_upload_mode == "live_recording"
    print("  ✅ config.json aligns with portrait Android mobile profile and native live_recording.")

if __name__ == "__main__":
    print("==================================================")
    print("🚀 RUNNING PROBLEM 4 TESTS (PROFILE ALIGNMENT)")
    print("==================================================")
    test_profile_definitions()
    test_config_alignment()
    print("\n🎉 ALL PROBLEM 4 TESTS PASSED!")
