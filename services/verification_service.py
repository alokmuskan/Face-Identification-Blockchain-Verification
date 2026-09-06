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
        self.contract_bridge: Any = None
        self._load_contract_bridge()

    # -- on-chain bridge setup ---------------------------------------------

    def _load_contract_bridge(self) -> None:
        """Lazy-load the on-chain bridge only when a local config is present.

        When config_chain.py is not present or is incomplete, the pipeline
        continues with the local ledger only and never touches the network.
        """
        try:
            import config_chain as cc  # type: ignore[import]
        except Exception:
            return
        address = getattr(cc, 'CONTRACT_ADDRESS', None)
        private_key = getattr(cc, 'PRIVATE_KEY', None)
        rpc = getattr(cc, 'POLY_AMOY_RPC', None)
        chain_id = getattr(cc, 'CHAIN_ID', 80143)
        if not address or not private_key or not rpc:
            logger.info('On-chain bridge disabled: config_chain missing values.')
            return
        try:
            from blockchain.contract import ContractBridge  # defer import so web3 is optional
        except Exception as exc:
            logger.warning('On-chain bridge unavailable: %s', exc)
            self.contract_bridge = None
            return
        try:
            self.contract_bridge = ContractBridge(
                rpc_url=rpc,
                contract_address=address,
                private_key=private_key,
                chain_id=chain_id,
            )
            logger.info('On-chain bridge enabled for contract %s.', address)
        except Exception as exc:
            logger.warning('On-chain bridge could not be initialized: %s', exc)
            self.contract_bridge = None

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
                with WebSearchEngine(
                    timeout_seconds=WEB_SEARCH_TIMEOUT,
                    cache_dir=PROBES_DIR.parent / 'webcache',
                    cache_ttl_seconds=3600,
                ) as engine:
                    web_results = engine.search(image_bytes)
            except Exception as exc:
                logger.warning('Web search skipped: %s', exc)

        tx_base = {
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
        }

        # Optionally write a matching record to the smart contract and store
        # the on-chain tx hash in the local ledger for cross-verification.
        contract_tx_hash: Optional[str] = None
        if self.contract_bridge is not None and match['matched']:
            try:
                contract_tx_hash = self.contract_bridge.submit_record(
                    subject_id=subject_id,
                    similarity=match['similarity'],
                    result=result,
                    probe_image_hash=digest,
                    web_result_count=len(web_results or []),
                )
                tx_base['contract_tx_hash'] = contract_tx_hash
                tx_base['contract_chain'] = 'polygon-amoy'
            except Exception as exc:
                logger.warning('On-chain write skipped: %s', exc)

        tx, block = self.blockchain.record(tx_base)
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

    def verify_contract(self, subject_id: str) -> Dict[str, Any]:
        """Cross-check the local ledger payload against the on-chain recordHash."""
        if self.contract_bridge is None:
            return {'ok': False, 'error': 'On-chain bridge is not configured.'}
        # Find the latest local FACE_VERIFICATION payload for this subject.
        events = self.blockchain.transactions_for_subject(subject_id)
        verif = None
        for ev in reversed(events):
            if ev.get('type') == 'FACE_VERIFICATION':
                verif = ev
                break
        if verif is None:
            return {'ok': False, 'error': 'No local FACE_VERIFICATION record for this subject.'}
        payload = {
            'subject_id': verif.get('subject_id', subject_id),
            'similarity': verif.get('similarity', 0.0),
            'result': verif.get('result', ''),
            'probe_image_hash': verif.get('probe_image_hash', ''),
            'web_result_count': verif.get('web_search_count', 0),
            'record_schema': 'v1',
            'chain': 'polygon-amoy',
        }
        payload_bytes = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
        local_record_hash = hashlib.sha256(payload_bytes).hexdigest()  # for display only; on-chain uses keccak256
        on_chain_hash = self.contract_bridge.get_record_hash(subject_id)
        matched = self.contract_bridge.verify_record(subject_id, on_chain_hash or '')
        return {
            'ok': True,
            'subject_id': subject_id,
            'local_payload_sha256': local_record_hash,
            'on_chain_record_hash': on_chain_hash,
            'on_chain_match': matched,
            'contract_tx_hash': verif.get('contract_tx_hash'),
            'contract_chain': verif.get('contract_chain', 'polygon-amoy'),
        }

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
