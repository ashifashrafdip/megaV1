<?php
declare(strict_types=1);

require_once __DIR__ . '/includes/layout.php';
$user = require_admin();

if ($_SERVER['REQUEST_METHOD'] === 'POST' && csrf_verify($_POST['csrf_token'] ?? null)) {
    $sessionId = (int)($_POST['session_id'] ?? 0);
    $userId = (int)($_POST['user_id'] ?? 0);
    if ($sessionId > 0) {
        revoke_session($sessionId);
        log_activity((int)$user['id'], 'force_logout', null, null, 'session_id=' . $sessionId);
        flash_set('success', 'Session revoked');
    } elseif ($userId > 0) {
        revoke_all_user_sessions($userId);
        log_activity((int)$user['id'], 'force_logout', null, null, 'user_id=' . $userId);
        flash_set('success', 'All sessions revoked');
    }
    admin_redirect('sessions.php');
}

$sessions = db()->query(
    'SELECT s.*, u.username, u.status AS user_status
     FROM sessions s
     JOIN users u ON u.id = s.user_id
     WHERE s.is_active = 1
     ORDER BY s.last_seen_at DESC'
)->fetchAll();

ob_start();
?>
<div class="card">
  <h3>Active Sessions</h3>
  <table>
    <thead>
      <tr><th>User</th><th>Device</th><th>PC</th><th>IP</th><th>Last Seen</th><th>Expires</th><th></th></tr>
    </thead>
    <tbody>
    <?php foreach ($sessions as $row): ?>
      <tr>
        <td><?= e($row['username']) ?> <span class="badge badge-<?= e($row['user_status']) ?>"><?= e($row['user_status']) ?></span></td>
        <td><?= e($row['device_id'] ?? '-') ?></td>
        <td><?= e($row['pc_name'] ?? '-') ?></td>
        <td><?= e($row['ip_address'] ?? '') ?></td>
        <td><?= e($row['last_seen_at']) ?></td>
        <td><?= e($row['expires_at']) ?></td>
        <td>
          <form method="post" style="display:inline">
            <?= csrf_field() ?>
            <input type="hidden" name="session_id" value="<?= (int)$row['id'] ?>">
            <button class="btn btn-sm btn-danger" type="submit">Force Logout</button>
          </form>
        </td>
      </tr>
    <?php endforeach; ?>
    </tbody>
  </table>
</div>
<?php
render_layout('Session Management', ob_get_clean(), $user, 'sessions');
