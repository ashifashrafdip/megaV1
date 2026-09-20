const { Client } = require('pg');

const DATABASE_URL =
  process.env.DATABASE_URL ||
  'postgresql://neondb_owner:npg_GHlkmV5Ii9tC@ep-lingering-credit-avo41viw-pooler.c-11.us-east-1.aws.neon.tech/neondb?channel_binding=require&sslmode=require';

async function run() {
  const client = new Client({
    connectionString: DATABASE_URL,
    ssl: { rejectUnauthorized: false }
  });

  await client.connect();
  console.log('Connected to database.');

  // Clean up any test users created during diagnosis
  await client.query("DELETE FROM users WHERE username IN ('testuser_1789939775899', 'admin')");
  console.log('Cleaned up diagnostic test accounts.');

  // Synchronize all SERIAL sequences with current MAX(id)
  await client.query(`
    SELECT setval('users_id_seq', GREATEST((SELECT COALESCE(MAX(id), 1) FROM users), 1));
    SELECT setval('roles_id_seq', GREATEST((SELECT COALESCE(MAX(id), 1) FROM roles), 3));
    SELECT setval('licenses_id_seq', GREATEST((SELECT COALESCE(MAX(id), 1) FROM licenses), 1));
    SELECT setval('devices_id_seq', GREATEST((SELECT COALESCE(MAX(id), 1) FROM devices), 1));
    SELECT setval('settings_id_seq', GREATEST((SELECT COALESCE(MAX(id), 1) FROM settings), 1));
  `);
  console.log('Synchronized all database sequences.');

  const users = await client.query('SELECT id, username, role_id FROM users ORDER BY id');
  console.log('Active users in DB:', users.rows);

  const seq = await client.query("SELECT currval('users_id_seq') as seq");
  console.log('users_id_seq current val:', seq.rows[0].seq);

  await client.end();
}

run().catch(err => {
  console.error('Error:', err);
  process.exit(1);
});
