<?php
/**
 * One-time script: create a default team user for desktop login.
 * DELETE this file after use.
 *
 * Usage: https://automation.orionu2.xyz/install/create_team_user.php
 */
require_once dirname(__DIR__) . '/includes/db.php';

$username = 'team1';
$password = 'Team@12345';
$roleId = 3; // team_member
$expires = date('Y-m-d H:i:s', strtotime('+365 days'));

$stmt = db()->prepare('SELECT id FROM users WHERE username = ? LIMIT 1');
$stmt->execute([$username]);
if ($stmt->fetch()) {
    echo "User {$username} already exists.\n";
    exit;
}

$hash = password_hash($password, PASSWORD_BCRYPT);
db()->prepare(
    'INSERT INTO users (username, password_hash, role_id, status, display_name) VALUES (?, ?, ?, ?, ?)'
)->execute([$username, $hash, $roleId, 'active', 'Team Member 1']);

$userId = (int)db()->lastInsertId();
db()->prepare(
    'INSERT INTO licenses (user_id, status, expires_at) VALUES (?, ?, ?)'
)->execute([$userId, 'active', $expires]);

echo "Created team user:\n";
echo "  Username: {$username}\n";
echo "  Password: {$password}\n";
echo "  License expires: {$expires}\n";
echo "\nDELETE install/create_team_user.php after use.\n";
