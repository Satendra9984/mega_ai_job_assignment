"""Face detection using MediaPipe + Pillow — no OpenCV (`cv2`) in application code."""

from __future__ import annotations

import io
import threading
from dataclasses import dataclass

import mediapipe as mp
import numpy as np
from PIL import Image, UnidentifiedImageError


@dataclass(frozen=True)
class DetectionResult:
    face_detected: bool
    x: int | None = None
    y: int | None = None
    w: int | None = None
    h: int | None = None
    confidence: float | None = None


class FaceDetector:
    """Thread-safe wrapper around MediaPipe FaceDetection."""

    def __init__(self, min_detection_confidence: float = 0.5) -> None:
        self._lock = threading.Lock()
        self._mp_face = mp.solutions.face_detection.FaceDetection(
            model_selection=0,
            min_detection_confidence=min_detection_confidence,
        )

    def detect(self, jpeg_bytes: bytes) -> DetectionResult:
        try:
            img = Image.open(io.BytesIO(jpeg_bytes)).convert("RGB")
        except (UnidentifiedImageError, OSError):
            raise ValueError("INVALID_JPEG") from None

        arr = np.asarray(img)
        if arr.ndim != 3 or arr.shape[2] != 3:
            raise ValueError("INVALID_IMAGE_SHAPE")

        height, width = arr.shape[0], arr.shape[1]

        with self._lock:
            results = self._mp_face.process(arr)

        if not results.detections:
            return DetectionResult(face_detected=False)

        det = results.detections[0]
        rel = det.location_data.relative_bounding_box

        x = max(0, int(rel.xmin * width))
        y = max(0, int(rel.ymin * height))
        w = max(0, int(rel.width * width))
        h = max(0, int(rel.height * height))

        conf = float(det.score[0]) if det.score else None

        return DetectionResult(
            face_detected=True,
            x=x,
            y=y,
            w=w,
            h=h,
            confidence=conf,
        )

    def close(self) -> None:
        with self._lock:
            self._mp_face.close()
