# Phase 4 tests: richer local verification record + on-chain cross-check fixes.
#
# These cover the approved Phase 4 scope: richer local metadata and UI without
# changing the canonical payload or the deployed contract. The contract bridge
# is swapped for a fake so the tests never touch the network.
import os
import tempfile

os.environ.setdefault('FCV_DATA_DIR', tempfile.mkdtemp(prefix='fcv-test-'))

import pytest  # noqa: E402

from app import service  # noqa: E402
from blockchain.contract import compute_record_hash  # noqa: E402


def _minimal_tx(**overrides):
    tx = {
        'type': 'FACE_VERIFICATION',
        'subject_id': 'phase4-subject',
        'subject_name': 'Phase 4',
        'result': 'VERIFIED',
        'matched': True,
        'similarity': 0.9,
        'threshold': 0.363,
        'probe_image_hash': 'a' * 64,
        'embedding_hash': 'b' * 64,
        'web_search_results': [{'url': 'https://example.com/post', 'page_type': 'social_media'}],
        'web_search_count': 1,
        'contract_tx_hash': '0x' + 'c' * 64,
        'contract_chain': 'polygon-amoy',
        'local_block_hash': '0x' + 'd' * 64,
    }
    tx.update(overrides)
    return tx


def test_build_verification_record_passes_through_metadata():
    tx = _minimal_tx(
        block_index=3,
        block_hash='0x' + 'e' * 64,
        block_time=1234567.0,
        result_metadata={'verdict': 'VERIFIED', 'similarity': 0.9},
    )
    vr = service.build_verification_record(tx)
    assert vr['subject_id'] == 'phase4-subject'
    assert vr['subject_name'] == 'Phase 4'
    assert vr['result'] == 'VERIFIED'
    assert vr['similarity'] == 0.9
    assert vr['threshold'] == 0.363
    assert vr['matched'] is True
    assert vr['probe_image_hash'] == 'a' * 64
    assert vr['embedding_hash'] == 'b' * 64
    assert vr['web_search_count'] == 1
    assert vr['web_search_results'][0]['url'] == 'https://example.com/post'
    assert vr['block_index'] == 3
    assert vr['block_hash'] == '0x' + 'e' * 64
    assert vr['block_time'] == 1234567.0
    assert vr['contract_tx_hash'] == '0x' + 'c' * 64
    assert vr['contract_chain'] == 'polygon-amoy'
    assert vr['local_block_hash'] == '0x' + 'd' * 64
    assert vr['result_metadata'] == {'verdict': 'VERIFIED', 'similarity': 0.9}


def test_build_verification_record_defaults_for_missing_fields():
    vr = service.build_verification_record({'type': 'FACE_VERIFICATION'})
    assert vr['subject_id'] is None
    assert vr['subject_name'] is None
    assert vr['result'] is None
    assert vr['similarity'] is None
    assert vr['web_search_results'] == []
    assert vr['web_search_count'] == 0
    assert vr['block_index'] is None
    assert vr['block_hash'] is None
    assert vr['block_time'] is None
    assert vr['contract_tx_hash'] is None
    assert vr['contract_chain'] == 'polygon-amoy'
    assert vr['local_block_hash'] is None
    assert vr['result_metadata'] is None


def test_verify_contract_without_bridge_reports_unconfigured():
    original = service.contract_bridge
    service.contract_bridge = None
    try:
        report = service.verify_contract('any-subject')
        assert report['ok'] is False
        assert 'bridge is not configured' in report['error']
    finally:
        service.contract_bridge = original


class _FakeBridge:
    """Records calls instead of touching the network."""

    def __init__(self, local_block_hash='0x' + '22' * 32):
        self.verify_calls = []
        self._local_block_hash = local_block_hash

    def get_record_hash(self, subject_id):
        return '0x' + '11' * 32

    def verify_record(self, subject_id, expected_hash):
        self.verify_calls.append((subject_id, expected_hash))
        return True

    def get_record_with_local_block_hash(self, subject_id):
        return ('0x' + '11' * 32, self._local_block_hash)


def test_verify_contract_passes_local_block_hash_into_record_hash():
    """The recomputed local hash must match what submit_record committed on-chain."""
    subject_id = 'phase4-crosscheck-subject'
    local_block_hash = '0x' + 'ab' * 32
    fake = _FakeBridge(local_block_hash=local_block_hash)
    original = service.contract_bridge
    service.contract_bridge = fake
    try:
        service.blockchain.record(_minimal_tx(
            subject_id=subject_id,
            contract_tx_hash='0x' + 'cc' * 32,
            local_block_hash=local_block_hash,
        ))
        report = service.verify_contract(subject_id)
        assert report['ok'] is True
        assert report['on_chain_match'] is True
        # The hash handed to verifyRecord() must include local_block_hash.
        expected = compute_record_hash(
            subject_id=subject_id,
            similarity=0.9,
            result='VERIFIED',
            probe_image_hash='a' * 64,
            web_result_count=1,
            local_block_hash=local_block_hash,
        )
        assert fake.verify_calls[-1][1] == expected
        assert report['local_record_hash'] == expected
        # The fake on-chain record points back to a real local block hash.
        assert report['local_block_hash_matches_on_chain'] is True
    finally:
        service.contract_bridge = original