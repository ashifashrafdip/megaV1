<?php
declare(strict_types=1);

require_once dirname(__DIR__) . '/includes/db.php';
require_once dirname(__DIR__) . '/includes/middleware.php';

$user = require_api_auth();
$body = read_json_body();
$targetUserId = (int)($body['user_id'] ?? 0);
$deviceId = trim((string)($body['device_id'] ?? ''));

if ($targetUserId <= 0 || $deviceId === '') {
    json_error('invalid', 'user_id and device_id required');
}

if (($user['role_name'] ?? '') !== 'super_admin') {
    json_error('forbidden', 'Super admin only', 403);
}

db()->prepare(
    'UPDATE devices SET is_authorized = 1, last_seen_at = NOW() WHERE user_id = ? AND device_id = ?'
)->execute([$targetUserId, $deviceId]);

log_activity((int)$user['id'], 'device_reset', $deviceId, null, 'user_id=' . $targetUserId);
json_ok(['reset' => true]);
