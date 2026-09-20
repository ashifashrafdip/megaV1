import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/db';
import { jsonError, jsonOk, getClientIp, logLoginHistory } from '@/lib/helpers';
import { verifyPassword, UserRecord } from '@/lib/auth';
import { signAdminToken } from '@/lib/admin-auth';

export async function POST(req: NextRequest) {
  let body: any = {};
  try {
    body = await req.json();
  } catch {
    return jsonError('invalid', 'Malformed JSON payload');
  }

  const username = String(body.username || '').trim();
  const password = String(body.password || '');
  const ip = getClientIp(req);

  if (!username || !password) {
    return jsonError('invalid', 'Username and password required');
  }

  const userRes = await query<UserRecord & { password_hash: string }>(
    `SELECT u.*, r.name AS role_name, r.label AS role_label
     FROM users u
     JOIN roles r ON r.id = u.role_id
     WHERE u.username = $1
     LIMIT 1`,
    [username]
  );

  const user = userRes.rows[0];

  if (!user || !(await verifyPassword(password, user.password_hash))) {
    await logLoginHistory(user ? user.id : null, username, false, ip, null, null, 'admin_invalid_credentials');
    return jsonError('invalid', 'Invalid credentials', 401);
  }

  if (user.role_name !== 'super_admin' && user.role_name !== 'admin') {
    await logLoginHistory(user.id, username, false, ip, null, null, 'admin_forbidden');
    return jsonError('forbidden', 'Admin panel access denied for this role', 403);
  }

  if (user.status !== 'active') {
    return jsonError('inactive', 'Account is not active', 403);
  }

  const token = signAdminToken(user);

  await query('UPDATE users SET last_login_at = NOW(), last_login_ip = $1 WHERE id = $2', [ip, user.id]);
  await logLoginHistory(user.id, username, true, ip, null, null, 'admin_login');

  const isHttps = req.nextUrl.protocol === 'https:' || req.headers.get('x-forwarded-proto') === 'https';

  const response = NextResponse.json({
    ok: true,
    token,
    user: {
      id: user.id,
      username: user.username,
      role: user.role_name,
      display_name: user.display_name,
    },
  });

  response.cookies.set({
    name: 'admin_session',
    value: token,
    httpOnly: true,
    secure: isHttps,
    sameSite: 'lax',
    path: '/',
    maxAge: 86400,
  });

  return response;
}
