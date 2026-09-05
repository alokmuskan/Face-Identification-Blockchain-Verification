# Hash-chained, proof-of-work ledger persisted as JSON with atomic writes.
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .block import Block, make_genesis_block


class Blockchain:
    # Append-only ledger: transactions queue up and are mined into linked
    # blocks. All mutations are guarded by a re-entrant lock so the Flask app
    # can call the ledger safely from request handlers.

    def __init__(self, ledger_path: Path, difficulty: int = 4, genesis_message: str = 'GENESIS') -> None:
        self.ledger_path = Path(ledger_path)
        self.difficulty = int(difficulty)
        self.genesis_message = genesis_message
        self._lock = threading.RLock()
        self.chain: List[Block] = []
        self.pending_transactions: List[Dict[str, Any]] = []
        self._load_or_create()

    # -- persistence ------------------------------------------------------

    def _load_or_create(self) -> None:
        if self.ledger_path.exists():
            self.chain = self._load_chain()
        else:
            genesis = make_genesis_block(self.difficulty, self.genesis_message)
            self.chain = [genesis]
            self._save()

    def _load_chain(self) -> List[Block]:
        raw = json.loads(self.ledger_path.read_text(encoding='utf-8'))
        return [Block.from_dict(item) for item in raw.get('chain', [])]

    def _save(self) -> None:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.ledger_path.with_suffix('.tmp')
        payload = {
            'difficulty': self.difficulty,
            'chain': [block.to_dict() for block in self.chain],
        }
        tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
        os.replace(tmp_path, self.ledger_path)

    # -- core operations ----------------------------------------------------

    def add_transaction(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            entry = dict(transaction)
            entry.setdefault('timestamp', time.time())
            self.pending_transactions.append(entry)
            return entry

    def mine_pending(self) -> Optional[Block]:
        with self._lock:
            if not self.pending_transactions:
                return None
            previous = self.chain[-1]
            block = Block(
                index=previous.index + 1,
                timestamp=time.time(),
                transactions=list(self.pending_transactions),
                previous_hash=previous.hash,
            )
            block.mine(self.difficulty)
            self.chain.append(block)
            self.pending_transactions = []
            self._save()
            return block

    def record(self, transaction: Dict[str, Any]) -> tuple:
        # Add a transaction and immediately mine it into a new block.
        entry = self.add_transaction(transaction)
        block = self.mine_pending()
        if block is None:
            raise RuntimeError('Mining produced no block for a pending transaction.')
        return entry, block

    # -- validation ----------------------------------------------------------

    def validate_chain(self, chain: Optional[List[Block]] = None) -> Dict[str, Any]:
        blocks = list(self.chain) if chain is None else chain
        errors: List[Dict[str, Any]] = []
        if not blocks:
            return {'valid': False, 'blocks_checked': 0,
                    'errors': [{'index': None, 'reason': 'chain is empty'}]}
        previous: Optional[Block] = None
        for block in blocks:
            if block.hash != block.compute_hash():
                errors.append({'index': block.index, 'reason': 'stored hash does not match block content'})
            elif not block.meets_difficulty(self.difficulty):
                errors.append({'index': block.index, 'reason': 'block does not satisfy proof-of-work difficulty'})
            if previous is not None and not block.links_to(previous):
                errors.append({'index': block.index, 'reason': 'broken link to previous block'})
            previous = block
        return {'valid': not errors, 'blocks_checked': len(blocks), 'errors': errors}

    # -- queries ---------------------------------------------------------------

    def find_block(self, index: int) -> Optional[Block]:
        with self._lock:
            if 0 <= index < len(self.chain):
                return self.chain[index]
            return None

    def transactions_for_subject(self, subject_id: str) -> List[Dict[str, Any]]:
        matches: List[Dict[str, Any]] = []
        with self._lock:
            for block in self.chain:
                for tx in block.transactions:
                    if tx.get('subject_id') == subject_id:
                        item = dict(tx)
                        item['block_index'] = block.index
                        item['block_hash'] = block.hash
                        item['block_time'] = block.timestamp
                        matches.append(item)
        return matches

    def all_transactions(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        with self._lock:
            for block in self.chain:
                for tx in block.transactions:
                    item = dict(tx)
                    item['block_index'] = block.index
                    rows.append(item)
        return rows

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            last = self.chain[-1]
            return {
                'blocks': len(self.chain),
                'pending_transactions': len(self.pending_transactions),
                'difficulty': self.difficulty,
                'last_block_hash': last.hash,
                'last_block_time': last.timestamp,
            }
