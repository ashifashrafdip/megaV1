import bcrypt from 'bcryptjs';
import crypto from 'crypto';
import jwt from 'jsonwebtoken';
import { query } from './db';
import { getSetting } from './helpers';

const JWT_SECRET = process.env.JWT_SECRET || 'dev_jwt_secret_change_before_production_use_64chars_minimum_abc123';
const ACCESS_TOKEN_TTL = parseInt(process.env.ACCESS_TOKEN_TTL || '900', 10);
const REFRESH_TOKEN_TTL = parseInt(process.env.REFRESH_TOKEN_TTL || '604800', 10);
const SESSION_TIMEOUT = parseInt(process.env.SESSION_TIMEOUT || '3600', 10);

export async function verifyPassword(password: string, hash: string): Promise<boolean> {
  // PHP password_hash default prefix is $2y$, bcryptjs supports $2a$ and $2b$
  const normalizedHash = hash.replace(/^\$2y\$/, '$2a$');
  return bcrypt.compare(password, normalizedHash);
}

export async function hashPassword(password: string): Promise<string> {
  return bcrypt.hash(password, 10);
}

export function randomToken(bytes = 32): string {
  return crypto.randomBytes(bytes).toString('hex');
}

export function hashToken(token: string): string {
  return crypto.createHash('sha256').update(token).digest('hex');
}

export function issueTokens(userId: number, sessionId: number, role: string) {
  const accessToken = jwt.sign(
    {
      sub: userId,
      sid: sessionId,
      role: role,
      type: 'access',
    },
    JWT_SECRET,
    { expiresIn: ACCESS_TOKEN_TTL }
  );

  const refreshToken = randomToken(32);

  return {
    access_token: accessToken,
    refresh_token: refreshToken,
    access_expires_in: ACCESS_TOKEN_TTL,
  };
}

export async function createUserSession(
  userId: number,
  deviceId: string,
  pcName: string,
  userAgent: string | null = null,
  ipAddress: string | null = null,
  roleName = 'team_member'
) {
  const timeoutSec = parseInt(await getSetting('session_timeout', String(SESSION_TIMEOUT)), 10);
  const refreshToken = randomToken(32);
  const refreshTokenHash = hashToken(refreshToken);

  // Temporary dummy session hash until session ID is generated
  const tempHash = randomToken(16);

  const insertRes = await query<{ id: number }>(
    `INSERT INTO sessions 
     (user_id, session_token_hash, refresh_token_hash, device_id, pc_name, ip_address, user_agent, is_active, force_logout, expires_at)
     VALUES ($1, $2, $3, $4, $5, $6, $7, 1, 0, NOW() + INTERVAL '${timeoutSec} seconds')
     RETURNING id`,
    [userId, tempHash, refreshTokenHash, deviceId, pcName, ipAddress, userAgent]
  );

  const sessionId = insertRes.rows[0].id;
  const tokens = issueTokens(userId, sessionId, roleName);
  const sessionTokenHash = hashToken(tokens.access_token);

  await query(
    'UPDATE sessions SET session_token_hash = $1 WHERE id = $2',
    [sessionTokenHash, sessionId]
  );

  return {
    sessionId,
    access_token: tokens.access_token,
    refresh_token: refreshToken,
    access_expires_in: tokens.access_expires_in,
  };
}

export interface UserRecord {
  id: number;
  username: string;
  role_id: number;
  role_name: string;
  role_label: string;
  status: string;
  display_name: string | null;
  email: string | null;
  last_login_at: string | null;
  session_id?: number;
}

export async function verifyBearerToken(req: Request): Promise<UserRecord | null> {
  const authHeader = req.headers.get('authorization') || '';
  const match = authHeader.match(/Bearer\s+(\S+)/i);
  if (!match) return null;

  const token = match[1];
  let payload: any;
  try {
    payload = jwt.verify(token, JWT_SECRET);
  } catch {
    return null;
  }

  if (payload.type !== 'access' || !payload.sub) {
    return null;
  }

  const userRes = await query<UserRecord>(
    `SELECT u.id, u.username, u.role_id, r.name AS role_name, r.label AS role_label,
            u.status, u.display_name, u.email, u.last_login_at
     FROM users u
     JOIN roles r ON r.id = u.role_id
     WHERE u.id = $1
     LIMIT 1`,
    [payload.sub]
  );

  if (userRes.rows.length === 0) return null;

  const user = userRes.rows[0];
  user.session_id = payload.sid;
  return user;
}

