import requests
import json
import sys

# Ensure UTF-8 output on Windows console
sys.stdout.reconfigure(encoding='utf-8')

BASE = "http://localhost:3000"

def test_admin():
    print("=" * 60)
    print("TESTING ADMIN DASHBOARD APIS & LIVE LINK RETRIEVAL")
    print("=" * 60)

    session = requests.Session()

    # 1. Admin login
    print("\n[Admin Test 1] Logging into admin console...")
    res = session.post(f"{BASE}/api/admin/login", json={"username": "superadmin", "password": "Admin@12345"})
    assert res.status_code == 200, f"Admin login failed: {res.text}"
    login_data = res.json()
    token = login_data.get("token")
    assert token, "Token missing in login response"
    session.headers["Authorization"] = f"Bearer {token}"
    print("  PASS: Admin login successful, token & session obtained.")

    # 2. Get stats
    print("\n[Admin Test 2] Fetching dashboard metrics...")
    stats_res = session.get(f"{BASE}/api/admin/stats")
    assert stats_res.status_code == 200, f"Stats failed: {stats_res.text}"
    stats_data = stats_res.json()
    print("  Stats:", json.dumps(stats_data.get("stats"), indent=2))
    assert stats_data.get("ok") is True
    print("  PASS: Dashboard metrics retrieved.")

    # 3. Check link logs
    print("\n[Admin Test 3] Checking link logs in admin panel...")
    links_res = session.get(f"{BASE}/api/admin/link-logs")
    assert links_res.status_code == 200, f"Links failed: {links_res.text}"
    links_data = links_res.json()
    print(f"  Total links in log: {links_data.get('total')}")
    assert links_data.get("total", 0) > 0, "Expected logged links to be retrieved"
    first_link = links_data["logs"][0]
    print(f"  Latest logged URL: {first_link['url']}")
    print(f"  Logged by User: {first_link['username']} via browser {first_link['browser']}")
    assert "sample_test_link_12345" in first_link['url']
    print("  PASS: Verified that desktop app input link is recorded and managed in admin panel!")

    # 4. Check users
    print("\n[Admin Test 4] Checking users list...")
    users_res = session.get(f"{BASE}/api/admin/users")
    assert users_res.status_code == 200, f"Users failed: {users_res.text}"
    users_data = users_res.json()
    print(f"  Users count: {len(users_data.get('users', []))}")
    print("  PASS: Users list retrieved.")

    # 5. Check sessions
    print("\n[Admin Test 5] Checking active sessions...")
    sess_res = session.get(f"{BASE}/api/admin/sessions")
    assert sess_res.status_code == 200, f"Sessions failed: {sess_res.text}"
    print("  PASS: Sessions retrieved.")

    # 6. Check devices
    print("\n[Admin Test 6] Checking devices...")
    dev_res = session.get(f"{BASE}/api/admin/devices")
    assert dev_res.status_code == 200, f"Devices failed: {dev_res.text}"
    print("  PASS: Devices retrieved.")

    # 7. Check settings
    print("\n[Admin Test 7] Checking settings...")
    sett_res = session.get(f"{BASE}/api/admin/settings")
    assert sett_res.status_code == 200, f"Settings failed: {sett_res.text}"
    print("  Settings:", sett_res.json().get("settings"))
    print("  PASS: Settings retrieved.")

    print("\n" + "=" * 60)
    print("ALL ADMIN PANEL APIS PASSED WITH 100% SUCCESS!")
    print("=" * 60)

if __name__ == "__main__":
    test_admin()
