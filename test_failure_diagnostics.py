import json
import shutil
import sys
from pathlib import Path
from unittest.mock import MagicMock

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def test_failure_diagnostics():
    print("Testing Automated Failure Diagnostics (Problem 5)...")
    
    # We will test WorkerThread._capture_failure_diagnostics directly
    # First, import WorkerThread from main
    try:
        from main import WorkerThread, AutomationServices
    except Exception as e:
        print(f"Failed to import WorkerThread: {e}")
        sys.exit(1)
        
    reports_dir = Path("debug_reports")
    # Clean up test reports dir if needed
    if reports_dir.exists():
        shutil.rmtree(reports_dir)
        
    # Mock services
    mock_services = MagicMock()
    mock_services.config = MagicMock()
    mock_services.config.automation = MagicMock()
    
    worker = WorkerThread(mock_services, ["file1.jpg", "file2.jpg", "file3.mp4"])
    worker.status = MagicMock()
    worker.status.emit = MagicMock()
    
    # Mock Page
    mock_page = MagicMock()
    mock_page.is_closed = MagicMock(return_value=False)
    mock_page.url = "https://agesmart.eu/verification/video/test1234"
    mock_page.content = MagicMock(return_value="<html><body><div id='wizard-backend-error-message'>Head movement verification failed. Too fast.</div></body></html>")
    
    # Mock screenshot by creating an actual file when called
    def fake_screenshot(path, full_page=True):
        Path(path).write_bytes(b"\x89PNG\r\n\x1a\nfake_image_data")
    mock_page.screenshot = MagicMock(side_effect=fake_screenshot)
    
    # Mock evaluate to return the backend error message
    mock_page.evaluate = MagicMock(return_value="Head movement verification failed. Too fast.")
    
    # Call _capture_failure_diagnostics
    test_reason = "liveness_attempt_1_error"
    worker._capture_failure_diagnostics(mock_page, reason=test_reason)
    
    assert reports_dir.exists(), "debug_reports directory was not created!"
    
    png_files = list(reports_dir.glob("failure_*_liveness_attempt_1_error.png"))
    html_files = list(reports_dir.glob("failure_*_liveness_attempt_1_error.html"))
    json_files = list(reports_dir.glob("failure_*_liveness_attempt_1_error_summary.json"))
    
    assert len(png_files) >= 1, f"Screenshot file missing in {reports_dir}"
    assert len(html_files) >= 1, f"HTML dump file missing in {reports_dir}"
    assert len(json_files) >= 1, f"Summary JSON file missing in {reports_dir}"
    
    png_file = png_files[0]
    html_file = html_files[0]
    json_file = json_files[0]
    
    assert png_file.stat().st_size > 0, "Screenshot file is empty!"
    assert "Head movement verification failed" in html_file.read_text(encoding="utf-8"), "HTML dump content mismatch!"
    
    summary_data = json.loads(json_file.read_text(encoding="utf-8"))
    assert summary_data["reason"] == test_reason, f"Summary reason mismatch: {summary_data.get('reason')}"
    assert summary_data["error_message"] == "Head movement verification failed. Too fast.", f"Summary error mismatch: {summary_data.get('error_message')}"
    assert summary_data["url"] == mock_page.url, f"Summary URL mismatch: {summary_data.get('url')}"
    
    print(f"Verified screenshot generated: {png_file.name} ({png_file.stat().st_size} bytes)")
    print(f"Verified HTML snapshot generated: {html_file.name} ({html_file.stat().st_size} bytes)")
    print(f"Verified JSON summary generated: {json_file.name}")
    print(f"Summary data: {json.dumps(summary_data, indent=2)}")
    
    # Also test graceful fallback when page is closed or evaluate fails
    mock_page_closed = MagicMock()
    mock_page_closed.is_closed = MagicMock(return_value=True)
    worker._capture_failure_diagnostics(mock_page_closed, reason="closed_test")
    # Should not raise any error
    
    # Test error fallback in screenshot/evaluate
    mock_page_err = MagicMock()
    mock_page_err.is_closed = MagicMock(return_value=False)
    mock_page_err.screenshot = MagicMock(side_effect=Exception("Screenshot driver crash"))
    mock_page_err.content = MagicMock(return_value="<html>Fallback</html>")
    mock_page_err.evaluate = MagicMock(side_effect=Exception("JS context destroyed"))
    worker._capture_failure_diagnostics(mock_page_err, reason="crash_test")
    
    crash_json = list(reports_dir.glob("failure_*_crash_test_summary.json"))
    assert len(crash_json) >= 1, "Crash test summary JSON was not generated!"
    
    # Clean up test output
    shutil.rmtree(reports_dir)
    print("\nALL AUTOMATED FAILURE DIAGNOSTICS TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_failure_diagnostics()
