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

    const search = req.nextUrl.searchParams.get('q') || '';
    const limit = parseInt(req.nextUrl.searchParams.get('limit') || '100', 10);
    const page = parseInt(req.nextUrl.searchParams.get('page') || '1', 10);
    const offset = (page - 1) * limit;

    let sql = `
      SELECT l.id, l.created_at, l.url, l.browser, l.device_id, l.user_id, u.username
      FROM link_logs l
      LEFT JOIN users u ON u.id = l.user_id
      WHERE 1=1
    `;
    const params: any[] = [];

    if (search) {
      params.push(`%${search}%`);
      sql += ` AND (l.url ILIKE $${params.length} OR u.username ILIKE $${params.length} OR l.device_id ILIKE $${params.length})`;
    }

    sql += ` ORDER BY l.id DESC LIMIT $${params.length + 1} OFFSET $${params.length + 2}`;
    params.push(limit, offset);

    const res = await query(sql, params);

    const countSql = search
      ? `SELECT COUNT(*) FROM link_logs l LEFT JOIN users u ON u.id = l.user_id WHERE (l.url ILIKE $1 OR u.username ILIKE $1 OR l.device_id ILIKE $1)`
      : 'SELECT COUNT(*) FROM link_logs';
    const countParams = search ? [`%${search}%`] : [];
    const totalRes = await query<{ count: string }>(countSql, countParams);

    return jsonOk({
      logs: res.rows,
      total: parseInt(totalRes.rows[0]?.count || '0', 10),
      page,
      limit,
    });
  } catch (err: any) {
    if (err?.digest === 'DYNAMIC_SERVER_USAGE') throw err;
    console.error('Link-logs GET error:', err);
    return jsonError('server_error', err.message || 'Internal server error', 500);
  }
}

export async function DELETE(req: NextRequest) {
  try {
    const admin = await getAdminSession();
    if (!admin || admin.role_name !== 'super_admin') {
      return jsonError('forbidden', 'Super Admin required to delete logs', 403);
    }

    const id = req.nextUrl.searchParams.get('id');
    if (id) {
      await query('DELETE FROM link_logs WHERE id = $1', [parseInt(id, 10)]);
      return jsonOk({ success: true, message: 'Link log deleted' });
    }

    const all = req.nextUrl.searchParams.get('all');
    if (all === 'true') {
      await query('TRUNCATE TABLE link_logs');
      return jsonOk({ success: true, message: 'All link logs cleared' });
    }

    return jsonError('invalid', 'id or all=true required');
  } catch (err: any) {
    console.error('Link-logs DELETE error:', err);
    return jsonError('server_error', err.message || 'Internal server error', 500);
  }
}
