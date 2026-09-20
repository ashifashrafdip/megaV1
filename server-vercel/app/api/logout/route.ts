import { NextRequest } from 'next/server';
import { query } from '@/lib/db';
import { jsonError, jsonOk, verifyAppKey, logActivity, getClientIp } from '@/lib/helpers';
import { verifyBearerToken } from '@/lib/auth';

export async function POST(req: NextRequest) {
  if (!verifyAppKey(req)) {
    return jsonError('invalid_api_key', 'Invalid application API key', 401);
  }

  const user = await verifyBearerToken(req);
  if (!user) {
    return jsonOk({ logged_out: true });
  }

  let body: any = {};
  try {
    body = await req.json();
  } catch {
    body = {};
  }

  const deviceId = String(body.device_id || '').trim() || null;
  const ip = getClientIp(req);

  if (user.session_id) {
    await query('UPDATE sessions SET is_active = 0 WHERE id = $1', [user.session_id]);
  }

  await logActivity(user.id, 'logout', deviceId, null, null, ip);

  return jsonOk({ logged_out: true });
}
