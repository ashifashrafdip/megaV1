import { NextRequest } from 'next/server';
import fs from 'fs';
import path from 'path';
import { query } from '@/lib/db';
import { jsonError, jsonOk } from '@/lib/helpers';

export async function GET(req: NextRequest) {
  const secret = req.nextUrl.searchParams.get('secret');
  const expectedSecret = process.env.SETUP_SECRET || process.env.APP_API_KEY || 'dev-desktop-app-key-change-me';

  if (secret !== expectedSecret) {
    return jsonError('forbidden', 'Invalid setup secret. Provide ?secret=YOUR_APP_API_KEY', 403);
  }

  try {
    const schemaPath = path.join(process.cwd(), 'schema.sql');
    let sql = '';
    if (fs.existsSync(schemaPath)) {
      sql = fs.readFileSync(schemaPath, 'utf-8');
    } else {
      return jsonError('not_found', 'schema.sql file not found on server', 500);
    }

    // Split and execute statements or run full sql
    await query(sql);

    return jsonOk({
      message: 'Database schema initialized successfully on Neon PostgreSQL!',
      default_admin: {
        username: 'superadmin',
        password: 'Admin@12345',
        note: 'Please change password immediately after first login.',
      },
    });
  } catch (err: any) {
    console.error('Setup error:', err);
    return jsonError('setup_failed', err.message || 'Failed to initialize schema', 500);
  }
}
