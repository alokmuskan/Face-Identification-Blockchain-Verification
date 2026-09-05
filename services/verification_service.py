# High-level workflow: enroll faces, identify probes, record events on-chain.
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from blockchain import Blockchain
from config import BASE_DIR, DIFFICULTY, FACES_DIR, GENESIS_MESSAGE, LEDGER_PATH, PROBES_DIR, WEB_SEARCH_TIMEOUT
from faceid.engine import FaceEngineError, get_engine
from faceid.store import FaceStore
from websearch.search import WebSearchEngine

logger = logging.getLogger(__name__)


class VerificationError(Exception):
    """Domain-level error with a user-presentable message."""
    pass


class VerificationService:
    def __init__(self) -> None:
        self.blockchain = Blockchain(LEDGER_PATH, difficulty=DIFFICULTY, genesis_message=GENESIS_MESSAGE)
        self.store = FaceStore()
        self.engine = get_engine()

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def image_digest(image_bytes: bytes) -> str:
        return hashlib.sha256(image_bytes).hexdigest()

    @staticmethod
    def _save_image(directory: Path, image_bytes: bytes, digest: str) -> str:
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f'{digest}.png'
        if not target.exists():
            target.write_bytes(image_bytes)
        return target.relative_to(BASE_DIR).as_posix()

    # -- workflows ----------------------------------------------------------

    def register(self, name: str, image_bytes: bytes) -> Dict[str, Any]:
        name = (name or '').strip()
        if not name:
            raise VerificationError('A subject name is required.')
        if len(name) > 80:
            raise VerificationError('Subject name is too long (80 characters max).')
        try:
            image = self.engine.decode_image(image_bytes)
            embedding = self.engine.embedding(image)
        except FaceEngineError as exc:
            raise VerificationError(str(exc)) from exc
        digest = self.image_digest(image_bytes)
        stored_path = self._save_image(FACES_DIR, image_bytes, digest)
        subject = self.store.add_subject(name, embedding, image_path=stored_path)
        tx, block = self.blockchain.record({
            'type': 'FACE_REGISTRATION',
            'subject_id': subject['subject_id'],
            'subject_name': subject['name'],
            'image_hash': digest,
            'embedding_hash': subject['embedding_hash'],
            'embedding_count': subject['embedding_count'],
        })
        return {'subject': subject, 'transaction': tx, 'block': block.to_dict()}

    def identify(self, image_bytes: bytes) -> Dict[str, Any]:
        try:
            image = self.engine.decode_image(image_bytes)
            embedding = self.engine.embedding(image)
        except FaceEngineError as exc:
            raise VerificationError(str(exc)) from exc
        match = self.store.match(embedding)
        digest = self.image_digest(image_bytes)
        stored_path = self._save_image(PROBES_DIR, image_bytes, digest)
        if match['matched']:
            result = 'VERIFIED'
            subject_id = match['subject']['subject_id']
            subject_name = match['subject']['name']
        else:
            result = 'REJECTED'
            subject_id = 'unknown'
            subject_name = None

        # Run reverse image search against the web when we have a match.
        web_results = None
        if match['matched']:
            try:
                with WebSearchEngine(timeout_seconds=WEB_SEARCH_TIMEOUT) as engine:
                    web_results = engine.search(image_bytes)
            except Exception as exc:
                logger.warning('Web search skipped: %s', exc)

        tx, block = self.blockchain.record({
            'type': 'FACE_VERIFICATION',
            'result': result,
            'subject_id': subject_id,
            'subject_name': subject_name,
            'matched': match['matched'],
            'similarity': match['similarity'],
            'threshold': match['threshold'],
            'probe_image_hash': digest,
            'web_search_results': [r.to_dict() for r in (web_results or [])],
            'web_search_count': len(web_results or []),
        })
        return {
            'result': result,
            'match': match,
            'web_results': [r.to_dict() for r in (web_results or [])],
            'transaction': tx,
            'block': block.to_dict(),
            'probe_path': stored_path,
        }

    # -- pass-through queries ----------------------------------------------

    def verify_chain(self) -> Dict[str, Any]:
        return self.blockchain.validate_chain()

    def history(self, subject_id: str) -> Optional[Dict[str, Any]]:
        subject = self.store.get(subject_id)
        if subject is None:
            return None
        return {
            'subject': subject,
            'events': self.blockchain.transactions_for_subject(subject_id),
        }

    def dashboard_stats(self) -> Dict[str, Any]:
        stats = self.blockchain.stats()
        stats['subjects'] = self.store.count()
        stats['chain_valid'] = self.blockchain.validate_chain()['valid']
        return stats

    def recent_events(self, limit: int = 10) -> list:
        rows = []
        for tx in self.blockchain.all_transactions():
            if tx.get('type') in ('FACE_REGISTRATION', 'FACE_VERIFICATION'):
                rows.append(tx)
        return list(reversed(rows[-limit:]))
