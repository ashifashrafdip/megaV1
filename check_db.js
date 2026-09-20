const { Pool } = require('./server-vercel/node_modules/pg');

async function check() {
    const pool = new Pool({
        connectionString: 'postgresql://neondb_owner:npg_GHlkmV5Ii9tC@ep-lingering-credit-avo41viw-pooler.c-11.us-east-1.aws.neon.tech/neondb?sslmode=require',
    });
    try {
        const sessRes = await pool.query('SELECT id, user_id, device_id, pc_name, last_seen_at FROM sessions ORDER BY id DESC LIMIT 1');
        const actRes = await pool.query('SELECT action, device_id, created_at FROM activity_logs ORDER BY id DESC LIMIT 1');
        const linkRes = await pool.query('SELECT url, browser, created_at FROM link_logs ORDER BY id DESC LIMIT 1');

        console.log(JSON.stringify({
            session: sessRes.rows[0] || null,
            activity: actRes.rows[0] || null,
            link: linkRes.rows[0] || null,
        }));
    } finally {
        await pool.end();
    }
}

check().catch(err => {
    console.error('Check failed:', err);
    process.exit(1);
});
