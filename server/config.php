<?php
/**
 * Production configuration for server.ashifashraf.com
 */
return [
    'db' => [
        'host' => 'localhost',
        'name' => 'ashifash_auth',
        'user' => 'ashifash',
        'pass' => 'y40V*2cW#FQd7r',
        'charset' => 'utf8mb4',
    ],
    'jwt_secret' => 'dev_jwt_secret_change_before_production_use_64chars_minimum_abc123',
    'app_api_key' => 'dev-desktop-app-key-change-me',
    'access_token_ttl' => 900,
    'refresh_token_ttl' => 604800,
    'session_timeout' => 86400,
    'heartbeat_interval' => 45,
    'offline_grace_seconds' => 300,
    'single_session' => false,
    'require_https' => false,
    'login_rate_limit' => 20,
    'timezone' => 'UTC',
];
