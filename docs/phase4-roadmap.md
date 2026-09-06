# Phase 4 roadmap — richer local record + UI, keep the public proof intact

Phase 4 improves what the application can show and trace **around** the existing on-chain proof. It does not change the deployed contract or the canonical record hash.

## Status: implemented ✅

- [x] 4.1 Richer local record — `build_verification_record()` in the service layer
- [x] 4.2 UI improvements — cleaned `history.html` + `history_contract.html` showing probe/embedding hashes, discovered posts, block + tx linkage, Polygonscan links
- [x] 4.3 Proof packaging — `tools/export_onchain_proof.py`, `docs/onchain-proof.md`
- [x] Cross-check fix — `verify_contract()` now passes `local_block_hash` into `compute_record_hash()` so enriched records re-verify correctly
- [x] Deployment scaffolding — `Dockerfile`, `.dockerignore`, `.env.example`, `/health` endpoint, env-configurable `HOST`/`PORT`/`FLASK_DEBUG`
- [x] Tests — `tests/test_phase4.py` (record builder, bridge-off fallback, local-block-hash cross-check), `/health` route test
- [x] Pytest config — `pytest.ini` scopes collection to `tests/` so standalone `tools/test_contract_*.py` scripts are not collected

## Goal

- Make each verification event easier to read, audit, and present.
- Keep the existing `FaceVerificationHub` on Polygon Amoy as the official public proof.
- Keep the existing canonical payload and `compute_record_hash(...)` unchanged so the existing proof relationship stays valid.

## Decision already approved

- Keep contract address `0x7fc71404Ce10f84B5C467AB3c9806507D422fEf4`
- Keep `createRecord(...) / getRecord(...) / verifyRecord(...)` flow
- Keep hash-first proof model
- Keep full-precision similarity in the canonical payload
- Keep URLs/metadata off-chain
- Do not create a second contract or redeploy

## Scope

### 4.1 Richer local record

Local verification records should include, where available:

- `subject_id`
- `subject_name`
- `similarity`
- `result`
- `probe_image_hash`
- `embedding_hash`
- `web_search_results`
- `contract_tx_hash`
- `local_block_hash`
- `block_index`
- verification timestamp
- verdict/result metadata
- on-chain verification status

These fields live in the app/ledger layer. They are descriptive, not part of the canonical on-chain payload unless the roadmap explicitly changes that later.

### 4.2 UI improvements

Show the richer record clearly:

- probe image hash
- embedding hash
- discovered posts / web results
- verification details and verdict
- local block information
- Polygon transaction hash
- on-chain record hash
- Polygonscan link
- on-chain verification result

Suggested views:

- improve `/history/<subject_id>`
- improve `/api/history/<subject_id>/contract` response shape
- optional dedicated traceability/re-verification view

### 4.3 Proof packaging

Make the final proof easy to export and present without changing the blockchain layer:

- console/export CLI that prints local + on-chain + traceability fields
- proof doc that contains only public on-chain information
- clear separation between public proof artifacts and secret config

## Out of scope for this phase

- new Solidity contract
- redeploy
- change to canonical payload or record hash
- unbounded on-chain arrays
- low-precision similarity storage

## Recommended order

1. Add richer local record construction in the service layer.
2. Update the contract-history and subject-history views.
3. Add an exportable proof snippet.
4. Update docs to mention the new traceability fields.
5. Run one fresh identify with a funded bridge if available, then re-verify.
6. If no funded bridge is available, keep the existing public proof as the demo anchor and use the richer local view for the recording.

## Safety rules

- The existing submission proof is immutable for this phase.
- Any new submission must keep using the same canonical hashing path.
- Secret config must stay out of version control.
- The app must degrade gracefully when the on-chain bridge is not configured.
