<?php
declare(strict_types=1);

/**
 * Run once after importing schema.sql to set the super admin password.
 * DELETE this file after setup on production.
 */
require_once dirname(__DIR__) . '/includes/db.php';

$password = 'Admin@12345';
$hash = password_hash($password, PASSWORD_BCRYPT);

db()->prepare(
    "UPDATE users SET password_hash = ? WHERE username = 'superadmin'"
)->execute([$hash]);

echo "Super admin password set to: {$password}\n";
echo "DELETE install/setup.php after use.\n";
