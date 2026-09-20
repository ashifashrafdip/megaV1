import { NextRequest } from 'next/server';
import { query } from '@/lib/db';
import { jsonError, jsonOk, verifyAppKey } from '@/lib/helpers';
import {
  hashToken,
  issueTokens,
  userLicense,
  licenseIsValid,
  UserRecord,
} from '@/lib/auth';

export async function POST(req: NextRequest) {
  if (!verifyAppKey(req)) {
    return jsonError('invalid_api_key', 'Invalid application API key', 401);
  }

  let body: any = {};
  try {
    body = await req.json();
  } catch {
    return jsonError('invalid', 'Malformed JSON payload');
  }

  const refreshToken = String(body.refresh_token || '').trim();
  const deviceId = String(body.device_id || '').trim();

  if (!refreshToken) {
    return jsonError('invalid', 'Refresh token required');
  }

  const tokenHash = hashToken(refreshToken);

  const sessionRes = await query<{
    id: number;
    user_id: number;
    device_id: string;
    is_active: number;
    force_logout: number;
    expires_at: string;
  }>(
    'SELECT id, user_id, device_id, is_active, force_logout, expires_at FROM sessions WHERE refresh_token_hash = $1 LIMIT 1',
    [tokenHash]
  );

  if (sessionRes.rows.length === 0) {
    return jsonError('invalid_token', 'Invalid refresh token', 401);
  }

  const session = sessionRes.rows[0];

  if (session.is_active !== 1 || session.force_logout === 1 || new Date(session.expires_at).getTime() < Date.now()) {
    return jsonError('session_expired', 'Session expired or terminated', 401);
  }

  const userRes = await query<UserRecord>(
    `SELECT u.*, r.name AS role_name, r.label AS role_label
     FROM users u
     JOIN roles r ON r.id = u.role_id
     WHERE u.id = $1 LIMIT 1`,
    [session.user_id]
  );

  if (userRes.rows.length === 0) {
    return jsonError('user_not_found', 'User not found', 404);
  }

  const user = userRes.rows[0];

  if (user.status !== 'active') {
    return jsonError('account_inactive', `Account is ${user.status}`, 403);
  }

  const license = await userLicense(user.id);
  if (!licenseIsValid(license)) {
    return jsonError('license_expired', 'License expired', 403);
  }

  const tokens = issueTokens(user.id, session.id, user.role_name);
  const newSessionTokenHash = hashToken(tokens.access_token);

  await query(
    'UPDATE sessions SET session_token_hash = $1, last_seen_at = CURRENT_TIMESTAMP WHERE id = $2',
    [newSessionTokenHash, session.id]
  );

  return jsonOk({
    access_token: tokens.access_token,
    expires_in: tokens.access_expires_in,
  });
}
