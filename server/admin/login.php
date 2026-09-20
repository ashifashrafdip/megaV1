<?php
declare(strict_types=1);

require_once __DIR__ . '/includes/layout.php';
admin_session_start();

if (admin_user()) {
    admin_redirect('index.php');
}

$error = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!csrf_verify($_POST['csrf_token'] ?? null)) {
        $error = 'Invalid CSRF token';
    } else {
        $username = trim((string)($_POST['username'] ?? ''));
        $password = (string)($_POST['password'] ?? '');
        $stmt = db()->prepare(
            'SELECT u.*, r.name AS role_name, r.label AS role_label
             FROM users u JOIN roles r ON r.id = u.role_id
             WHERE u.username = ? LIMIT 1'
        );
        $stmt->execute([$username]);
        $user = $stmt->fetch();
        if (!$user || !password_verify($password, $user['password_hash'])) {
            $error = 'Invalid credentials';
            log_login_history(null, $username, false, null, null, 'admin_login_failed');
        } elseif (!in_array($user['role_name'], ['super_admin', 'admin'], true)) {
            $error = 'Admin access only';
        } elseif ($user['status'] !== 'active') {
            $error = 'Account is ' . $user['status'];
        } else {
            $_SESSION['admin_user_id'] = (int)$user['id'];
            log_activity((int)$user['id'], 'admin_login');
            admin_redirect('index.php');
        }
    }
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Admin Login</title>
  <link rel="stylesheet" href="assets/style.css">
</head>
<body class="login-page">
  <div class="login-box">
    <h1>Admin Panel</h1>
    <?php if ($error): ?><div class="alert alert-error"><?= e($error) ?></div><?php endif; ?>
    <form method="post">
      <?= csrf_field() ?>
      <div class="form-row">
        <label>Username</label>
        <input name="username" required autofocus>
      </div>
      <div class="form-row">
        <label>Password</label>
        <input name="password" type="password" required>
      </div>
      <button class="btn" type="submit" style="width:100%;margin-top:8px;">Login</button>
    </form>
  </div>
</body>
</html>
