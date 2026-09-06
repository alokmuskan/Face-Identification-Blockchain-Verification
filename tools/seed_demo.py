#!/usr/bin/env python
"""Seed a fresh data directory so a new deployment is demo-ready.

Deployments on ephemeral filesystems (Render/Railway free tiers) start with
an empty data/ dir on every boot. This script restores the demo baseline:

1. Registers the bundled seed probe (seed/obama-probe.jpg) as its subject,
   exactly like a /register call would, so face matching works immediately.
2. Copies the probe into data/probes/ so the /demo page has a sample.
3. Mines a FACE_VERIFICATION block (without touching the network) so the
   ledger, history pages, and dashboard show real content on first visit.

Idempotent: safe to run on every boot; it exits early when the subject
already exists. Enable it by setting SEED_DEMO=1 (the Dockerfile CMD does
this when SEED_DEMO is on).
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

SEED_PROBE = BASE_DIR / "seed" / "obama-probe.jpg"
SUBJECT_NAME = "Barack Obama"


def main() -> int:
    from config import ensure_dirs

    if not SEED_PROBE.exists():
        print(f"[seed] seed probe missing at {SEED_PROBE}; skipping.")
        return 0

    ensure_dirs()

    from services.verification_service import VerificationService

    service = VerificationService()

    probe_bytes = SEED_PROBE.read_bytes()

    # Detect whether the seed subject is already enrolled by matching the
    # probe's embedding against the store.
    from faceid.engine import get_engine

    engine = get_engine()
    probe_embedding = engine.embedding(engine.decode_image(probe_bytes))
    already = bool(service.store.match(probe_embedding).get("matched"))

    if not already:
        print(f"[seed] registering seed subject '{SUBJECT_NAME}' ...")
        service.register(SUBJECT_NAME, probe_bytes)
    else:
        print(f"[seed] subject for seed probe already enrolled; skipping registration.")

    # Make the probe available to the /demo page.
    from config import PROBES_DIR

    demo_probe = PROBES_DIR / SEED_PROBE.name
    if not demo_probe.exists():
        shutil.copyfile(SEED_PROBE, demo_probe)
        print(f"[seed] copied demo probe to {demo_probe}")

    # Mine a demo FACE_VERIFICATION block (local only, no web search, no
    # network) so history/dashboard pages have content on a fresh deploy.
    subject = service.store.list_subjects()[0]
    events = service.blockchain.transactions_for_subject(subject["subject_id"])
    has_verification = any(
        e.get("type") == "FACE_VERIFICATION" for e in events
    )
    if not has_verification:
        import hashlib

        match_info = service.store.match(probe_embedding)
        service.blockchain.record({
            "type": "FACE_VERIFICATION",
            "result": "VERIFIED" if match_info["matched"] else "REJECTED",
            "subject_id": subject["subject_id"],
            "subject_name": subject["name"],
            "matched": match_info["matched"],
            "similarity": match_info["similarity"],
            "threshold": match_info["threshold"],
            "probe_image_hash": service.image_digest(probe_bytes),
            "embedding_hash": hashlib.sha256(probe_embedding.tobytes()).hexdigest(),
            "web_search_results": [],
            "web_search_count": 0,
            "seeded": True,
        })
        print("[seed] mined demo FACE_VERIFICATION block.")
    else:
        print("[seed] verification event already present; ledger untouched.")

    print("[seed] done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
