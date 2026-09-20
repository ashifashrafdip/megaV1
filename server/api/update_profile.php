<?php
declare(strict_types=1);

require_once dirname(__DIR__) . '/includes/db.php';
require_once dirname(__DIR__) . '/includes/middleware.php';

$user = require_api_auth();
$check = validate_active_session($user);
if (!$check['ok']) {
    json_error($check['code'], $check['message'], 403);
}

$body = read_json_body();
$displayName = trim((string)($body['display_name'] ?? ''));
$email = trim((string)($body['email'] ?? ''));

if ($displayName === '' && $email === '') {
    json_error('invalid', 'Nothing to update');
}

$fields = [];
$params = [];
if ($displayName !== '') {
    $fields[] = 'display_name = ?';
    $params[] = $displayName;
}
if ($email !== '') {
    $fields[] = 'email = ?';
    $params[] = $email;
}
$params[] = (int)$user['id'];

db()->prepare('UPDATE users SET ' . implode(', ', $fields) . ' WHERE id = ?')->execute($params);
log_activity((int)$user['id'], 'profile_update');

$updated = fetch_user_by_id((int)$user['id']);
json_ok(['user' => public_user($updated)]);
