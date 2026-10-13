<?php
declare(strict_types=1);

error_reporting(E_ALL);
ini_set('display_errors', '1');

header('Content-Type: application/json; charset=utf-8');

$key = $_GET['key'] ?? '';
if ($key !== 'mega_auth_setup_2026') {
    http_response_code(403);
    echo json_encode(['ok' => false, 'error' => 'Invalid setup key']);
    exit;
}

require_once dirname(__DIR__) . '/includes/db.php';

try {
    $pdo = db();
    $sqlFile = __DIR__ . '/schema.sql';
    if (!file_exists($sqlFile)) {
        throw new RuntimeException("schema.sql not found at $sqlFile");
    }

    $sql = file_get_contents($sqlFile);
    
    // Execute DDL statements
    $pdo->exec("SET FOREIGN_KEY_CHECKS = 0;");
    
    // Split statements by semicolon
    $statements = array_filter(array_map('trim', explode(';', $sql)));
    $executed = 0;
    foreach ($statements as $stmt) {
        if ($stmt !== '' && !preg_match('/^--/', $stmt)) {
            $pdo->exec($stmt);
            $executed++;
        }
    }
    
    // Ensure Super Admin Password is set to Admin@12345
    $adminPass = 'Admin@12345';
    $hash = password_hash($adminPass, PASSWORD_BCRYPT);
    $checkUser = $pdo->query("SELECT id FROM users WHERE username = 'superadmin'")->fetch();
    if ($checkUser) {
        $pdo->prepare("UPDATE users SET password_hash = ?, status = 'active', role_id = 1 WHERE username = 'superadmin'")->execute([$hash]);
        $adminId = (int)$checkUser['id'];
    } else {
        $stmt = $pdo->prepare("INSERT INTO users (username, password_hash, role_id, status, display_name) VALUES ('superadmin', ?, 1, 'active', 'Super Admin')");
        $stmt->execute([$hash]);
        $adminId = (int)$pdo->lastInsertId();
    }

    // Ensure license for superadmin
    $checkLic = $pdo->query("SELECT id FROM licenses WHERE user_id = $adminId")->fetch();
    if ($checkLic) {
        $pdo->exec("UPDATE licenses SET status = 'active', expires_at = '2099-12-31 23:59:59', is_trial = 0 WHERE user_id = $adminId");
    } else {
        $pdo->exec("INSERT INTO licenses (user_id, status, is_trial, expires_at) VALUES ($adminId, 'active', 0, '2099-12-31 23:59:59')");
    }

    // Ensure multi-device settings
    $pdo->exec("INSERT INTO settings (setting_key, setting_value) VALUES ('single_session', '0') ON DUPLICATE KEY UPDATE setting_value = '0'");
    $pdo->exec("INSERT INTO settings (setting_key, setting_value) VALUES ('heartbeat_interval', '45') ON DUPLICATE KEY UPDATE setting_value = '45'");

    $pdo->exec("SET FOREIGN_KEY_CHECKS = 1;");

    // Fetch created tables
    $tables = $pdo->query("SHOW TABLES")->fetchAll(PDO::FETCH_COLUMN);

    echo json_encode([
        'ok' => true,
        'message' => 'Schema migration completed successfully!',
        'statements_executed' => $executed,
        'tables_created' => $tables,
        'superadmin_user' => 'superadmin',
        'superadmin_password' => $adminPass,
        'license_expires' => '2099-12-31 23:59:59',
    ], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES);

} catch (Throwable $e) {
    http_response_code(500);
    echo json_encode([
        'ok' => false,
        'error' => $e->getMessage(),
        'trace' => $e->getTraceAsString(),
    ], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES);
}
