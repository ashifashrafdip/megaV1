import { NextRequest } from 'next/server';
import { query } from '@/lib/db';
import { jsonError, jsonOk, verifyAppKey, logActivity, getClientIp } from '@/lib/helpers';
import { verifyBearerToken, revokeAllUserSessions } from '@/lib/auth';

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

  const targetUserId = body.user_id ? parseInt(body.user_id, 10) : 0;
  if (!targetUserId) {
    return jsonError('invalid', 'user_id required');
  }

  const ip = getClientIp(req);

  await query("UPDATE users SET status = 'banned', updated_at = NOW() WHERE id = $1", [targetUserId]);
  await revokeAllUserSessions(targetUserId);
  await logActivity(user.id, 'ban_user', null, null, `user_id=${targetUserId}`, ip);

  return jsonOk({ success: true, message: 'User banned' });
}
