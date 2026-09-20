const fs = require('fs');
const path = require('path');
const { Client } = require('pg');

// Simple .env parser if dotenv is not installed
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
  const dbUrl =
    process.env.DATABASE_URL ||
    process.env.POSTGRES_URL ||
    'postgresql://neondb_owner:npg_GHlkmV5Ii9tC@ep-lingering-credit-avo41viw-pooler.c-11.us-east-1.aws.neon.tech/neondb?channel_binding=require&sslmode=require';

  console.log('🔄 Connecting to Neon PostgreSQL...');


  const client = new Client({
    connectionString: dbUrl,
    ssl: { rejectUnauthorized: false }
  });

  try {
    await client.connect();
    console.log('✅ Connected successfully.');

    const schemaPath = path.join(__dirname, '..', 'schema.sql');
    const sql = fs.readFileSync(schemaPath, 'utf-8');

    console.log('🔄 Executing schema.sql...');
    await client.query(sql);
    console.log('\n🎉 Database initialized successfully!');
    console.log('Default super admin created:');
    console.log('  Username: superadmin');
    console.log('  Password: Admin@12345\n');
  } catch (err) {
    console.error('❌ Failed to initialize database:', err);
    process.exit(1);
  } finally {
    await client.end();
  }
}

main();
