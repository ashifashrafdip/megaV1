import { NextResponse } from 'next/server';
import { query } from '@/lib/db';
import { jsonError, jsonOk } from '@/lib/helpers';
import { getAdminSession } from '@/lib/admin-auth';

export async function GET() {
  const admin = await getAdminSession();
  if (!admin) {
    return jsonError('unauthorized', 'Unauthorized', 401);
  }

  try {
    const usersCount = await query<{ count: string }>('SELECT COUNT(*) FROM users');
    const onlineSessions = await query<{ count: string }>(
      "SELECT COUNT(*) FROM sessions WHERE is_active = 1 AND last_seen_at > NOW() - INTERVAL '3 minutes'"
    );
    const todayLinks = await query<{ count: string }>(
      "SELECT COUNT(*) FROM link_logs WHERE created_at >= NOW() - INTERVAL '24 hours'"
    );
    const totalLinks = await query<{ count: string }>('SELECT COUNT(*) FROM link_logs');
    const devicesCount = await query<{ count: string }>('SELECT COUNT(*) FROM devices');
    const activeLicenses = await query<{ count: string }>(
      "SELECT COUNT(*) FROM licenses WHERE status IN ('active', 'trial') AND (expires_at IS NULL OR expires_at > NOW())"
    );

    const recentLinks = await query(
      `SELECT l.id, l.created_at, l.url, l.browser, l.device_id, u.username
       FROM link_logs l
       LEFT JOIN users u ON u.id = l.user_id
       ORDER BY l.id DESC LIMIT 10`
    );

    const recentActivities = await query(
      `SELECT a.id, a.created_at, a.action, a.ip_address, a.device_id, a.details, u.username
       FROM activity_logs a
       LEFT JOIN users u ON u.id = a.user_id
       ORDER BY a.id DESC LIMIT 10`
    );

    return jsonOk({
      stats: {
        total_users: parseInt(usersCount.rows[0]?.count || '0', 10),
        online_sessions: parseInt(onlineSessions.rows[0]?.count || '0', 10),
        today_links: parseInt(todayLinks.rows[0]?.count || '0', 10),
        total_links: parseInt(totalLinks.rows[0]?.count || '0', 10),
        total_devices: parseInt(devicesCount.rows[0]?.count || '0', 10),
        active_licenses: parseInt(activeLicenses.rows[0]?.count || '0', 10),
      },
      recent_links: recentLinks.rows,
      recent_activities: recentActivities.rows,
      current_user: {
        id: admin.id,
        username: admin.username,
        role: admin.role_name,
      },
    });
  } catch (err: any) {
    console.error('Stats error:', err);
    return jsonError('server_error', err.message || 'Error fetching stats', 500);
  }
}
