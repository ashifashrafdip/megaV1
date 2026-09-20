<?php
/**
 * Copy to config.php and fill in your values.
 * On cPanel, keep config.php outside public_html if possible and adjust paths.
 */
return [
    'db' => [
        'host' => 'localhost',
        'name' => 'your_database',
        'user' => 'your_db_user',
        'pass' => 'your_db_password',
        'charset' => 'utf8mb4',
    ],
    'jwt_secret' => 'CHANGE_ME_TO_A_LONG_RANDOM_STRING_64_CHARS_MIN',
    'app_api_key' => 'CHANGE_ME_DESKTOP_APP_API_KEY',
    'access_token_ttl' => 900,       // 15 minutes
    'refresh_token_ttl' => 604800,   // 7 days
    'session_timeout' => 3600,       // inactivity seconds
    'heartbeat_interval' => 45,
    'offline_grace_seconds' => 300,  // Phase 2
    'single_session' => true,        // reject second login if active session exists
    'require_https' => true,
    'login_rate_limit' => 5,         // per minute per IP
    'timezone' => 'UTC',
];
