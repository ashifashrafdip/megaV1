import { NextRequest } from 'next/server';
import { query } from '@/lib/db';
import { jsonError, jsonOk, verifyAppKey, logActivity, getClientIp } from '@/lib/helpers';
import { verifyBearerToken, revokeSession, revokeAllUserSessions } from '@/lib/auth';

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

  const sessionId = body.session_id ? parseInt(body.session_id, 10) : 0;
  const targetUserId = body.user_id ? parseInt(body.user_id, 10) : 0;
  const ip = getClientIp(req);

  if (sessionId > 0) {
    await revokeSession(sessionId);
    await logActivity(user.id, 'force_logout', null, null, `session_id=${sessionId}`, ip);
    return jsonOk({ success: true, message: 'Session terminated' });
  }

  if (targetUserId > 0) {
    await revokeAllUserSessions(targetUserId);
    await logActivity(user.id, 'force_logout', null, null, `user_id=${targetUserId}`, ip);
    return jsonOk({ success: true, message: 'All user sessions terminated' });
  }

  return jsonError('invalid', 'session_id or user_id required');
}
