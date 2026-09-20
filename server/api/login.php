<?php
declare(strict_types=1);

require_once dirname(__DIR__) . '/includes/db.php';
require_once dirname(__DIR__) . '/includes/middleware.php';

verify_app_api_key();
rate_limit('login', (int)app_config()['login_rate_limit'], 60);

$body = read_json_body();
$username = trim((string)($body['username'] ?? ''));
$password = (string)($body['password'] ?? '');
$deviceId = trim((string)($body['device_id'] ?? ''));
$pcName = trim((string)($body['pc_name'] ?? ''));

if ($username === '' || $password === '') {
    json_error('invalid', 'Username and password are required');
}
if ($deviceId === '') {
    json_error('invalid', 'Device ID is required');
}

$stmt = db()->prepare(
    'SELECT u.*, r.name AS role_name, r.label AS role_label
     FROM users u
     JOIN roles r ON r.id = u.role_id
     WHERE u.username = ?
     LIMIT 1'
);
$stmt->execute([$username]);
$user = $stmt->fetch();

if (!$user || !password_verify($password, $user['password_hash'])) {
    log_login_history($user ? (int)$user['id'] : null, $username, false, $deviceId, $pcName, 'invalid_credentials');
    json_error('invalid', 'Invalid username or password', 401);
}

if ($user['status'] === 'banned') {
    log_login_history((int)$user['id'], $username, false, $deviceId, $pcName, 'banned');
    json_error('banned', 'Account is banned', 403);
}
if ($user['status'] === 'disabled') {
    log_login_history((int)$user['id'], $username, false, $deviceId, $pcName, 'disabled');
    json_error('disabled', 'Account is disabled', 403);
}

$license = user_license((int)$user['id']);
if (!license_is_valid($license)) {
    log_login_history((int)$user['id'], $username, false, $deviceId, $pcName, 'license_expired');
    json_error('license_expired', 'License expired or inactive', 403);
}

if (!device_is_authorized((int)$user['id'], $deviceId)) {
    log_login_history((int)$user['id'], $username, false, $deviceId, $pcName, 'device_unauthorized');
    json_error('device_mismatch', 'Device is not authorized for this account', 403);
}

$singleSession = !empty(app_config()['single_session']) || setting('single_session', '1') === '1';
if ($singleSession) {
    $activeStmt = db()->prepare(
        'SELECT id FROM sessions WHERE user_id = ? AND is_active = 1 AND expires_at > NOW() LIMIT 1'
    );
    $activeStmt->execute([(int)$user['id']]);
    if ($activeStmt->fetch()) {
        log_login_history((int)$user['id'], $username, false, $deviceId, $pcName, 'session_active');
        json_error('session_active', 'Account is already active on another device', 409);
    }
}

$tokens = create_user_session(
    (int)$user['id'],
    $deviceId,
    $pcName,
    $_SERVER['HTTP_USER_AGENT'] ?? null
);

db()->prepare('UPDATE users SET last_login_at = NOW(), last_login_ip = ? WHERE id = ?')
    ->execute([client_ip(), (int)$user['id']]);

log_login_history((int)$user['id'], $username, true, $deviceId, $pcName, null);
log_activity((int)$user['id'], 'login', $deviceId, $pcName);

json_ok([
    'access_token' => $tokens['access_token'],
    'refresh_token' => $tokens['refresh_token'],
    'access_expires_in' => $tokens['access_expires_in'],
    'user' => public_user($user),
    'license' => $license ? [
        'status' => $license['status'],
        'expires_at' => $license['expires_at'],
        'days_left' => $license['days_left'],
        'is_trial' => (bool)$license['is_trial'],
    ] : null,
    'heartbeat_interval' => (int)(setting('heartbeat_interval', (string)app_config()['heartbeat_interval']) ?? 45),
]);
