import { NextRequest } from 'next/server';
import { jsonError, jsonOk, verifyAppKey } from '@/lib/helpers';
import { verifyBearerToken, userLicense, licenseIsValid } from '@/lib/auth';

export async function POST(req: NextRequest) {
  if (!verifyAppKey(req)) {
    return jsonError('invalid_api_key', 'Invalid application API key', 401);
  }

  const user = await verifyBearerToken(req);
  if (!user) {
    return jsonError('unauthorized', 'Authentication required', 401);
  }

  const license = await userLicense(user.id);
  const isValid = licenseIsValid(license);

  return jsonOk({
    valid: isValid,
    license: license
      ? {
          status: license.status,
          expires_at: license.expires_at,
          days_left: license.days_left,
        }
      : null,
  });
}
