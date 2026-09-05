#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
End-to-end demo of the face identification and blockchain verification pipeline.

Pipeline:
  1. Load a probe image (face scan input).
  2. Run face detection + embedding (YuNet + SFace).
  3. Identify the face against enrolled subjects (or enroll one first if needed).
  4. If matched, upload the probe image to a reverse-image search engine
     (Yandex Images via headless Chrome) to find matching web/social media posts.
  5. Record the face verification + web search results on the blockchain.
  6. Validate the chain to prove the record is tamper-evident.

Usage:
    python tools/demo_pipeline.py                       # use a built-in probe image
    python tools/demo_pipeline.py --probe path/to.jpg   # use your own image

If no subjects are enrolled yet, the script registers a subject from the probe
image first so the pipeline can run end-to-end non-interactively.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import logging
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np

# Ensure the project root is on sys.path so the package imports work from
# any working directory.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config import DATA_DIR, FACES_DIR, PROBES_DIR, ensure_dirs
from faceid.engine import FaceEngine, FaceEngineError, get_engine
from faceid.similarity import cosine_similarity
from services.verification_service import VerificationError, VerificationService
from websearch.search import WebSearchEngine, WebSearchResult

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)-7s %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger('demo')


def load_image(path: Path) -> bytes:
    """Read an image file and return raw bytes."""
    if not path.exists():
        raise FileNotFoundError(f'Image not found: {path}')
    data = path.read_bytes()
    if not data:
        raise ValueError('Image file is empty.')
    return data


def encode_image_to_data_url(image_bytes: bytes) -> str:
    """Convert raw image bytes to a base64 data URL for web upload."""
    encoded = base64.b64encode(image_bytes).decode('ascii')
    return f'data:image/png;base64,{encoded}'


def make_synthetic_face(face_name: str = 'demo-subject') -> tuple:
    """
    Create a larger, more realistic synthetic face-like image so the demo works
    without external photos. The image is saved into DATA_DIR/faces/ and also
    returned as bytes. The larger size and more features help YuNet detect it.
    """
    ensure_dirs()

    # Larger canvas (YuNet works better with >~100px faces).
    h, w = 320, 280
    img = np.full((h, w, 3), 255, dtype=np.uint8)
    # Skin tone background
    img[:, :] = (225, 175, 135)

    # Hair (dark oval on top)
    cv2.ellipse(img, (140, 60), (120, 55), 0, 0, 360, (40, 30, 30), -1)

    # Forehead / face oval
    cv2.ellipse(img, (140, 150), (100, 130), 0, 0, 360, (230, 180, 145), -1)

    # Eyes (with eyebrows)
    cv2.rectangle(img, (70, 95), (120, 102), (50, 30, 20), -1)   # left brow
    cv2.rectangle(img, (165, 95), (215, 102), (50, 30, 20), -1)  # right brow
    cv2.circle(img, (95, 115), 14, (255, 255, 255), -1)           # left eye white
    cv2.circle(img, (190, 115), 14, (255, 255, 255), -1)          # right eye white
    cv2.circle(img, (96, 116), 7, (40, 40, 40), -1)               # left pupil
    cv2.circle(img, (191, 116), 7, (40, 40, 40), -1)              # right pupil
    cv2.circle(img, (97, 114), 2, (255, 255, 255), -1)            # left highlight
    cv2.circle(img, (192, 114), 2, (255, 255, 255), -1)           # right highlight

    # Nose
    cv2.line(img, (140, 130), (140, 165), (170, 130, 110), 3)
    cv2.circle(img, (140, 165), 5, (200, 160, 130), -1)

    # Mouth
    cv2.ellipse(img, (140, 200), (50, 14), 0, 0, 360, (190, 90, 85), -1)
    # Upper lip line
    pts = np.array([[95,200],[140,188],[185,200]], np.int32)
    cv2.polylines(img, [pts], True, (225, 150, 135), 2)

    # Ears (simple)
    cv2.ellipse(img, (35, 150), (12, 25), 0, 0, 360, (190, 150, 125), -1)
    cv2.ellipse(img, (245, 150), (12, 25), 0, 0, 360, (190, 150, 125), -1)

    # Save a copy into the faces dir.
    ok, buffer = cv2.imencode('.png', img)
    if not ok:
        raise RuntimeError('Could not encode synthetic face image.')
    image_bytes = buffer.tobytes()

    store_path = FACES_DIR / 'demo-subject-synthetic.png'
    store_path.write_bytes(image_bytes)
    return image_bytes, store_path


def detect_and_embed(engine: FaceEngine, image_bytes: bytes) -> dict:
    """Run face detection and embedding, return structured results."""
    image = engine.decode_image(image_bytes)
    faces = engine.detect_faces(image)
    if not faces:
        raise FaceEngineError('No face detected in the image.')
    embedding = engine.embedding(image)
    return {
        'face_count': len(faces),
        'largest_face': faces[0],
        'embedding_shape': list(embedding.shape),
        'embedding_hash': hashlib.sha256(embedding.tobytes()).hexdigest(),
    }


