const http = require('http');

const BASE_URL = 'http://localhost:3010';

function request(path, options = {}) {
  return new Promise((resolve, reject) => {
    const url = new URL(path, BASE_URL);
    const reqOptions = {
      method: options.method || 'GET',
      headers: options.headers || {},
    };

    const req = http.request(url, reqOptions, (res) => {
      let data = '';
      res.on('data', chunk => (data += chunk));
      res.on('end', () => {
        let json = null;
        try {
          json = JSON.parse(data);
        } catch (_) {}
        resolve({
          status: res.statusCode,
          headers: res.headers,
          data: json || data,
        });
      });
    });

    req.on('error', reject);

    if (options.body) {
      req.write(typeof options.body === 'string' ? options.body : JSON.stringify(options.body));
    }
    req.end();
  });
}

async function run() {
  console.log('========================================================');
  console.log('🚀 Comprehensive Server & Neon DB Full System Health Check');
  console.log('========================================================\n');

  let passed = 0;
  let total = 0;

  function assert(condition, message, detail = '') {
    total++;
    if (condition) {
      passed++;
      console.log(`✅ [PASS] ${message}${detail ? ' -> ' + detail : ''}`);
    } else {
      console.error(`❌ [FAIL] ${message}${detail ? ' -> ' + detail : ''}`);
    }
  }

  // 1. Admin Login Page UI
  try {
    const res = await request('/admin/login');
    assert(res.status === 200, 'GET /admin/login (Admin UI Login Page)', `HTTP ${res.status}`);
  } catch (e) {
    assert(false, 'GET /admin/login', e.message);
  }

  // 2. Admin Login API
  let adminCookie = '';
  try {
    const res = await request('/api/admin/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: { username: 'superadmin', password: 'Admin@12345' },
    });
    const ok = res.status === 200 && res.data.ok === true;
    assert(ok, 'POST /api/admin/login (Superadmin Authentication)', `User: ${res.data.user?.username} (${res.data.user?.role})`);
    if (res.headers['set-cookie']) {
      adminCookie = res.headers['set-cookie'][0].split(';')[0];
    }
  } catch (e) {
    assert(false, 'POST /api/admin/login', e.message);
  }

  // 3. Admin Dashboard Analytics
  try {
    const res = await request('/api/admin/stats', {
      headers: { Cookie: adminCookie },
    });
    const ok = res.status === 200 && res.data.ok === true;
    assert(ok, 'GET /api/admin/stats (Dashboard Analytics)', `Total users: ${res.data.stats?.total_users}`);
  } catch (e) {
    assert(false, 'GET /api/admin/stats', e.message);
  }

  // 4. Admin Users Management
  try {
    const res = await request('/api/admin/users', {
      headers: { Cookie: adminCookie },
    });
    const ok = res.status === 200 && res.data.ok === true;
    assert(ok, 'GET /api/admin/users (Users List Query)', `${res.data.users?.length} user(s) returned`);
  } catch (e) {
    assert(false, 'GET /api/admin/users', e.message);
  }

  // Clear any existing active sessions for user 1 before client login test
  try {
    await request('/api/admin/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Cookie: adminCookie },
      body: { user_id: 1 },
    });
  } catch (_) {}

  // 5. Desktop Client Login
  let clientToken = '';
  try {
    const res = await request('/api/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-app-key': 'dev-desktop-app-key-change-me',
      },
      body: {
        username: 'superadmin',
        password: 'Admin@12345',
        device_id: 'test-device-uuid-999',
        pc_name: 'TEST-WORKSTATION',
      },
    });
    const ok = res.status === 200 && res.data.ok === true && !!res.data.access_token;
    assert(ok, 'POST /api/login (Desktop Client Login & JWT Generation)', `Heartbeat Interval: ${res.data.heartbeat_interval}s`);
    clientToken = res.data.access_token;
  } catch (e) {
    assert(false, 'POST /api/login', e.message);
  }

  // 6. License Validation
  try {
    const res = await request('/api/validate_license', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-app-key': 'dev-desktop-app-key-change-me',
        Authorization: `Bearer ${clientToken}`,
      },
    });
    const ok = res.status === 200 && res.data.ok === true && res.data.valid === true;
    assert(ok, 'POST /api/validate_license (License Enforcement)', `License Status: ${res.data.license?.status}`);
  } catch (e) {
    assert(false, 'POST /api/validate_license', e.message);
  }

  // 7. Client Heartbeat
  try {
    const res = await request('/api/heartbeat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-app-key': 'dev-desktop-app-key-change-me',
        Authorization: `Bearer ${clientToken}`,
      },
      body: {
        device_id: 'test-device-uuid-999',
        status: 'active',
      },
    });
    const ok = res.status === 200 && res.data.ok === true;
    assert(ok, 'POST /api/heartbeat (Active Session Heartbeat)', res.data.message || 'Acknowledged');
  } catch (e) {
    assert(false, 'POST /api/heartbeat', e.message);
  }

  // 8. Secure Dynamic Payload Delivery
  try {
    const res = await request('/api/payload', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-app-key': 'dev-desktop-app-key-change-me',
        Authorization: `Bearer ${clientToken}`,
      },
      body: {
        device_id: 'test-device-uuid-999',
      },
    });
    const ok = res.status === 200 && res.data.ok === true && !!res.data.payload;
    assert(ok, 'POST /api/payload (Encrypted Payload & Target Link Delivery)', `Payload Length: ${res.data.payload?.length || 0} chars`);
  } catch (e) {
    assert(false, 'POST /api/payload', e.message);
  }

  // 9. Target Link Audit Logging
  try {
    const res = await request('/api/link_log', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-app-key': 'dev-desktop-app-key-change-me',
        Authorization: `Bearer ${clientToken}`,
      },
      body: {
        url: 'https://agesmart.eu/verification/documents/test',
        browser: 'multilogin',
        device_id: 'test-device-uuid-999',
      },
    });
    const ok = res.status === 200 && res.data.ok === true;
    assert(ok, 'POST /api/link_log (Link Audit Trail Logging)', res.data.message || 'Logged');
  } catch (e) {
    assert(false, 'POST /api/link_log', e.message);
  }

  // 10. Client Activity Log
  try {
    const res = await request('/api/activity_log', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-app-key': 'dev-desktop-app-key-change-me',
        Authorization: `Bearer ${clientToken}`,
      },
      body: {
        action: 'camera_capture_complete',
        device_id: 'test-device-uuid-999',
        pc_name: 'TEST-WORKSTATION',
        details: JSON.stringify({ duration_ms: 12500, frames: 35 }),
      },
    });
    const ok = res.status === 200 && res.data.ok === true;
    assert(ok, 'POST /api/activity_log (Device Event Activity Logging)', res.data.message || 'Logged');
  } catch (e) {
    assert(false, 'POST /api/activity_log', e.message);
  }

  // Cleanup session
  try {
    await request('/api/logout', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-app-key': 'dev-desktop-app-key-change-me',
        Authorization: `Bearer ${clientToken}`,
      },
    });
  } catch (_) {}

  console.log('\n========================================================');
  console.log(`🏁 TEST SUMMARY: ${passed}/${total} TESTS PASSED (${((passed / total) * 100).toFixed(0)}%)`);
  console.log('========================================================');

  process.exit(passed === total ? 0 : 1);
}

run();
