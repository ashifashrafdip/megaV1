<?php
declare(strict_types=1);

require_once dirname(__DIR__) . '/includes/db.php';
require_once dirname(__DIR__) . '/includes/middleware.php';

$user = require_api_auth();
$check = validate_active_session($user);
if (!$check['ok']) {
    json_error($check['code'], $check['message'], 403);
}

$license = user_license((int)$user['id']);
$valid = license_is_valid($license);

json_ok([
    'valid' => $valid,
    'license' => $license ? [
        'status' => $license['status'],
        'expires_at' => $license['expires_at'],
        'days_left' => $license['days_left'],
        'is_trial' => (bool)$license['is_trial'],
    ] : ['status' => 'none', 'valid' => true],
]);
