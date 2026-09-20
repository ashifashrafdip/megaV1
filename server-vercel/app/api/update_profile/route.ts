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

  const displayName = body.display_name ? String(body.display_name).trim() : null;
  const email = body.email ? String(body.email).trim() : null;

  await query(
    'UPDATE users SET display_name = $1, email = $2, updated_at = NOW() WHERE id = $3',
    [displayName, email, user.id]
  );

  return jsonOk({ updated: true });
}
