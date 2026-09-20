<?php
declare(strict_types=1);

require_once __DIR__ . '/includes/layout.php';
$user = require_super_admin();

$rows = db()->query(
    'SELECT l.*, u.username FROM link_logs l LEFT JOIN users u ON u.id = l.user_id ORDER BY l.id DESC LIMIT 200'
)->fetchAll();

ob_start();
?>
<div class="card">
  <h3>Link Logs (Phase 2 — desktop URL tracking)</h3>
  <table>
    <thead><tr><th>Time</th><th>User</th><th>URL</th><th>Browser</th><th>Device</th></tr></thead>
    <tbody>
    <?php foreach ($rows as $row): ?>
      <tr>
        <td><?= e($row['created_at']) ?></td>
        <td><?= e($row['username'] ?? '-') ?></td>
        <td style="max-width:400px;word-break:break-all;"><?= e($row['url']) ?></td>
        <td><?= e($row['browser'] ?? '') ?></td>
        <td><?= e($row['device_id'] ?? '') ?></td>
      </tr>
    <?php endforeach; ?>
    </tbody>
  </table>
</div>
<?php
render_layout('Link Logs', ob_get_clean(), $user, 'link_logs');
