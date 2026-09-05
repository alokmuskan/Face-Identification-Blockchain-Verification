# Face detection (YuNet) and embedding (SFace) built on OpenCV contrib models.
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from config import DETECT_SCORE_THRESHOLD, MAX_DETECT_SIDE, SFACE_MODEL_PATH, YUNET_MODEL_PATH


class FaceEngineError(Exception):
    # Raised when models are missing or an image cannot be processed.
    pass


class FaceEngine:
    # Thread-safe wrapper around the YuNet face detector and SFace recognizer.

    def __init__(self, yunet_path: Path = YUNET_MODEL_PATH, sface_path: Path = SFACE_MODEL_PATH) -> None:
        self.yunet_path = Path(yunet_path)
        self.sface_path = Path(sface_path)
        self._lock = threading.RLock()
        self._detector: Any = None
        self._recognizer: Any = None

    def models_available(self) -> bool:
        return self.yunet_path.exists() and self.sface_path.exists()

    def _require_models(self) -> None:
        if not self.models_available():
            raise FaceEngineError('Face models are missing. Run: python tools/fetch_models.py')

    def _get_detector(self, width: int, height: int) -> Any:
        self._require_models()
        with self._lock:
            if self._detector is None:
                self._detector = cv2.FaceDetectorYN.create(
                    str(self.yunet_path),
                    '',
                    (320, 320),
                    score_threshold=DETECT_SCORE_THRESHOLD,
                )
            self._detector.setInputSize((int(width), int(height)))
            return self._detector

    def _get_recognizer(self) -> Any:
        self._require_models()
        with self._lock:
            if self._recognizer is None:
                self._recognizer = cv2.FaceRecognizerSF.create(str(self.sface_path), '')
            return self._recognizer

    @staticmethod
    def decode_image(image_bytes: bytes) -> np.ndarray:
        buffer = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        if image is None:
            raise FaceEngineError('Unsupported or corrupted image data.')
        return image

    @staticmethod
    def _downscale(image: np.ndarray) -> Tuple[np.ndarray, float]:
        height, width = image.shape[:2]
        longest = max(height, width)
        scale = 1.0
        if longest > MAX_DETECT_SIDE:
            scale = MAX_DETECT_SIDE / float(longest)
            image = cv2.resize(
                image,
                (max(1, int(round(width * scale))), max(1, int(round(height * scale)))),
                interpolation=cv2.INTER_AREA,
            )
        return image, scale

    def detect_faces(self, image_bgr: np.ndarray) -> List[Dict[str, Any]]:
        # Returns faces ordered largest-first as box + score dictionaries.
        work_image, _scale = self._downscale(image_bgr)
        height, width = work_image.shape[:2]
        with self._lock:
            detector = self._get_detector(width, height)
            _ok, rows = detector.detect(work_image)
        results: List[Dict[str, Any]] = []
        if rows is None:
            return results
        for row in rows:
            results.append({
                'box': [int(round(row[0])), int(round(row[1])), int(round(row[2])), int(round(row[3]))],
                'score': round(float(row[14]), 4),
            })
        results.sort(key=lambda item: item['box'][2] * item['box'][3], reverse=True)
        return results

    def embedding(self, image_bgr: np.ndarray) -> np.ndarray:
        # Detects the largest face and returns its 128-d SFace embedding.
        work_image, _scale = self._downscale(image_bgr)
        height, width = work_image.shape[:2]
        recognizer = self._get_recognizer()
        with self._lock:
            detector = self._get_detector(width, height)
            _ok, rows = detector.detect(work_image)
            if rows is None or len(rows) == 0:
                raise FaceEngineError('No face detected in the image.')
            best = max(rows, key=lambda row: float(row[2]) * float(row[3]))
            aligned = recognizer.alignCrop(work_image, best)
            feature = recognizer.feature(aligned)
        return np.asarray(feature, dtype=np.float32).flatten()


_engine: Optional[FaceEngine] = None
_engine_lock = threading.Lock()


def get_engine() -> FaceEngine:
    global _engine
    with _engine_lock:
        if _engine is None:
            _engine = FaceEngine()
        return _engine
