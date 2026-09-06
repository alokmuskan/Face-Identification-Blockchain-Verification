# High-level workflow: enroll faces, identify probes, record events on-chain.
from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from blockchain import Blockchain
from blockchain.contract import compute_record_hash
from config import BASE_DIR, DIFFICULTY, FACES_DIR, GENESIS_MESSAGE, LEDGER_PATH, PROBES_DIR, WEB_SEARCH_TIMEOUT
from faceid.engine import FaceEngineError, get_engine
from faceid.store import FaceStore
from websearch.search import WebSearchEngine

logger = logging.getLogger(__name__)


class VerificationError(Exception):
    """Domain-level error with a user-presentable message."""
    pass


def resolve_chain_config() -> Optional[Dict[str, Any]]:
    """Return on-chain bridge settings, or None when unconfigured.

    Precedence: values from the local, gitignored config_chain.py, with the
    WEB3_RPC_URL / CONTRACT_ADDRESS / PRIVATE_KEY environment variables as
    fallbacks so deployments can supply secrets via the environment.
    """
    try:
        import config_chain as cc  # type: ignore[import]
        rpc = getattr(cc, 'POLY_AMOY_RPC', '') or os.environ.get('WEB3_RPC_URL', '')
        address = getattr(cc, 'CONTRACT_ADDRESS', '') or os.environ.get('CONTRACT_ADDRESS', '')
        private_key = getattr(cc, 'PRIVATE_KEY', '') or os.environ.get('PRIVATE_KEY', '')
        chain_id = getattr(cc, 'CHAIN_ID', 80002)
    except Exception:
        rpc = os.environ.get('WEB3_RPC_URL', '')
        address = os.environ.get('CONTRACT_ADDRESS', '')
        private_key = os.environ.get('PRIVATE_KEY', '')
        chain_id = int(os.environ.get('CHAIN_ID', '80002'))
    if not (rpc and address and private_key):
        return None
    return {
        'rpc_url': rpc,
        'contract_address': address,
        'private_key': private_key,
        'chain_id': chain_id,
    }


