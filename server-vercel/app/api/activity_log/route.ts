import { NextRequest } from 'next/server';
import { jsonError, jsonOk, verifyAppKey, logActivity, getClientIp } from '@/lib/helpers';
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

  const action = String(body.action || '').trim();
  if (!action) {
    return jsonError('invalid', 'Action required', 400);
  }

  const deviceId = String(body.device_id || '').trim() || null;
  const pcName = String(body.pc_name || '').trim() || null;
  const details = body.details ? JSON.stringify(body.details) : null;
  const ip = getClientIp(req);

  await logActivity(user.id, action, deviceId, pcName, details, ip);

  return jsonOk({ logged: true });
}
