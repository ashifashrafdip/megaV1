<?php
declare(strict_types=1);

require_once dirname(__DIR__) . '/includes/db.php';
require_once dirname(__DIR__) . '/includes/middleware.php';

$user = require_api_auth();
if (!in_array($user['role_name'] ?? '', ['super_admin', 'admin'], true)) {
    json_error('forbidden', 'Admin access required', 403);
}

$timeout = (int)(setting('session_timeout', '3600') ?? 3600);
$stmt = db()->query(
    "SELECT s.id, s.user_id, s.device_id, s.pc_name, s.ip_address, s.last_seen_at, u.username, u.status
     FROM sessions s
     JOIN users u ON u.id = s.user_id
     WHERE s.is_active = 1 AND s.last_seen_at >= DATE_SUB(NOW(), INTERVAL {$timeout} SECOND)
     ORDER BY s.last_seen_at DESC"
);
$rows = $stmt->fetchAll();
json_ok(['online_users' => $rows, 'count' => count($rows)]);
