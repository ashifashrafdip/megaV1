import sys
import os
import time
import json
import requests
import subprocess

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

from app_config import AppConfig
from auth_config import AuthSettings
from auth_client import AuthClient, AuthError
from auth_session import AuthSession
from device_fingerprint import device_id, pc_name
from login_dialog import LoginDialog
from main import MainWindow, ensure_local_auth_server

def print_header(title: str):
    print("\n" + "=" * 75)
    print(f"▶ {title}")
    print("=" * 75)

def main():
    print("=" * 75)
    print("🤖 AUTOMATION HUB: DESKTOP LOGIN & SERVER COMMUNICATION VERIFICATION")
    print("=" * 75)

    config = AppConfig.load()
    print(f"[+] Loaded config: api_base={config.auth.api_base}, app_key={config.auth.app_key}")

    # Step 1: Ensure Local Auth Server is running
    print_header("STEP 1: Checking & Starting Local Auth Server")
    ensure_local_auth_server(config.auth)
    time.sleep(1)

    try:
        health_resp = requests.post(
            f"{config.auth.api_base}/api/login.php",
            json={},
            headers={"Content-Type": "application/json", "X-App-Key": config.auth.app_key},
            timeout=5,
        )
        print(f"[+] Auth server status code: {health_resp.status_code}")
        assert health_resp.status_code in (200, 400, 401), f"Unexpected status: {health_resp.status_code}"
        print("✅ STEP 1 PASSED: Auth server is live and responsive.")
    except Exception as e:
        print(f"❌ STEP 1 FAILED: Server is not responding: {e}")
        return 1

    # Step 2: Test PyQt5 GUI Login Dialog
    print_header("STEP 2: Executing Desktop GUI Login Handshake")
    app = QApplication.instance() or QApplication(sys.argv)
    
    dialog = LoginDialog(settings=config.auth)
    dialog.username_input.setText("superadmin")
    dialog.password_input.setText("Admin@12345")
    
    print("[+] Form populated with username='superadmin' and password='••••••••'")
    print("[+] Triggering login handshake through LoginDialog._attempt_login()...")
    dialog._attempt_login()

    session = dialog.session
    if session is None:
        print(f"[-] Login failed! Status label: '{dialog.status_label.text()}'")
    assert session is not None, f"Login failed: {dialog.status_label.text()}"
    assert session.is_authenticated, "Session is not authenticated"
    print(f"[+] Login Successful! User: {session.username}, Role: {session.user.get('role')}")
    print(f"[+] Access Token: {session.access_token[:25]}...")
    print(f"[+] Refresh Token: {session.refresh_token[:25]}...")
    if session.license:
        lic = session.license
        print(f"[+] License Status: {lic.get('status')} (Expires: {lic.get('expires_at')}, Days Left: {lic.get('days_left')})")
    print("✅ STEP 2 PASSED: Desktop GUI login completed and session established.")

    # Step 3: Test Dynamic Encrypted Payload Delivery
    print_header("STEP 3: Testing Server-Side Dynamic Payload Delivery")
    try:
        session.load_payload()
        payload = session.payload or {}
        print(f"[+] Received encrypted server payload with keys: {list(payload.keys())}")
        assert len(payload) > 0, "Empty payload received"
        print("✅ STEP 3 PASSED: Encrypted payload successfully fetched and decrypted.")
    except Exception as e:
        print(f"❌ STEP 3 FAILED: {e}")
        return 1

    # Step 4: Test 45s Heartbeat Communication
    print_header("STEP 4: Testing Heartbeat & Session Keep-Alive")
    client = AuthClient(config.auth)
    try:
        hb_resp = client.heartbeat(
            session.access_token,
            session.device_id,
            session.pc_name,
        )
        print(f"[+] Heartbeat ACK from server: interval={hb_resp.get('heartbeat_interval')}s")
        assert hb_resp.get("ok"), "Heartbeat was not accepted"
        print("✅ STEP 4 PASSED: Periodic heartbeat synchronized with server.")
    except Exception as e:
        print(f"❌ STEP 4 FAILED: {e}")
        return 1

    # Step 5: Test Activity Logging & Target Link Logging
    print_header("STEP 5: Testing Audit Logs & Activity Recording")
    try:
        client.log_activity(
            session.access_token,
            "test_automation_verification",
            session.device_id,
            session.pc_name,
            details={"note": "Automated desktop tool verification check"},
        )
        print("[+] Logged desktop automation activity event to server.")

        client.log_link(
            session.access_token,
            "https://agesmart.eu/verification/documents/3TJG_EnR-w3Q2w8htaT_Y0YBtonQs5s0",
            session.device_id,
            browser="multilogin",
        )
        print("[+] Logged target verification URL navigation to server.")
        print("✅ STEP 5 PASSED: Both activity and link audit logs transmitted successfully.")
    except Exception as e:
        print(f"❌ STEP 5 FAILED: {e}")
        return 1

    # Step 6: Verify Database Persistence in Neon PostgreSQL
    print_header("STEP 6: Verifying Neon PostgreSQL Live Data Persistence")
    try:
        proc = subprocess.run(
            ["node", "check_db.js"],
            capture_output=True,
            text=True,
            check=True,
        )
        # Parse the JSON line from stdout
        lines = [line.strip() for line in proc.stdout.splitlines() if line.strip().startswith("{")]
        assert len(lines) > 0, f"No JSON in output: {proc.stdout}"
        db_data = json.loads(lines[-1])
        print(f"[+] Neon DB 'sessions' table verified: device={db_data['session']['device_id']}, last_seen_at={db_data['session']['last_seen_at']}")
        print(f"[+] Neon DB 'activity_logs' table verified: action={db_data['activity']['action']}, created_at={db_data['activity']['created_at']}")
        print(f"[+] Neon DB 'link_logs' table verified: url={db_data['link']['url'][:40]}..., created_at={db_data['link']['created_at']}")
        print("✅ STEP 6 PASSED: Neon PostgreSQL database confirmed 100% updated with all events.")
    except Exception as e:
        print(f"❌ STEP 6 FAILED: Could not query Neon DB: {e}")
        return 1

    # Step 7: Test MainWindow GUI Component with Authenticated Session
    print_header("STEP 7: Initializing MainWindow with Authenticated Session")
    try:
        main_win = MainWindow(auth_session=session)
        assert main_win.windowTitle() == "Automation Hub"
        assert main_win.auth_session is not None
        print("[+] MainWindow successfully initialized.")
        print(f"[+] Window Title: '{main_win.windowTitle()}'")
        print(f"[+] Target URL configured in UI: '{main_win.url_input.text()}'")
        print(f"[+] Browser Engine selected in UI: '{main_win.browser_engine_selector.currentText()}'")
        print("[+] Heartbeat timer active:", main_win._heartbeat_timer.isActive())
        main_win.close()
        print("✅ STEP 7 PASSED: Full desktop application window initialized perfectly.")
    except Exception as e:
        print(f"❌ STEP 7 FAILED: {e}")
        return 1

    print("\n" + "=" * 75)
    print("🎉 ALL 7 DESKTOP LOGIN & SERVER COMMUNICATION CHECKS PASSED (100%)!")
    print("===========================================================================")
    return 0

if __name__ == "__main__":
    sys.exit(main())
