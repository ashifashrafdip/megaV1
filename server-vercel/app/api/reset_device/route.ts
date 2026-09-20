import { NextRequest } from 'next/server';
import { query } from '@/lib/db';
import { jsonError, jsonOk, verifyAppKey } from '@/lib/helpers';
import { verifyBearerToken } from '@/lib/auth';

export async function POST(req: NextRequest) {
  if (!verifyAppKey(req)) {
    return jsonError('invalid_api_key', 'Invalid application API key', 401);
  }

  const user = await verifyBearerToken(req);
  if (!user || (user.role_name !== 'super_admin' && user.role_name !== 'admin')) {
    return jsonError('forbidden', 'Admin access required', 403);
  }

  let body: any = {};
  try {
    body = await req.json();
  } catch {
    body = {};
  }

  const deviceRowId = body.device_row_id ? parseInt(body.device_row_id, 10) : 0;
  const action = String(body.action || 'authorize').trim();

  if (!deviceRowId) {
    return jsonError('invalid', 'device_row_id required');
  }

  const isAuth = action === 'revoke' ? 0 : 1;
  await query('UPDATE devices SET is_authorized = $1, last_seen_at = CURRENT_TIMESTAMP WHERE id = $2', [
    isAuth,
    deviceRowId,
  ]);

  return jsonOk({ success: true, is_authorized: isAuth === 1 });
}
