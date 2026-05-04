"""Download BlazeFace short-range TFLite for MediaPipe Tasks (required for FaceDetector)."""

from __future__ import annotations

import urllib.request
from pathlib import Path

URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite"
)
DEST = Path(__file__).resolve().parent.parent / "models" / "blaze_face_short_range.tflite"


def main() -> None:
    DEST.parent.mkdir(parents=True, exist_ok=True)
    if DEST.is_file():
        print("Already present:", DEST)
        return
    print("Downloading", URL)
    req = urllib.request.Request(URL, headers={"User-Agent": "megaai-foundation-setup/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        DEST.write_bytes(resp.read())
    print("Wrote", DEST, f"({DEST.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
