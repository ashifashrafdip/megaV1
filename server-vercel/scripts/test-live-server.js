const https = require('https');

const BASE_URL = 'https://mega-v1-server.vercel.app';

function request(path, options = {}) {
  return new Promise((resolve, reject) => {
    const url = new URL(path, BASE_URL);
    const reqOptions = {
      method: options.method || 'GET',
      headers: options.headers || {},
    };

    const req = https.request(url, reqOptions, (res) => {
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

async function runLiveTests() {
  console.log('=====================================================');
  console.log(`🚀 Testing Live Server at: ${BASE_URL}`);
  console.log('=====================================================\n');

  let adminCookie = '';

  // 1. Admin Login API
  try {
    const res = await request('/api/admin/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: { username: 'superadmin', password: 'Admin@12345' },
    });
    console.log(`1. POST /api/admin/login: Status ${res.status}`);
    if (res.status === 200 && res.data.ok) {
      console.log('   ✅ Admin Login SUCCESS:', res.data.user.username, `(${res.data.user.role})`);
      if (res.headers['set-cookie']) {
        adminCookie = res.headers['set-cookie'][0].split(';')[0];
      }
    } else {
      console.log('   ❌ Failed:', res.data);
    }
  } catch (err) {
    console.log('   ❌ Error:', err.message);
  }

  // 2. Admin Stats (with Cookie)
  try {
    const res = await request('/api/admin/stats', {
      headers: { Cookie: adminCookie },
    });
    console.log(`\n2. GET /api/admin/stats: Status ${res.status}`);
    if (res.status === 200 && res.data.ok) {
      console.log('   ✅ Admin Stats SUCCESS: Total Users =', res.data.stats?.total_users ?? JSON.stringify(res.data));
    } else {
      console.log('   ❌ Failed:', res.data);
    }
  } catch (err) {
    console.log('   ❌ Error:', err.message);
  }

  // 3. Admin Users List
  try {
    const res = await request('/api/admin/users', {
      headers: { Cookie: adminCookie },
    });
    console.log(`\n3. GET /api/admin/users: Status ${res.status}`);
    if (res.status === 200 && res.data.ok) {
      console.log(`   ✅ Admin Users SUCCESS: Retrieved ${res.data.users?.length || 0} user(s)`);
    } else {
      console.log('   ❌ Failed:', res.data);
    }
  } catch (err) {
    console.log('   ❌ Error:', err.message);
  }

  // 3.5. Revoke existing active sessions for user 1 to allow fresh client test
  try {
    const res = await request('/api/admin/sessions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Cookie: adminCookie,
      },
      body: { user_id: 1 },
    });
    console.log(`\n3.5 POST /api/admin/sessions (Revoke Previous Sessions): Status ${res.status}`);
    if (res.status === 200) {
      console.log('   ✅ Previous test sessions successfully cleared for fresh login');
    }
  } catch (err) {
    console.log('   ❌ Error:', err.message);
  }

  // 4. Desktop Client Login (/api/login)
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
        device_id: 'live-test-device-123',
        pc_name: 'LIVE-TEST-PC',
      },
    });
    console.log(`\n4. POST /api/login (Desktop Client): Status ${res.status}`);
    if (res.status === 200 && res.data.ok) {
      console.log('   ✅ Desktop Client Login SUCCESS:', res.data.user?.username);
      clientToken = res.data.access_token;
    } else {
      console.log('   ❌ Failed:', res.data);
    }
  } catch (err) {
    console.log('   ❌ Error:', err.message);
  }

  // 5. Desktop Client Heartbeat (/api/heartbeat)
  try {
    const res = await request('/api/heartbeat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-app-key': 'dev-desktop-app-key-change-me',
        Authorization: `Bearer ${clientToken}`,
      },
      body: {
        device_id: 'live-test-device-123',
        status: 'active',
      },
    });
    console.log(`\n5. POST /api/heartbeat: Status ${res.status}`);
    if (res.status === 200 && res.data.ok) {
      console.log('   ✅ Heartbeat SUCCESS:', res.data.message || 'Heartbeat acknowledged');
    } else {
      console.log('   ❌ Failed:', res.data);
    }
  } catch (err) {
    console.log('   ❌ Error:', err.message);
  }

  // 6. Desktop Client Payload (/api/payload)
  try {
    const res = await request('/api/payload', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-app-key': 'dev-desktop-app-key-change-me',
        Authorization: `Bearer ${clientToken}`,
      },
      body: {
        device_id: 'live-test-device-123',
      },
    });
    console.log(`\n6. POST /api/payload: Status ${res.status}`);
    if (res.status === 200 && res.data.ok) {
      console.log('   ✅ Secure Payload SUCCESS: Encrypted config received (keys:', Object.keys(res.data).join(', '), ')');
    } else {
      console.log('   ❌ Failed:', res.data);
    }
  } catch (err) {
    console.log('   ❌ Error:', err.message);
  }

  // 7. Desktop Client Link Log (/api/link_log)
  try {
    const res = await request('/api/link_log', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-app-key': 'dev-desktop-app-key-change-me',
        Authorization: `Bearer ${clientToken}`,
      },
      body: {
        url: 'https://example.com/test-live',
        browser: 'chrome',
        device_id: 'live-test-device-123',
      },
    });
    console.log(`\n7. POST /api/link_log: Status ${res.status}`);
    if (res.status === 200 && res.data.ok) {
      console.log('   ✅ Link Log SUCCESS:', res.data.message || 'Logged');
    } else {
      console.log('   ❌ Failed:', res.data);
    }
  } catch (err) {
    console.log('   ❌ Error:', err.message);
  }

  // 8. Test Admin Login UI Page
  try {
    const res = await request('/admin/login');
    console.log(`\n8. GET /admin/login (UI): Status ${res.status}`);
    if (res.status === 200) {
      console.log('   ✅ Admin Login Page renders directly (200 OK)');
    } else if (res.status === 307 || res.status === 308) {
      console.log(`   ⚠️ Redirect detected: ${res.status} -> Location: ${res.headers.location}`);
    } else {
      console.log('   Status:', res.status);
    }
  } catch (err) {
    console.log('   ❌ Error:', err.message);
  }

  console.log('\n=====================================================');
}

runLiveTests();
