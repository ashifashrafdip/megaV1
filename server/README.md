# Automation Hub Auth Server

PHP + MySQL backend for desktop login, licensing, heartbeat, and admin panel.

## cPanel Deployment

1. Create a MySQL database and user in cPanel.
2. Upload the `server/` folder to e.g. `public_html/app-auth/`.
3. Copy `config.example.php` to `config.php` and set DB credentials, `jwt_secret`, and `app_api_key`.
4. Import `install/schema.sql` via phpMyAdmin.
5. Visit `https://yourdomain.com/app-auth/install/setup.php` once to set the super admin password (`Admin@12345` by default).
6. **Delete** `install/setup.php` after use.
7. Enable SSL (Let's Encrypt). Set `require_https` to `true` in `config.php`.
8. Open admin panel: `https://yourdomain.com/app-auth/admin/login.php`

## Default Admin

- Username: `superadmin`
- Password: set via `install/setup.php`

## Desktop Config

In the PyQt app `config.json`:

```json
"auth": {
  "enabled": true,
  "api_base": "https://yourdomain.com/app-auth",
  "app_key": "same-as-config.php-app_api_key",
  "heartbeat_seconds": 45,
  "verify_ssl": true
}
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `api/login.php` | POST | Desktop login |
| `api/logout.php` | POST | Desktop logout |
| `api/heartbeat.php` | POST | Session + license check |
| `api/refresh_token.php` | POST | Refresh JWT |
| `api/activity_log.php` | POST | Log app events |
| `api/link_log.php` | POST | Log opened URLs |

All desktop API calls require header `X-App-Key` and JSON body where applicable.

## Admin Roles

| Role | Access |
|------|--------|
| Super Admin | Users, sessions, devices, logs, settings |
| Admin | Team members only (no logs/settings) |
| Team Member | Desktop app only |

## Phase 2 (see `protection_stub.py`)

- Offline grace period
- Strict device binding enforcement
- Anti-tamper / obfuscation
