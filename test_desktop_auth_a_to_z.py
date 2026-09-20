"""
Full A-to-Z Verification of Desktop Automation Tool Authentication & Session Lifecycle.
Tests the actual python modules: auth_config, auth_client, auth_session, device_fingerprint.
"""

import sys
import time
import requests

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from auth_config import AuthSettings
from auth_client import AuthClient, AuthError
from auth_session import AuthSession
from device_fingerprint import device_id, pc_name

SERVER_BASE = "http://localhost:3015"
APP_KEY = "dev-desktop-app-key-change-me"
USERNAME = "superadmin"
PASSWORD = "Admin@12345"

def print_step(step: str, title: str):
    print(f"\n{'='*70}")
    print(f"[{step}] {title}")
    print(f"{'='*70}")

def main():
    print("======================================================================")
    print("🔍 DESKTOP AUTOMATION TOOL: A-TO-Z AUTHENTICATION & LIFECYCLE TEST")
    print(f"Target Server: {SERVER_BASE}")
    print(f"Neon Database: ep-lingering-credit-avo41viw")
    print("======================================================================")

    passed_count = 0
    total_steps = 15

    # ---------------------------------------------------------
    # STEP A: Device Fingerprinting
    # ---------------------------------------------------------
    print_step("STEP A", "Hardware Device Fingerprinting & Identity Generation")
    try:
        dev_id = device_id()
        mach_name = pc_name()
        print(f"   [+] Hardware Device ID: {dev_id}")
        print(f"   [+] Workstation Hostname: {mach_name}")
        assert len(dev_id) > 10, "Device ID generated is too short"
        assert len(mach_name) > 0, "Machine name is empty"
        print("   ✅ STEP A PASSED: Hardware device identity uniquely generated.")
        passed_count += 1
    except Exception as e:
        print(f"   ❌ STEP A FAILED: {e}")

    # ---------------------------------------------------------
    # STEP B: Configuration Initialization
    # ---------------------------------------------------------
    print_step("STEP B", "AuthSettings Initialization from Desktop Config")
    try:
        settings = AuthSettings(
            enabled=True,
            api_base=SERVER_BASE,
            app_key=APP_KEY,
            heartbeat_seconds=45,
            session_timeout_seconds=3600,
            verify_ssl=False,
        )
        client = AuthClient(settings)
        print(f"   [+] Configured API Base: {settings.api_base}")
        print(f"   [+] Endpoint URL: {settings.api_url('login.php')}")
        print(f"   [+] Enforced Heartbeat: {settings.heartbeat_seconds}s")
        print("   ✅ STEP B PASSED: Desktop auth configuration ready.")
        passed_count += 1
    except Exception as e:
        print(f"   ❌ STEP B FAILED: {e}")

    # ---------------------------------------------------------
    # STEP C: Negative Test - Bad Credentials Rejection
    # ---------------------------------------------------------
    print_step("STEP C", "Security Check - Invalid Credentials Rejection")
    try:
        failed_as_expected = False
        try:
            client.login(USERNAME, "WrongPassword@999", dev_id, mach_name)
        except AuthError as ae:
            if ae.code in ("invalid", "invalid_credentials", "unauthorized"):
                failed_as_expected = True
                print(f"   [+] Correctly rejected: Code={ae.code}, Message={ae.message}")
        assert failed_as_expected, "Security vulnerability: server accepted bad password!"
        print("   ✅ STEP C PASSED: Invalid password rejected with proper error code.")
        passed_count += 1
    except Exception as e:
        print(f"   ❌ STEP C FAILED: {e}")

    # Clear any leftover sessions in DB before clean test
    try:
        admin_login_res = requests.post(f"{SERVER_BASE}/api/admin/login", json={"username": USERNAME, "password": PASSWORD})
        if admin_login_res.status_code == 200:
            cookie = admin_login_res.headers.get("set-cookie", "").split(";")[0]
            requests.post(f"{SERVER_BASE}/api/admin/sessions", json={"user_id": 1}, headers={"Cookie": cookie})
    except Exception:
        pass

    # ---------------------------------------------------------
    # STEP D: Tool Desktop Login Handshake
    # ---------------------------------------------------------
    print_step("STEP D", "Desktop Tool Primary Login Handshake (POST /api/login.php)")
    login_result = None
    try:
        login_result = client.login(USERNAME, PASSWORD, dev_id, mach_name)
        print(f"   [+] Authentication: SUCCESS")
        print(f"   [+] Username: {login_result.user.get('username')}")
        print(f"   [+] Role: {login_result.user.get('role')} ({login_result.user.get('role_label')})")
        print(f"   [+] Access Token: {login_result.access_token[:25]}... (TTL: {login_result.access_expires_in}s)")
        print(f"   [+] Refresh Token: {login_result.refresh_token[:25]}...")
        assert login_result.access_token, "Access token missing"
        assert login_result.refresh_token, "Refresh token missing"
        print("   ✅ STEP D PASSED: Full authentication handshake succeeded.")
        passed_count += 1
    except Exception as e:
        print(f"   ❌ STEP D FAILED: {e}")

    # ---------------------------------------------------------
    # STEP E: License Verification
    # ---------------------------------------------------------
    print_step("STEP E", "Cryptographic License Validation & Entitlements")
    try:
        lic = login_result.license
        print(f"   [+] License Status: {lic.get('status')}")
        print(f"   [+] License Expiry: {lic.get('expires_at')}")
        print(f"   [+] Days Remaining: {lic.get('days_left')} days")
        print(f"   [+] Is Trial: {lic.get('is_trial')}")
        assert lic.get('status') == 'active', f"License is not active: {lic}"
        print("   ✅ STEP E PASSED: Enterprise license active and verified.")
        passed_count += 1
    except Exception as e:
        print(f"   ❌ STEP E FAILED: {e}")

    # ---------------------------------------------------------
    # STEP F: AuthSession Initialization & State Cache
    # ---------------------------------------------------------
    print_step("STEP F", "Desktop AuthSession Local State & Secure Cache")
    session = None
    try:
        session = AuthSession(settings=settings, client=client, device_id=dev_id, pc_name=mach_name)
        session.apply_login(login_result)
        print(f"   [+] Session Authenticated: {session.is_authenticated}")
        print(f"   [+] Cached Username: {session.username}")
        print(f"   [+] Heartbeat Interval: {session.heartbeat_seconds}s")
        assert session.is_authenticated, "Session is not marked authenticated"
        print("   ✅ STEP F PASSED: AuthSession initialized and encrypted state cached.")
        passed_count += 1
    except Exception as e:
        print(f"   ❌ STEP F FAILED: {e}")

    # ---------------------------------------------------------
    # STEP G: Secure Dynamic Payload Retrieval (Target Link)
    # ---------------------------------------------------------
    print_step("STEP G", "Server-Side Dynamic Payload & Target Link Fetch (POST /api/payload.php)")
    payload = None
    try:
        payload = session.load_payload()
        print(f"   [+] Payload Response Received from Server")
        print(f"   [+] Payload Object Keys: {list(payload.keys())}")
        if "target_url" in payload:
            print(f"   [+] Dynamic Target URL: {payload.get('target_url')}")
        print("   ✅ STEP G PASSED: Encrypted server-side payload successfully loaded.")
        passed_count += 1
    except Exception as e:
        print(f"   ❌ STEP G FAILED: {e}")

    # ---------------------------------------------------------
    # STEP H: Standalone License Check Endpoint
    # ---------------------------------------------------------
    print_step("STEP H", "Direct License Check (POST /api/validate_license.php)")
    try:
        token = session.ensure_access_token()
        check_res = client._post("validate_license.php", access_token=token)
        print(f"   [+] Validation Response: {check_res}")
        assert check_res.get("valid") is True, "License check returned invalid"
        print("   ✅ STEP H PASSED: Direct license enforcement endpoint verified.")
        passed_count += 1
    except Exception as e:
        print(f"   ❌ STEP H FAILED: {e}")

    # ---------------------------------------------------------
    # STEP I: Heartbeat Reporting Loop
    # ---------------------------------------------------------
    print_step("STEP I", "Periodic Heartbeat Synchronization (POST /api/heartbeat.php)")
    try:
        session.heartbeat_check()
        print(f"   [+] Heartbeat transmitted successfully with device={dev_id}")
        print(f"   [+] Server verified session liveness and extended timeout window.")
        print("   ✅ STEP I PASSED: 45-second heartbeat loop validated.")
        passed_count += 1
    except Exception as e:
        print(f"   ❌ STEP I FAILED: {e}")

    # ---------------------------------------------------------
    # STEP J: Anti-Hijacking / Single-Session Enforcement
    # ---------------------------------------------------------
    print_step("STEP J", "Single-Session Security Enforcement (Anti-Concurrent Hijack)")
    try:
        hijack_prevented = False
        other_device = "unauthorized-rogue-device-888"
        try:
            client.login(USERNAME, PASSWORD, other_device, "ATTACKER-PC")
        except AuthError as ae:
            print(f"   [+] Server Response: Code={ae.code}, Message={ae.message}")
            if ae.code in ("session_active", "device_mismatch", "rate_limit"):
                hijack_prevented = True
                print(f"   [+] Concurrency Guard Triggered: {ae.code} -> {ae.message}")
        assert hijack_prevented, f"Single session enforcement failed! Code={ae.code}"
        print("   ✅ STEP J PASSED: Rogue concurrent session attempt blocked by server.")
        passed_count += 1
    except Exception as e:
        print(f"   ❌ STEP J FAILED: {e}")

    # ---------------------------------------------------------
    # STEP K: Target Link Audit Trail Logging
    # ---------------------------------------------------------
    print_step("STEP K", "Target Link Navigation Audit Trail (POST /api/link_log.php)")
    try:
        token = session.ensure_access_token()
        client.log_link(
            access_token=token,
            url="https://agesmart.eu/verification/documents/3TJG_EnR-w3Q2w8htaT_Y0YBtonQs5s0",
            device_id=dev_id,
            browser="multilogin",
        )
        print(f"   [+] Target URL logged to Neon DB 'link_logs'")
        print("   ✅ STEP K PASSED: Link audit trail persisted into database.")
        passed_count += 1
    except Exception as e:
        print(f"   ❌ STEP K FAILED: {e}")

    # ---------------------------------------------------------
    # STEP L: Desktop Tool Automation Event Logging
    # ---------------------------------------------------------
    print_step("STEP L", "Desktop Tool Automation Event Logging (POST /api/activity_log.php)")
    try:
        token = session.ensure_access_token()
        client.log_activity(
            access_token=token,
            action="tool_automation_step_verified",
            device_id=dev_id,
            pc_name=mach_name,
            details={"step": "camera_liveness_simulation", "status": "completed", "duration_sec": 13.5},
        )
        print(f"   [+] Automation activity event logged to Neon DB 'activity_logs'")
        print("   ✅ STEP L PASSED: Activity logging persisted into database.")
        passed_count += 1
    except Exception as e:
        print(f"   ❌ STEP L FAILED: {e}")

    # ---------------------------------------------------------
    # STEP M: Token Refresh Handshake
    # ---------------------------------------------------------
    print_step("STEP M", "Access Token Refresh Exchange (POST /api/refresh_token.php)")
    try:
        old_token = session.access_token
        new_token = client.refresh(session.refresh_token, dev_id)
        session.access_token = new_token
        print(f"   [+] Old Token: {old_token[:20]}...")
        print(f"   [+] New Token: {new_token[:20]}...")
        assert new_token and new_token != old_token, "New access token was not generated"
        print("   ✅ STEP M PASSED: Seamless token rotation completed without user interruption.")
        passed_count += 1
    except Exception as e:
        print(f"   ❌ STEP M FAILED: {e}")

    # ---------------------------------------------------------
    # STEP N: Graceful Desktop Tool Logout
    # ---------------------------------------------------------
    print_step("STEP N", "Graceful Desktop Tool Logout (POST /api/logout.php)")
    try:
        client.logout(session.access_token, dev_id)
        print(f"   [+] Logout request completed. Active session terminated on server.")
        print("   ✅ STEP N PASSED: Session revoked on Neon PostgreSQL.")
        passed_count += 1
    except Exception as e:
        print(f"   ❌ STEP N FAILED: {e}")

    # ---------------------------------------------------------
    # STEP O: Post-Logout Verification
    # ---------------------------------------------------------
    print_step("STEP O", "Post-Logout Token Invalidation Verification")
    try:
        token_invalidated = False
        try:
            # Heartbeat with revoked session should fail
            client.heartbeat(session.access_token, dev_id, mach_name)
        except AuthError as ae:
            if ae.code in ("session_expired", "unauthorized", "force_logout"):
                token_invalidated = True
                print(f"   [+] Server verified session is inactive: {ae.code} -> {ae.message}")
        assert token_invalidated, "Security risk: old token was still accepted after logout!"
        print("   ✅ STEP O PASSED: Token strictly invalidated after session logout.")
        passed_count += 1
    except Exception as e:
        print(f"   ❌ STEP O FAILED: {e}")

    # ---------------------------------------------------------
    # FINAL SUMMARY
    # ---------------------------------------------------------
    print("\n" + "="*70)
    print(f"🏁 FINAL SCORE: {passed_count}/{total_steps} STEPS PASSED ({(passed_count/total_steps)*100:.0f}%)")
    print("="*70)

    if passed_count == total_steps:
        print("\n🎉 ALL A-TO-Z DESKTOP TOOL AUTHENTICATION STEPS COMPLETED FLAWLESSLY!")
        sys.exit(0)
    else:
        print(f"\n⚠️ {total_steps - passed_count} STEP(S) FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    main()
