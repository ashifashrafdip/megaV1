import { NextRequest } from 'next/server';
import fs from 'fs';
import path from 'path';
import { jsonError, jsonOk, verifyAppKey, logActivity, getClientIp } from '@/lib/helpers';
import { verifyBearerToken, validateActiveSession } from '@/lib/auth';

let cachedPayload: any = null;

function getPayloadData() {
  if (!cachedPayload) {
    const filePath = path.join(process.cwd(), 'lib', 'payload_data.json');
    if (fs.existsSync(filePath)) {
      const raw = fs.readFileSync(filePath, 'utf-8');
      cachedPayload = JSON.parse(raw);
    } else {
      cachedPayload = {};
    }
  }
  return cachedPayload;
}

export async function POST(req: NextRequest) {
  if (!verifyAppKey(req)) {
    return jsonError('invalid_api_key', 'Invalid application API key', 401);
  }

  const user = await verifyBearerToken(req);
  if (!user) {
    return jsonError('unauthorized', 'Active session required', 401);
  }

  let body: any = {};
  try {
    body = await req.json();
  } catch {
    body = {};
  }

  const deviceId = String(body.device_id || '').trim() || null;
  const ip = getClientIp(req);

  const check = await validateActiveSession(user, deviceId);
  if (!check.ok) {
    return jsonError(check.code || 'unauthorized', check.message || 'License expired or session invalid', 403);
  }

  await logActivity(user.id, 'fetch_payload', deviceId, null, 'Authorized payload delivery', ip);

  const payload = getPayloadData();

  return jsonOk({
    payload,
    timestamp: Date.now(),
  });
}
