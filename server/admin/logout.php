<?php
declare(strict_types=1);
require_once __DIR__ . '/includes/layout.php';
admin_session_start();
session_destroy();
header('Location: login.php');
exit;
