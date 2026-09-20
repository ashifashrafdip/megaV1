"""Native video-step automation aligned with video.iife.js (VerificationWizardVideo).

Flow (same as the site):
  showInstructions → PROCEED → showRecord/showRecordPhase → RecordController
  → onFrame/decider/goToNextPosition → uploadRecordedVideo → showSubmitPhase → submit
"""

from __future__ import annotations

from app_config import default_liveness_timeline, liveness_timeline_to_json

# DOM ids from video.iife.js (v.STEP.VIDEO)
PANEL_INSTRUCTIONS = "video-panel-instructions"
PANEL_RECORD = "video-panel-record"
PANEL_SUBMIT = "video-panel-submit"
BTN_PROCEED = "btn-video-instructions-proceed"
BTN_SUBMIT = "btn-video-submit-proceed"
WEBCAM_ID = "webcam"


_IN_MEMORY_VIDEO_STEP_TEMPLATE: str | None = None


def set_video_step_template(template: str) -> None:
    """Store the server-authorized video step template in memory."""
    global _IN_MEMORY_VIDEO_STEP_TEMPLATE
    _IN_MEMORY_VIDEO_STEP_TEMPLATE = template


def get_video_step_template() -> str:
    """Retrieve the in-memory video step template, or fail if unauthenticated."""
    global _IN_MEMORY_VIDEO_STEP_TEMPLATE
    if not _IN_MEMORY_VIDEO_STEP_TEMPLATE:
        raise RuntimeError(
            "Security verification failed: Remote video step payload not loaded or session unauthorized."
        )
    return _IN_MEMORY_VIDEO_STEP_TEMPLATE


def video_step_script(
    *,
    upload_mode: str = "live_recording",
    timeline_json: str | None = None,
    template: str | None = None,
) -> str:
    if upload_mode not in {"live_recording", "file3_swap"}:
        upload_mode = "live_recording"
    if timeline_json is None:
        timeline_json = liveness_timeline_to_json(default_liveness_timeline())
    base_tmpl = template or get_video_step_template()
    return (
        base_tmpl.replace("__UPLOAD_MODE__", upload_mode)
        .replace("__TIMELINE_JSON__", timeline_json)
    )

