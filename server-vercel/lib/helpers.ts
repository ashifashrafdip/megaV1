import { NextResponse } from 'next/server';
import { query } from './db';

export function jsonOk(payload: Record<string, any> = {}, status = 200) {
  return NextResponse.json(
    { ok: true, ...payload },
    {
      status,
      headers: {
        'Content-Type': 'application/json; charset=utf-8',
        'X-Content-Type-Options': 'nosniff',
      },
    }
  );
}

export function jsonError(
  code: string,
  message: string,
  status = 400,
  extra: Record<string, any> = {}
) {
  return NextResponse.json(
    { ok: false, code, message, ...extra },
    {
      status,
      headers: {
        'Content-Type': 'application/json; charset=utf-8',
        'X-Content-Type-Options': 'nosniff',
      },
    }
  );
}

export function getClientIp(req: Request): string {
  const forwarded = req.headers.get('x-forwarded-for');
  if (forwarded) {
    return forwarded.split(',')[0].trim();
  }
  return req.headers.get('x-real-ip') || '127.0.0.1';
}

export function verifyAppKey(req: Request): boolean {
  const expectedKey = process.env.APP_API_KEY || 'dev-desktop-app-key-change-me';
  const provided = req.headers.get('x-app-key') || '';
  return expectedKey === '' || expectedKey === provided;
}

export async function rateLimit(
  bucket: string,
  ip: string,
  maxHits = 5,
  windowSeconds = 60
): Promise<boolean> {
  const rateKey = `${bucket}:${ip}`;
  const now = new Date();

  try {
    const existing = await query<{ id: number; hits: number; window_start: string }>(
      'SELECT id, hits, window_start FROM rate_limits WHERE rate_key = $1 LIMIT 1',
      [rateKey]
    );

    if (existing.rows.length === 0) {
      await query(
        'INSERT INTO rate_limits (rate_key, hits, window_start) VALUES ($1, 1, CURRENT_TIMESTAMP)',
        [rateKey]
      );
      return true;
    }

    const row = existing.rows[0];
    const windowStart = new Date(row.window_start).getTime();
    const elapsedSeconds = (now.getTime() - windowStart) / 1000;

    if (elapsedSeconds > windowSeconds) {
      await query(
        'UPDATE rate_limits SET hits = 1, window_start = CURRENT_TIMESTAMP WHERE id = $1',
        [row.id]
      );
      return true;
    }

    if (row.hits >= maxHits) {
      return false;
    }

    await query('UPDATE rate_limits SET hits = hits + 1 WHERE id = $1', [row.id]);
    return true;
  } catch (err) {
    // If rate limits table has transient issue, permit request
    console.error('Rate limit check error:', err);
    return true;
  }
}

export async function logActivity(
  userId: number | null,
  action: string,
  deviceId: string | null = null,
  pcName: string | null = null,
  details: string | null = null,
  ip: string | null = null
) {
  try {
    await query(
      'INSERT INTO activity_logs (user_id, action, ip_address, device_id, pc_name, details) VALUES ($1, $2, $3, $4, $5, $6)',
      [userId, action, ip, deviceId, pcName, details]
    );
  } catch (e) {
    console.error('Failed to log activity:', e);
  }
}

export async function logLoginHistory(
  userId: number | null,
  username: string,
  success: boolean,
  ip: string,
  deviceId: string | null = null,
  pcName: string | null = null,
  reason: string | null = null
) {
  try {
    await query(
      'INSERT INTO login_history (user_id, username, success, ip_address, device_id, pc_name, reason) VALUES ($1, $2, $3, $4, $5, $6, $7)',
      [userId, username, success ? 1 : 0, ip, deviceId, pcName, reason]
    );
  } catch (e) {
    console.error('Failed to log login history:', e);
  }
}

export async function getSetting(key: string, defaultVal: string): Promise<string> {
  try {
    const res = await query<{ setting_value: string }>(
      'SELECT setting_value FROM settings WHERE setting_key = $1 LIMIT 1',
      [key]
    );
    return res.rows[0]?.setting_value ?? defaultVal;
  } catch {
    return defaultVal;
  }
}
