"""
Test suite to verify full feature parity of the Vercel-ready Next.js server
with the desktop automation client (main.py, auth_client.py).
"""

import sys
import json
import time
import requests

API_BASE = "http://localhost:3000"
APP_KEY = "dev-desktop-app-key-change-me"

def run_tests():
    print("=" * 60)
    print("AUTOMATION HUB VERCEL SERVER - VERIFICATION TEST SUITE")
    print("=" * 60)

    headers = {
        "Content-Type": "application/json",
        "X-App-Key": APP_KEY
    }

    # 1. Test invalid API key
    print("\n[Test 1] Checking X-App-Key enforcement...")
    bad_res = requests.post(f"{API_BASE}/api/login.php", json={}, headers={"X-App-Key": "wrong-key"})
    assert bad_res.status_code == 401, f"Expected 401, got {bad_res.status_code}"
    print("  PASS: Invalid App Key rejected with 401.")

    # 2. Test invalid credentials
    print("\n[Test 2] Checking invalid credentials rejection...")
    bad_login = requests.post(
        f"{API_BASE}/api/login.php",
        headers=headers,
        json={"username": "nonexistent", "password": "wrongpassword", "device_id": "test-dev-1", "pc_name": "PC-1"}
    )
    assert bad_login.status_code == 401, f"Expected 401, got {bad_login.status_code}"
    print("  PASS: Invalid credentials rejected with 401.")

    # 3. Test valid login with superadmin
    print("\n[Test 3] Checking valid login with superadmin (.php rewrite test)...")
    login_res = requests.post(
        f"{API_BASE}/api/login.php",
        headers=headers,
        json={"username": "superadmin", "password": "Admin@12345", "device_id": "test-device-uuid-101", "pc_name": "WIN-AUTOMATION"}
    )
    login_data = login_res.json()
    print("  Response:", json.dumps(login_data, indent=2))
    assert login_res.status_code == 200, f"Login failed: {login_data}"
    assert login_data.get("ok") is True, "Expected ok: true"
    assert "access_token" in login_data, "Missing access_token"
    assert "refresh_token" in login_data, "Missing refresh_token"
    access_token = login_data["access_token"]
    refresh_token = login_data["refresh_token"]
    print("  PASS: Login successful. JWT Access and Refresh tokens obtained.")

    auth_headers = {
        **headers,
        "Authorization": f"Bearer {access_token}"
    }

    # 4. Test Heartbeat (.php rewrite)
    print("\n[Test 4] Checking 45s Heartbeat endpoint (/api/heartbeat.php)...")
    hb_res = requests.post(
        f"{API_BASE}/api/heartbeat.php",
        headers=auth_headers,
        json={"device_id": "test-device-uuid-101", "pc_name": "WIN-AUTOMATION"}
    )
    hb_data = hb_res.json()
    print("  Response:", json.dumps(hb_data, indent=2))
    assert hb_res.status_code == 200, f"Heartbeat failed: {hb_data}"
    assert hb_data.get("status") == "active", "Expected status: active"
    print("  PASS: Heartbeat verified and session maintained.")

    # 5. Test Link Logging (The core feature requested by user!)
    print("\n[Test 5] Checking Target Link Logging (/api/link_log.php)...")
    target_url = "https://agesmart.eu/verification/documents/sample_test_link_12345"
    link_res = requests.post(
        f"{API_BASE}/api/link_log.php",
        headers=auth_headers,
        json={"url": target_url, "browser": "multilogin", "device_id": "test-device-uuid-101"}
    )
    link_data = link_res.json()
    print("  Response:", json.dumps(link_data, indent=2))
    assert link_res.status_code == 200, f"Link log failed: {link_data}"
    assert link_data.get("logged") is True, "Expected logged: true"
    print("  PASS: Target link successfully logged into database.")

    # 6. Test Token Refresh
    print("\n[Test 6] Checking Token Refresh (/api/refresh_token.php)...")
    ref_res = requests.post(
        f"{API_BASE}/api/refresh_token.php",
        headers=headers,
        json={"refresh_token": refresh_token, "device_id": "test-device-uuid-101"}
    )
    ref_data = ref_res.json()
    print("  Response:", json.dumps(ref_data, indent=2))
    assert ref_res.status_code == 200, f"Refresh failed: {ref_data}"
    assert "access_token" in ref_data, "Missing refreshed access_token"
    print("  PASS: Refresh token exchanged for new access token.")

    # 7. Test License Validation
    print("\n[Test 7] Checking License Validation (/api/validate_license.php)...")
    lic_res = requests.post(f"{API_BASE}/api/validate_license.php", headers=auth_headers)
    lic_data = lic_res.json()
    print("  Response:", json.dumps(lic_data, indent=2))
    assert lic_res.status_code == 200, f"License check failed: {lic_data}"
    assert lic_data.get("valid") is True, "Expected license valid: true"
    print("  PASS: License status verified.")

    # 8. Test Activity Logging
    print("\n[Test 8] Checking Activity Logging (/api/activity_log.php)...")
    act_res = requests.post(
        f"{API_BASE}/api/activity_log.php",
        headers=auth_headers,
        json={"action": "test_verification_run", "device_id": "test-device-uuid-101", "details": {"step": "id_capture"}}
    )
    act_data = act_res.json()
    assert act_res.status_code == 200, f"Activity log failed: {act_data}"
    print("  PASS: Activity logged.")

    # 9. Test Payload Delivery (Protected Server-Side Payload)
    print("\n[Test 9] Checking Server-Side Payload Delivery (/api/payload.php)...")
    payload_res = requests.post(
        f"{API_BASE}/api/payload.php",
        headers=auth_headers,
        json={"device_id": "test-device-uuid-101"}
    )
    payload_data = payload_res.json()
    assert payload_res.status_code == 200, f"Payload delivery failed: {payload_data}"
    assert payload_data.get("ok") is True, "Expected ok: true"
    assert "payload" in payload_data, "Missing payload object"
    assert "liveness_template" in payload_data["payload"], "Missing liveness_template in payload"
    assert "video_step_template" in payload_data["payload"], "Missing video_step_template in payload"
    print(f"  PASS: Security payload delivered (liveness length: {len(payload_data['payload']['liveness_template'])}, video_step length: {len(payload_data['payload']['video_step_template'])}).")

    # 10. Test Logout
    print("\n[Test 10] Checking Logout (/api/logout.php)...")
    logout_res = requests.post(
        f"{API_BASE}/api/logout.php",
        headers=auth_headers,
        json={"device_id": "test-device-uuid-101"}
    )
    logout_data = logout_res.json()
    assert logout_res.status_code == 200, f"Logout failed: {logout_data}"
    print("  PASS: Successfully logged out.")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED! 100% FEATURE PARITY & PAYLOAD VERIFIED.")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()
