import { NextRequest } from 'next/server';
import { query } from '@/lib/db';
import { jsonError, jsonOk, verifyAppKey } from '@/lib/helpers';
import { verifyBearerToken } from '@/lib/auth';

export async function POST(req: NextRequest) {
  if (!verifyAppKey(req)) {
    return jsonError('invalid_api_key', 'Invalid application API key', 401);
  }

  const user = await verifyBearerToken(req);
  if (!user) {
    return jsonError('unauthorized', 'Authentication required', 401);
  }

  let body: any = {};
  try {
    body = await req.json();
  } catch {
    body = {};
  }

  const url = String(body.url || '').trim();
  const browser = String(body.browser || 'adspower').trim();
  const deviceId = String(body.device_id || '').trim();

  if (!url) {
    return jsonError('invalid', 'URL required', 400);
  }

  await query(
    'INSERT INTO link_logs (user_id, url, browser, device_id) VALUES ($1, $2, $3, $4)',
    [user.id, url, browser, deviceId || null]
  );

  return jsonOk({ logged: true });
}
