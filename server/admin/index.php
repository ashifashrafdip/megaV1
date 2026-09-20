<?php
declare(strict_types=1);

require_once __DIR__ . '/includes/layout.php';
$user = require_admin();

$totalUsers = (int)db()->query('SELECT COUNT(*) FROM users')->fetchColumn();
$onlineCount = (int)db()->query(
    "SELECT COUNT(*) FROM sessions WHERE is_active = 1 AND last_seen_at >= DATE_SUB(NOW(), INTERVAL 3600 SECOND)"
)->fetchColumn();
$bannedCount = (int)db()->query("SELECT COUNT(*) FROM users WHERE status = 'banned'")->fetchColumn();
$activeLicenses = (int)db()->query("SELECT COUNT(*) FROM licenses WHERE status = 'active'")->fetchColumn();

$recent = db()->query(
    'SELECT a.action, a.ip_address, a.pc_name, a.created_at, u.username
     FROM activity_logs a
     LEFT JOIN users u ON u.id = a.user_id
     ORDER BY a.created_at DESC LIMIT 10'
)->fetchAll();

ob_start();
?>
<div class="stats">
  <div class="stat"><div class="value"><?= $totalUsers ?></div><div class="label">Total Users</div></div>
  <div class="stat"><div class="value"><?= $onlineCount ?></div><div class="label">Online Now</div></div>
  <div class="stat"><div class="value"><?= $bannedCount ?></div><div class="label">Banned</div></div>
  <div class="stat"><div class="value"><?= $activeLicenses ?></div><div class="label">Active Licenses</div></div>
</div>

<div class="card">
  <h3>Recent Activity</h3>
  <table>
    <thead><tr><th>Time</th><th>User</th><th>Action</th><th>IP</th><th>PC</th></tr></thead>
    <tbody>
    <?php foreach ($recent as $row): ?>
      <tr>
        <td><?= e($row['created_at']) ?></td>
        <td><?= e($row['username'] ?? '-') ?></td>
        <td><?= e($row['action']) ?></td>
        <td><?= e($row['ip_address'] ?? '') ?></td>
        <td><?= e($row['pc_name'] ?? '') ?></td>
      </tr>
    <?php endforeach; ?>
    </tbody>
  </table>
</div>
<?php
render_layout('Dashboard', ob_get_clean(), $user, 'dashboard');
