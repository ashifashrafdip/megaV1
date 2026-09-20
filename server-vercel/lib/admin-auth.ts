import { cookies, headers } from 'next/headers';
import jwt from 'jsonwebtoken';
import { query } from './db';
import { UserRecord } from './auth';

const SESSION_SECRET = process.env.SESSION_SECRET || 'admin_session_secret_change_in_production_key_xyz_98765';

export interface AdminSession {
  userId: number;
  username: string;
  role: string;
}

export function signAdminToken(user: UserRecord): string {
  return jwt.sign(
    {
      sub: user.id,
      username: user.username,
      role: user.role_name,
    },
    SESSION_SECRET,
    { expiresIn: 86400 } // 24 hours
  );
}

export function verifyAdminToken(token: string): AdminSession | null {
  try {
    const payload: any = jwt.verify(token, SESSION_SECRET);
    if (!payload.sub || (payload.role !== 'super_admin' && payload.role !== 'admin')) {
      return null;
    }
    return {
      userId: payload.sub,
      username: payload.username,
      role: payload.role,
    };
  } catch {
    return null;
  }
}

export async function getAdminSession(): Promise<UserRecord | null> {
  const cookieStore = cookies();
  let token = cookieStore.get('admin_session')?.value;

  if (!token) {
    const reqHeaders = headers();
    const authHeader = reqHeaders.get('authorization') || '';
    const match = authHeader.match(/Bearer\s+(\S+)/i);
    if (match) token = match[1];
  }

  if (!token) return null;

  const session = verifyAdminToken(token);
  if (!session) return null;

  const res = await query<UserRecord>(
    `SELECT u.id, u.username, u.role_id, r.name AS role_name, r.label AS role_label,
            u.status, u.display_name, u.email, u.last_login_at
     FROM users u
     JOIN roles r ON r.id = u.role_id
     WHERE u.id = $1 AND u.status = 'active'
     LIMIT 1`,
    [session.userId]
  );

  return res.rows[0] || null;
}
