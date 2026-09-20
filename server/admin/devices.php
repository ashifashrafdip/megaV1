<?php
declare(strict_types=1);

require_once __DIR__ . '/includes/layout.php';
$user = require_admin();

if ($_SERVER['REQUEST_METHOD'] === 'POST' && csrf_verify($_POST['csrf_token'] ?? null)) {
    $deviceRowId = (int)($_POST['device_row_id'] ?? 0);
    $action = $_POST['action'] ?? '';
    if ($deviceRowId > 0 && $action === 'reset') {
        db()->prepare('UPDATE devices SET is_authorized = 1 WHERE id = ?')->execute([$deviceRowId]);
        flash_set('success', 'Device re-authorized');
    } elseif ($deviceRowId > 0 && $action === 'revoke') {
        db()->prepare('UPDATE devices SET is_authorized = 0 WHERE id = ?')->execute([$deviceRowId]);
        flash_set('success', 'Device revoked');
    }
    admin_redirect('devices.php');
}

$devices = db()->query(
    'SELECT d.*, u.username FROM devices d JOIN users u ON u.id = d.user_id ORDER BY d.last_seen_at DESC LIMIT 200'
)->fetchAll();

ob_start();
?>
<div class="card">
  <h3>Registered Devices</h3>
  <table>
    <thead><tr><th>User</th><th>Device ID</th><th>PC</th><th>Authorized</th><th>Last Seen</th><th></th></tr></thead>
    <tbody>
    <?php foreach ($devices as $row): ?>
      <tr>
        <td><?= e($row['username']) ?></td>
        <td style="font-family:monospace;font-size:0.8rem;"><?= e($row['device_id']) ?></td>
        <td><?= e($row['pc_name'] ?? '') ?></td>
        <td><?= (int)$row['is_authorized'] ? 'Yes' : 'No' ?></td>
        <td><?= e($row['last_seen_at']) ?></td>
        <td>
          <form method="post" style="display:inline">
            <?= csrf_field() ?>
            <input type="hidden" name="device_row_id" value="<?= (int)$row['id'] ?>">
            <button class="btn btn-sm" name="action" value="reset">Authorize</button>
            <button class="btn btn-sm btn-danger" name="action" value="revoke">Revoke</button>
          </form>
        </td>
      </tr>
    <?php endforeach; ?>
    </tbody>
  </table>
</div>
<?php
render_layout('Device Management', ob_get_clean(), $user, 'devices');
