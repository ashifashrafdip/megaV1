# MoreLogin Automation Hub

This is a dedicated automation tool built exclusively for **MoreLogin**.

## Features

- **Direct MoreLogin Integration**: Connects directly with the MoreLogin Local API (`http://127.0.0.1:40000`) and `ml-cli`.
- **Automatic Profile Detection**: Auto-detects and loads all MoreLogin browser profiles (including Mobile Device Emulation profiles).
- **Virtual Camera Video Injection**: Seamlessly feeds File 1 (ID Card), File 2 (Selfie), and File 3 (Liveness Video) into the Chromium media stream using Chromium flags:
  - `--use-fake-ui-for-media-stream`
  - `--use-fake-device-for-media-stream`
  - `--use-file-for-fake-video-capture=<path>`
- **Playwright CDP Automation**: Directly attaches to MoreLogin's `debugPort` via Chrome DevTools Protocol (CDP) for instant DOM automation and script injection without latency.
- **Clean UI**: Modern PyQt5 dark-themed interface with live activity logs and connection status.

## How to Run

1. Make sure **MoreLogin Client** is running and logged in.
2. In PowerShell / Terminal, run:
   ```powershell
   cd d:\create-a-pyqt5-desktop-application-with\create-a-pyqt5-desktop-application-with\morelogin_automation
   python main.py
   ```
3. In the UI:
   - Verify that the status indicator shows **MoreLogin API: Connected (Port 40000)**.
   - Choose your desired browser profile from the dropdown (e.g. `P-1` or your mobile profile).
   - Enter your Target Verification URL.
   - Select **File 1 (ID)**, **File 2 (Selfie)**, and **File 3 (Liveness)**.
   - Click **▶ Start MoreLogin Automation**.
