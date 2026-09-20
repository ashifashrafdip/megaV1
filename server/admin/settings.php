<?php
declare(strict_types=1);

require_once __DIR__ . '/includes/layout.php';
$user = require_super_admin();

if ($_SERVER['REQUEST_METHOD'] === 'POST' && csrf_verify($_POST['csrf_token'] ?? null)) {
    $keys = ['heartbeat_interval', 'session_timeout', 'offline_grace_seconds', 'single_session', 'app_name'];
    foreach ($keys as $key) {
        if (isset($_POST[$key])) {
            db()->prepare(
                'INSERT INTO settings (setting_key, setting_value) VALUES (?, ?)
                 ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)'
            )->execute([$key, trim((string)$_POST[$key])]);
        }
    }
    flash_set('success', 'Settings saved');
    admin_redirect('settings.php');
}

$settings = [];
foreach (db()->query('SELECT setting_key, setting_value FROM settings')->fetchAll() as $row) {
    $settings[$row['setting_key']] = $row['setting_value'];
}

ob_start();
?>
<div class="card">
  <h3>Security & Session Settings</h3>
  <form method="post">
    <?= csrf_field() ?>
    <div class="form-row"><label>App Name</label><input name="app_name" value="<?= e($settings['app_name'] ?? 'Automation Hub') ?>"></div>
    <div class="form-row"><label>Heartbeat Interval (seconds)</label><input name="heartbeat_interval" type="number" value="<?= e($settings['heartbeat_interval'] ?? '45') ?>"></div>
    <div class="form-row"><label>Session Timeout (seconds)</label><input name="session_timeout" type="number" value="<?= e($settings['session_timeout'] ?? '3600') ?>"></div>
    <div class="form-row"><label>Offline Grace (seconds, Phase 2)</label><input name="offline_grace_seconds" type="number" value="<?= e($settings['offline_grace_seconds'] ?? '300') ?>"></div>
    <div class="form-row"><label>Single Session (1=yes, 0=no)</label><input name="single_session" value="<?= e($settings['single_session'] ?? '1') ?>"></div>
    <button class="btn" type="submit">Save Settings</button>
  </form>
</div>
<div class="card">
  <h3>API Configuration</h3>
  <p>Edit <code>server/config.php</code> for JWT secret and desktop API key. Never expose these in the admin UI.</p>
</div>
<?php
render_layout('Settings', ob_get_clean(), $user, 'settings');
