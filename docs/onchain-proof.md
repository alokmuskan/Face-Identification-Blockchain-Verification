# On-chain proof — FaceVerificationHub on Polygon Amoy

This note records the live on-chain verification trail for the deployed
`FaceVerificationHub` contract. It is intentionally nonsecret: it contains only
public on-chain data and the public-facing record parameters used in the demo.

## Deployment

- Contract: `FaceVerificationHub`
- Network: Polygon Amoy testnet
- Contract address: `0x7fc71404Ce10f84B5C467AB3c9806507D422fEf4`
- ABI: `contracts/FaceVerificationHub.abi.json`
- Source: `contracts/FaceVerificationHub.sol`

## What gets written on-chain

Each time the pipeline identifies a matched face, the backend builds a canonical
JSON payload and writes its keccak256 hash to the smart contract.

Stored fields:

- `subjectId`
- `recordHash` — keccak256 of the canonical JSON payload
- `similarity` — stored as `round(similarity * 1_000_000)`
- `result` — `VERIFIED` or `REJECTED`
- `probeImageHash` — SHA-256 of the probe image
- `webResultCount` — number of reverse-image search results found
- `localBlockHash` — bytes32 local ledger block hash attached to the on-chain record so each on-chain record can be traced back to the local block that carried the matching `contract_tx_hash` (Phase 3 traceability field)

## Latest submitted record

- Transaction hash: `0x0abb16c8429166476a85aa2606fb743404d264e98129fbf2938a6208c9ebb9ae`
- Subject ID: `barack-obama-ee8f7c`
- Polygon block: `46874016`
- Nonce: `10`
- Gas used: `54270`
- Status: `SUCCESS`
- Similarity: `0.9999`
- Web results: `10`

## Cross-verification result

- Local record hash: `0x97189e2976e5009b8d221605aacb00398100d7974363eab455e6f006d970a456`
- On-chain record hash: `0x97189e2976e5009b8d221605aacb00398100d7974363eab455e6f006d970a456`
- Local and on-chain hashes match exactly.
- `verifyRecord(subjectId, expectedHash)` returned `True`.

That is the tamper-evidence demonstration: the local pipeline and the smart
contract are bound to the same keccak256 hash, so any later change to the local
payload would break the match.

## Public verification links

- Contract address: `0x7fc71404Ce10f84B5C467AB3c9806507D422fEf4`
- Transaction on Polygonscan:
  `https://amoy.polygonscan.com/tx/0x0abb16c8429166476a85aa2606fb743404d264e98129fbf2938a6208c9ebb9ae`
- Contract on Polygonscan:
  `https://amoy.polygonscan.com/address/0x7fc71404Ce10f84B5C467AB3c9806507D422fEf4`

PolygonScan's transaction view exposes the transaction hash, status, block,
from/to, and transaction details, so the transaction link above is the primary
public evidence link.

## Traceability

The deployed contract now supports an optional traceability field,
`localBlockHash`, on records submitted with the enriched pipeline. When present,
it lets the app show exactly which local ledger block the on-chain record points
back to.

The existing published submission for `barack-obama-ee8f7c` was created before 
this field was added, so its `localBlockHash` is the zero bytes32. Its public 
proof values above are unchanged. New enriched submissions will attach a real 
`localBlockHash`, and the app will then show the full local <-> on-chain 
traceability linkage.

## How to prove it again

This is the exact reproducibility path for reviewers and for the submission form.

### Option 1: from the app

1. Start the app:
   `.venv\Scripts\python.exe app.py`
2. Open the subject history:
   `http://127.0.0.1:5000/history/barack-obama-ee8f7c`
3. Query the on-chain cross-check:
   `http://127.0.0.1:5000/api/history/barack-obama-ee8f7c/contract`

Expected response shape:

- `ok`: `true`
- `local_record_hash`: `0x97189e2976e5009b8d221605aacb00398100d7974363eab455e6f006d970a456`
- `on_chain_record_hash`: `0x97189e2976e5009b8d221605aacb00398100d7974363eab455e6f006d970a456`
- `on_chain_match`: `true`
- `contract_tx_hash`: `0x0abb16c8429166476a85aa2606fb743404d264e98129fbf2938a6208c9ebb9ae`.

If the app is no longer running with the same configured bridge, the endpoint may
return a bridge-not-configured message. In that case, use Option 2 below.

### Option 2: from Polygonscan

1. Open the transaction link above.
2. Confirm:
   - status is successful
   - block number is `46874016`
   - the transaction interacts with contract `0x7fc71404Ce10f84B5C467AB3c9806507D422fEf4`
3. Open the contract address on Polygonscan.
4. In the contract UI, locate the stored record for subject `barack-obama-ee8f7c`.
5. Confirm the stored `recordHash` equals
   `0x97189e2976e5009b8d221605aacb00398100d7974363eab455e6f006d970a456`.

### Option 3: re-run the bridge CLI

From the project root, with `config_chain.py` configured and web3 installed:

```bash
.venv\Scripts\python.exe tools\contract.py verify \
  --subject-id barack-obama-ee8f7c
```

This should report the same on-chain `recordHash` and the same cross-check
result.

### Option 4: print the full Phase 3 proof from the CLI

For a recording or submission review, you can print the full local + on-chain + 
traceability proof in one place:

```bash
.venv\Scripts\python.exe tools\export_onchain_proof.py \
  --subject-id barack-obama-ee8f7c
```

This prints the local record hash, the on-chain record hash, the on-chain 
cross-check, the local block index and local block hash, the on-chain local block 
hash, whether the local block hash matches on-chain, the contract tx hash, and the 
Polygonscan links when they are available.

### What proves the tamper-evidence claim

The claim is proved when all of these are consistent:

- the local record hash computed from the canonical JSON payload,
- the on-chain `recordHash` stored by the contract,
- the transaction that wrote it on Polygon Amoy,
- and the value returned by `verifyRecord(...)`.

If any party alters the local payload after submission, the recomputed local
record hash will no longer match the on-chain record hash.

## Privacy note

This file contains only public on-chain information and public record fields.
It does **not** contain wallet private keys, signed payloads, or any biometric
image data. Private key material remains in the local, gitignored
`config_chain.py` and is supplied via environment variable only.
