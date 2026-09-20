<?php
declare(strict_types=1);

require_once __DIR__ . '/includes/layout.php';
$user = require_super_admin();

$action = trim((string)($_GET['action'] ?? ''));
$search = trim((string)($_GET['q'] ?? ''));

if ($action === 'export') {
    header('Content-Type: text/csv');
    header('Content-Disposition: attachment; filename="activity_logs.csv"');
    $out = fopen('php://output', 'w');
    fputcsv($out, ['id', 'user_id', 'username', 'action', 'ip_address', 'device_id', 'pc_name', 'details', 'created_at']);
    $sql = 'SELECT a.*, u.username FROM activity_logs a LEFT JOIN users u ON u.id = a.user_id ORDER BY a.id DESC LIMIT 5000';
    foreach (db()->query($sql) as $row) {
        fputcsv($out, [
            $row['id'], $row['user_id'], $row['username'], $row['action'],
            $row['ip_address'], $row['device_id'], $row['pc_name'], $row['details'], $row['created_at'],
        ]);
    }
    fclose($out);
    exit;
}

$params = [];
$sql = 'SELECT a.*, u.username FROM activity_logs a LEFT JOIN users u ON u.id = a.user_id WHERE 1=1';
if ($search !== '') {
    $sql .= ' AND (a.action LIKE ? OR u.username LIKE ? OR a.ip_address LIKE ?)';
    $params = ["%{$search}%", "%{$search}%", "%{$search}%"];
}
$sql .= ' ORDER BY a.id DESC LIMIT 200';
$stmt = db()->prepare($sql);
$stmt->execute($params);
$rows = $stmt->fetchAll();

ob_start();
?>
<div class="card">
  <div class="filters">
    <form method="get">
      <input name="q" placeholder="Search..." value="<?= e($search) ?>">
      <button class="btn" type="submit">Filter</button>
    </form>
    <a class="btn" href="?action=export">Export CSV</a>
  </div>
  <table>
    <thead><tr><th>Time</th><th>User</th><th>Action</th><th>IP</th><th>Device</th><th>PC</th><th>Details</th></tr></thead>
    <tbody>
    <?php foreach ($rows as $row): ?>
      <tr>
        <td><?= e($row['created_at']) ?></td>
        <td><?= e($row['username'] ?? '-') ?></td>
        <td><?= e($row['action']) ?></td>
        <td><?= e($row['ip_address'] ?? '') ?></td>
        <td><?= e($row['device_id'] ?? '') ?></td>
        <td><?= e($row['pc_name'] ?? '') ?></td>
        <td><?= e($row['details'] ?? '') ?></td>
      </tr>
    <?php endforeach; ?>
    </tbody>
  </table>
</div>
<?php
render_layout('Activity Logs', ob_get_clean(), $user, 'logs');
