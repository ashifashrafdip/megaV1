<?php
declare(strict_types=1);

require_once dirname(__DIR__) . '/includes/db.php';
require_once dirname(__DIR__) . '/includes/middleware.php';

$user = require_api_auth();
$body = read_json_body();
$action = trim((string)($body['action'] ?? 'event'));
$deviceId = trim((string)($body['device_id'] ?? ''));
$pcName = trim((string)($body['pc_name'] ?? ''));
$details = isset($body['details']) ? json_encode($body['details']) : null;

log_activity((int)$user['id'], $action, $deviceId ?: null, $pcName ?: null, $details);
json_ok(['logged' => true]);
