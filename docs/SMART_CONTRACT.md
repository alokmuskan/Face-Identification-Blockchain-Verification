# Phase 2/3 — On-chain smart contract

## Contract

File: `contracts/FaceVerificationHub.sol`

A minimal, append-only registry that binds a face-verification **record hash** to a
subject id. The key property for the shortlist: the on-chain `recordHash` is the
keccak256 of the exact JSON payload that was also written to the local ledger, so
both layers are bound to the same bytes and can be cross-validated.

### What is stored on-chain

| Field | Meaning |
|-------|---------|
| `subjectId` | normalized subject id (e.g. `barack-obama-ee8f7c`) |
| `recordHash` | keccak256 of the JSON record payload (the same bytes logged locally) |
| `similarity` | cosine similarity scaled to an integer: `round(similarity * 1e6)` |
| `result` | `"VERIFIED"` or `"REJECTED"` |
| `probeImageHash` | SHA-256 of the probe image (utf8 hex, same as local ledger) |
| `webResultCount` | number of reverse-image results found |
| `RECORD_SCHEMA` | `"v1"` — version tag for the record shape |

### Events

- `RecordCreated(...)` — emitted on every `createRecord(...)`.
- `RecordVerified(recordHash, subjectId, timestamp)` — emitted by `verifyLatest(...)`.

### Why this is tamper-evident

The local ledger stores a `contract_tx_hash` for each block that was also written to
the smart contract. The smart contract stores `recordHash`. To verify:

1. Re-compute the JSON payload bytes locally (same shape as submitted).
2. keccak256 those bytes → local `recordHash`.
3. Compare to `records[subjectId]` on-chain via `getRecord(...)`.
4. If equal, the on-chain record is bound to the exact local payload. Any later
   tampering with the local ledger would break this equality.

## Deploy to Polygon Amoy (testnet)

### Prerequisites

- MetaMask wallet with **Amoy MATIC** for gas.
- Get Amoy MATIC from the official faucet:
  - https://faucet.polygon.technology/
  - Alternative: https://www.alchemy.com/faucets/polygon-amoy (Alchemy account)

Polygon Amoy is the recommended testnet because:
- It is Polygon's current testnet (PoS).
- Public RPC `https://rpc-amoy.polygon.technology` requires no API key for basic use.
- Etherscan `https://amoy.polygonscan.com` for contract verification.

### Remix deploy (no local compiler needed)

1. Open https://remix.ethereum.org
2. In the File Explorer tab, create a new file `FaceVerificationHub.sol`.
3. Paste the contents of `contracts/FaceVerificationHub.sol` into it.
4. Open the **Solidity Compiler** tab. Set Compiler Version to `0.8.20` (or any
   `0.8.x`). Click **Compile FaceVerificationHub.sol**.
5. Open the **Deploy & Run Transactions** tab:
   - **Environment**: `Injected Provider (MetaMask)`. MetaMask will prompt; connect
     your wallet and switch to the Polygon Amoy network.
   - **Contract**: `FaceVerificationHub`.
   - Click **Deploy**.
6. MetaMask will prompt for the transaction. Confirm.
7. When the transaction is mined, Remix shows the deployed contract under
   "Deployed Contracts". Copy the contract address.

### After deploy — save these three values

These are the values you will paste into the project config so the Python pipeline
can write records to the contract.

| Config key | Value |
|------------|-------|
| `CONTRACT_ADDRESS` | the deployed contract address (0x...) |
| `CONTRACT_ABI_PATH` | `contracts/FaceVerificationHub.abi.json` (already in the repo) |
| `POLY_AMOY_RPC` | `https://rpc-amoy.polygon.technology` |
| `POLYSCAN_URL` | `https://amoy.polygonscan.com` |

Do **not** commit real private keys or real funded wallet addresses to the repo.

### Verify the contract on Amoy Etherscan (optional but impressive)

In Remix, after deploy:
1. Copy the contract address.
2. On the **Solidity Compiler** tab, check **Flatten** or copy the full source.
3. Go to https://amoy.polygonscan.com, paste the address, click **Contract** → **Verify and Publish**.
4. Choose Solidity Single file, compiler version `0.8.20`, paste the source, submit.

Verification makes the on-chain code readable on Polygonscan — good for the demo and
for the shortlist.

## Python bridge

See `tools/contract.py` and `blockchain/contract.py`.

### Requirements

Add to `requirements.txt`:
```
web3>=6.0
```

### Config (placeholders — fill after deploy)

File: `config_chain.py` (new, not committed with real values).

```python
# Dev-only config for the on-chain bridge. Fill these in after deploying
# FaceVerificationHub to Polygon Amoy. Keep real keys out of version control.

POLY_AMOY_RPC = "https://rpc-amoy.polygon.technology"
CONTRACT_ADDRESS = ""   # paste the deployed contract address here
PRIVATE_KEY = ""        # your funded wallet private key, NEVER commit this
CHAIN_ID = 80002        # Polygon Amoy testnet chain id
```

### What the bridge does

- `submit_record(...)`: builds the JSON payload, keccak256 it, calls `createRecord(...)`
  on-chain, returns the tx hash.
- `get_record_hash(subject_id)`: calls `getRecord(...)` on-chain, returns the bytes32.
- `verify_record(subject_id, expected_hash)`: calls `verifyRecord(...)` on-chain, returns bool.

### Local ledger integration

When the bridge is configured and funded, `VerificationService.identify(...)` can
optionally write the on-chain tx hash into the local block as `contract_tx_hash`, so
each local block is cross-linked to the smart contract. The `/verify` page can then
show both:
- Local chain validity (current behavior).
- On-chain record validity: "On-chain recordHash matches local payload: True/False".

## Submit-order note

1. Write + compile + deploy via Remix → get contract address.
2. Paste address + RPC into a local `config_chain.py` (not committed).
3. Run a single `identify(...)` with a funded wallet to write the first on-chain record.
4. Show: local ledger block with `contract_tx_hash`, Polygonscan tx link, and the
   on-chain `recordHash` matching the local payload.

## Live deployment

See `docs/onchain-proof.md` for the current public deployment proof:

- deployed contract address: `0x7fc71404Ce10f84B5C467AB3c9806507D422fEf4`
- subject id: `barack-obama-ee8f7c`
- latest submitted transaction hash: `0x0abb16c8429166476a85aa2606fb743404d264e98129fbf2938a6208c9ebb9ae`
- Polygon block: `46874016`
- nonce: `10`
- gas used: `54270`
- status: `SUCCESS`
- local record hash: `0x97189e2976e5009b8d221605aacb00398100d7974363eab455e6f006d970a456`
- on-chain record hash: `0x97189e2976e5009b8d221605aacb00398100d7974363eab455e6f006d970a456`
- cross-verification result: `True`
- transaction on Polygonscan:
  `https://amoy.polygonscan.com/tx/0x0abb16c8429166476a85aa2606fb743404d264e98129fbf2938a6208c9ebb9ae`
- contract on Polygonscan:
  `https://amoy.polygonscan.com/address/0x7fc71404Ce10f84B5C467AB3c9806507D422fEf4`

Keep `config_chain.py` out of version control. The proof note is safe to commit
because it contains only public on-chain information.
