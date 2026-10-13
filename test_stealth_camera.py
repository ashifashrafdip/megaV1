import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
import subprocess
from main import WorkerThread

def test_stealth_camera_in_node():
    print("Testing stealth camera evasion and native toString in Node.js environment...")
    
    # Generate the blob camera script with test urls
    blob_script = WorkerThread._blob_camera_script(["http://127.0.0.1/1.mp4"], 1280, 720)
    
    runner_js = f"""
    // Mock minimal browser globals
    global.window = global;
    window.document = {{
      documentElement: {{
        appendChild: () => {{}},
      }},
      createElement: (tag) => {{
        return {{
          setAttribute: () => {{}},
          style: {{}},
          width: 1280,
          height: 720,
          addEventListener: () => {{}},
          play: async () => {{}},
          pause: () => {{}},
          load: () => {{}},
          captureStream: () => ({{
            getVideoTracks: () => [{{
              getSettings: () => ({{}}),
              getCapabilities: () => ({{}}),
            }}],
          }}),
          getContext: () => ({{
            fillRect: () => {{}},
            drawImage: () => {{}},
          }}),
        }};
      }},
      addEventListener: () => {{}},
    }};

    Object.defineProperty(navigator, 'mediaDevices', {{
      value: {{
        getUserMedia: async () => ({{}}),
        enumerateDevices: async () => [{{ kind: "audioinput", label: "Microphone" }}],
      }},
      configurable: true,
      writable: true,
    }});

    // Run the blob camera script
    {blob_script}

    // 1. Check Function.prototype.toString for getUserMedia
    const gumStr = Function.prototype.toString.call(navigator.mediaDevices.getUserMedia);
    console.log("GUM_TOSTRING:" + gumStr);

    // 2. Check enumerateDevices
    navigator.mediaDevices.enumerateDevices().then((devices) => {{
      const videoDevices = devices.filter((d) => d.kind === "videoinput");
      console.log("DEVICES_COUNT:" + videoDevices.length);
      if (videoDevices.length > 0) {{
        console.log("DEVICE_LABEL:" + videoDevices[0].label);
      }}

      // 3. Check property enumeration stealth
      const keys = Object.keys(window);
      const isLeaked = keys.includes("__setVirtualCameraVideo") || keys.includes("__stopVirtualCamera");
      console.log("KEYS_LEAKED:" + isLeaked);
      console.log("CAN_ACCESS_DIRECTLY:" + Boolean(window.__setVirtualCameraVideo));
    }});
    """

    res = subprocess.run(["node", "-"], input=runner_js, capture_output=True, text=True)
    if res.returncode != 0:
        print("Node test execution failed:\n", res.stderr)
        raise AssertionError("Node execution failed")

    stdout = res.stdout
    print("Execution output:\n" + stdout.strip())
    
    assert "GUM_TOSTRING:function getUserMedia() { [native code] }" in stdout
    assert "DEVICES_COUNT:1" in stdout
    assert "DEVICE_LABEL:HD Pro Webcam C920 (046d:082d)" in stdout
    assert "KEYS_LEAKED:false" in stdout
    assert "CAN_ACCESS_DIRECTLY:true" in stdout

    print("\n  ✅ getUserMedia() masked as native code.")
    print("  ✅ Hardware webcam properly enumerated via enumerateDevices().")
    print("  ✅ Automation properties hidden from Object.keys() enumeration.")

if __name__ == "__main__":
    print("==================================================")
    print("🚀 RUNNING PROBLEM 3 TESTS (STEALTH & ANTI-DETECT)")
    print("==================================================")
    test_stealth_camera_in_node()
    print("\n🎉 ALL PROBLEM 3 TESTS PASSED!")
