# Block model and hashing rules for the verification ledger.
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, List, Optional


class Block:
    # A single immutable block in the hash chain.
    #
    # The block hash covers every field of the block, so any modification of
    # persisted data (transactions, link, nonce or proof-of-work) breaks the
    # chain and is reported by validation.

    def __init__(self, index: int, timestamp: float, transactions: List[Dict[str, Any]],
                 previous_hash: str, nonce: int = 0, block_hash: Optional[str] = None) -> None:
        self.index = index
        self.timestamp = timestamp
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.nonce = nonce
        self.hash = block_hash if block_hash is not None else self.compute_hash()

    def compute_hash(self) -> str:
        payload = json.dumps(
            {
                'index': self.index,
                'timestamp': self.timestamp,
                'transactions': self.transactions,
                'previous_hash': self.previous_hash,
                'nonce': self.nonce,
            },
            sort_keys=True,
            separators=(',', ':'),
            ensure_ascii=False,
        )
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()

    def mine(self, difficulty: int) -> str:
        target = '0' * difficulty
        self.nonce = 0
        self.hash = self.compute_hash()
        while not self.hash.startswith(target):
            self.nonce += 1
            self.hash = self.compute_hash()
        return self.hash

    def meets_difficulty(self, difficulty: int) -> bool:
        return self.hash.startswith('0' * difficulty)

    def links_to(self, previous: 'Block') -> bool:
        return self.previous_hash == previous.hash and self.index == previous.index + 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            'index': self.index,
            'timestamp': self.timestamp,
            'transactions': self.transactions,
            'previous_hash': self.previous_hash,
            'nonce': self.nonce,
            'hash': self.hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Block':
        return cls(
            index=data['index'],
            timestamp=data['timestamp'],
            transactions=data['transactions'],
            previous_hash=data['previous_hash'],
            nonce=data.get('nonce', 0),
            block_hash=data.get('hash'),
        )


def make_genesis_block(difficulty: int, message: str) -> Block:
    block = Block(
        index=0,
        timestamp=time.time(),
        transactions=[{'type': 'GENESIS', 'message': message, 'timestamp': time.time()}],
        previous_hash='0' * 64,
    )
    block.mine(difficulty)
    return block
