<?php
declare(strict_types=1);

require_once dirname(__DIR__) . '/includes/db.php';
require_once dirname(__DIR__) . '/includes/middleware.php';

verify_app_api_key();
$body = read_json_body();
$refreshToken = trim((string)($body['refresh_token'] ?? ''));
$deviceId = trim((string)($body['device_id'] ?? ''));

if ($refreshToken === '') {
    json_error('invalid', 'Refresh token required');
}

$stmt = db()->prepare(
    'SELECT s.*, u.status AS user_status, r.name AS role_name
     FROM sessions s
     JOIN users u ON u.id = s.user_id
     JOIN roles r ON r.id = u.role_id
     WHERE s.refresh_token_hash = ? AND s.is_active = 1
     LIMIT 1'
);
$stmt->execute([hash_token($refreshToken)]);
$session = $stmt->fetch();

if (!$session) {
    json_error('session_revoked', 'Refresh token invalid', 401);
}
if (strtotime((string)$session['expires_at']) < time()) {
    revoke_session((int)$session['id']);
    json_error('session_revoked', 'Refresh token expired', 401);
}
if ($session['user_status'] !== 'active') {
    json_error($session['user_status'], 'Account not active', 403);
}

$license = user_license((int)$session['user_id']);
if (!license_is_valid($license)) {
    json_error('license_expired', 'License expired', 403);
}

if ($deviceId && $session['device_id'] && $session['device_id'] !== $deviceId) {
    json_error('device_mismatch', 'Device mismatch', 403);
}

$tokens = issue_tokens((int)$session['user_id'], (int)$session['id'], $session['role_name']);
db()->prepare('UPDATE sessions SET last_seen_at = NOW() WHERE id = ?')->execute([(int)$session['id']]);

json_ok([
    'access_token' => $tokens['access_token'],
    'access_expires_in' => $tokens['access_expires_in'],
]);
