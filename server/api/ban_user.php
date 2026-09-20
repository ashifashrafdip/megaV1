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
$ban = !empty($body['ban']);

if ($targetUserId <= 0) {
    json_error('invalid', 'user_id required');
}

$target = fetch_user_by_id($targetUserId);
if (!$target) {
    json_error('not_found', 'User not found', 404);
}

if (($user['role_name'] ?? '') === 'admin' && ($target['role_name'] ?? '') !== 'team_member') {
    json_error('forbidden', 'Admins can only manage team members', 403);
}

$newStatus = $ban ? 'banned' : 'active';
db()->prepare('UPDATE users SET status = ? WHERE id = ?')->execute([$newStatus, $targetUserId]);
if ($ban) {
    revoke_all_user_sessions($targetUserId);
}

log_activity((int)$user['id'], $ban ? 'ban_user' : 'unban_user', null, null, 'user_id=' . $targetUserId);
json_ok(['user_id' => $targetUserId, 'status' => $newStatus]);
