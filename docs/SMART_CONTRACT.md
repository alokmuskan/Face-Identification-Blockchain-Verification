# Smart Contract — On-Chain Face Verification

Move from the local JSON ledger to a **public blockchain** (Polygon Amoy testnet) so anyone can verify the records on Polygonscan.

---

## Why a Smart Contract

The local JSON ledger is great for demos, but judges may see it as "just a file." A public blockchain record is:
- **Immutable** — no one can change it after deployment
- **Publicly verifiable** — anyone with the tx hash can look it up on Polygonscan
- **Trustless** — no need to trust the developer; the code enforces the rules
- **Timestamped** — the block timestamp is the proof of when the recording happened

---

## Smart Contract

File: `contracts/FaceVerification.sol`

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract FaceVerification {
    // Result enum: 0 = REJECTED, 1 = VERIFIED
    enum Result { REJECTED, VERIFIED }

    struct Verification {
        bytes32 subjectId;        // keccak256(name)
        string subjectName;       // human-readable name
        bytes32 imageHash;        // SHA-256 of face image
        bytes32 embeddingHash;    // SHA-256 of SFace embedding
        Result result;            // 0 or 1
        uint8 similarity;         // 0-100 (similarity * 100, rounded)
        string[] webUrls;         // discovered social media URLs
        uint64 timestamp;         // block.timestamp at recording
        bytes32 localChainHash;   // hash of the corresponding local ledger block
    }

    mapping(bytes32 => Verification) public verifications;
    bytes32[] public verificationIds;

    event VerificationRecorded(
        bytes32 indexed verificationId,
        bytes32 subjectId,
        string subjectName,
        bytes32 imageHash,
        bytes32 embeddingHash,
        Result result,
        uint8 similarity,
        uint64 timestamp,
        bytes32 localChainHash
    );

    /// @notice Record a face verification on-chain
    /// @param _subjectId keccak256 of the subject name
    /// @param _subjectName human-readable subject name
    /// @param _imageHash SHA-256 of the face image
    /// @param _embeddingHash SHA-256 of the SFace embedding
    /// @param _result 0=REJECTED, 1=VERIFIED
    /// @param _similarity similarity * 100 (0-100)
    /// @param _webUrls discovered social media URLs
    /// @param _localChainHash hash of the local ledger block for cross-reference
    function recordVerification(
        bytes32 _subjectId,
        string calldata _subjectName,
        bytes32 _imageHash,
        bytes32 _embeddingHash,
        uint8 _result,
        uint8 _similarity,
        string[] calldata _webUrls,
        bytes32 _localChainHash
    ) public {
        bytes32 verificationId = keccak256(abi.encodePacked(
            _subjectId,
            block.timestamp,
            _imageHash
        ));

        Verification storage v = verifications[verificationId];
        v.subjectId = _subjectId;
        v.subjectName = _subjectName;
        v.imageHash = _imageHash;
        v.embeddingHash = _embeddingHash;
        v.result = Result(_result);
        v.similarity = _similarity;
        v.timestamp = uint64(block.timestamp);
        v.localChainHash = _localChainHash;

        // Copy web URLs into storage array
        delete v.webUrls;
        for (uint i = 0; i < _webUrls.length; i++) {
            v.webUrls.push(_webUrls[i]);
        }

        verificationIds.push(verificationId);

        emit VerificationRecorded(
            verificationId,
            _subjectId,
            _subjectName,
            _imageHash,
            _embeddingHash,
            Result(_result),
            _similarity,
            uint64(block.timestamp),
            _localChainHash
        );
    }

    function getVerification(bytes32 _id) public view returns (Verification memory) {
        return verifications[_id];
    }

    function listVerificationIds() public view returns (bytes32[] memory) {
        return verificationIds;
    }

    function verificationCount() public view returns (uint256) {
        return verificationIds.length;
    }

    /// @notice Compute the verification ID for a given subject + image hash
    function computeVerificationId(bytes32 _subjectId, uint256 _timestamp, bytes32 _imageHash) public pure returns (bytes32) {
        return keccak256(abi.encodePacked(_subjectId, _timestamp, _imageHash));
    }
}
```

---

## Deployment Script

File: `scripts/deploy.py`

```python
#!/usr/bin/env python
"""Deploy the FaceVerification contract to Polygon Amoy testnet."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from web3 import Web3
from web3.middleware import geth_persistent_nonce_middleware
from eth_account import Account
from eth_account.signers.local_signer import LocalSigner

# ── Configuration ──────────────────────────────────────────────────────────
RPC_URL = os.environ.get('WEB3_RPC_URL', 'https://polygon-amoy.g.alchemy.com/v2/demo')
PRIVATE_KEY = os.environ.get('PRIVATE_KEY')
CONTRACT_PATH = Path(__file__).resolve().parent.parent / 'contracts' / 'FaceVerification.sol'

if not PRIVATE_KEY:
    print('ERROR: Set PRIVATE_KEY environment variable (Polygon Amoy private key).')
    print('Get testnet MATIC from: https://faucet.polygon.technology/')
    sys.exit(1)

# ── Compile contract ───────────────────────────────────────────────────────
# For simplicity, we use the Solidity compiler via solcx or a pre-compiled bytecode.
# In production, use brownie / hardhat / foundry. Here we use a minimal approach.

try:
    from solcx import compile_source, install_solc
    install_solc('0.8.20')
    compiled = compile_source(
        CONTRACT_PATH.read_text(encoding='utf-8'),
        output_values=['abi', 'bin'],
        solc_version='0.8.20',
    )
    contract_id = '<stdin>:FaceVerification'
    abi = compiled[contract_id]['abi']
    bytecode = compiled[contract_id]['bin']
except ImportError:
    print('ERROR: Install py-solc-x: pip install py-solc-x')
    print('Or use a pre-compiled bytecode in scripts/deploy.py')
    sys.exit(1)

# ── Connect to network ─────────────────────────────────────────────────────
w3 = Web3(Web3.HTTPProvider(RPC_URL))
if not w3.is_connected():
    print(f'ERROR: Cannot connect to {RPC_URL}')
    sys.exit(1)

print(f'Connected to: {w3.eth.block_number} blocks')

account = Account.from_key(PRIVATE_KEY)
signer = LocalSigner(account.key)
w3.eth.default_account = account.address

print(f'Deployer: {account.address}')
print(f'Balance: {w3.eth.get_balance(account.address) / 1e18:.4f} MATIC')

# ── Deploy ─────────────────────────────────────────────────────────────────
FaceVerification = w3.eth.contract(abi=abi, bytecode=bytecode)

construct_txn = FaceVerification.constructor().build_transaction({
    'from': account.address,
    'nonce': w3.eth.get_transaction_count(account.address),
    'gas': 3000000,
    'gasPrice': w3.eth.gas_price,
})

signed = w3.eth.account.sign_transaction(construct_txn, PRIVATE_KEY)
tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

print(f'Transaction hash: {tx_hash.hex()}')
print('Waiting for confirmation...')

tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
contract_address = tx_receipt.contractAddress

print(f'✅ Contract deployed at: {contract_address}')
print(f'🔗 Polygonscan: https://amoy.polygonscan.com/address/{contract_address}')
print()
print('Save these to your .env:')
print(f'  CONTRACT_ADDRESS={contract_address}')
print()
print('Next steps:')
print('  1. pip install web3 py-solc-x')
print('  2. Set PRIVATE_KEY and CONTRACT_ADDRESS in your environment')
print('  3. Run: python scripts/interact.py --record --subject "Test" --image-hash 0x...')
```

---

## Interaction Script

File: `scripts/interact.py`

```python
#!/usr/bin/env python
"""Record a face verification on-chain and verify it back."""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from web3 import Web3
from web3.middleware import geth_persistent_nonce_middleware
from eth_account import Account
from eth_account.signers.local_signer import LocalSigner

RPC_URL = os.environ.get('WEB3_RPC_URL', 'https://polygon-amoy.g.alchemy.com/v2/demo')
PRIVATE_KEY = os.environ.get('PRIVATE_KEY')
CONTRACT_ADDRESS = os.environ.get('CONTRACT_ADDRESS')

# Contract ABI (minimal — just the functions we need)
ABI = [
    {
        "inputs": [
            {"internalType": "bytes32", "name": "_subjectId", "type": "bytes32"},
            {"internalType": "string", "name": "_subjectName", "type": "string"},
            {"internalType": "bytes32", "name": "_imageHash", "type": "bytes32"},
            {"internalType": "bytes32", "name": "_embeddingHash", "type": "bytes32"},
            {"internalType": "uint8", "name": "_result", "type": "uint8"},
            {"internalType": "uint8", "name": "_similarity", "type": "uint8"},
            {"internalType": "string[]", "name": "_webUrls", "type": "string[]"},
            {"internalType": "bytes32", "name": "_localChainHash", "type": "bytes32"},
        ],
        "name": "recordVerification",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "bytes32", "name": "", "type": "bytes32"}],
        "name": "verifications",
        "outputs": [
            {"internalType": "bytes32", "name": "subjectId", "type": "bytes32"},
            {"internalType": "string", "name": "subjectName", "type": "string"},
            {"internalType": "bytes32", "name": "imageHash", "type": "bytes32"},
            {"internalType": "bytes32", "name": "embeddingHash", "type": "bytes32"},
            {"internalType": "uint8", "name": "result", "type": "uint8"},
            {"internalType": "uint8", "name": "similarity", "type": "uint8"},
            {"internalType": "string[]", "name": "webUrls", "type": "string[]"},
            {"internalType": "uint64", "name": "timestamp", "type": "uint64"},
            {"internalType": "bytes32", "name": "localChainHash", "type": "bytes32"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "verificationIds",
        "outputs": [{"internalType": "bytes32[]", "name": "", "type": "bytes32[]"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "verificationCount",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]


def get_contract(w3: Web3):
    return w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=ABI)


def _hash_sha256_hex(data: bytes) -> str:
    return '0x' + hashlib.sha256(data).hexdigest()


def record(
    w3: Web3,
    contract,
    subject_name: str,
    image_bytes: bytes,
    embedding: bytes,
    result: int,  # 0 or 1
    similarity: float,
    web_urls: list[str],
    local_chain_hash_hex: str,
) -> str:
    """Record a verification on-chain. Returns the transaction hash."""
    subject_id = hashlib.sha256(subject_name.encode()).digest()
    image_hash = _hash_sha256_hex(image_bytes)
    embedding_hash = _hash_sha256_hex(embedding)
    similarity_int = min(100, max(0, int(round(similarity * 100))))
    result_int = 1 if result == 'VERIFIED' or result == 1 else 0

    print(f'Subject ID: {subject_id.hex()[:32]}...')
    print(f'Image hash: {image_hash}')
    print(f'Embedding hash: {embedding_hash}')
    print(f'Result: {"VERIFIED" if result_int == 1 else "REJECTED"}')
    print(f'Similarity: {similarity} -> {similarity_int}')
    print(f'Web URLs: {len(web_urls)}')
    print(f'Local chain hash: {local_chain_hash_hex}')

    account = Account.from_key(PRIVATE_KEY)
    signer = LocalSigner(account.key)

    built = contract.functions.recordVerification(
        Web3.to_bytes(hexstr='0x' + subject_id.hex()),
        subject_name,
        Web3.to_bytes(hexstr=image_hash),
        Web3.to_bytes(hexstr=embedding_hash),
        result_int,
        similarity_int,
        web_urls,
        Web3.to_bytes(hexstr=local_chain_hash_hex),
    ).build_transaction({
        'from': account.address,
        'nonce': w3.eth.get_transaction_count(account.address),
        'gas': 500000,
        'gasPrice': w3.eth.gas_price,
    })

    signed = w3.eth.account.sign_transaction(built, PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f'\nTransaction sent: {tx_hash.hex()}')
    print(f'Polygonscan: https://amoy.polygonscan.com/tx/{tx_hash.hex()}')
    print('Waiting for confirmation...')

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    print(f'✅ Confirmed in block {receipt.blockNumber}')
    print(f'Gas used: {receipt.gasUsed}')
    print(f'Effective gas price: {receipt.effectiveGasPrice / 1e18:.4f} MATIC')
    print(f'\nTotal cost: {receipt.gasUsed * receipt.effectiveGasPrice / 1e18:.6f} MATIC')

    return tx_hash.hex()


def verify(tx_hash_hex: str, w3: Web3, contract) -> dict:
    """Look up a verification by transaction hash (approximate — uses list + search)."""
    verification_ids = contract.functions.listVerificationIds().call()
    print(f'Total verifications on-chain: {len(verification_ids)}')

    for vid in verification_ids:
        v = contract.functions.getVerification(vid).call()
        print(f'\n── Verification {vid.hex()[:32]}... ──')
        print(f'  Subject:    {v[1]}')
        print(f'  Image Hash: {v[2]}')
        print(f'  Embedding:  {v[3]}')
        print(f'  Result:     {"VERIFIED" if v[4] == 1 else "REJECTED"}')
        print(f'  Similarity: {v[5]}%')
        print(f'  Web URLs:   {len(v[6])} URLs')
        for url in v[6]:
            print(f'    - {url}')
        print(f'  Timestamp:  {v[7]} ({_nice_time(v[7])})')
        print(f'  Local hash: {v[8]}')


def _nice_time(epoch: int) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description='On-chain face verification interaction')
    sub = parser.add_subparsers(dest='command')

    rec = sub.add_parser('record', help='Record a verification on-chain')
    rec.add_argument('--subject', required=True, help='Subject name')
    rec.add_argument('--image-hash', help='Pre-computed image hash (hex, with 0x prefix)')
    rec.add_argument('--embedding-hash', help='Pre-computed embedding hash')
    rec.add_argument('--similarity', type=float, default=1.0, help='Similarity score 0-1')
    rec.add_argument('--result', choices=['VERIFIED', 'REJECTED'], default='VERIFIED')
    rec.add_argument('--web-urls', nargs='*', default=[], help='Discovered URLs')
    rec.add_argument('--local-chain-hash', required=True, help='Local ledger block hash (0x...)')

    ver = sub.add_parser('verify', help='List all on-chain verifications')
    ver.add_argument('--lookup', help='Look for a specific transaction hash')

    args = parser.parse_args()

    if not PRIVATE_KEY or not CONTRACT_ADDRESS:
        print('ERROR: Set PRIVATE_KEY and CONTRACT_ADDRESS environment variables.')
        sys.exit(1)

    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        print(f'ERROR: Cannot connect to {RPC_URL}')
        sys.exit(1)

    contract = get_contract(w3)

    if args.command == 'record':
        image_hash = args.image_hash
        embedding_hash = args.embedding_hash

        if not image_hash or not embedding_hash:
            print('ERROR: Provide --image-hash and --embedding-hash, or modify the script to compute them.')
            sys.exit(1)

        tx_hash = record(
            w3=w3,
            contract=contract,
            subject_name=args.subject,
            image_bytes=b'',
            embedding=b'',
            result=args.result,
            similarity=args.similarity,
            web_urls=args.web_urls,
            local_chain_hash_hex=args.local_chain_hash,
        )
        print(f'\n✅ Recorded! Tx hash: {tx_hash}')
        print(f'🔗 https://amoy.polygonscan.com/tx/{tx_hash}')

    elif args.command == 'verify':
        verify(None, w3, contract)


if __name__ == '__main__':
    main()
```

---

## How to Use

### 1. Install dependencies

```bash
.venv\Scripts\python.exe -m pip install web3 py-solc-x eth-account
```

### 2. Get testnet MATIC

Go to https://faucet.polygon.technology/ and get free MATIC for Polygon Amoy testnet.

### 3. Set environment variables

Create a `.env` file (never commit it):

```
WEB3_RPC_URL=https://polygon-amoy.g.alchemy.com/v2/YOUR_ALCHEMY_KEY
PRIVATE_KEY=0x...          # Polygon Amoy private key (NOT mainnet!)
CONTRACT_ADDRESS=0x...     # Set after deployment
```

### 4. Deploy the contract

```bash
python scripts/deploy.py
```

Save the contract address from the output.

### 5. Record a verification on-chain

After running the pipeline and getting web results:

```bash
python scripts/interact.py record \
  --subject "Barack Obama" \
  --image-hash 0x744dd848fbb0584229169e01... \
  --embedding-hash 0x2e25c6ff2a25... \
  --similarity 1.0 \
  --result VERIFIED \
  --web-urls \
    "https://upload.wikimedia.org/wikipedia/commons/8/8d/President_Barack_Obama.jpg" \
    "https://1000logos.net/wp-content/uploads/2017/05/Barack-Obama-US-president.jpg" \
    "https://i.imgur.com/c9d3Eb7.jpeg" \
    "https://i.pinimg.com/originals/76/46/db/7646db273116354ecf3195fe92d70105.webp" \
  --local-chain-hash 0x00009e728b9ebeeb54fd450fe264362e1bbbc9bbb1eda2dc550340848862970c
```

### 6. Verify on Polygonscan

Open the transaction link shown in the output:
`https://amoy.polygonscan.com/tx/{tx_hash}`

This shows:
- The transaction that recorded the verification
- The block number and timestamp (immutable)
- The contract interaction details
- Gas used

Anyone can verify: "Yes, this face verification was recorded on Polygon blockchain at this time."

---

## Bridge: Local Ledger ↔ Smart Contract

The local ledger and the smart contract serve different purposes:

| Local ledger (`data/ledger.json`) | Smart contract (Polygon) |
|-----------------------------------|-------------------------|
| Fast, free, local | Public, immutable, verifiable by anyone |
| Stores full block structure (nonce, prev hash, etc.) | Stores verification data (hashes, URLs, result) |
| Used for quick local validation | Used for public proof |
| Cross-referenced by `localChainHash` in contract | Cross-referenced by `localChainHash` in local block |

**Verification flow**:
1. Pick a subject
2. Look up in local ledger → get `contract_tx_hash`
3. Look up tx on Polygonscan → confirms the data was recorded publicly
4. Call `getVerification()` on contract → confirms the data matches the local record

---

## Cost

Polygon Amoy testnet: **free** (testnet MATIC from faucet).

Polygon mainnet (if you ever go live): ~100,000-300,000 gas per recordVerification call. At ~$0.01-0.05 per tx (depending on gas price), that's $0.01-$0.05 per verification — cheap enough for production.

---

## Contract Address (once deployed)

Add to README and docs once deployed:

```
Contract: 0x... (Polygon Amoy testnet)
Explorer: https://amoy.polygonscan.com/address/0x...
```

---

## Alternatives if Polygon is Too Much

If you can't deploy to a testnet before the deadline:

1. **Keep the local ledger** — it's valid per the task requirements
2. **Add a public hash anchor** — publish the Merkle root of each block as a GitHub Gist or tweet
3. **Show the local ledger validation** — the tamper demo already proves the concept

The smart contract is a "nice to have" for the shortlist round. Focus on submitting the task first.
