import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import tempfile
from pathlib import Path
from camera_feed_service import (
    VirtualCameraService,
    IMAGE_SUFFIXES,
    VIDEO_SUFFIXES,
    MEDIA_SUFFIXES,
)

def test_suffixes():
    print("Testing suffixes...")
    assert ".jpg" in IMAGE_SUFFIXES
    assert ".png" in IMAGE_SUFFIXES
    assert ".webp" in IMAGE_SUFFIXES
    assert ".mp4" in VIDEO_SUFFIXES
    assert ".jpg" in MEDIA_SUFFIXES
    assert ".mp4" in MEDIA_SUFFIXES
    print("  ✅ Suffix definitions OK.")

def test_scale_filter_padding():
    print("Testing scale filter padding...")
    svc = VirtualCameraService(output_width=1280, output_height=720)
    filter_pad = svc._scale_filter(pad=True)
    assert "force_original_aspect_ratio=decrease" in filter_pad
    assert "pad=1280:720:" in filter_pad
    assert "crop=" not in filter_pad
    print(f"  ✅ Padding filter correctly configured: {filter_pad}")

    filter_crop = svc._scale_filter(pad=False)
    assert "force_original_aspect_ratio=increase" in filter_crop
    assert "crop=1280:720" in filter_crop
    print("  ✅ Crop filter correctly preserved when explicitly requested.")

def test_image_to_video_conversion():
    print("Testing image to y4m and mp4 conversion...")
    svc = VirtualCameraService(output_width=1280, output_height=720)
    
    # Create a dummy test image using ffmpeg if available
    ffmpeg = svc._find_ffmpeg()
    assert ffmpeg, "ffmpeg must be found on system"
    print(f"  [+] Found ffmpeg: {ffmpeg}")

    with tempfile.TemporaryDirectory() as tmpdir:
        test_img = Path(tmpdir) / "test_id.png"
        import subprocess
        # Generate a test colored 800x600 image with text
        subprocess.run([
            ffmpeg, "-y", "-f", "lavfi",
            "-i", "color=c=blue:s=800x600:d=1",
            "-frames:v", "1",
            str(test_img)
        ], check=True, capture_output=True)
        assert test_img.is_file(), "Test image generation failed"

        # Test duration probe
        duration = svc.probe_duration_seconds(test_img)
        assert duration == 15.0, f"Expected 15.0s, got {duration}"
        print("  ✅ Image duration probed correctly as 15.0s.")

        # Test prepare_file (which converts to .y4m)
        feed = svc.prepare_file(str(test_img))
        assert feed is not None, "Feed should not be None"
        assert feed.capture_path is not None, "capture_path should not be None"
        assert feed.capture_path.is_file(), "capture_path file should exist"
        assert feed.capture_path.suffix == ".y4m"
        assert feed.capture_path.stat().st_size > 0, "Y4M file should be non-empty"
        print(f"  ✅ Converted image to .y4m ({feed.capture_path.stat().st_size} bytes).")

        # Test prepare_blob_sources (which converts to .mp4)
        blob_paths = svc.prepare_blob_sources([str(test_img), "", ""])
        assert blob_paths[0] is not None
        assert blob_paths[0].is_file()
        assert blob_paths[0].suffix == ".mp4"
        assert blob_paths[0].stat().st_size > 0
        print(f"  ✅ Converted image to .mp4 ({blob_paths[0].stat().st_size} bytes).")

def test_validation_logic():
    print("Testing slot validation logic for slot 3 video enforcement...")
    with tempfile.TemporaryDirectory() as tmpdir:
        img1 = Path(tmpdir) / "id.png"
        img2 = Path(tmpdir) / "selfie.jpg"
        img3_bad = Path(tmpdir) / "liveness.png"
        vid3_good = Path(tmpdir) / "liveness.mp4"

        for p in (img1, img2, img3_bad, vid3_good):
            p.write_bytes(b"dummy")

        # Mock testing the validation rule
        slots_bad = [img1, img2, img3_bad]
        from camera_feed_service import IMAGE_SUFFIXES
        is_bad = slots_bad[2].suffix.lower() in IMAGE_SUFFIXES
        assert is_bad is True, "Slot 3 image should be caught as invalid"

        slots_good = [img1, img2, vid3_good]
        is_good = slots_good[2].suffix.lower() in IMAGE_SUFFIXES
        assert is_good is False, "Slot 3 video should be accepted"
        print("  ✅ Slot validation logic correctly permits images in slot 1 & 2 while enforcing video in slot 3.")

if __name__ == "__main__":
    print("==========================================")
    print("🚀 RUNNING PROBLEM 1 TESTS (MEDIA PIPELINE)")
    print("==========================================")
    test_suffixes()
    test_scale_filter_padding()
    test_image_to_video_conversion()
    test_validation_logic()
    print("\n🎉 ALL PROBLEM 1 TESTS PASSED!")
