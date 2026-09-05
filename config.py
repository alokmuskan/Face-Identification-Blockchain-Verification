# Central configuration for the Face Identification and Blockchain Verification pipeline.
# Controls face model paths, blockchain difficulty, matching thresholds, and the data
# directory layout used by both the server and the test suite.
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get('FCV_DATA_DIR', str(BASE_DIR / 'data')))
MODELS_DIR = BASE_DIR / 'models'
FACES_DIR = DATA_DIR / 'faces'
PROBES_DIR = DATA_DIR / 'probes'
LEDGER_PATH = DATA_DIR / 'ledger.json'
FACE_STORE_PATH = DATA_DIR / 'face_store.json'

YUNET_MODEL_PATH = MODELS_DIR / 'face_detection_yunet_2023mar.onnx'
SFACE_MODEL_PATH = MODELS_DIR / 'face_recognition_sface_2021dec.onnx'

# Blockchain / ledger settings
DIFFICULTY = 4
GENESIS_MESSAGE = 'Face Verification Chain Genesis Block'

# Face matching settings (SFace cosine threshold recommended by OpenCV)
MATCH_THRESHOLD = 0.363
MAX_EMBEDDINGS_PER_SUBJECT = 3
MAX_IMAGES_PER_SUBJECT = 3
DETECT_SCORE_THRESHOLD = 0.6
MAX_DETECT_SIDE = 640

# Web search settings
WEB_SEARCH_TIMEOUT = 45                      # seconds given to the reverse-image search
WEB_MIN_RESULTS_TO_FLOG = 1                  # log a warning when fewer than this are found

# Uploads
MAX_IMAGE_BYTES = 10 * 1024 * 1024

# Flask dev server
HOST = '127.0.0.1'
PORT = 5000

def ensure_dirs() -> None:
    for directory in (DATA_DIR, MODELS_DIR, FACES_DIR, PROBES_DIR):
        directory.mkdir(parents=True, exist_ok=True)
