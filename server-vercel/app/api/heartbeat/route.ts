import { NextRequest } from 'next/server';
import { query } from '@/lib/db';
import {
  jsonError,
  jsonOk,
  getClientIp,
  verifyAppKey,
  logActivity,
  getSetting,
} from '@/lib/helpers';
import {
  verifyBearerToken,
  validateActiveSession,
  upsertDevice,
  publicUser,
  userLicense,
} from '@/lib/auth';

export async function POST(req: NextRequest) {
  if (!verifyAppKey(req)) {
    return jsonError('invalid_api_key', 'Invalid application API key', 401);
  }

  const user = await verifyBearerToken(req);
  if (!user) {
    return jsonError('unauthorized', 'Invalid or expired access token', 401);
  }

  let body: any = {};
  try {
    body = await req.json();
  } catch {
    body = {};
  }

  const deviceId = String(body.device_id || '').trim() || null;
  const pcName = String(body.pc_name || '').trim() || null;
  const ip = getClientIp(req);

  const check = await validateActiveSession(user, deviceId);
  if (!check.ok) {
    await logActivity(user.id, 'heartbeat_fail', deviceId, pcName, check.code, ip);
    await query(
      'INSERT INTO heartbeat_logs (user_id, session_id, status, ip_address, device_id) VALUES ($1, $2, $3, $4, $5)',
      [user.id, user.session_id || null, check.code, ip, deviceId]
    );
    return jsonError(check.code || 'unauthorized', check.message || 'Session invalid', 403);
  }

  if (deviceId) {
    await upsertDevice(user.id, deviceId, pcName);
  }

  await query(
    'INSERT INTO heartbeat_logs (user_id, session_id, status, ip_address, device_id) VALUES ($1, $2, $3, $4, $5)',
    [user.id, user.session_id || null, 'active', ip, deviceId]
  );

  const license = check.license || (await userLicense(user.id));
  const heartbeatInterval = parseInt(await getSetting('heartbeat_interval', '45'), 10);

  return jsonOk({
    status: 'active',
    user: publicUser(user),
    license: license
      ? {
          status: license.status,
          expires_at: license.expires_at,
          days_left: license.days_left,
        }
      : null,
    heartbeat_interval: heartbeatInterval,
    server_time: new Date().toISOString(),
  });
}
