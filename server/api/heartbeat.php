<?php
declare(strict_types=1);

require_once dirname(__DIR__) . '/includes/db.php';
require_once dirname(__DIR__) . '/includes/middleware.php';

$user = require_api_auth();
$body = read_json_body();
$deviceId = trim((string)($body['device_id'] ?? ''));

$check = validate_active_session($user, $deviceId ?: null);
if (!$check['ok']) {
    log_activity((int)$user['id'], 'heartbeat_fail', $deviceId ?: null, null, $check['code']);
    db()->prepare(
        'INSERT INTO heartbeat_logs (user_id, session_id, status, ip_address, device_id)
         VALUES (?, ?, ?, ?, ?)'
    )->execute([
        (int)$user['id'],
        (int)($user['session_id'] ?? 0),
        $check['code'],
        client_ip(),
        $deviceId ?: null,
    ]);
    json_error($check['code'], $check['message'], 403);
}

if ($deviceId) {
    upsert_device((int)$user['id'], $deviceId, $body['pc_name'] ?? null);
}

db()->prepare(
    'INSERT INTO heartbeat_logs (user_id, session_id, status, ip_address, device_id)
     VALUES (?, ?, ?, ?, ?)'
)->execute([
    (int)$user['id'],
    (int)$user['session_id'],
    'active',
    client_ip(),
    $deviceId ?: null,
]);

$license = $check['license'] ?? user_license((int)$user['id']);

json_ok([
    'status' => 'active',
    'user' => public_user($user),
    'license' => $license ? [
        'status' => $license['status'],
        'expires_at' => $license['expires_at'],
        'days_left' => $license['days_left'],
    ] : null,
    'heartbeat_interval' => (int)(setting('heartbeat_interval', '45') ?? 45),
    'server_time' => date('c'),
]);
