"""Face detection using MediaPipe Tasks FaceDetector + Pillow — no OpenCV (`cv2`) in app code."""

from __future__ import annotations

import io
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError

from mediapipe.tasks.python.core import base_options as mp_base_options
from mediapipe.tasks.python.vision import FaceDetector as MpFaceDetector
from mediapipe.tasks.python.vision import FaceDetectorOptions, RunningMode
from mediapipe.tasks.python.vision.core import image as mp_image

# backend/app/services/detector.py → backend/models/…
_DEFAULT_MODEL = (
    Path(__file__).resolve().parent.parent.parent
    / "models"
    / "blaze_face_short_range.tflite"
)


@dataclass(frozen=True)
class DetectionResult:
    face_detected: bool
    x: int | None = None
    y: int | None = None
    w: int | None = None
    h: int | None = None
    confidence: float | None = None


class FaceDetector:
    """Thread-safe wrapper around MediaPipe Tasks FaceDetector (BlazeFace short-range)."""

    def __init__(
        self,
        min_detection_confidence: float = 0.5,
        *,
        model_path: Path | None = None,
    ) -> None:
        path = model_path or _DEFAULT_MODEL
        if not path.is_file():
            raise FileNotFoundError(
                f"Face detector model missing: {path}. "
                "Run: python scripts/download_face_detector_model.py"
            )

        self._lock = threading.Lock()
        opts = FaceDetectorOptions(
            base_options=mp_base_options.BaseOptions(model_asset_path=str(path)),
            running_mode=RunningMode.IMAGE,
            min_detection_confidence=min_detection_confidence,
        )
        self._detector = MpFaceDetector.create_from_options(opts)

    def detect(self, jpeg_bytes: bytes) -> DetectionResult:
        try:
            img = Image.open(io.BytesIO(jpeg_bytes)).convert("RGB")
        except (UnidentifiedImageError, OSError):
            raise ValueError("INVALID_JPEG") from None

        arr = np.ascontiguousarray(np.asarray(img), dtype=np.uint8)
        if arr.ndim != 3 or arr.shape[2] != 3:
            raise ValueError("INVALID_IMAGE_SHAPE")

        mp_img = mp_image.Image(mp_image.ImageFormat.SRGB, arr)

        with self._lock:
            result = self._detector.detect(mp_img)

        if not result.detections:
            return DetectionResult(face_detected=False)

        det = result.detections[0]
        bbox = det.bounding_box
        conf: float | None = None
        if det.categories:
            s = det.categories[0].score
            conf = float(s) if s is not None else None

        return DetectionResult(
            face_detected=True,
            x=max(0, bbox.origin_x),
            y=max(0, bbox.origin_y),
            w=max(0, bbox.width),
            h=max(0, bbox.height),
            confidence=conf,
        )

    def close(self) -> None:
        with self._lock:
            self._detector.close()
