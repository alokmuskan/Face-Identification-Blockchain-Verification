# Download the YuNet detector and SFace recognizer ONNX models from OpenCV Zoo.
# Git LFS pointer files are detected and rejected; a media.github mirror URL is
# tried as a fallback for each model.
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parent.parent / 'models'
USER_AGENT = 'face-chain-verify-model-fetcher/1.0'

MODEL_FILES = {
    'face_detection_yunet_2023mar.onnx': [
        'https://raw.githubusercontent.com/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx',
        'https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx',
    ],
    'face_recognition_sface_2021dec.onnx': [
        'https://raw.githubusercontent.com/opencv/opencv_zoo/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx',
        'https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx',
    ],
}


def looks_valid(target: Path) -> bool:
    if not target.exists() or target.stat().st_size < 1000:
        return False
    with target.open('rb') as handle:
        head = handle.read(64)
    return not head.startswith(b'version https://git-lfs')


def download(name: str, urls: list) -> bool:
    target = MODELS_DIR / name
    for url in urls:
        print(f'[get ] {name} from {url}')
        try:
            request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
            with urllib.request.urlopen(request, timeout=60) as response, target.open('wb') as out:
                while True:
                    chunk = response.read(1 << 20)
                    if not chunk:
                        break
                    out.write(chunk)
        except Exception as exc:
            print(f'[warn] download failed: {exc}')
            if target.exists():
                target.unlink()
            continue
        if looks_valid(target):
            print(f'[ok  ] {name} ({target.stat().st_size} bytes)')
            return True
        print('[warn] downloaded file is not a valid ONNX model (git-lfs pointer?)')
        if target.exists():
            target.unlink()
    return False


def main() -> int:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    failures = 0
    for name, urls in MODEL_FILES.items():
        target = MODELS_DIR / name
        if looks_valid(target):
            print(f'[skip] {name} already present ({target.stat().st_size} bytes)')
            continue
        if not download(name, urls):
            failures += 1
            print(f'[fail] could not fetch {name}')
    if failures:
        print('Some models are missing. The app will refuse face operations until they are downloaded.')
    else:
        print('All models ready.')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
