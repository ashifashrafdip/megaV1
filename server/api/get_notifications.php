<?php
declare(strict_types=1);

require_once dirname(__DIR__) . '/includes/db.php';
require_once dirname(__DIR__) . '/includes/middleware.php';

$user = require_api_auth();
$stmt = db()->prepare(
    'SELECT id, title, message, is_read, created_at
     FROM notifications
     WHERE user_id IS NULL OR user_id = ?
     ORDER BY created_at DESC
     LIMIT 20'
);
$stmt->execute([(int)$user['id']]);
json_ok(['notifications' => $stmt->fetchAll()]);