def find_closest_subject(service: VerificationService, embedding: np.ndarray) -> dict:
    """Find the closest enrolled subject for the given embedding."""
    match = service.store.match(embedding)
    return match


def enroll_subject_if_needed(service: VerificationService, name: str, image_bytes: bytes) -> dict:
    """Register a subject if no matching subject exists yet."""
    image = service.engine.decode_image(image_bytes)
    embedding = service.engine.embedding(image)
    match = service.store.match(embedding)

    if match['matched']:
        return {
            'enrolled': False,
            'subject': match['subject'],
            'similarity': match['similarity'],
        }

    logger.info('No matching subject found; enrolling "%s"...', name)
    result = service.register(name, image_bytes)
    logger.info('Enrolled subject: %s (id=%s)', result['subject']['name'], result['subject']['subject_id'])
    return {
        'enrolled': True,
        'subject': result['subject'],
        'block': result['block'],
    }


def search_web_for_image(image_bytes: bytes) -> list:
    """Run reverse image search and return a list of WebSearchResult dicts."""
    logger.info('Launching reverse image search (Yandex Images via headless Chrome)...')
    t0 = time.time()
    results: list = []
    try:
        with WebSearchEngine(timeout_seconds=45) as engine:
            results = engine.search(image_bytes)
    except Exception as exc:
        logger.warning('Web search failed: %s', exc)
        return []

    elapsed = time.time() - t0
    logger.info('Web search completed in %.1fs — %d result(s)', elapsed, len(results))
    return [r.to_dict() for r in results]


def print_section(title: str, width: int = 72) -> None:
    print()
    print('=' * width)
    print(f'  {title}')
    print('=' * width)


def print_kv(label: str, value: str, indent: int = 2) -> None:
    pad = ' ' * indent
    print(f"{pad}{label}: {value}")


