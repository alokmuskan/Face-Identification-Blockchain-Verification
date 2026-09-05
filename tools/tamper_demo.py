# Demonstrate tamper detection: mutate one persisted transaction, then let
# the verifier report the broken chain.
#
# Usage:
#   python tools/tamper_demo.py            (flip a similarity value in the first verification tx)
#   python tools/tamper_demo.py --restore  (remove the ledger so a fresh chain starts)
from __future__ import annotations

import json
import sys
from pathlib import Path

LEDGER_PATH = Path(__file__).resolve().parent.parent / 'data' / 'ledger.json'


def tamper() -> int:
    if not LEDGER_PATH.exists():
        print('No ledger found. Register and identify a face first.')
        return 1
    raw = json.loads(LEDGER_PATH.read_text(encoding='utf-8'))
    changed = False
    for block in raw.get('chain', []):
        for tx in block.get('transactions', []):
            if tx.get('type') == 'FACE_VERIFICATION' and 'similarity' in tx:
                print(f'Block #{block["index"]}: similarity {tx["similarity"]} -> 0.9999')
                tx['similarity'] = 0.9999
                changed = True
                break
        if changed:
            break
    if not changed:
        print('No FACE_VERIFICATION transaction found to tamper with.')
        return 1
    LEDGER_PATH.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding='utf-8')
    print('Ledger tampered. Open the Verify page or GET /api/chain/validate to see the chain fail.')
    print(f'Restore by deleting {LEDGER_PATH} (or run: python tools/tamper_demo.py --restore).')
    return 0


def restore() -> int:
    if LEDGER_PATH.exists():
        LEDGER_PATH.unlink()
        print(f'Removed {LEDGER_PATH}. A fresh chain is created on next start.')
    else:
        print('Nothing to restore.')
    return 0


if __name__ == '__main__':
    sys.exit(restore() if '--restore' in sys.argv[1:] else tamper())
