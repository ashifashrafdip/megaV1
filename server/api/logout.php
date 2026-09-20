<?php
declare(strict_types=1);

require_once dirname(__DIR__) . '/includes/db.php';
require_once dirname(__DIR__) . '/includes/middleware.php';

$user = require_api_auth();
$body = read_json_body();
$deviceId = trim((string)($body['device_id'] ?? ''));

$check = validate_active_session($user, $deviceId ?: null);
if (!$check['ok']) {
    json_error($check['code'], $check['message'], 403);
}

$sessionId = (int)$user['session_id'];
revoke_session($sessionId, false);
log_activity((int)$user['id'], 'logout', $deviceId ?: null, null);

json_ok(['message' => 'Logged out']);
