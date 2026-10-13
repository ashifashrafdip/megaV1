import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
import subprocess
from payload_defaults import DEFAULT_VIDEO_STEP_TEMPLATE, DEFAULT_LIVENESS_TEMPLATE
from video_step_automation import video_step_script

def test_script_generation():
    print("Testing video_step_script generation...")
    script = video_step_script(upload_mode="live_recording")
    assert "__UPLOAD_MODE__" not in script
    assert "__TIMELINE_JSON__" not in script
    assert "buildLandmarks" in script
    assert "ensureDynamicTimeline" in script
    print("  ✅ video_step_script properly formats template.")

def test_landmark_and_dynamic_timeline_execution():
    print("Testing landmark geometry and dynamic timeline with Node.js...")
    script = video_step_script(upload_mode="live_recording")

    # Node runner script to verify in a mock browser environment
    runner_js = f"""
    // Mock minimal browser globals
    global.window = global;
    window.__videoStepNativeInstalled = false;
    window.document = {{
      getElementById: (id) => null,
      querySelectorAll: (sel) => [],
    }};

    // Inject the script
    {script}

    // Test 1: Check dynamic timeline generation with a server sequence: CENTER, RIGHT, UP
    const mockController = {{
      opts: {{ steps: "CENTER,RIGHT,UP" }},
      positions: ["CENTER", "RIGHT", "UP"],
    }};
    window.__activeVideoController = mockController;

    // Trigger dynamic timeline creation
    const timeline = window.ensureDynamicTimeline ? window.ensureDynamicTimeline() : window.__livenessTimeline;
    console.log("TIMELINE_RESULT:" + JSON.stringify(window.__livenessTimeline));

    // Test 2: Check buildLandmarks output for 478 valid points across different poses
    const poses = ["center", "left", "right", "up", "down"];
    for (const pose of poses) {{
      const points = window.__buildLandmarks(pose);
      if (!Array.isArray(points) || points.length !== 478) {{
        throw new Error("Landmarks must have exactly 478 points, got: " + points?.length);
      }}
      for (let i = 0; i < points.length; i++) {{
        const pt = points[i];
        if (typeof pt.x !== "number" || typeof pt.y !== "number" || typeof pt.z !== "number") {{
          throw new Error(`Point ${{i}} has non-number coords in pose ${{pose}}`);
        }}
        if (pt.x < 0 || pt.x > 1 || pt.y < 0 || pt.y > 1) {{
          throw new Error(`Point ${{i}} out of bounds [0, 1] in pose ${{pose}}: x=${{pt.x}}, y=${{pt.y}}`);
        }}
      }}
    }}
    console.log("LANDMARKS_OK");
    """

    res = subprocess.run(["node", "-"], input=runner_js, capture_output=True, text=True)
    if res.returncode != 0:
        print("Node test execution failed:\n", res.stderr)
        raise AssertionError("Node execution failed")

    stdout = res.stdout
    assert "LANDMARKS_OK" in stdout, "Landmarks test failed"

    # Verify timeline output
    for line in stdout.splitlines():
        if line.startswith("TIMELINE_RESULT:"):
            data = json.loads(line.replace("TIMELINE_RESULT:", ""))
            positions = [item["position"] for item in data]
            assert positions == ["center", "right", "up"], f"Unexpected dynamic positions: {positions}"
            print(f"  ✅ Dynamic timeline successfully generated matching server steps: {positions}")
            break

    print("  ✅ All 478 landmarks verified valid within [0.0, 1.0] for CENTER, LEFT, RIGHT, UP, DOWN.")

if __name__ == "__main__":
    print("==================================================")
    print("🚀 RUNNING PROBLEM 2 TESTS (DYNAMIC LIVENESS & POSE)")
    print("==================================================")
    test_script_generation()
    test_landmark_and_dynamic_timeline_execution()
    print("\n🎉 ALL PROBLEM 2 TESTS PASSED!")
