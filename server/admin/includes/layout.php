<?php
declare(strict_types=1);

require_once dirname(__DIR__, 2) . '/includes/db.php';
require_once dirname(__DIR__, 2) . '/includes/csrf.php';

function admin_session_start(): void
{
    if (session_status() !== PHP_SESSION_ACTIVE) {
        session_set_cookie_params([
            'lifetime' => 0,
            'path' => '/',
            'httponly' => true,
            'samesite' => 'Strict',
        ]);
        session_start();
    }
}

function admin_user(): ?array
{
    admin_session_start();
    if (empty($_SESSION['admin_user_id'])) {
        return null;
    }
    return fetch_user_by_id((int)$_SESSION['admin_user_id']);
}

function require_admin(array $allowedRoles = ['super_admin', 'admin']): array
{
    $user = admin_user();
    if (!$user) {
        header('Location: login.php');
        exit;
    }
    if (!in_array($user['role_name'] ?? '', $allowedRoles, true)) {
        http_response_code(403);
        echo 'Access denied';
        exit;
    }
    return $user;
}

function require_super_admin(): array
{
    return require_admin(['super_admin']);
}

function admin_redirect(string $path): void
{
    header('Location: ' . $path);
    exit;
}

function flash_set(string $type, string $message): void
{
    admin_session_start();
    $_SESSION['flash'] = ['type' => $type, 'message' => $message];
}

function flash_get(): ?array
{
    admin_session_start();
    if (empty($_SESSION['flash'])) {
        return null;
    }
    $flash = $_SESSION['flash'];
    unset($_SESSION['flash']);
    return $flash;
}

function render_layout(string $title, string $content, array $user, string $active = ''): void
{
    $role = $user['role_name'] ?? '';
    $isSuper = $role === 'super_admin';
    $flash = flash_get();
    ?>
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title><?= e($title) ?> — Automation Admin</title>
  <link rel="stylesheet" href="assets/style.css">
</head>
<body>
<div class="layout">
  <aside class="sidebar">
    <h1>Automation Hub</h1>
    <nav>
      <a href="index.php" class="<?= $active === 'dashboard' ? 'active' : '' ?>">Dashboard</a>
      <a href="users.php" class="<?= $active === 'users' ? 'active' : '' ?>">Users</a>
      <a href="sessions.php" class="<?= $active === 'sessions' ? 'active' : '' ?>">Sessions</a>
      <a href="devices.php" class="<?= $active === 'devices' ? 'active' : '' ?>">Devices</a>
      <?php if ($isSuper): ?>
      <a href="logs.php" class="<?= $active === 'logs' ? 'active' : '' ?>">Activity Logs</a>
      <a href="link_logs.php" class="<?= $active === 'link_logs' ? 'active' : '' ?>">Link Logs</a>
      <a href="settings.php" class="<?= $active === 'settings' ? 'active' : '' ?>">Settings</a>
      <?php endif; ?>
      <a href="logout.php">Logout</a>
    </nav>
  </aside>
  <main class="main">
    <div class="header">
      <h2><?= e($title) ?></h2>
      <div><?= e($user['username']) ?> (<?= e($user['role_label'] ?? $role) ?>)</div>
    </div>
    <?php if ($flash): ?>
      <div class="alert alert-<?= e($flash['type']) ?>"><?= e($flash['message']) ?></div>
    <?php endif; ?>
    <?= $content ?>
  </main>
</div>
</body>
</html>
    <?php
}
