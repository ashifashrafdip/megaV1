<?php
declare(strict_types=1);

require_once __DIR__ . '/includes/layout.php';
$user = require_admin();
$isSuper = ($user['role_name'] ?? '') === 'super_admin';

if ($_SERVER['REQUEST_METHOD'] === 'POST' && csrf_verify($_POST['csrf_token'] ?? null)) {
    $action = $_POST['action'] ?? '';
    $userId = (int)($_POST['user_id'] ?? 0);

    if ($action === 'create') {
        $username = trim((string)($_POST['username'] ?? ''));
        $password = (string)($_POST['password'] ?? '');
        $roleId = (int)($_POST['role_id'] ?? 3);
        $expires = trim((string)($_POST['expires_at'] ?? ''));

        if ($username && strlen($password) >= 8) {
            if (!$isSuper && $roleId !== 3) {
                flash_set('error', 'Admins can only create team members');
            } else {
                $hash = password_hash($password, PASSWORD_BCRYPT);
                db()->prepare(
                    'INSERT INTO users (username, password_hash, role_id, status) VALUES (?, ?, ?, ?)'
                )->execute([$username, $hash, $roleId, 'active']);
                $newId = (int)db()->lastInsertId();
                if ($expires) {
                    db()->prepare(
                        'INSERT INTO licenses (user_id, status, expires_at) VALUES (?, ?, ?)'
                    )->execute([$newId, 'active', $expires]);
                } else {
                    db()->prepare(
                        'INSERT INTO licenses (user_id, status) VALUES (?, ?)'
                    )->execute([$newId, 'active']);
                }
                log_activity((int)$user['id'], 'user_create', null, null, 'user_id=' . $newId);
                flash_set('success', 'User created');
            }
        } else {
            flash_set('error', 'Username and password (8+ chars) required');
        }
    } elseif ($userId > 0) {
        $target = fetch_user_by_id($userId);
        if (!$target) {
            flash_set('error', 'User not found');
        } elseif (!$isSuper && ($target['role_name'] ?? '') !== 'team_member') {
            flash_set('error', 'Cannot manage this user');
        } else {
            switch ($action) {
                case 'ban':
                    db()->prepare("UPDATE users SET status = 'banned' WHERE id = ?")->execute([$userId]);
                    revoke_all_user_sessions($userId);
                    log_activity((int)$user['id'], 'ban_user', null, null, 'user_id=' . $userId);
                    flash_set('success', 'User banned');
                    break;
                case 'unban':
                    db()->prepare("UPDATE users SET status = 'active' WHERE id = ?")->execute([$userId]);
                    log_activity((int)$user['id'], 'unban_user', null, null, 'user_id=' . $userId);
                    flash_set('success', 'User unbanned');
                    break;
                case 'disable':
                    db()->prepare("UPDATE users SET status = 'disabled' WHERE id = ?")->execute([$userId]);
                    revoke_all_user_sessions($userId);
                    flash_set('success', 'User disabled');
                    break;
                case 'enable':
                    db()->prepare("UPDATE users SET status = 'active' WHERE id = ?")->execute([$userId]);
                    flash_set('success', 'User enabled');
                    break;
                case 'delete':
                    db()->prepare('DELETE FROM users WHERE id = ?')->execute([$userId]);
                    flash_set('success', 'User deleted');
                    break;
                case 'reset_password':
                    $newPass = (string)($_POST['new_password'] ?? '');
                    if (strlen($newPass) >= 8) {
                        db()->prepare('UPDATE users SET password_hash = ? WHERE id = ?')
                            ->execute([password_hash($newPass, PASSWORD_BCRYPT), $userId]);
                        revoke_all_user_sessions($userId);
                        flash_set('success', 'Password reset');
                    } else {
                        flash_set('error', 'Password must be 8+ characters');
                    }
                    break;
                case 'update_license':
                    $expires = trim((string)($_POST['expires_at'] ?? ''));
                    $status = trim((string)($_POST['license_status'] ?? 'active'));
                    db()->prepare(
                        'INSERT INTO licenses (user_id, status, expires_at) VALUES (?, ?, ?)
                         ON DUPLICATE KEY UPDATE status = VALUES(status), expires_at = VALUES(expires_at)'
                    )->execute([$userId, $status, $expires ?: null]);
                    flash_set('success', 'License updated');
                    break;
            }
        }
    }
    admin_redirect('users.php');
}

