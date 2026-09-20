<?php
declare(strict_types=1);

require_once __DIR__ . '/helpers.php';

function json_response(array $payload, int $status = 200): void
{
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    header('X-Content-Type-Options: nosniff');
    echo json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

function json_error(string $code, string $message, int $status = 400, array $extra = []): void
{
    json_response(array_merge(['ok' => false, 'code' => $code, 'message' => $message], $extra), $status);
}

function json_ok(array $payload = []): void
{
    json_response(array_merge(['ok' => true], $payload));
}

function read_json_body(): array
{
    $raw = file_get_contents('php://input') ?: '';
    $data = json_decode($raw, true);
    return is_array($data) ? $data : [];
}

function enforce_https(): void
{
    if (empty(app_config()['require_https'])) {
        return;
    }
    $https = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off')
        || (($_SERVER['HTTP_X_FORWARDED_PROTO'] ?? '') === 'https');
    if (!$https) {
        json_error('https_required', 'HTTPS is required', 403);
    }
}

function verify_app_api_key(): void
{
    $expected = app_config()['app_api_key'] ?? '';
    if ($expected === '') {
        return;
    }
    $provided = $_SERVER['HTTP_X_APP_KEY'] ?? '';
    if (!hash_equals($expected, $provided)) {
        json_error('invalid_api_key', 'Invalid application API key', 401);
    }
}

function rate_limit(string $bucket, int $maxHits, int $windowSeconds = 60): void
{
    $key = $bucket . ':' . client_ip();
    $stmt = db()->prepare('SELECT id, hits, window_start FROM rate_limits WHERE rate_key = ? LIMIT 1');
    $stmt->execute([$key]);
    $row = $stmt->fetch();
    $now = time();
    if (!$row) {
        db()->prepare('INSERT INTO rate_limits (rate_key, hits, window_start) VALUES (?, 1, FROM_UNIXTIME(?))')
            ->execute([$key, $now]);
        return;
    }
    $windowStart = strtotime((string)$row['window_start']);
    if ($now - $windowStart >= $windowSeconds) {
        db()->prepare('UPDATE rate_limits SET hits = 1, window_start = FROM_UNIXTIME(?) WHERE id = ?')
            ->execute([$now, $row['id']]);
        return;
    }
    if ((int)$row['hits'] >= $maxHits) {
        json_error('rate_limited', 'Too many requests. Try again later.', 429);
    }
    db()->prepare('UPDATE rate_limits SET hits = hits + 1 WHERE id = ?')->execute([$row['id']]);
}

function require_api_auth(): array
{
    enforce_https();
    verify_app_api_key();
    $user = bearer_user();
    if (!$user) {
        json_error('unauthorized', 'Missing or invalid access token', 401);
    }
    return $user;
}

function bootstrap_api(): void
{
    require_once __DIR__ . '/db.php';
    require_once __DIR__ . '/auth.php';
    enforce_https();
}

require_once __DIR__ . '/auth.php';
