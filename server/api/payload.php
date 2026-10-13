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

log_activity((int)$user['id'], 'fetch_payload', $deviceId ?: null, null, 'Authorized payload delivery');

$payloadFile = dirname(__DIR__) . '/includes/payload_data.json';
$payload = file_exists($payloadFile) ? json_decode((string)file_get_contents($payloadFile), true) : [];

json_ok([
    'payload' => $payload ?: (object)[],
    'timestamp' => (int)round(microtime(true) * 1000),
]);
