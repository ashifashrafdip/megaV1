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

  const res = await query<{
    user_id: number;
    username: string;
    pc_name: string | null;
    device_id: string | null;
    last_seen_at: string;
  }>(
    `SELECT s.user_id, u.username, s.pc_name, s.device_id, s.last_seen_at
     FROM sessions s
     JOIN users u ON u.id = s.user_id
     WHERE s.is_active = 1 AND s.last_seen_at > NOW() - INTERVAL '3 minutes'
     ORDER BY s.last_seen_at DESC`
  );

  return jsonOk({ users: res.rows, count: res.rows.length });
}
