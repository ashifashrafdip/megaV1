<?php
declare(strict_types=1);

require_once __DIR__ . '/helpers.php';

class JwtAuth
{
    public static function encode(array $payload, string $secret, int $ttlSeconds): string
    {
        $now = time();
        $payload['iat'] = $now;
        $payload['exp'] = $now + $ttlSeconds;
        $header = self::base64UrlEncode(json_encode(['typ' => 'JWT', 'alg' => 'HS256']));
        $body = self::base64UrlEncode(json_encode($payload));
        $signature = self::base64UrlEncode(
            hash_hmac('sha256', $header . '.' . $body, $secret, true)
        );
        return $header . '.' . $body . '.' . $signature;
    }

    public static function decode(string $token, string $secret): array
    {
        $parts = explode('.', $token);
        if (count($parts) !== 3) {
            throw new RuntimeException('Invalid token format');
        }
        [$headerB64, $payloadB64, $signatureB64] = $parts;
        $expected = self::base64UrlEncode(
            hash_hmac('sha256', $headerB64 . '.' . $payloadB64, $secret, true)
        );
        if (!hash_equals($expected, $signatureB64)) {
            throw new RuntimeException('Invalid token signature');
        }
        $payload = json_decode(self::base64UrlDecode($payloadB64), true);
        if (!is_array($payload)) {
            throw new RuntimeException('Invalid token payload');
        }
        if (($payload['exp'] ?? 0) < time()) {
            throw new RuntimeException('Token expired');
        }
        return $payload;
    }

    private static function base64UrlEncode(string $data): string
    {
        return rtrim(strtr(base64_encode($data), '+/', '-_'), '=');
    }

    private static function base64UrlDecode(string $data): string
    {
        $remainder = strlen($data) % 4;
        if ($remainder) {
            $data .= str_repeat('=', 4 - $remainder);
        }
        return base64_decode(strtr($data, '-_', '+/')) ?: '';
    }
}

function issue_tokens(int $userId, int $sessionId, string $role): array
{
    $cfg = app_config();
    $access = JwtAuth::encode([
        'sub' => $userId,
        'sid' => $sessionId,
        'role' => $role,
        'type' => 'access',
    ], $cfg['jwt_secret'], (int)$cfg['access_token_ttl']);

    $refresh = random_token(32);
    return [
        'access_token' => $access,
        'refresh_token' => $refresh,
        'access_expires_in' => (int)$cfg['access_token_ttl'],
    ];
}

function bearer_user(): ?array
{
    $header = $_SERVER['HTTP_AUTHORIZATION'] ?? $_SERVER['REDIRECT_HTTP_AUTHORIZATION'] ?? '';
    if (!preg_match('/Bearer\s+(\S+)/i', $header, $matches)) {
        return null;
    }
    try {
        $payload = JwtAuth::decode($matches[1], app_config()['jwt_secret']);
    } catch (Throwable $e) {
        return null;
    }
    if (($payload['type'] ?? '') !== 'access') {
        return null;
    }
    $user = fetch_user_by_id((int)$payload['sub']);
    if (!$user) {
        return null;
    }
    $user['session_id'] = (int)($payload['sid'] ?? 0);
    return $user;
}

function validate_active_session(array $user, ?string $deviceId = null): array
{
    $sessionId = (int)($user['session_id'] ?? 0);
    if ($sessionId <= 0) {
        return ['ok' => false, 'code' => 'session_revoked', 'message' => 'Invalid session'];
    }

    $stmt = db()->prepare('SELECT * FROM sessions WHERE id = ? AND user_id = ? LIMIT 1');
    $stmt->execute([$sessionId, (int)$user['id']]);
    $session = $stmt->fetch();
    if (!$session || !(int)$session['is_active']) {
        return ['ok' => false, 'code' => 'session_revoked', 'message' => 'Session ended'];
    }
    if ((int)$session['force_logout'] === 1) {
        return ['ok' => false, 'code' => 'session_revoked', 'message' => 'Force logout requested'];
    }
    if (strtotime((string)$session['expires_at']) < time()) {
        return ['ok' => false, 'code' => 'session_revoked', 'message' => 'Session expired'];
    }

    $timeout = (int)(setting('session_timeout', (string)app_config()['session_timeout']) ?? 3600);
    $lastSeen = strtotime((string)$session['last_seen_at']);
    if ($lastSeen + $timeout < time()) {
        db()->prepare('UPDATE sessions SET is_active = 0 WHERE id = ?')->execute([$sessionId]);
        return ['ok' => false, 'code' => 'session_revoked', 'message' => 'Session timed out'];
    }

    if ($user['status'] === 'banned') {
        return ['ok' => false, 'code' => 'banned', 'message' => 'Account banned'];
    }
    if ($user['status'] === 'disabled') {
        return ['ok' => false, 'code' => 'disabled', 'message' => 'Account disabled'];
    }

    $license = user_license((int)$user['id']);
    if (!license_is_valid($license)) {
        return ['ok' => false, 'code' => 'license_expired', 'message' => 'License expired or revoked'];
    }

    if ($deviceId && !device_is_authorized((int)$user['id'], $deviceId)) {
        return ['ok' => false, 'code' => 'device_mismatch', 'message' => 'Device not authorized'];
    }

    db()->prepare('UPDATE sessions SET last_seen_at = NOW() WHERE id = ?')->execute([$sessionId]);
    return ['ok' => true, 'session' => $session, 'license' => $license];
}

function create_user_session(
    int $userId,
    string $deviceId,
    ?string $pcName,
    ?string $userAgent
): array {
    $cfg = app_config();
    $refreshToken = random_token(32);
    $sessionToken = random_token(32);
    $expiresAt = date('Y-m-d H:i:s', time() + (int)$cfg['refresh_token_ttl']);

    if (!empty($cfg['single_session']) || setting('single_session', '1') === '1') {
        db()->prepare(
            'UPDATE sessions SET is_active = 0, force_logout = 1 WHERE user_id = ? AND is_active = 1'
        )->execute([$userId]);
    }

    $stmt = db()->prepare(
        'INSERT INTO sessions (user_id, session_token_hash, refresh_token_hash, device_id, pc_name, ip_address, user_agent, is_active, expires_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)'
    );
    $stmt->execute([
        $userId,
        hash_token($sessionToken),
        hash_token($refreshToken),
        $deviceId,
        $pcName,
        client_ip(),
        $userAgent ? substr($userAgent, 0, 255) : null,
        $expiresAt,
    ]);
    $sessionId = (int)db()->lastInsertId();
    upsert_device($userId, $deviceId, $pcName);

    $user = fetch_user_by_id($userId);
    $tokens = issue_tokens($userId, $sessionId, $user['role_name'] ?? 'team_member');
    $tokens['refresh_token'] = $refreshToken;
    $tokens['session_id'] = $sessionId;
    return $tokens;
}

function revoke_session(int $sessionId, bool $force = true): void
{
    db()->prepare(
        'UPDATE sessions SET is_active = 0, force_logout = ? WHERE id = ?'
    )->execute([$force ? 1 : 0, $sessionId]);
}

function revoke_all_user_sessions(int $userId): void
{
    db()->prepare(
        'UPDATE sessions SET is_active = 0, force_logout = 1 WHERE user_id = ? AND is_active = 1'
    )->execute([$userId]);
}
