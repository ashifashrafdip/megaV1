<?php
declare(strict_types=1);

require_once dirname(__DIR__) . '/includes/db.php';
require_once dirname(__DIR__) . '/includes/middleware.php';

$user = require_api_auth();
$body = read_json_body();
$url = trim((string)($body['url'] ?? ''));
$browser = trim((string)($body['browser'] ?? 'adspower'));
$deviceId = trim((string)($body['device_id'] ?? ''));

if ($url === '') {
    json_error('invalid', 'URL required');
}

$stmt = db()->prepare(
    'INSERT INTO link_logs (user_id, url, browser, device_id) VALUES (?, ?, ?, ?)'
);
$stmt->execute([(int)$user['id'], $url, $browser, $deviceId ?: null]);
json_ok(['logged' => true]);
