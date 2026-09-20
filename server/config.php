<?php
/**
 * Production config — update before deploy.
 * Default credentials are for local XAMPP testing only.
 */
return [
    'db' => [
        'host' => 'localhost',
        'name' => 'orionuxy_auto',
        'user' => 'orionuxy_auto',
        'pass' => 'ashifQW!@',
        'charset' => 'utf8mb4',
    ],
    'jwt_secret' => 'dev_jwt_secret_change_before_production_use_64chars_minimum_abc123',
    'app_api_key' => 'dev-desktop-app-key-change-me',
    'access_token_ttl' => 900,
    'refresh_token_ttl' => 604800,
    'session_timeout' => 3600,
    'heartbeat_interval' => 45,
    'offline_grace_seconds' => 300,
    'single_session' => true,
    'require_https' => true,
    'login_rate_limit' => 5,
    'timezone' => 'UTC',
];
