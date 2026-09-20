import { NextRequest } from 'next/server';
import { query } from '@/lib/db';
import { jsonError, jsonOk } from '@/lib/helpers';
import { getAdminSession } from '@/lib/admin-auth';

export const dynamic = 'force-dynamic';

export async function GET(req: NextRequest) {
  try {
    const admin = await getAdminSession();
    if (!admin) {
      return jsonError('unauthorized', 'Unauthorized', 401);
    }

    const type = req.nextUrl.searchParams.get('type') || 'activity';

    if (type === 'login') {
      const res = await query(
        `SELECT h.id, h.created_at, h.user_id, h.username, h.success, h.ip_address, h.device_id, h.pc_name, h.reason
         FROM login_history h
         ORDER BY h.id DESC LIMIT 200`
      );
      return jsonOk({ logs: res.rows, type: 'login' });
    }

    const res = await query(
      `SELECT a.id, a.created_at, a.user_id, a.action, a.ip_address, a.device_id, a.pc_name, a.details,
              u.username
       FROM activity_logs a
       LEFT JOIN users u ON u.id = a.user_id
       ORDER BY a.id DESC LIMIT 200`
    );

    return jsonOk({ logs: res.rows, type: 'activity' });
  } catch (err: any) {
    if (err?.digest === 'DYNAMIC_SERVER_USAGE') {
      throw err;
    }
    console.error('Logs GET error:', err);
    return jsonError('server_error', err.message || 'Internal server error', 500);
  }
}
