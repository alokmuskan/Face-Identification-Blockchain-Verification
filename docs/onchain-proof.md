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

## Latest submitted record

- Transaction hash: `0x0abb16c8...9ebb9ae`
- Polygon block: `46874016`
- Gas used: `54270`
- Status: `SUCCESS`

## Cross-verification result

- Local record hash matches the on-chain `recordHash`
- `verifyRecord(subjectId, expectedHash)` returned `True`

That is the tamper-evidence demonstration: the local pipeline and the smart
contract are bound to the same keccak256 hash, so any later change to the local
payload would break the match.

## How to re-verify

1. Go to the deployed contract on Polygonscan:
   `https://amoy.polygonscan.com/address/0x7fc71404Ce10f84B5C467AB3c9806507D422fEf4`
2. Open the latest `RecordCreated` event or the latest transaction listed above.
3. In the app, open the same subject history and run the contract verification
   endpoint for that subject:
   `/api/history/<subject_id>/contract`

The endpoint returns:

- `local_record_hash`
- `on_chain_record_hash`
- `on_chain_match`
- `contract_tx_hash`

If `on_chain_match` is `True`, the on-chain record is bound to the exact local
payload that was submitted.

## Privacy note

This file contains only public on-chain information and public record fields.
It does **not** contain wallet private keys, signed payloads, or any biometric
image data. Private key material remains in the local, gitignored
`config_chain.py` and is supplied via environment variable only.
