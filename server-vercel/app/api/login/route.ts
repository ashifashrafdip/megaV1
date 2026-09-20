import { NextRequest } from 'next/server';
import { query } from '@/lib/db';
import {
  jsonError,
  jsonOk,
  getClientIp,
  verifyAppKey,
  rateLimit,
  logLoginHistory,
  logActivity,
  getSetting,
} from '@/lib/helpers';
import {
  verifyPassword,
  userLicense,
  licenseIsValid,
  deviceIsAuthorized,
  createUserSession,
  publicUser,
  UserRecord,
} from '@/lib/auth';

export async function POST(req: NextRequest) {
  if (!verifyAppKey(req)) {
    return jsonError('invalid_api_key', 'Invalid application API key', 401);
  }

  const ip = getClientIp(req);
  const rateLimitAllowed = await rateLimit('login', ip, 5, 60);
  if (!rateLimitAllowed) {
    return jsonError('rate_limit', 'Too many login attempts. Please wait 1 minute.', 429);
  }

  let body: any = {};
  try {
    body = await req.json();
  } catch {
    return jsonError('invalid', 'Malformed JSON payload');
  }

  const username = String(body.username || '').trim();
  const password = String(body.password || '');
  const deviceId = String(body.device_id || '').trim();
  const pcName = String(body.pc_name || '').trim();

  if (!username || !password) {
    return jsonError('invalid', 'Username and password are required');
  }
  if (!deviceId) {
    return jsonError('invalid', 'Device ID is required');
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
    await logLoginHistory(
      user ? user.id : null,
      username,
      false,
      ip,
      deviceId,
      pcName,
      'invalid_credentials'
    );
    return jsonError('invalid', 'Invalid username or password', 401);
  }

  if (user.status === 'banned') {
    await logLoginHistory(user.id, username, false, ip, deviceId, pcName, 'banned');
    return jsonError('banned', 'Account is banned', 403);
  }
  if (user.status === 'disabled') {
    await logLoginHistory(user.id, username, false, ip, deviceId, pcName, 'disabled');
    return jsonError('disabled', 'Account is disabled', 403);
  }

  const license = await userLicense(user.id);
  if (!licenseIsValid(license)) {
    await logLoginHistory(user.id, username, false, ip, deviceId, pcName, 'license_expired');
    return jsonError('license_expired', 'License expired or inactive', 403);
  }

  const isDevAuth = await deviceIsAuthorized(user.id, deviceId);
  if (!isDevAuth) {
    await logLoginHistory(user.id, username, false, ip, deviceId, pcName, 'device_unauthorized');
    return jsonError('device_mismatch', 'Device is not authorized for this account', 403);
  }

  const singleSession = (await getSetting('single_session', '1')) === '1';
  if (singleSession) {
    const activeRes = await query<{ id: number }>(
      'SELECT id FROM sessions WHERE user_id = $1 AND is_active = 1 AND expires_at > NOW() LIMIT 1',
      [user.id]
    );
    if (activeRes.rows.length > 0) {
      await logLoginHistory(user.id, username, false, ip, deviceId, pcName, 'session_active');
      return jsonError('session_active', 'Account is already active on another device', 409);
    }
  }

  const userAgent = req.headers.get('user-agent');
  const tokens = await createUserSession(
    user.id,
    deviceId,
    pcName,
    userAgent,
    ip,
    user.role_name
  );

  await query('UPDATE users SET last_login_at = NOW(), last_login_ip = $1 WHERE id = $2', [
    ip,
    user.id,
  ]);

  await logLoginHistory(user.id, username, true, ip, deviceId, pcName, null);
  await logActivity(user.id, 'login', deviceId, pcName, null, ip);

  const heartbeatInterval = parseInt(await getSetting('heartbeat_interval', '45'), 10);

  return jsonOk({
    access_token: tokens.access_token,
    refresh_token: tokens.refresh_token,
    access_expires_in: tokens.access_expires_in,
    user: publicUser(user),
    license: license
      ? {
          status: license.status,
          expires_at: license.expires_at,
          days_left: license.days_left,
          is_trial: license.is_trial,
        }
      : null,
    heartbeat_interval: heartbeatInterval,
  });
}