def print_results(results: list, max_items: int = 8) -> None:
    if not results:
        print('(no external matches returned)')
        return
    for i, r in enumerate(results[:max_items], 1):
        print(f"  [{i}] {r['page_type']}: {r['title']}")
        print(f"      URL: {r['url']}")
        desc = (r['description'] or '').strip()
        if desc:
            print(f"      {desc[:120]}")
        print()


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(description='Face Identification & Blockchain Verification pipeline demo.')
    parser.add_argument('--probe', type=Path, help='Path to a probe image (face scan).')
    parser.add_argument('--subject-name', default='Demo Subject', help='Subject name to enroll if needed.')
    args = parser.parse_args(argv)

    ensure_dirs()

    print_section('Face Identification & Blockchain Verification Pipeline')
    print(f'  Project root: {_ROOT}')
    print(f'  Data directory: {DATA_DIR}')

    # Resolve the probe image.
    if args.probe:
        probe_path = args.probe.resolve()
    else:
        # Try to find an image the user may have enrolled already; otherwise make one.
        probes = list(PROBES_DIR.glob('*.png')) if PROBES_DIR.exists() else []
        faces = list(FACES_DIR.glob('*.png')) if FACES_DIR.exists() else []
        if probes:
            probe_path = probes[-1]
            print(f'  Using probe image from data/probes/: {probe_path.name}')
        elif faces:
            probe_path = faces[-1]
            print(f'  Using face image from data/faces/ as probe: {probe_path.name}')
        else:
            print('  No existing images found — generating a synthetic face for the demo.')
            image_bytes, _ = make_synthetic_face(args.subject_name)
            probe_path = PROBES_DIR / 'demo-synthetic-probed.png'
            probe_path.write_bytes(image_bytes)
            print(f'  Synthetic probe saved to: {probe_path}')

    image_bytes = load_image(probe_path)
    print_kv('Probe image', probe_path.name)
    print_kv('Image bytes', f'{len(image_bytes)} bytes')
    print_kv('SHA-256', hashlib.sha256(image_bytes).hexdigest()[:16] + '...')

    # Step 1: face detection + embedding.
    print_section('STEP 1 — Face detection & embedding')
    engine = get_engine()
    if not engine.models_available():
        print('ERROR: Face models not found. Run: python tools/fetch_models.py')
        return 1
    # Step 2: identify against enrolled subjects.
    print_section('STEP 2 — Face identification (against enrolled subjects)')
    service = VerificationService()
    try:
        det_info = detect_and_embed(engine, image_bytes)
        print(f'  Face detected: {det_info["face_count"]} face(s)')
        print(f'  Largest face box: {det_info["largest_face"]["box"]}')
        print(f'  Detection score: {det_info["largest_face"]["score"]}')
        print(f'  Embedding: {det_info["embedding_shape"][0]}-d vector, hash {det_info["embedding_hash"][:12]}...')
        embedding = engine.embedding(engine.decode_image(image_bytes))
    except FaceEngineError as exc:
        print(f'  Detection warning: {exc}')
        print('  Attempting embedding-only path (may still work if face is detected during embedding)...')
        embedding = engine.embedding(engine.decode_image(image_bytes))

    match = find_closest_subject(service, embedding)
    print(f'  Best similarity: {match["similarity"]:.4f} (threshold {match["threshold"]:.3f})')
    if match['subject']:
        print(f'  Matched subject: {match["subject"]["name"]} (id={match["subject"]["subject_id"]})')
    else:
        print('  No enrolled subject matched.')

    # If no match, enroll from the probe image so the pipeline can continue.
    if not match['matched']:
        enroll_result = enroll_subject_if_needed(service, args.subject_name, image_bytes)
        if enroll_result['enrolled']:
            subject = enroll_result['subject']
            print(f'  Enrolled: {subject["name"]} (id={subject["subject_id"]})')
            print(f'  On-chain block: #{enroll_result["block"]["index"]} hash={enroll_result["block"]["hash"][:16]}...')
            # Re-run matching against the freshly enrolled subject.
            match = find_closest_subject(service, embedding)
            print(f'  Re-checked similarity: {match["similarity"]:.4f}')

    # Step 3: verify via the full service (this also runs web search internally).
    print_section('STEP 3 — Identify via VerificationService (with web search)')

    # We want to demo the web search explicitly, so run it separately here.
    # But the identify() call also does a web search — to avoid double work,
    # we run identify() with a short-circuit: pass image, then separately print
    # web results from the return.
    identify_result = service.identify(image_bytes)
    print(f'  Result: {identify_result["result"]}')
    print(f'  Match similarity: {identify_result["match"]["similarity"]:.4f}')
    if identify_result['match']['subject']:
        print(f'  Matched: {identify_result["match"]["subject"]["name"]} (id={identify_result["match"]["subject"]["subject_id"]})')

    print()
    print(f'  Block # {identify_result["block"]["index"]}')
    print(f'  Block hash: {identify_result["block"]["hash"]}')
    print(f'  Nonce: {identify_result["block"]["nonce"]}')
    print(f'  Previous hash: {identify_result["block"]["previous_hash"][:16]}...')

    web_results = identify_result.get('web_results', [])
    print(f'  Web search results returned: {len(web_results)}')
    if web_results:
        print_results(web_results)
    else:
        print('  (No web results returned — Yandex may not have indexed similar images. The pipeline still records the search attempt on-chain.)')

    # Step 4: show what was recorded on-chain.
    print_section('STEP 4 — On-chain record (blockchain)')
    tx = identify_result['transaction']
    print_kv('Transaction type', tx.get('type'))
    print_kv('Result', tx.get('result'))
    print_kv('Subject ID', tx.get('subject_id'))
    print_kv('Subject name', tx.get('subject_name') or '-')
    print_kv('Similarity', tx.get('similarity'))
    print_kv('Probe image hash', tx.get('probe_image_hash', '-')[:24] + '...')
    print_kv('Web search count (on-chain)', tx.get('web_search_count', 0))
    if tx.get('web_search_results'):
        print('  Web search results recorded on-chain:')
        for i, r in enumerate(tx['web_search_results'][:5], 1):
            print(f'    [{i}] {r["page_type"]}: {r["url"]}')

    print()
    print(f'  Ledger location: {DATA_DIR / "ledger.json"}')

    # Step 5: validate the chain.
    print_section('STEP 5 — Blockchain integrity verification')
    report = service.blockchain.validate_chain()
    print(f'  Blocks checked: {report["blocks_checked"]}')
    print(f'  Chain valid: {report["valid"]}')
    if report['errors']:
        print('  ERRORS:')
        for err in report['errors']:
            print(f'    - Block #{err["index"]}: {err["reason"]}')
    else:
        print('  All hashes and links verified — the record is tamper-evident.')

    # Step 6: show full chain stats.
    print_section('Pipeline complete — chain statistics')
    stats = service.blockchain.stats()
    print(f'  Total blocks: {stats["blocks"]}')
    print(f'  Difficulty: {stats["difficulty"]} leading hex zeros')
    print(f'  Last block hash: {stats["last_block_hash"][:16]}...')
    print(f'  Last block time: {time.strftime("%H:%M:%S", time.localtime(stats["last_block_time"]))}')

    subjects = service.store.list_subjects()
    print(f'  Enrolled subjects: {len(subjects)}')
    for s in subjects:
        print(f'    - {s["name"]} ({s["subject_id"]}): {s["embedding_count"]} embedding(s)')

    print()
    print('=' * 72)
    print('  Pipeline finished successfully.')
    print('  The face scan resulted in a subject match, a web/social media search')
    print('  was performed, and the entire outcome was recorded on a tamper-evident')
    print('  blockchain — ready for re-verification at any time.')
    print('=' * 72)
    return 0


if __name__ == '__main__':
    sys.exit(main())
