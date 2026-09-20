<?php
declare(strict_types=1);

function app_config(): array
{
    static $config = null;
    if ($config === null) {
        $path = dirname(__DIR__) . '/config.php';
        if (!is_file($path)) {
            http_response_code(500);
            header('Content-Type: application/json');
            echo json_encode(['ok' => false, 'message' => 'Server config missing']);
            exit;
        }
        $config = require $path;
        date_default_timezone_set($config['timezone'] ?? 'UTC');
    }
    return $config;
}

function db(): PDO
{
    static $pdo = null;
    if ($pdo instanceof PDO) {
        return $pdo;
    }
    $cfg = app_config()['db'];
    $dsn = sprintf(
        'mysql:host=%s;dbname=%s;charset=%s',
        $cfg['host'],
        $cfg['name'],
        $cfg['charset'] ?? 'utf8mb4'
    );
    $pdo = new PDO($dsn, $cfg['user'], $cfg['pass'], [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_EMULATE_PREPARES => false,
    ]);
    return $pdo;
}

function setting(string $key, ?string $default = null): ?string
{
    static $cache = [];
    if (array_key_exists($key, $cache)) {
        return $cache[$key];
    }
    $stmt = db()->prepare('SELECT setting_value FROM settings WHERE setting_key = ? LIMIT 1');
    $stmt->execute([$key]);
    $row = $stmt->fetch();
    $value = $row ? (string)$row['setting_value'] : $default;
    $cache[$key] = $value;
    return $value;
}

function e(?string $value): string
{
    return htmlspecialchars((string)$value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

function client_ip(): string
{
    foreach (['HTTP_CF_CONNECTING_IP', 'HTTP_X_FORWARDED_FOR', 'REMOTE_ADDR'] as $key) {
        if (!empty($_SERVER[$key])) {
            $ip = trim(explode(',', (string)$_SERVER[$key])[0]);
            if (filter_var($ip, FILTER_VALIDATE_IP)) {
                return $ip;
            }
        }
    }
    return '0.0.0.0';
}

function random_token(int $bytes = 32): string
{
    return bin2hex(random_bytes($bytes));
}

function hash_token(string $token): string
{
    return hash('sha256', $token);
}

function log_activity(
    ?int $userId,
    string $action,
    ?string $deviceId = null,
    ?string $pcName = null,
    ?string $details = null
): void {
    $stmt = db()->prepare(
        'INSERT INTO activity_logs (user_id, action, ip_address, device_id, pc_name, details)
         VALUES (?, ?, ?, ?, ?, ?)'
    );
    $stmt->execute([$userId, $action, client_ip(), $deviceId, $pcName, $details]);
}

function log_login_history(
    ?int $userId,
    ?string $username,
    bool $success,
    ?string $deviceId,
    ?string $pcName,
    ?string $reason
): void {
    $stmt = db()->prepare(
        'INSERT INTO login_history (user_id, username, success, ip_address, device_id, pc_name, reason)
         VALUES (?, ?, ?, ?, ?, ?, ?)'
    );
    $stmt->execute([
        $userId,
        $username,
        $success ? 1 : 0,
        client_ip(),
        $deviceId,
        $pcName,
        $reason,
    ]);
}

function user_license(int $userId): ?array
{
    $stmt = db()->prepare('SELECT * FROM licenses WHERE user_id = ? LIMIT 1');
    $stmt->execute([$userId]);
    $license = $stmt->fetch();
    if (!$license) {
        return null;
    }
    $expiresAt = $license['expires_at'] ?? null;
    $daysLeft = null;
    if ($expiresAt) {
        $daysLeft = (int)floor((strtotime($expiresAt) - time()) / 86400);
    }
    $license['days_left'] = $daysLeft;
    $license['is_expired'] = $expiresAt ? (strtotime($expiresAt) < time()) : false;
    return $license;
}

function license_is_valid(?array $license): bool
{
    if (!$license) {
        return true;
    }
    if (in_array($license['status'], ['inactive', 'revoked'], true)) {
        return false;
    }
    if (!empty($license['is_expired'])) {
        return false;
    }
    return true;
}

function fetch_user_by_id(int $userId): ?array
{
    $stmt = db()->prepare(
        'SELECT u.*, r.name AS role_name, r.label AS role_label
         FROM users u
         JOIN roles r ON r.id = u.role_id
         WHERE u.id = ?
         LIMIT 1'
    );
    $stmt->execute([$userId]);
    $user = $stmt->fetch();
    return $user ?: null;
}

function public_user(array $user): array
{
    return [
        'id' => (int)$user['id'],
        'username' => $user['username'],
        'display_name' => $user['display_name'] ?? $user['username'],
        'role' => $user['role_name'] ?? 'team_member',
        'status' => $user['status'],
        'last_login_at' => $user['last_login_at'],
    ];
}

function upsert_device(int $userId, string $deviceId, ?string $pcName, ?string $fingerprintHash = null): void
{
    $stmt = db()->prepare(
        'INSERT INTO devices (user_id, device_id, pc_name, fingerprint_hash, is_authorized, last_seen_at)
         VALUES (?, ?, ?, ?, 1, NOW())
         ON DUPLICATE KEY UPDATE pc_name = VALUES(pc_name), last_seen_at = NOW(), fingerprint_hash = COALESCE(VALUES(fingerprint_hash), fingerprint_hash)'
    );
    $stmt->execute([$userId, $deviceId, $pcName, $fingerprintHash]);
}

function device_is_authorized(int $userId, string $deviceId): bool
{
    $stmt = db()->prepare(
        'SELECT is_authorized FROM devices WHERE user_id = ? AND device_id = ? LIMIT 1'
    );
    $stmt->execute([$userId, $deviceId]);
    $row = $stmt->fetch();
    if (!$row) {
        return true;
    }
    return (int)$row['is_authorized'] === 1;
}
