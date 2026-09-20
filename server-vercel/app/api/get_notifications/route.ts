import { NextRequest } from 'next/server';
import { query } from '@/lib/db';
import { jsonError, jsonOk, verifyAppKey } from '@/lib/helpers';
import { verifyBearerToken } from '@/lib/auth';

export async function GET(req: NextRequest) {
  if (!verifyAppKey(req)) {
    return jsonError('invalid_api_key', 'Invalid application API key', 401);
  }

  const user = await verifyBearerToken(req);
  if (!user) {
    return jsonError('unauthorized', 'Authentication required', 401);
  }

  const res = await query(
    'SELECT id, title, message, is_read, created_at FROM notifications WHERE user_id = $1 OR user_id IS NULL ORDER BY id DESC LIMIT 50',
    [user.id]
  );

  return jsonOk({ notifications: res.rows });
}
