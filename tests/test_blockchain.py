# Unit tests for the blockchain core.
import json

from blockchain import Block, Blockchain


def make_ledger(tmp_path, difficulty=3):
    return Blockchain(tmp_path / 'ledger.json', difficulty=difficulty, genesis_message='test genesis')


def test_genesis_block_is_created_and_valid(tmp_path):
    chain = make_ledger(tmp_path)
    assert len(chain.chain) == 1
    report = chain.validate_chain()
    assert report['valid'] is True
    assert chain.chain[0].transactions[0]['type'] == 'GENESIS'


def test_mining_links_blocks_and_satisfies_difficulty(tmp_path):
    chain = make_ledger(tmp_path, difficulty=3)
    entry = chain.add_transaction({'type': 'FACE_VERIFICATION', 'subject_id': 'alice'})
    assert 'timestamp' in entry
    block = chain.mine_pending()
    assert block is not None
    assert block.index == 1
    assert block.previous_hash == chain.chain[0].hash
    assert block.hash.startswith('000')
    assert chain.validate_chain()['valid'] is True


def test_record_returns_entry_and_block(tmp_path):
    chain = make_ledger(tmp_path)
    entry, block = chain.record({'type': 'FACE_REGISTRATION', 'subject_id': 'bob'})
    assert entry['subject_id'] == 'bob'
    assert block.index == 1
    assert block.transactions[0]['subject_id'] == 'bob'


def test_tampering_is_detected(tmp_path):
    chain = make_ledger(tmp_path)
    chain.record({'type': 'FACE_VERIFICATION', 'subject_id': 'bob', 'similarity': 0.9})
    path = chain.ledger_path
    raw = json.loads(path.read_text(encoding='utf-8'))
    raw['chain'][1]['transactions'][0]['similarity'] = 0.11
    path.write_text(json.dumps(raw), encoding='utf-8')
    reloaded = Blockchain(path, difficulty=3, genesis_message='test genesis')
    report = reloaded.validate_chain()
    assert report['valid'] is False
    assert report['errors']


def test_history_lookup(tmp_path):
    chain = make_ledger(tmp_path)
    chain.record({'type': 'FACE_VERIFICATION', 'subject_id': 'carol', 'result': 'VERIFIED'})
    events = chain.transactions_for_subject('carol')
    assert len(events) == 1
    assert events[0]['block_index'] == 1
    assert events[0]['result'] == 'VERIFIED'


def test_persistence_round_trip(tmp_path):
    chain = make_ledger(tmp_path)
    chain.record({'type': 'FACE_REGISTRATION', 'subject_id': 'dave'})
    second = Blockchain(chain.ledger_path, difficulty=3, genesis_message='test genesis')
    assert len(second.chain) == len(chain.chain)
    assert second.validate_chain()['valid'] is True
    assert second.pending_transactions == []


def test_block_hash_covers_all_fields():
    block = Block(1, 123.0, [{'a': 1}], '0' * 64)
    digest = block.compute_hash()
    block.nonce = 5
    assert block.compute_hash() != digest
    block.nonce = 0
    assert block.compute_hash() == digest


def test_empty_ledger_rejects_mining(tmp_path):
    chain = make_ledger(tmp_path)
    assert chain.mine_pending() is None
