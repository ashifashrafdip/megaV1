const fs = require('fs');
const path = require('path');
const mysql = require('mysql2/promise');

function loadEnv() {
  const envPath = path.join(__dirname, '..', '.env');
  if (fs.existsSync(envPath)) {
    const lines = fs.readFileSync(envPath, 'utf-8').split('\n');
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('#')) continue;
      const idx = trimmed.indexOf('=');
      if (idx !== -1) {
        const key = trimmed.slice(0, idx).trim();
        let val = trimmed.slice(idx + 1).trim();
        if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
          val = val.slice(1, -1);
        }
        if (!process.env[key]) {
          process.env[key] = val;
        }
      }
    }
  }
}

async function main() {
  loadEnv();
  const host = process.env.DB_HOST || 'localhost';
  const user = process.env.DB_USER || 'ashifash_auth';
  const password = process.env.DB_PASSWORD || 'AuthDbPass@2026!#Mega';
  const database = process.env.DB_NAME || 'ashifash_auth';
  const port = parseInt(process.env.DB_PORT || '3306', 10);

  console.log(`🔄 Connecting to MySQL (${user}@${host}:${port}/${database})...`);

  try {
    const conn = await mysql.createConnection({
      host,
      user,
      password,
      database,
      port,
      multipleStatements: true
    });
    console.log('✅ Connected successfully to MySQL.');

    const schemaPath = path.join(__dirname, '..', 'schema.sql');
    const sql = fs.readFileSync(schemaPath, 'utf-8');

    console.log('🔄 Executing MySQL schema.sql...');
    await conn.query(sql);
    console.log('\n🎉 MySQL Database initialized successfully!');
    console.log('Default super admin created/updated:');
    console.log('  Username: superadmin');
    console.log('  Password: Admin@12345\n');
    await conn.end();
  } catch (err) {
    console.error('❌ Failed to initialize MySQL database:', err);
    process.exit(1);
  }
}

main();
