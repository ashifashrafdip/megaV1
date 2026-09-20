import { NextRequest } from 'next/server';
import { query } from '@/lib/db';
import { jsonError, jsonOk, logActivity, getClientIp } from '@/lib/helpers';
import { getAdminSession } from '@/lib/admin-auth';

export async function GET() {
  const admin = await getAdminSession();
  if (!admin) {
    return jsonError('unauthorized', 'Unauthorized', 401);
  }

  const res = await query(
    `SELECT d.id, d.user_id, d.device_id, d.pc_name, d.is_authorized, d.first_seen_at, d.last_seen_at,
            u.username
     FROM devices d
     JOIN users u ON u.id = d.user_id
     ORDER BY d.last_seen_at DESC LIMIT 200`
  );

  return jsonOk({ devices: res.rows });
}

export async function POST(req: NextRequest) {
  const admin = await getAdminSession();
  if (!admin) {
    return jsonError('unauthorized', 'Unauthorized', 401);
  }

  const ip = getClientIp(req);
  let body: any = {};
  try {
    body = await req.json();
  } catch {
    body = {};
  }

  const deviceRowId = body.device_row_id ? parseInt(body.device_row_id, 10) : 0;
  const action = String(body.action || '').trim();

  if (!deviceRowId) {
    return jsonError('invalid', 'device_row_id required');
  }

  if (action === 'authorize') {
    await query('UPDATE devices SET is_authorized = 1 WHERE id = $1', [deviceRowId]);
    await logActivity(admin.id, 'authorize_device', null, null, `device_row_id=${deviceRowId}`, ip);
    return jsonOk({ success: true, message: 'Device authorized' });
  }

  if (action === 'revoke') {
    await query('UPDATE devices SET is_authorized = 0 WHERE id = $1', [deviceRowId]);
    await logActivity(admin.id, 'revoke_device', null, null, `device_row_id=${deviceRowId}`, ip);
    return jsonOk({ success: true, message: 'Device revoked' });
  }

  return jsonError('invalid', 'action must be authorize or revoke');
}
