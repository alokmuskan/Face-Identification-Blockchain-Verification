# Face verification ledger built as a hash-chained, proof-of-work blockchain.
from .block import Block, make_genesis_block
from .ledger import Blockchain

__all__ = ['Block', 'Blockchain', 'make_genesis_block']
