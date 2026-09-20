import { NextRequest } from 'next/server';
import { jsonError, jsonOk, verifyAppKey } from '@/lib/helpers';
import { verifyBearerToken, userLicense, publicUser } from '@/lib/auth';

export async function GET(req: NextRequest) {
  if (!verifyAppKey(req)) {
    return jsonError('invalid_api_key', 'Invalid application API key', 401);
  }

  const user = await verifyBearerToken(req);
  if (!user) {
    return jsonError('unauthorized', 'Authentication required', 401);
  }

  const license = await userLicense(user.id);

  return jsonOk({
    user: publicUser(user),
    license,
  });
}
