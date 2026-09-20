import { NextRequest } from 'next/server';
import { query } from '@/lib/db';
import { jsonError, jsonOk, logActivity, getClientIp } from '@/lib/helpers';
import { hashPassword, revokeAllUserSessions } from '@/lib/auth';
import { getAdminSession } from '@/lib/admin-auth';

export const dynamic = 'force-dynamic';

function parseExpiryDate(raw: any): string | null {
  if (!raw || typeof raw !== 'string') return null;
  const trimmed = raw.trim();
  if (!trimmed) return null;
  const parsed = new Date(trimmed);
  if (isNaN(parsed.getTime())) return null;
  return parsed.toISOString();
}

export async function GET(req: NextRequest) {
  try {
    const admin = await getAdminSession();
    if (!admin) {
      return jsonError('unauthorized', 'Unauthorized', 401);
    }

    const search = req.nextUrl.searchParams.get('q') || '';
    const isSuper = admin.role_name === 'super_admin';
    const roleFilter = isSuper ? '' : " AND r.name = 'team_member'";

    let sql = `
      SELECT u.id, u.username, u.display_name, u.email, u.status, u.last_login_at, u.created_at,
             r.id AS role_id, r.name AS role_name, r.label AS role_label,
             l.status AS license_status, l.expires_at, l.is_trial
      FROM users u
      JOIN roles r ON r.id = u.role_id
      LEFT JOIN licenses l ON l.user_id = u.id
      WHERE 1=1 ${roleFilter}
    `;
    const params: any[] = [];

    if (search) {
      params.push(`%${search}%`);
      sql += ` AND (u.username ILIKE $${params.length} OR u.display_name ILIKE $${params.length} OR u.email ILIKE $${params.length})`;
    }

    sql += ' ORDER BY u.id DESC';

    const res = await query(sql, params);
    const rolesRes = await query('SELECT * FROM roles ORDER BY id');

    const usersWithDaysLeft = res.rows.map((row) => {
      let daysLeft: number | null = null;
      if (row.expires_at) {
        const diff = new Date(row.expires_at).getTime() - Date.now();
        daysLeft = Math.max(0, Math.ceil(diff / (1000 * 60 * 60 * 24)));
      }
      return {
        ...row,
        days_left: daysLeft,
      };
    });

    return jsonOk({ users: usersWithDaysLeft, roles: rolesRes.rows });
  } catch (err: any) {
    if (err?.digest === 'DYNAMIC_SERVER_USAGE') {
      throw err;
    }
    console.error('Admin users GET error:', err);
    return jsonError('server_error', err.message || 'Internal server error', 500);
  }
}

