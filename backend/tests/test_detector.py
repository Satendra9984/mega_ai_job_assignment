"""Unit tests for FaceDetector."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.services.detector import FaceDetector


def _solid_jpeg_rgb(width: int = 64, height: int = 64, color: tuple[int, int, int] = (255, 255, 255)) -> bytes:
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def test_detector_no_face_white_frame() -> None:
    det = FaceDetector(min_detection_confidence=0.1)
    try:
        jpeg = _solid_jpeg_rgb()
        result = det.detect(jpeg)
        assert result.face_detected is False
        assert result.x is None
    finally:
        det.close()


def test_detector_invalid_bytes() -> None:
    det = FaceDetector()
    try:
        with pytest.raises(ValueError, match="INVALID_JPEG"):
            det.detect(b"not an image")
    finally:
        det.close()
