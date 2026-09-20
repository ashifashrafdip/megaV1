const { Client } = require('pg');

const DATABASE_URL =
  process.env.DATABASE_URL ||
  'postgresql://neondb_owner:npg_Y3hiK4JNXqsx@ep-quiet-darkness-auh729zw-pooler.c-10.us-east-1.aws.neon.tech/neondb?channel_binding=require&sslmode=require';

async function verifyDatabase() {
  console.log('====================================================');
  console.log('🔍 Neon PostgreSQL Connection Diagnostic Check');
  console.log('====================================================');
  console.log(`Endpoint: ep-quiet-darkness-auh729zw-pooler.c-10.us-east-1.aws.neon.tech`);
  console.log(`Database: neondb`);
  console.log('Connecting to Neon PostgreSQL...');

  const client = new Client({
    connectionString: DATABASE_URL,
    ssl: { rejectUnauthorized: false }
  });

  const startTime = Date.now();
  await client.connect();
  const latency = Date.now() - startTime;
  console.log(`✅ Connection SUCCESSFUL (Latency: ${latency}ms)`);

  // 1. Version Check
  const verRes = await client.query('SELECT version()');
  console.log(`\n📌 PostgreSQL Version: ${verRes.rows[0].version.split(',')[0]}`);

  // 2. Public Tables Check
  const tablesRes = await client.query(`
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    ORDER BY table_name;
  `);
  console.log(`\n📋 Public Tables Verified (${tablesRes.rows.length} tables):`);
  for (const row of tablesRes.rows) {
    const countRes = await client.query(`SELECT COUNT(*) as count FROM "${row.table_name}"`);
    console.log(`   - ${row.table_name.padEnd(20)} : ${countRes.rows[0].count} rows`);
  }

  // 3. Superadmin Account Check
  console.log('\n👤 Superadmin Account Verification:');
  const userRes = await client.query(`
    SELECT u.id, u.username, u.email, r.name as role_name, r.label as role_label, u.status, u.created_at,
           l.id as license_id, l.status as license_status, l.expires_at
    FROM users u
    JOIN roles r ON r.id = u.role_id
    LEFT JOIN licenses l ON l.user_id = u.id
    WHERE u.username = 'superadmin';
  `);
  if (userRes.rows.length > 0) {
    const admin = userRes.rows[0];
    console.log(`   - User ID:        ${admin.id}`);
    console.log(`   - Username:       ${admin.username}`);
    console.log(`   - Role:           ${admin.role_name} (${admin.role_label})`);
    console.log(`   - Status:         ${admin.status}`);
    console.log(`   - License Status: ${admin.license_status}`);
    console.log(`   - License Expiry: ${admin.expires_at}`);
  } else {
    console.log('   ⚠️ Superadmin not found!');
  }

  // 4. Settings Check
  console.log('\n⚙️ Default System Settings:');
  const settingsRes = await client.query('SELECT setting_key, setting_value FROM settings');
  for (const row of settingsRes.rows) {
    console.log(`   - ${row.setting_key.padEnd(25)} = ${row.setting_value}`);
  }

  // 5. Read/Write/Delete Test
  console.log('\n🧪 Testing Read/Write/Delete Operations:');
  const testPayload = JSON.stringify({ ping: 'pong', timestamp: Date.now() });
  const insertRes = await client.query(
    `INSERT INTO activity_logs (user_id, action, details) VALUES ($1, $2, $3) RETURNING id`,
    [1, 'DIAGNOSTIC_HEALTH_CHECK', testPayload]
  );
  const newId = insertRes.rows[0].id;
  console.log(`   - INSERT into activity_logs: SUCCESS (Created ID: ${newId})`);

  const selectRes = await client.query(
    `SELECT id, action, details FROM activity_logs WHERE id = $1`,
    [newId]
  );
  console.log(`   - SELECT verified: SUCCESS (Action: "${selectRes.rows[0].action}")`);

  await client.query(`DELETE FROM activity_logs WHERE id = $1`, [newId]);
  console.log(`   - DELETE cleanup: SUCCESS (Cleaned up temporary diagnostic row)`);

  await client.end();
  console.log('\n====================================================');
  console.log('🎉 ALL DATABASE CHECKS PASSED WITH 100% SUCCESS!');
  console.log('====================================================');
}

verifyDatabase().catch(err => {
  console.error('❌ Connection Failed:', err.message);
  process.exit(1);
});
