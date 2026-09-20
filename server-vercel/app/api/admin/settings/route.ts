import { NextRequest } from 'next/server';
import { query } from '@/lib/db';
import { jsonError, jsonOk, logActivity, getClientIp } from '@/lib/helpers';
import { getAdminSession } from '@/lib/admin-auth';

export async function GET() {
  const admin = await getAdminSession();
  if (!admin) {
    return jsonError('unauthorized', 'Unauthorized', 401);
  }

  const res = await query<{ setting_key: string; setting_value: string }>(
    'SELECT setting_key, setting_value FROM settings'
  );

  const settings: Record<string, string> = {
    app_name: 'Automation Hub',
    heartbeat_interval: '45',
    session_timeout: '3600',
    offline_grace_seconds: '300',
    single_session: '1',
  };

  for (const row of res.rows) {
    settings[row.setting_key] = row.setting_value;
  }

  return jsonOk({ settings, is_super: admin.role_name === 'super_admin' });
}

export async function POST(req: NextRequest) {
  const admin = await getAdminSession();
  if (!admin || admin.role_name !== 'super_admin') {
    return jsonError('forbidden', 'Super Admin required to edit settings', 403);
  }

  const ip = getClientIp(req);
  let body: any = {};
  try {
    body = await req.json();
  } catch {
    return jsonError('invalid', 'Malformed JSON payload');
  }

  const allowedKeys = ['app_name', 'heartbeat_interval', 'session_timeout', 'offline_grace_seconds', 'single_session'];
  for (const key of allowedKeys) {
    if (body[key] !== undefined) {
      const val = String(body[key]).trim();
      await query(
        `INSERT INTO settings (setting_key, setting_value, updated_at)
         VALUES ($1, $2, NOW())
         ON CONFLICT (setting_key)
         DO UPDATE SET setting_value = EXCLUDED.setting_value, updated_at = NOW()`,
        [key, val]
      );
    }
  }

  await logActivity(admin.id, 'update_settings', null, null, 'Updated system settings', ip);

  return jsonOk({ success: true, message: 'Settings saved successfully' });
}
