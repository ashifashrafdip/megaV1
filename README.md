# PyQt5 Desktop Automation Hub

Small desktop application with:

- URL input field
- Device profile dropdown loaded from `device_browser/profiles.json`
- HTTP and SOCKS5 proxy controls with optional username/password
- Three file picker buttons that can provide a virtual webcam video
- Start and Stop buttons
- Log console
- Background work running on `QThread`
- Device Profile Browser launcher backed by `QWebEngineView`

## Run

```powershell
pip install -r requirements.txt
python main.py
```

`main.py` is the central app bootstrap. It initializes Qt, exception logging, the main GUI, automation service factories, the QThread worker path, and the Device Profile Browser launcher.

## Execution Flow

```text
QApplication
  -> MainWindow
  -> WorkerThread
  -> Device Profile Manager
  -> Virtual Camera Service
  -> TemporaryFileServer
  -> PlaywrightProfileManager
  -> ChromiumBrowser
  -> Playwright page
  -> QTextEdit GUI log
```

The worker loads `config.json`, prepares the selected device profile, applies proxy settings, prepares a virtual camera feed, starts a temporary local server, launches a Playwright persistent Chromium profile through the profile manager and browser service, opens the target URL, waits for page load, and reports progress to the GUI log console.

## Config

`config.json` supports:

- `proxy`: enable/disable proxy, `type` (`http` or `socks5`), host, port, username, and password
- `user_agent`: browser user-agent override
- `window_size`: Chromium viewport and window size
- `camera_output_size`: webcam video output width/height (default `1080x1980`)
- `automation`: click retries, camera warmup, step settle, and liveness timeout
- `target_url`: URL opened by the worker; use `{server_url}` to reference the temporary local server
- `timeouts`: browser launch, page load, script, and shutdown timeout values
- `profile_name`: legacy persistent Playwright profile name
- `device_profile_id`: selected device profile id; this becomes the Playwright persistent profile directory name
- `headless`: Chromium headless mode

Example proxy settings:

```json
{
  "proxy": {
    "enabled": true,
    "type": "socks5",
    "host": "127.0.0.1",
    "port": "1080",
    "server": "socks5://127.0.0.1:1080",
    "username": "",
    "password": ""
  }
}
```

## Device Profile, Proxy, and Virtual Camera

1. Choose a `Device Profile` from the dropdown.
2. Enable proxy and select `HTTP` or `SOCKS5`, then enter host, port, and optional username/password.
3. Choose **three different videos** in `File 1`, `File 2`, and `File 3`. File 1 is used for ID, File 2 for selfie, and File 3 for liveness. The same video cannot be reused in multiple slots.
4. Click `Start`.

Chromium fake webcam capture works directly with `.y4m` files. If you select `.mp4`, `.mov`, `.webm`, `.mkv`, `.avi`, or `.m4v`, the app converts it to `.y4m` with `ffmpeg`. The bundled `imageio-ffmpeg` package is used automatically when system `ffmpeg` is not installed.

All camera feeds are normalized to `camera_output_size` from `config.json` (default `1080x1980`) before automation starts.

The Playwright launch includes these camera flags when a video is selected:

```text
--use-fake-ui-for-media-stream
--use-fake-device-for-media-stream
--use-file-for-fake-video-capture=/path/to/video.y4m
```

`--use-fake-ui-for-media-stream` auto-accepts the camera permission prompt. `--use-fake-device-for-media-stream` feeds the selected `.y4m` video as the webcam source, so HTTPS pages do not need to load local HTTP video URLs.

After the target page loads, the worker runs the capture automation:

1. Switches to `File 1` before the ID camera step.
2. Clicks `btn-take-photo-id`, `btn-take-photo-camera`, `btn-black-out-modal`, and `btn-go-to-photo-id-redacting`.
3. Switches to `File 2` before the selfie camera step.
4. Clicks `btn-take-photo-selfy`, `btn-take-photo-camera`, `btn-black-out-modal`, and `btn-go-to-photo-id-redacting`.
5. Switches to `File 3` before the liveness camera step.
6. Installs the `VerificationWizardVideo` liveness bypass before recording starts.
7. Polls `btn-video-instructions-proceed`, then clicks `btn-video-submit-proceed` when it appears.

Each camera step uses its own slot video. Reusing the same file in two slots is blocked before automation starts.

After automation starts, the browser stays open until you click `Stop`.

## Playwright Chromium Class

`playwright_browser.py` provides a reusable `ChromiumBrowser` class with persistent context, proxy support, custom user agent support, and `start()` / `stop()` methods.

```powershell
pip install -r requirements.txt
playwright install chromium
python playwright_browser.py
```

## Device Profile Browser

Use the `Device Browser` button in `main.py` to start a PyQt5 `QWebEngineView` browser with JSON-backed mobile device profiles. Profiles are loaded as complete records from `device_browser/profiles.json` so user agent, OS, browser, viewport, DPR, language, timezone, orientation, and color scheme stay together during the session.

`device_browser_app.py` remains a focused direct launcher for this browser:

```powershell
pip install -r requirements.txt
python device_browser_app.py
```

## Temporary File Server

`temp_file_server.py` provides a lightweight HTTP server backed by a temporary directory. Use it to create files and get local URLs for testing.

```powershell
python temp_file_server.py
```

## Playwright Profile Manager

`playwright_profile_manager.py` manages named Chromium profiles with Playwright persistent contexts. Each profile gets its own user-data directory, so cookies, local storage, IndexedDB, cache, permissions, and Chromium settings persist between launches.

```python
from playwright_profile_manager import PlaywrightProfileManager

manager = PlaywrightProfileManager()
manager.create_profile("mobile-test", overwrite=True, locale="en-US")
page = manager.start("mobile-test", start_url="https://example.com")
manager.save_storage_state()
manager.stop()
```

## PyQt QTextEdit Logging

`qt_logging.py` provides a thread-safe Python `logging.Handler` for `QTextEdit`. The QThread demo in `main.py` now uses Python logging, so background worker messages are displayed in the UI without directly touching widgets from the worker thread.

## User Authentication & Admin Panel

The desktop app can require login before automation starts. User management is done from the PHP admin panel (not inside the desktop app).

### Architecture

```text
PyQt5 Desktop App -> HTTPS JSON API -> PHP (server/) -> MySQL
Admin browser UI -> server/admin/
```

### Local test (XAMPP)

1. Create database `automation_auth` and import `server/install/schema.sql`.
2. Edit `server/config.php` (set `require_https` to `false` for local HTTP).
3. Run `http://localhost/app-auth/install/setup.php` once.
4. Create team users in `admin/users.php`.
5. Set `config.json` → `auth.api_base` to your local server URL.
6. Run `python main.py` — login dialog appears first.

### Features

- Bcrypt passwords, JWT access + refresh tokens
- Single active session per user
- Heartbeat every 45s — ban/disable/force logout locks app within one cycle
- License expiry per user
- Activity logs + link logs (URL opens)
- Device fingerprint registration

See [server/README.md](server/README.md) for full deployment steps.
