<?php
declare(strict_types=1);

require_once dirname(__DIR__) . '/includes/db.php';
require_once dirname(__DIR__) . '/includes/middleware.php';

$user = require_api_auth();
if (!in_array($user['role_name'] ?? '', ['super_admin', 'admin'], true)) {
    json_error('forbidden', 'Admin access required', 403);
}

$body = read_json_body();
$targetUserId = (int)($body['user_id'] ?? 0);
$sessionId = (int)($body['session_id'] ?? 0);

if ($sessionId > 0) {
    revoke_session($sessionId);
    log_activity((int)$user['id'], 'force_logout', null, null, 'session_id=' . $sessionId);
    json_ok(['forced' => true, 'session_id' => $sessionId]);
}

if ($targetUserId > 0) {
    revoke_all_user_sessions($targetUserId);
    log_activity((int)$user['id'], 'force_logout', null, null, 'user_id=' . $targetUserId);
    json_ok(['forced' => true, 'user_id' => $targetUserId]);
}

json_error('invalid', 'session_id or user_id required');