export async function POST(req: NextRequest) {
  try {
    const admin = await getAdminSession();
    if (!admin) {
      return jsonError('unauthorized', 'Unauthorized', 401);
    }

    const isSuper = admin.role_name === 'super_admin';
    const ip = getClientIp(req);

    let body: any = {};
    try {
      body = await req.json();
    } catch {
      return jsonError('invalid', 'Malformed JSON payload');
    }

    const action = String(body.action || '').trim();
    const userId = body.user_id ? parseInt(body.user_id, 10) : 0;

    if (action === 'create') {
      const username = String(body.username || '').trim();
      const password = String(body.password || '');
      const roleId = body.role_id ? parseInt(body.role_id, 10) : 3;
      const expiresAt = parseExpiryDate(body.expires_at);

      if (!username || password.length < 8) {
        return jsonError('invalid', 'Username and password (min 8 chars) required');
      }

      if (!isSuper && roleId !== 3) {
        return jsonError('forbidden', 'Admins can only create team members', 403);
      }

      const existing = await query('SELECT id FROM users WHERE username = $1', [username]);
      if (existing.rows.length > 0) {
        return jsonError('conflict', 'Username already exists', 409);
      }

      const hashed = await hashPassword(password);
      const insertUser = await query<{ id: number }>(
        'INSERT INTO users (username, password_hash, role_id, status) VALUES ($1, $2, $3, $4) RETURNING id',
        [username, hashed, roleId, 'active']
      );

      const newId = insertUser.rows[0].id;
      if (expiresAt) {
        await query(
          'INSERT INTO licenses (user_id, status, expires_at) VALUES ($1, $2, $3)',
          [newId, 'active', expiresAt]
        );
      } else {
        await query('INSERT INTO licenses (user_id, status) VALUES ($1, $2)', [newId, 'active']);
      }

      await logActivity(admin.id, 'user_create', null, null, `user_id=${newId}`, ip);
      return jsonOk({ success: true, message: 'User created successfully', user_id: newId });
    }

    if (!userId) {
      return jsonError('invalid', 'user_id required');
    }

    const targetRes = await query<{ id: number; role_name: string }>(
      'SELECT u.id, r.name AS role_name FROM users u JOIN roles r ON r.id = u.role_id WHERE u.id = $1',
      [userId]
    );
    const target = targetRes.rows[0];
    if (!target) {
      return jsonError('not_found', 'User not found', 404);
    }

    if (!isSuper && target.role_name !== 'team_member') {
      return jsonError('forbidden', 'Cannot modify administrator accounts', 403);
    }

    switch (action) {
      case 'ban':
        await query("UPDATE users SET status = 'banned', updated_at = NOW() WHERE id = $1", [userId]);
        await revokeAllUserSessions(userId);
        await logActivity(admin.id, 'ban_user', null, null, `user_id=${userId}`, ip);
        return jsonOk({ success: true, message: 'User banned' });

      case 'unban':
        await query("UPDATE users SET status = 'active', updated_at = NOW() WHERE id = $1", [userId]);
        await logActivity(admin.id, 'unban_user', null, null, `user_id=${userId}`, ip);
        return jsonOk({ success: true, message: 'User unbanned' });

      case 'disable':
        await query("UPDATE users SET status = 'disabled', updated_at = NOW() WHERE id = $1", [userId]);
        await revokeAllUserSessions(userId);
        await logActivity(admin.id, 'disable_user', null, null, `user_id=${userId}`, ip);
        return jsonOk({ success: true, message: 'User disabled' });

      case 'enable':
        await query("UPDATE users SET status = 'active', updated_at = NOW() WHERE id = $1", [userId]);
        await logActivity(admin.id, 'enable_user', null, null, `user_id=${userId}`, ip);
        return jsonOk({ success: true, message: 'User enabled' });

      case 'delete':
        if (userId === admin.id) {
          return jsonError('invalid', 'Cannot delete your own account', 400);
        }
        await query('DELETE FROM users WHERE id = $1', [userId]);
        await logActivity(admin.id, 'delete_user', null, null, `user_id=${userId}`, ip);
        return jsonOk({ success: true, message: 'User deleted' });

      case 'reset_password':
        const newPassword = String(body.new_password || '');
        if (newPassword.length < 8) {
          return jsonError('invalid', 'Password must be at least 8 characters', 400);
        }
        const newHash = await hashPassword(newPassword);
        await query('UPDATE users SET password_hash = $1, updated_at = NOW() WHERE id = $2', [newHash, userId]);
        await revokeAllUserSessions(userId);
        await logActivity(admin.id, 'reset_password', null, null, `user_id=${userId}`, ip);
        return jsonOk({ success: true, message: 'Password reset successfully' });

      case 'update_license':
        const licenseStatus = String(body.license_status || 'active').trim();
        const expires = parseExpiryDate(body.expires_at);
        await query(
          `INSERT INTO licenses (user_id, status, expires_at, updated_at)
           VALUES ($1, $2, $3, NOW())
           ON CONFLICT (user_id)
           DO UPDATE SET status = EXCLUDED.status, expires_at = EXCLUDED.expires_at, updated_at = NOW()`,
          [userId, licenseStatus, expires]
        );
        await logActivity(admin.id, 'update_license', null, null, `user_id=${userId}`, ip);
        return jsonOk({ success: true, message: 'License updated' });

      default:
        return jsonError('invalid', 'Unknown action');
    }
  } catch (err: any) {
    if (err?.digest === 'DYNAMIC_SERVER_USAGE') {
      throw err;
    }
    console.error('Admin users POST error:', err);
    if (err?.code === '23505') {
      return jsonError('conflict', 'A user with this unique identifier already exists', 409);
    }
    return jsonError('server_error', err.message || 'Internal server error', 500);
  }
}