$roleFilter = $isSuper ? '' : ' AND r.name = \'team_member\'';
$users = db()->query(
    "SELECT u.*, r.name AS role_name, r.label AS role_label, l.expires_at, l.status AS license_status
     FROM users u
     JOIN roles r ON r.id = u.role_id
     LEFT JOIN licenses l ON l.user_id = u.id
     WHERE 1=1 {$roleFilter}
     ORDER BY u.id DESC"
)->fetchAll();

$roles = db()->query('SELECT * FROM roles ORDER BY id')->fetchAll();

ob_start();
?>
<div class="card">
  <h3>Create User</h3>
  <form method="post" style="display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end;">
    <?= csrf_field() ?>
    <input type="hidden" name="action" value="create">
    <div class="form-row"><label>Username</label><input name="username" required></div>
    <div class="form-row"><label>Password</label><input name="password" type="password" required minlength="8"></div>
    <div class="form-row"><label>Role</label>
      <select name="role_id">
        <?php foreach ($roles as $role): ?>
          <?php if ($isSuper || $role['name'] === 'team_member'): ?>
            <option value="<?= (int)$role['id'] ?>"><?= e($role['label']) ?></option>
          <?php endif; ?>
        <?php endforeach; ?>
      </select>
    </div>
    <div class="form-row"><label>License Expires</label><input name="expires_at" type="datetime-local"></div>
    <button class="btn" type="submit">Create</button>
  </form>
</div>

<div class="card">
  <h3>Users</h3>
  <table>
    <thead>
      <tr>
        <th>ID</th><th>Username</th><th>Role</th><th>Status</th><th>License</th><th>Last Login</th><th>Actions</th>
      </tr>
    </thead>
    <tbody>
    <?php foreach ($users as $row): ?>
      <tr>
        <td><?= (int)$row['id'] ?></td>
        <td><?= e($row['username']) ?></td>
        <td><?= e($row['role_label']) ?></td>
        <td><span class="badge badge-<?= e($row['status']) ?>"><?= e($row['status']) ?></span></td>
        <td><?= e($row['license_status'] ?? '-') ?> <?= $row['expires_at'] ? '<br><small>' . e($row['expires_at']) . '</small>' : '' ?></td>
        <td><?= e($row['last_login_at'] ?? '-') ?></td>
        <td>
          <form method="post" style="display:inline">
            <?= csrf_field() ?>
            <input type="hidden" name="user_id" value="<?= (int)$row['id'] ?>">
            <?php if ($row['status'] === 'banned'): ?>
              <button class="btn btn-sm" name="action" value="unban">Unban</button>
            <?php else: ?>
              <button class="btn btn-sm btn-danger" name="action" value="ban">Ban</button>
            <?php endif; ?>
            <?php if ($row['status'] === 'disabled'): ?>
              <button class="btn btn-sm" name="action" value="enable">Enable</button>
            <?php else: ?>
              <button class="btn btn-sm" name="action" value="disable">Disable</button>
            <?php endif; ?>
            <button class="btn btn-sm btn-danger" name="action" value="delete" onclick="return confirm('Delete user?')">Delete</button>
          </form>
          <details style="margin-top:6px;">
            <summary class="btn btn-sm">License / Password</summary>
            <form method="post" style="margin-top:8px;">
              <?= csrf_field() ?>
              <input type="hidden" name="user_id" value="<?= (int)$row['id'] ?>">
              <div class="form-row"><label>License Status</label>
                <select name="license_status">
                  <?php foreach (['active','inactive','trial','revoked'] as $st): ?>
                    <option value="<?= $st ?>" <?= ($row['license_status'] ?? '') === $st ? 'selected' : '' ?>><?= $st ?></option>
                  <?php endforeach; ?>
                </select>
              </div>
              <div class="form-row"><label>Expires</label><input name="expires_at" type="datetime-local" value="<?= $row['expires_at'] ? e(date('Y-m-d\TH:i', strtotime($row['expires_at']))) : '' ?>"></div>
              <button class="btn btn-sm" name="action" value="update_license">Save License</button>
              <div class="form-row" style="margin-top:8px;"><label>New Password</label><input name="new_password" type="password" minlength="8"></div>
              <button class="btn btn-sm" name="action" value="reset_password">Reset Password</button>
            </form>
          </details>
        </td>
      </tr>
    <?php endforeach; ?>
    </tbody>
  </table>
</div>
<?php
render_layout('User Management', ob_get_clean(), $user, 'users');
