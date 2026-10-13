const { Pool } = require('../node_modules/pg');

const pool = new Pool({
  connectionString: 'postgresql://neondb_owner:npg_GHlkmV5Ii9tC@ep-lingering-credit-avo41viw-pooler.c-11.us-east-1.aws.neon.tech/neondb?sslmode=require',
});

async function main() {
  try {
    // 1. Set single_session to '0' so multiple devices / other PCs can log in and work
    const res = await pool.query(
      "UPDATE settings SET setting_value = '0', updated_at = NOW() WHERE setting_key = 'single_session'"
    );
    console.log('[+] Updated single_session to 0. Row count:', res.rowCount);

    // 2. Clear any lingering active session locks
    const sessRes = await pool.query(
      "UPDATE sessions SET is_active = 0 WHERE is_active = 1"
    );
    console.log('[+] Reset lingering active sessions. Row count:', sessRes.rowCount);

    // 3. Ensure all devices are authorized
    const devRes = await pool.query(
      "UPDATE devices SET is_authorized = 1 WHERE is_authorized = 0"
    );
    console.log('[+] Authorized any previously blocked devices. Row count:', devRes.rowCount);

    // 4. Verify settings
    const checkRes = await pool.query("SELECT setting_key, setting_value FROM settings");
    console.log('[+] Current settings:', checkRes.rows);

  } catch (err) {
    console.error('[-] Error configuring database:', err);
  } finally {
    await pool.end();
  }
}

main();
