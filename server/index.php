<?php
declare(strict_types=1);

header('Content-Type: application/json; charset=utf-8');
echo json_encode([
    'ok' => true,
    'service' => 'Automation Hub Auth Server',
    'status' => 'operational',
    'version' => '1.0.0',
    'admin_panel' => '/admin/login.php',
    'timestamp' => time(),
], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES);
