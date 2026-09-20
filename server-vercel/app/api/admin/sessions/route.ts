import { NextRequest } from 'next/server';
import { query } from '@/lib/db';
import { jsonError, jsonOk, logActivity, getClientIp } from '@/lib/helpers';
import { revokeSession, revokeAllUserSessions } from '@/lib/auth';
import { getAdminSession } from '@/lib/admin-auth';

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const admin = await getAdminSession();
    if (!admin) {
      return jsonError('unauthorized', 'Unauthorized', 401);
    }

    const res = await query(
      `SELECT s.id, s.user_id, s.device_id, s.pc_name, s.ip_address, s.last_seen_at, s.expires_at,
              u.username, u.status AS user_status
       FROM sessions s
       JOIN users u ON u.id = s.user_id
       WHERE s.is_active = 1
       ORDER BY s.last_seen_at DESC`
    );

    return jsonOk({ sessions: res.rows });
  } catch (err: any) {
    if (err?.digest === 'DYNAMIC_SERVER_USAGE') throw err;
    console.error('Sessions GET error:', err);
    return jsonError('server_error', err.message || 'Internal server error', 500);
  }
}

export async function POST(req: NextRequest) {
  try {
    const admin = await getAdminSession();
    if (!admin) {
      return jsonError('unauthorized', 'Unauthorized', 401);
    }

    const ip = getClientIp(req);
    let body: any = {};
    try {
      body = await req.json();
    } catch {
      body = {};
    }

    const sessionId = body.session_id ? parseInt(body.session_id, 10) : 0;
    const userId = body.user_id ? parseInt(body.user_id, 10) : 0;

    if (sessionId > 0) {
      await revokeSession(sessionId);
      await logActivity(admin.id, 'force_logout', null, null, `session_id=${sessionId}`, ip);
      return jsonOk({ success: true, message: 'Session revoked' });
    }

    if (userId > 0) {
      await revokeAllUserSessions(userId);
      await logActivity(admin.id, 'force_logout', null, null, `user_id=${userId}`, ip);
      return jsonOk({ success: true, message: 'All user sessions revoked' });
    }

    return jsonError('invalid', 'session_id or user_id required');
  } catch (err: any) {
    if (err?.digest === 'DYNAMIC_SERVER_USAGE') throw err;
    console.error('Sessions POST error:', err);
    return jsonError('server_error', err.message || 'Internal server error', 500);
  }
}