export async function userLicense(userId: number) {
  const res = await query<{
    status: string;
    expires_at: string | null;
    is_trial: number;
  }>(
    'SELECT status, expires_at, is_trial FROM licenses WHERE user_id = $1 LIMIT 1',
    [userId]
  );

  if (res.rows.length === 0) return null;

  const row = res.rows[0];
  let daysLeft: number | null = null;
  if (row.expires_at) {
    const diffMs = new Date(row.expires_at).getTime() - Date.now();
    daysLeft = Math.max(0, Math.ceil(diffMs / (1000 * 60 * 60 * 24)));
  }

  return {
    status: row.status,
    expires_at: row.expires_at,
    days_left: daysLeft,
    is_trial: Boolean(row.is_trial),
  };
}

export function licenseIsValid(license: any): boolean {
  if (!license) return false;
  if (license.status !== 'active' && license.status !== 'trial') return false;
  if (license.expires_at) {
    return new Date(license.expires_at).getTime() > Date.now();
  }
  return true;
}

export async function deviceIsAuthorized(userId: number, deviceId: string): Promise<boolean> {
  const res = await query<{ is_authorized: number }>(
    'SELECT is_authorized FROM devices WHERE user_id = $1 AND device_id = $2 LIMIT 1',
    [userId, deviceId]
  );
  if (res.rows.length === 0) {
    // Automatically authorize first time device connects
    await query(
      'INSERT INTO devices (user_id, device_id, is_authorized) VALUES ($1, $2, 1)',
      [userId, deviceId]
    );
    return true;
  }
  return res.rows[0].is_authorized === 1;
}

export async function upsertDevice(userId: number, deviceId: string, pcName: string | null = null) {
  await query(
    `INSERT INTO devices (user_id, device_id, pc_name, is_authorized, last_seen_at)
     VALUES ($1, $2, $3, 1, CURRENT_TIMESTAMP)
     ON CONFLICT (user_id, device_id)
     DO UPDATE SET pc_name = COALESCE(EXCLUDED.pc_name, devices.pc_name), last_seen_at = CURRENT_TIMESTAMP`,
    [userId, deviceId, pcName]
  );
}

export async function validateActiveSession(
  user: UserRecord,
  deviceId: string | null = null
): Promise<{ ok: boolean; code?: string; message?: string; license?: any }> {
  if (user.status === 'banned') {
    return { ok: false, code: 'banned', message: 'Account is banned' };
  }
  if (user.status === 'disabled') {
    return { ok: false, code: 'disabled', message: 'Account is disabled' };
  }

  const license = await userLicense(user.id);
  if (!licenseIsValid(license)) {
    return { ok: false, code: 'license_expired', message: 'License expired or inactive' };
  }

  if (deviceId && !(await deviceIsAuthorized(user.id, deviceId))) {
    return { ok: false, code: 'device_mismatch', message: 'Device is not authorized for this account' };
  }

  const sessionId = user.session_id;
  if (sessionId) {
    const sessionRes = await query<{
      is_active: number;
      force_logout: number;
      expires_at: string;
    }>(
      'SELECT is_active, force_logout, expires_at FROM sessions WHERE id = $1 LIMIT 1',
      [sessionId]
    );

    if (sessionRes.rows.length === 0) {
      return { ok: false, code: 'session_expired', message: 'Session expired' };
    }

    const s = sessionRes.rows[0];
    if (s.force_logout === 1) {
      await query('UPDATE sessions SET is_active = 0 WHERE id = $1', [sessionId]);
      return { ok: false, code: 'force_logout', message: 'Session was terminated by administrator' };
    }

    if (s.is_active !== 1 || new Date(s.expires_at).getTime() < Date.now()) {
      return { ok: false, code: 'session_expired', message: 'Session expired' };
    }

    const timeoutSec = parseInt(await getSetting('session_timeout', String(SESSION_TIMEOUT)), 10);
    await query(
      `UPDATE sessions SET last_seen_at = CURRENT_TIMESTAMP, expires_at = NOW() + INTERVAL '${timeoutSec} seconds' WHERE id = $1`,
      [sessionId]
    );
  }

  return { ok: true, license };
}

export async function revokeSession(sessionId: number) {
  await query('UPDATE sessions SET is_active = 0, force_logout = 1 WHERE id = $1', [sessionId]);
}

export async function revokeAllUserSessions(userId: number) {
  await query('UPDATE sessions SET is_active = 0, force_logout = 1 WHERE user_id = $1', [userId]);
}

export function publicUser(user: UserRecord) {
  return {
    id: user.id,
    username: user.username,
    display_name: user.display_name,
    email: user.email,
    role: user.role_name,
    role_label: user.role_label,
  };
}