class VerificationService:
    def __init__(self) -> None:
        self.blockchain = Blockchain(LEDGER_PATH, difficulty=DIFFICULTY, genesis_message=GENESIS_MESSAGE)
        self.store = FaceStore()
        self.engine = get_engine()
        self.contract_bridge: Any = None
        self._load_contract_bridge()

    # -- on-chain bridge setup ---------------------------------------------

    def _load_contract_bridge(self) -> None:
        """Lazy-load the on-chain bridge only when a config is present.

        When config_chain.py is not present, is incomplete, or the relevant
        environment variables are unset, the pipeline continues with the local
        ledger only and never touches the network.
        """
        cfg = resolve_chain_config()
        if cfg is None:
            logger.info('On-chain bridge disabled: no config_chain.py values or env vars.')
            return
        try:
            from blockchain.contract import ContractBridge  # defer import so web3 is optional
        except Exception as exc:
            logger.warning('On-chain bridge unavailable: %s', exc)
            self.contract_bridge = None
            return
        try:
            self.contract_bridge = ContractBridge(
                rpc_url=cfg['rpc_url'],
                contract_address=cfg['contract_address'],
                private_key=cfg['private_key'],
                chain_id=cfg['chain_id'],
            )
            logger.info('On-chain bridge enabled for contract %s.', cfg['contract_address'])
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
            'embedding_hash': hashlib.sha256(embedding.tobytes()).hexdigest(),
            'web_search_results': [r.to_dict() for r in (web_results or [])],
            'web_search_count': len(web_results or []),
        }

        # Optionally write a matching record to the smart contract and store
        # the on-chain tx hash in the local ledger for cross-verification.
        # The local block is mined first so the on-chain record can reference it.
        contract_tx_hash: Optional[str] = None
        local_block_hash: Optional[str] = None
        on_chain_error: Optional[str] = None
        on_chain_skipped_reason: Optional[str] = None
        if match['matched']:
            if self.contract_bridge is None:
                on_chain_skipped_reason = (
                    'On-chain bridge not configured (set config_chain.py or the '
                    'WEB3_RPC_URL / CONTRACT_ADDRESS / PRIVATE_KEY env vars).'
                )
            else:
                try:
                    # Mine the local block before submitting on-chain so the on-chain
                    # record can reference the exact local block that carries it.
                    tx, block = self.blockchain.record(tx_base)
                    local_block_hash = block.hash
                    contract_tx_hash = self.contract_bridge.submit_record(
                        subject_id=subject_id,
                        similarity=match['similarity'],
                        result=result,
                        probe_image_hash=digest,
                        web_result_count=len(web_results or []),
                        local_block_hash=local_block_hash,
                    )
                    tx_base['contract_tx_hash'] = contract_tx_hash
                    tx_base['contract_chain'] = 'polygon-amoy'
                    tx_base['local_block_hash'] = local_block_hash
                    tx_base['block_index'] = block.index
                    tx_base['block_hash'] = block.hash
                    tx_base['verification_time'] = block.timestamp
                    tx_base['result_metadata'] = {
                        'verdict': result,
                        'similarity': match['similarity'],
                        'threshold': match['threshold'],
                        'matched': match['matched'],
                    }
                except Exception as exc:
                    on_chain_error = f'{type(exc).__name__}: {exc}'
                    tx_base['on_chain_error'] = on_chain_error
                    logger.warning('On-chain write skipped: %s', on_chain_error)

        tx, block = self.blockchain.record(tx_base)
        return {
            'result': result,
            'match': match,
            'web_results': [r.to_dict() for r in (web_results or [])],
            'transaction': tx,
            'block': block.to_dict(),
            'probe_path': stored_path,
            'on_chain_submitted': contract_tx_hash is not None,
            'contract_tx_hash': contract_tx_hash,
            'contract_chain': 'polygon-amoy' if contract_tx_hash else None,
            'on_chain_error': on_chain_error,
            'on_chain_skipped_reason': on_chain_skipped_reason,
        }

    # -- richer local verification record -------------------------------------

    def build_verification_record(self, tx: Dict[str, Any]) -> Dict[str, Any]:
        """Build a UI-friendly local verification record from a ledger transaction.

        This keeps the richer display metadata local while the on-chain record
        remains the immutable public proof.
        """
        return {
            'subject_id': tx.get('subject_id'),
            'subject_name': tx.get('subject_name'),
            'result': tx.get('result'),
            'similarity': tx.get('similarity'),
            'threshold': tx.get('threshold'),
            'matched': tx.get('matched'),
            'probe_image_hash': tx.get('probe_image_hash'),
            'embedding_hash': tx.get('embedding_hash'),
            'web_search_results': tx.get('web_search_results', []),
            'web_search_count': tx.get('web_search_count', 0),
            'block_index': tx.get('block_index'),
            'block_hash': tx.get('block_hash'),
            'block_time': tx.get('block_time'),
            'contract_tx_hash': tx.get('contract_tx_hash'),
            'contract_chain': tx.get('contract_chain', 'polygon-amoy'),
            'local_block_hash': tx.get('local_block_hash'),
            'result_metadata': tx.get('result_metadata'),
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
        # compute_record_hash is the single source of truth for the canonical
        # payload + its keccak256 hash. Don't reconstruct the payload bytes here.
        # The local_block_hash must be passed through so the recomputed hash
        # matches what submit_record() committed on-chain for enriched records.
        local_record_hash = compute_record_hash(
            subject_id=verif.get('subject_id', subject_id),
            similarity=verif.get('similarity', 0.0),
            result=verif.get('result', ''),
            probe_image_hash=verif.get('probe_image_hash', ''),
            web_result_count=verif.get('web_search_count', 0),
            local_block_hash=verif.get('local_block_hash') or '',
        )
        on_chain_hash = self.contract_bridge.get_record_hash(subject_id)
        # Compare the LOCAL payload hash against the on-chain record hash.
        # This is the tamper-evidence check: if the local payload was altered,
        # local_record_hash will differ from the on-chain recordHash and this
        # will return False.
        matched = self.contract_bridge.verify_record(subject_id, local_record_hash)
        # Optional traceability: read the on-chain local block hash if the
        # contract supports it and the record has one attached.
        local_block_hash_on_chain = None
        try:
            pair = self.contract_bridge.get_record_with_local_block_hash(subject_id)
            if pair is not None:
                _, local_block_hash_on_chain = pair
        except Exception as exc:
            logger.debug('Could not read on-chain local block hash: %s', exc)

        return {
            'ok': True,
            'subject_id': subject_id,
            'local_record_hash': local_record_hash,
            'on_chain_record_hash': on_chain_hash,
            'on_chain_match': matched,
            'contract_tx_hash': verif.get('contract_tx_hash'),
            'contract_chain': verif.get('contract_chain', 'polygon-amoy'),
            'local_block_hash': verif.get('local_block_hash'),
            'on_chain_local_block_hash': local_block_hash_on_chain,
            'local_block_index': verif.get('block_index'),
            'local_block_hash_matches_on_chain': (
                local_block_hash_on_chain is not None
                and verif.get('local_block_hash') == local_block_hash_on_chain
            ),
            'local_verification_record': self.build_verification_record(verif),
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
