# Face Identification & Blockchain Verification

A pipeline that takes a face scan as input, identifies matching content on the
web/social media, and then verifies that discovered data using a blockchain —
end to end.

Pipeline shape:

```
Face scan input → Web/social media search (find matching post)
→ Blockchain upload/verification of the discovered data
```

---

## Table of contents

- [What the project does](#what-the-project-does)
- [Task origin and submission requirements](#task-origin-and-submission-requirements)
- [Architecture](#architecture)
- [Workflow](#workflow)
- [Pipeline diagram](#pipeline-diagram)
- [Dual blockchain model](#dual-blockchain-model)
- [Local ledger](#local-ledger)
- [On-chain smart contract](#on-chain-smart-contract)
- [Canonical record hash](#canonical-record-hash)
- [Current live deployment](#current-live-deployment)
- [How to prove it again](#how-to-prove-it-again)
- [Project structure](#project-structure)
- [How to run](#how-to-run)
- [Web UI](#web-ui)
- [JSON API](#json-api)
- [Reverse image search details](#reverse-image-search-details)
- [Configuration](#configuration)
- [Tests](#tests)
- [Tamper demo](#tamper-demo)
- [Known limitations](#known-limitations)
- [Security and privacy](#security-and-privacy)
- [Recording and submission](#recording-and-submission)
- [Roadmap](#roadmap)

---

Submission requirements
● GitHub repo link
● A screen recording of the working project (no live working link required)
● Submission form link : https://forms.gle/oZbQGuwiNeHVcHWo8  (No resubmissions will be allowed — submit only when your build is final.)

## What the project does

This project takes **one face image** and runs it end to end:

1. **Face detection & encoding** — YuNet finds the largest face, SFace produces a
   128-d embedding.
2. **Face identification** — the embedding is matched against enrolled subjects
   using cosine similarity; a `VERIFIED` / `REJECTED` verdict is recorded.
3. **Web / social media search** — when a match is found, the probe image is
   uploaded to a headless Yandex Images reverse-image search over a
   Selenium-driven Chrome browser. Matching URLs (social media posts, image hosts,
   blogs) are extracted and classified by page type.
4. **Blockchain verification** — the face verification result **and the web search
   results** are mined as a transaction into a SHA-256 hash-chained, proof-of-work
   local ledger. The chain is re-validated on demand: any tampered transaction
   breaks the hash chain.
5. **On-chain record** — the same canonical verification payload is also written
   to a live smart contract on Polygon Amoy, so the local ledger and the public
   chain can be cross-verified.
6. **Demo script** — `tools/demo_pipeline.py` drives the whole pipeline from the
   command line and prints a readable transcript suitable for screen recording.

---

## Task origin and submission requirements

This repo was built for the **HH Goa 2026 Shortlisting Task 3**:
Face Identification & Blockchain Verification.

Technical requirements from the task:

1. **Face identification** — detect and encode a face from an input image.
2. **Social media / web search** — use the face to search the web and find at
   least one real, matching social media post. This must be a genuine search step,
   not a hardcoded result.
3. **Blockchain verification** — once a matching post is found, upload the post or
   a hash/fingerprint of it to a blockchain to create a verifiable, tamper-evident
   record. Any blockchain may be used, as long as you can demonstrate
   re-verifying the data against the on-chain record.
4. **No website required** — focus on the pipeline itself.
5. **GitHub repo required** — full source code in a GitHub repo, with a README
   covering what the project does, how to run it, which blockchain you used, and
   any known limitations.

Submission requirements:

- GitHub repo link
- A screen recording of the working project (no live working link required)
- Submission form link:
  https://forms.gle/oZbQGuwiNeHVcHWo8
- No resubmissions are allowed — submit only when the build is final.

Screen recording:

- Record your screen showing the pipeline working end to end:
  face scan → social post found → blockchain upload/verification.
- No editing or production needed — a plain screen recording is enough.
- Upload it anywhere (YouTube unlisted, Google Drive, Loom, etc.) and share a
  working link.

Timeline:

- Task launch: August 31, 2026
- Deadline: Sept 7, 2026, 11:59 PM

---

## Architecture

The system has three logical layers:

1. **Face layer**
   - Input: raw image bytes from upload or camera capture.
   - Detection: YuNet face detector.
   - Recognition: SFace face recognizer.
   - Output: 128-d embedding.

2. **Identity + search layer**
   - Matching: cosine similarity against enrolled subjects.
   - Web search: reverse image search via Yandex Images when there is a match.
   - Classification: each result is labeled as `social_media`, `image_host`,
     `blog`, or `web`.

3. **Verification layer**
   - Local blockchain: a SHA-256 hash-chained, proof-of-work ledger in
     `data/ledger.json`.
   - On-chain bridge: optional integration with `FaceVerificationHub` on Polygon
     Amoy.
   - Verification endpoints: local chain integrity and on-chain cross-check.

Key design choices:

- The local ledger is the demo backbone. It shows tamper evidence through hash
  chaining and proof of work.
- The on-chain bridge is optional. When configured, the same canonical payload
  that is written locally is also hashed with Keccak-256 and submitted to the
  smart contract.
- The web search is never allowed to block the pipeline. If the browser cannot
  start or no results are returned, the pipeline still records the attempt on-chain.

---

## Workflow

### Step 1 — Accept the face scan

The app accepts:

- a multipart file upload, or
- a base64 data URL captured from the browser camera canvas

The image is validated and size-limited before any processing.

### Step 2 — Detect and encode the face

- The image is decoded with OpenCV.
- YuNet detects faces and selects the largest one.
- SFace produces a 128-d embedding for that face.

If no face is detected, the request is rejected with a clear error.

### Step 3 — Identify the subject

The embedding is matched against enrolled subjects using cosine similarity.

- If the best similarity is above the threshold, the result is `VERIFIED` and the
  matched subject is identified.
- Otherwise, the result is `REJECTED`.

### Step 4 — Run the web / social media search

When there is a match:

- the probe image is uploaded to Yandex Images through a headless Chrome browser
- matching result cards are extracted
- each result is classified by page type

If there is no match, or if the search fails, the pipeline still proceeds.

### Step 5 — Record the result locally

The face verification result, probe image hash, similarity, and any discovered web
results are written as a transaction into the local hash-chained ledger.

### Step 6 — Optionally record the result on-chain

When the on-chain bridge is configured and the result is a match, the same
canonical payload is:

- hashed with Keccak-256
- submitted to `FaceVerificationHub` on Polygon Amoy
- cross-linked back to the local block via `contract_tx_hash`

### Step 7 — Verify

Two independent verification paths are available:

- **Local integrity**: re-hash every block and check links and proof of work.
- **On-chain cross-check**: recompute the canonical payload hash locally and
  compare it to the on-chain `recordHash`.

---

## Pipeline diagram

```
Face scan (image bytes)
      │
      ▼
[ Image validation ]
      │
      ▼
[ YuNet  ] → detect largest face
      │
      ▼
[ SFace  ] → 128-d embedding
      │
      ▼
[ FaceStore ] → cosine-similarity match vs enrolled subjects
      │
      ├─ NOT matched → REJECTED, recorded locally (no web search)
      │
      ▼ MATCHED
[ WebSearchEngine (Selenium + Chrome headless) ]
      │   upload probe image to Yandex Images
      │   extract matching URLs
      │   classify social_media / image_host / blog / web
      ▼
[ Local blockchain ] → FACE_VERIFICATION tx + web_search_results[]
                         mined into SHA-256 hash chain
      │
      ▼
[ On-chain bridge ] → Keccak-256 payload hash submitted to
                        FaceVerificationHub on Polygon Amoy
      │
      ▼
[ Verification ]
   ├── local: validate_chain()
   └── on-chain: local_record_hash == on-chain recordHash
```

---

## Dual blockchain model

This project uses two complementary verification layers:

1. **Local ledger**
   - A SHA-256 hash-chained, proof-of-work ledger persisted as JSON.
   - Demonstrates tamper evidence locally.
   - Fast, offline, and fully under the control of the demo.

2. **On-chain smart contract**
   - A live, public, append-only registry on Polygon Amoy.
   - Stores one Keccak-256 record hash per subject.
   - Provides public proof that a specific local payload was submitted.

These two layers are intentionally bound together. The important property is:

- the same canonical record payload is used for both
- the local payload hash is Keccak-256
- the on-chain `recordHash` is Keccak-256 of the same canonical JSON bytes
- the app re-verifies the local payload against the on-chain record

---

## Local ledger

The local ledger is a hash-chained, proof-of-work blockchain persisted as
`data/ledger.json`.

Each block contains:

- index
- timestamp
- transactions
- previous hash
- nonce
- block hash

The block hash covers every field, including transactions, previous hash, and
nonce.

Proof of work:

- each block hash must start with `DIFFICULTY` leading hex zeros
- default difficulty is `4`
- the nonce is incremented until the condition is satisfied

Tamper evidence:

- `validate_chain()` recomputes every block hash
- it checks the proof-of-work requirement
- it verifies that every block links to its predecessor
- any altered transaction changes the block hash and breaks the chain

This is a demo ledger. It demonstrates tamper evidence, not distributed consensus.

---

## On-chain smart contract

Contract: `FaceVerificationHub`

File: `contracts/FaceVerificationHub.sol`

A minimal, append-only registry that binds a face-verification **record hash** to a
subject id.

Stored fields:

- `subjectId`
- `recordHash` — Keccak-256 of the canonical JSON record payload
- `similarity` — stored as `round(similarity * 1_000_000)`
- `result` — `VERIFIED` or `REJECTED`
- `probeImageHash` — SHA-256 of the probe image
- `webResultCount` — number of reverse-image results found
- `localBlockHash` — optional bytes32 local ledger block hash attached to the on-chain record so each on-chain record can be traced back to the local block that carried the matching `contract_tx_hash` (Phase 3 traceability field)

Solidity events:

- `RecordCreated(...)` — emitted on every `createRecord(...)`
- `RecordVerified(...)` — emitted by `verifyLatest(...)`

Key functions:

- `createRecord(...)` — create or overwrite the on-chain record for a subject
- `getRecord(...)` — read the on-chain record hash for a subject, with an optional two-field variant that also returns the attached local block hash
- `verifyRecord(...)` — verify a subject's record against an expected hash

This contract is deliberately small and focused. It is enough to demonstrate that a
specific local payload was submitted and can be re-verified on-chain. The optional
`localBlockHash` field adds traceability without changing the hash-first
verification model.

---

## Canonical record hash

The tamper-evidence proof depends on using the same canonical payload everywhere.

The canonical payload is built in one place:
`blockchain/_keccak.py`.

It includes:

- `subject_id`
- `similarity`
- `result`
- `probe_image_hash`
- `web_result_count`
- `record_schema`
- `chain`

The payload is serialized with:

- `sort_keys=True`
- compact `separators`
- `ensure_ascii=False`
- UTF-8 encoding

That makes the serialized bytes deterministic.

The on-chain `recordHash` is:

- `keccak256(canonical_payload_json_bytes(...))`

Python uses the same Keccak-256 backend that Solidity uses for `keccak256()`:

- preferred backend: `eth_hash`
- fallback backend: `web3`

This keeps the on-chain record hash computable even when `web3` is not installed.

---

## Current live deployment

The smart contract is deployed on **Polygon Amoy testnet**.

Contract:

- `FaceVerificationHub`
- Address: `0x7fc71404Ce10f84B5C467AB3c9806507D422fEf4`
- Source: `contracts/FaceVerificationHub.sol`
- ABI: `contracts/FaceVerificationHub.abi.json`

Latest verified submission:

- Subject ID: `barack-obama-ee8f7c`
- Transaction hash: `0x0abb16c8429166476a85aa2606fb743404d264e98129fbf2938a6208c9ebb9ae`
- Polygon block: `46874016`
- Nonce: `10`
- Gas used: `54270`
- Status: `SUCCESS`
- Similarity: `0.9999`
- Web results: `10`
- Local record hash:
  `0x97189e2976e5009b8d221605aacb00398100d7974363eab455e6f006d970a456`
- On-chain record hash:
  `0x97189e2976e5009b8d221605aacb00398100d7974363eab455e6f006d970a456`
- Local and on-chain hashes match exactly.
- `verifyRecord(...)` returned `True`.

Public links:

- Transaction on Polygonscan:
  https://amoy.polygonscan.com/tx/0x0abb16c8429166476a85aa2606fb743404d264e98129fbf2938a6208c9ebb9ae
- Contract on Polygonscan:
  https://amoy.polygonscan.com/address/0x7fc71404Ce10f84B5C467AB3c9806507D422fEf4

Phase 3 traceability:

The deployed contract now also supports an optional `localBlockHash` field. When a
new record is submitted with the enriched pipeline, the app can show exactly which
local ledger block the on-chain record points back to. The existing submission
proof above stays unchanged because it was created before this field was added, so 
its `localBlockHash` is currently the zero bytes32. New enriched submissions will 
expose the full local <-> on-chain traceability linkage on public chains and in the 
app's on-chain verification page.

Detailed proof and reproducibility notes:

- `docs/onchain-proof.md`
- `docs/recording-guide.md`
- `docs/recording-plan.md`
- `docs/phase3-roadmap.md`

Never commit wallet private keys. The on-chain config lives in a local, gitignored
`config_chain.py` and is supplied via environment variable.

---

## How to prove it again

If a reviewer or the submission form asks how to verify the on-chain claim, use one
of these paths.

### Option 1 — from the app

1. Start the app:
   `.venv/Scripts/python.exe app.py`
2. Open the subject history:
   `http://127.0.0.1:5000/history/barack-obama-ee8f7c`
3. Query the on-chain cross-check:
   `http://127.0.0.1:5000/api/history/barack-obama-ee8f7c/contract`

Expected response shape:

- `ok`
- `local_record_hash`
- `on_chain_record_hash`
- `on_chain_match`
- `contract_tx_hash`

If the app is not running with the same configured bridge, the endpoint may return a
bridge-not-configured message. In that case, use Option 2.

### Option 2 — from Polygonscan

1. Open the transaction link above.
2. Confirm:
   - status is successful
   - block number is `46874016`
   - the transaction interacts with contract `0x7fc71404Ce10f84B5C467AB3c9806507D422fEf4`
3. Open the contract address on Polygonscan.
4. Locate the stored record for subject `barack-obama-ee8f7c`.
5. Confirm the stored `recordHash` equals
   `0x97189e2976e5009b8d221605aacb00398100d7974363eab455e6f006d970a456`.

### Option 3 — from the CLI bridge

From the project root, with `config_chain.py` configured and `web3` installed:

```bash
.venv/Scripts/python.exe tools/contract.py verify \
  --subject-id barack-obama-ee8f7c
```

This should report the same on-chain `recordHash` and the same cross-check result.

---

## Project structure

```
app.py                          Flask web UI
config.py                       Shared configuration
requirements.txt                Python dependencies
.services/
  verification_service.py       Workflow layer: register / identify / history
.blockchain/
  __init__.py
  block.py                      Block model and hashing
  ledger.py                     Hash-chained PoW ledger
  contract.py                   Optional on-chain bridge
  _keccak.py                    Keccak-256 compatibility layer
.faceid/
  __init__.py
  engine.py                     YuNet detection + SFace embedding
  similarity.py                 Cosine similarity helper
  store.py                      Subject registry
.websearch/
  __init__.py
  search.py                     Headless reverse image search
.contracts/
  FaceVerificationHub.sol       Smart contract source
  FaceVerificationHub.abi.json  ABI for Python bridge
.tools/
  fetch_models.py               Downloads YuNet + SFace ONNX models
  demo_pipeline.py              End-to-end CLI demo / recording script
  tamper_demo.py                Tamper-evidence demonstration
  contract.py                   CLI for on-chain submit/verify
  export_onchain_proof.py       Prints the full Phase 3 proof fields for a subject
  config_chain.example.py       Template for local on-chain config
.tests/
  test_app.py
  test_faceid.py
  test_blockchain.py
  conftest.py
.data/                          Runtime data (git-ignored)
  ledger.json
  face_store.json
  faces/
  probes/
.models/                        Downloaded ONNX models (git-ignored)
.templates/                     Flask HTML templates
.static/                        CSS + JS
.docs/
  SMART_CONTRACT.md
  onchain-proof.md
  recording-plan.md
  recording-guide.md
  phase2-checklist.md
```

---

## How to run

## Dual blockchain model

This project uses two complementary verification layers:

1. **Local ledger**
   - A SHA-256 hash-chained, proof-of-work ledger persisted as JSON.
   - Demonstrates tamper evidence locally.
   - Fast, offline, and fully under the control of the demo.

2. **On-chain smart contract**
   - A live, public, append-only registry on Polygon Amoy.
- Flask
- OpenCV contrib (YuNet + SFace)
- NumPy
- Pillow
- Playwright and Selenium for the web search
- the optional on-chain bridge dependencies

The model fetcher downloads **YuNet** and **SFace** ONNX files into `models/`.

### 2. Install Chrome or Chromium

The web search module drives a headless Chrome via Selenium.

- If Chrome is already installed, Selenium's driver manager usually picks it up.
- Otherwise, install the matching Chromium/ChromeDriver, or configure the browser
  path if needed.

### 3. Run the pipeline demo

```bash
.venv/Scripts/python.exe tools/demo_pipeline.py
```
=======
2. **On-chain smart contract**
   - A live, public, append-only registry on Polygon Amoy.
   - Stores one Keccak-256 record hash per subject.
   - Provides public proof that a specific local payload was submitted.

These two layers are intentionally bound together. The important property is:

- the same canonical record payload is used for both
- the local payload hash is Keccak-256
- the on-chain `recordHash` is Keccak-256 of the same canonical JSON bytes
- the app re-verifies the local payload against the on-chain record

---

## Local ledger

The local ledger is a hash-chained, proof-of-work blockchain persisted as
`data/ledger.json`.

Each block contains:

- index
- timestamp
- transactions
- previous hash
- nonce
- block hash

The block hash covers every field, including transactions, previous hash, and
nonce.

Proof of work:

- each block hash must start with `DIFFICULTY` leading hex zeros
- default difficulty is `4`
- the nonce is incremented until the condition is satisfied

Tamper evidence:

- `validate_chain()` recomputes every block hash
- it checks the proof-of-work requirement
- it verifies that every block links to its predecessor
- any altered transaction changes the block hash and breaks the chain

This is a demo ledger. It demonstrates tamper evidence, not distributed consensus.

---

## On-chain smart contract


## On-chain smart contract

Contract: `FaceVerificationHub`

File: `contracts/FaceVerificationHub.sol`

A minimal, append-only registry that binds a face-verification **record hash** to a
subject id.

Stored fields:

- `subjectId`
- `recordHash` — Keccak-256 of the canonical JSON record payload
- `similarity` — stored as `round(similarity * 1_000_000)`
- `result` — `VERIFIED` or `REJECTED`
- `probeImageHash` — SHA-256 of the probe image
- `webResultCount` — number of reverse-image results found
- `localBlockHash` — optional bytes32 local ledger block hash attached to the on-chain record so each on-chain record can be traced back to the local block that carried the matching `contract_tx_hash` (Phase 3 traceability field)

Solidity events:

- `RecordCreated(...)` — emitted on every `createRecord(...)`
- `RecordVerified(...)` — emitted by `verifyLatest(...)`

Key functions:

- `createRecord(...)` — create or overwrite the on-chain record for a subject
- `getRecord(...)` — read the on-chain record hash for a subject, with an optional two-field variant that also returns the attached local block hash
- `verifyRecord(...)` — verify a subject's record against an expected hash

This contract is deliberately small and focused. It is enough to demonstrate that a
specific local payload was submitted and can be re-verified on-chain. The optional
`localBlockHash` field adds traceability without changing the hash-first
verification model.

---

## Canonical record hash

The tamper-evidence proof depends on using the same canonical payload everywhere.

The canonical payload is built in one place:
`blockchain/_keccak.py`.

It includes:

- `subject_id`
- `similarity`
- `result`
- `probe_image_hash`
- `web_result_count`
- `record_schema`
- `chain`

The payload is serialized with:

- `sort_keys=True`
- compact `separators`
- `ensure_ascii=False`
- UTF-8 encoding

That makes the serialized bytes deterministic.

The on-chain `recordHash` is:

- `keccak256(canonical_payload_json_bytes(...))`

Python uses the same Keccak-256 backend that Solidity uses for `keccak256()`:

- preferred backend: `eth_hash`
- fallback backend: `web3`

This keeps the on-chain record hash computable even when `web3` is not installed.

---

## Current live deployment

The smart contract is deployed on **Polygon Amoy testnet**.

Contract:

- `FaceVerificationHub`
- Address: `0x7fc71404Ce10f84B5C467AB3c9806507D422fEf4`
- Source: `contracts/FaceVerificationHub.sol`
- ABI: `contracts/FaceVerificationHub.abi.json`

Latest verified submission:

- Subject ID: `barack-obama-ee8f7c`
- Transaction hash: `0x0abb16c8429166476a85aa2606fb743404d264e98129fbf2938a6208c9ebb9ae`
- Polygon block: `46874016`
- Nonce: `10`
- Gas used: `54270`
- Status: `SUCCESS`
- Similarity: `0.9999`
- Web results: `10`
- Local record hash:
  `0x97189e2976e5009b8d221605aacb00398100d7974363eab455e6f006d970a456`
- On-chain record hash:
  `0x97189e2976e5009b8d221605aacb00398100d7974363eab455e6f006d970a456`
- Local and on-chain hashes match exactly.
- `verifyRecord(...)` returned `True`.

Public links:

- Transaction on Polygonscan:
  https://amoy.polygonscan.com/tx/0x0abb16c8429166476a85aa2606fb743404d264e98129fbf2938a6208c9ebb9ae
- Contract on Polygonscan:
  https://amoy.polygonscan.com/address/0x7fc71404Ce10f84B5C467AB3c9806507D422fEf4

Phase 3 traceability:

The deployed contract now also supports an optional `localBlockHash` field. When a
new record is submitted with the enriched pipeline, the app can show exactly which
local ledger block the on-chain record points back to. The existing submission
proof above stays unchanged because it was created before this field was added, so 
its `localBlockHash` is currently the zero bytes32. New enriched submissions will 
expose the full local <-> on-chain traceability linkage on public chains and in the 
app's on-chain verification page.

Detailed proof and reproducibility notes:

- `docs/onchain-proof.md`
- `docs/recording-guide.md`
- `docs/recording-plan.md`
- `docs/phase3-roadmap.md`

Never commit wallet private keys. The on-chain config lives in a local, gitignored
`config_chain.py` and is supplied via environment variable.

---

## How to prove it again

If a reviewer or the submission form asks how to verify the on-chain claim, use one
of these paths.

### Option 1 — from the app

1. Start the app:
   `.venv/Scripts/python.exe app.py`
2. Open the subject history:
   `http://127.0.0.1:5000/history/barack-obama-ee8f7c`
3. Query the on-chain cross-check:
   `http://127.0.0.1:5000/api/history/barack-obama-ee8f7c/contract`

Expected response shape:

- `ok`
- `local_record_hash`
- `on_chain_record_hash`
- `on_chain_match`
- `contract_tx_hash`

If the app is not running with the same configured bridge, the endpoint may return a
bridge-not-configured message. In that case, use Option 2.

### Option 2 — from Polygonscan

1. Open the transaction link above.
2. Confirm:
   - status is successful
   - block number is `46874016`
   - the transaction interacts with contract `0x7fc71404Ce10f84B5C467AB3c9806507D422fEf4`
3. Open the contract address on Polygonscan.
4. Locate the stored record for subject `barack-obama-ee8f7c`.
5. Confirm the stored `recordHash` equals
   `0x97189e2976e5009b8d221605aacb00398100d7974363eab455e6f006d970a456`.

### Option 3 — from the CLI bridge

From the project root, with `config_chain.py` configured and `web3` installed:

```bash
.venv/Scripts/python.exe tools/contract.py verify \
  --subject-id barack-obama-ee8f7c
```

This should report the same on-chain `recordHash` and the same cross-check result.

---

## Project structure

```
app.py                          Flask web UI
config.py                       Shared configuration
requirements.txt                Python dependencies
.services/
  verification_service.py       Workflow layer: register / identify / history
.blockchain/
  __init__.py
  block.py                      Block model and hashing
  ledger.py                     Hash-chained PoW ledger
  contract.py                   Optional on-chain bridge
  _keccak.py                    Keccak-256 compatibility layer
.faceid/
  __init__.py
  engine.py                     YuNet detection + SFace embedding
  similarity.py                 Cosine similarity helper
  store.py                      Subject registry
.websearch/
  __init__.py
  search.py                     Headless reverse image search
.contracts/
  FaceVerificationHub.sol       Smart contract source
  FaceVerificationHub.abi.json  ABI for Python bridge
.tools/
  fetch_models.py               Downloads YuNet + SFace ONNX models
  demo_pipeline.py              End-to-end CLI demo / recording script
  tamper_demo.py                Tamper-evidence demonstration
  contract.py                   CLI for on-chain submit/verify
  export_onchain_proof.py       Prints the full Phase 3 proof fields for a subject
  config_chain.example.py       Template for local on-chain config
.tests/
  test_app.py
  test_faceid.py
  test_blockchain.py
  conftest.py
.data/                          Runtime data (git-ignored)
  ledger.json
  face_store.json
  faces/
  probes/
.models/                        Downloaded ONNX models (git-ignored)
.templates/                     Flask HTML templates
.static/                        CSS + JS
.docs/
  SMART_CONTRACT.md
  onchain-proof.md
  recording-plan.md
  recording-guide.md
  phase2-checklist.md
```

---

## How to run

### 1. Set up the environment

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe tools/fetch_models.py
```

`requirements.txt` includes the dependencies for:

- Flask
- OpenCV contrib (YuNet + SFace)
- NumPy
- Pillow
- Playwright and Selenium for the web search
- the optional on-chain bridge dependencies

The model fetcher downloads **YuNet** and **SFace** ONNX files into `models/`.

### 2. Install Chrome or Chromium

The web search module drives a headless Chrome via Selenium.

- If Chrome is already installed, Selenium's driver manager usually picks it up.
- Otherwise, install the matching Chromium/ChromeDriver, or configure the browser
  path if needed.

### 3. Run the pipeline demo

```bash
.venv/Scripts/python.exe tools/demo_pipeline.py
```

This will:

- load or generate a probe image
- run detection + embedding
- identify or register a subject
- run the reverse image search through Yandex
- mine the result into the blockchain
- validate the chain
- print a step-by-step transcript

You can also point it at your own photo:

```bash
.venv/Scripts/python.exe tools/demo_pipeline.py --probe mypic.jpg
```

### 4. Run the web UI

```bash
.venv/Scripts/python.exe app.py
```

Then open `http://127.0.0.1:5000`.

---

## Web UI

The app exposes these pages:

- **Dashboard** — subject count, block count, chain status, recent events, and the
  pipeline diagram.
- **Register** — type a name, upload a photo, or capture a camera frame.
- **Identify** — submit a probe photo; the verdict, web-search hit list, and the
  resulting block are shown.
- **Ledger** — every block with its transactions, hashes, nonce, and embedded
  web-search results.
- **Verify** — one-click integrity check of the whole chain.
- **History** — on-chain events for a subject.
- **Web results** — a dedicated view for the reverse-image search results attached
  to a block.

---

## JSON API

```
GET  /api/status                                  models available, subject count, chain stats
POST /api/register                                multipart form: name, image -> 201
POST /api/identify                                multipart form: image -> verdict + block + web_results[]
GET  /api/chain                                   full chain with all blocks
GET  /api/chain/validate                          integrity report: valid, blocks_checked, errors
GET  /api/history/<subject_id>                    subject record plus on-chain events
GET  /api/history/<subject_id>/contract           on-chain cross-check: local_record_hash, on_chain_record_hash, on_chain_match, contract_tx_hash
```

Example:

```bash
curl -F name=Alice -F image=@alice.jpg http://127.0.0.1:5000/api/register
curl -F image=@probe.jpg http://127.0.0.1:5000/api/identify
curl http://127.0.0.1:5000/api/chain/validate
```

The `/api/identify` response includes `web_results[]`, each with `url`, `title`,
`description`, `image_url`, and `page_type`.

The `/api/history/<subject_id>/contract` response includes:

- `local_record_hash`
- `on_chain_record_hash`
- `on_chain_match`
- `contract_tx_hash`
- `local_block_hash`
- `on_chain_local_block_hash`
- `local_block_index`
- `local_block_hash_matches_on_chain`

When the on-chain bridge is configured and the record was submitted with the
Phase 3 traceability field, the response also shows exactly which local block the
on-chain record points back to.

---

## Reverse image search details

Engine: **Yandex Images** (`yandex.com/images`) via a headless Chrome driven by
Selenium.

The flow in headless mode:

1. navigate to Yandex Images
2. click the “Search by image” control
3. upload the probe image through the file input
4. wait for result cards
5. extract the top 10 result URLs and classify each as `social_media`, `image_host`,
   `blog`, or `web`

No API key is required.

If the browser cannot start or no results are returned, the pipeline still records an
**empty web-search result** on-chain. The face verification step is never blocked by
a search failure.

Known limitation: headless Chrome on some environments may need an explicit browser
path or a manual ChromeDriver install. Web UI layouts also change, so selectors may
need updating.

---

## Configuration

Key settings from `config.py`:

```
DIFFICULTY = 4                      leading hex zeros required per block
MATCH_THRESHOLD = 0.363             SFace cosine threshold recommended by OpenCV
MAX_EMBEDDINGS_PER_SUBJECT = 3
MAX_IMAGES_PER_SUBJECT = 3
WEB_SEARCH_TIMEOUT = 45             seconds given to the reverse-image search
MAX_DETECT_SIDE = 640               probes are downscaled before detection
MAX_IMAGE_BYTES = 10 MB
HOST = 127.0.0.1
PORT = 5000
```

Data layout:

```
data/
  ledger.json
  face_store.json
  faces/
  probes/
models/
  face_detection_yunet_2023mar.onnx
  face_recognition_sface_2021dec.onnx
```

---

## Tests

```bash
.venv/Scripts/python.exe -m pytest -q
```

The test suite covers:

- blockchain core: genesis, mining, linking, tamper detection, persistence
- similarity math
- subject registry
- HTTP layer through the Flask test client with an isolated data directory

---

## Tamper demo

The tamper demo shows that the local ledger is tamper-evident.

```bash
.venv/Scripts/python.exe tools/tamper_demo.py            # flip a recorded similarity
.venv/Scripts/python.exe tools/tamper_demo.py --restore  # fresh chain
```

After tampering:

- the Verify page and `/api/chain/validate` report the chain as INVALID
- the offending block is named

This makes the tamper-evidence claim concrete for the recording and the submission.

---

## Known limitations

- The PoW ledger is local and single-writer. It demonstrates tamper evidence, not
  distributed consensus or a public chain.
- `data/` is git-ignored. It contains biometric data such as enrollment photos and
  probes. Never commit or share it.
- The web search requires a working headless Chrome. If it fails, the pipeline still
  records the attempt on-chain but may not have live social-media links.
- Models (YuNet and SFace) come from OpenCV Zoo and must be downloaded once with
  `tools/fetch_models.py`.
- Matching is against **enrolled subjects** only. The pipeline identifies a face,
  then, only on a match, looks the probe up on the web.
- The built-in Flask dev server is for local use only.
- The on-chain contract currently stores one latest record per subject. For a longer
  audit trail, a per-post append-only registry would be a natural extension.

---

## Security and privacy

This repo is built so that secrets never need to be committed.

- Wallet private keys are supplied through a local `config_chain.py` or an
  environment variable.
- `config_chain.py` is gitignored.
- Biometric images are stored under `data/`, which is gitignored.
- The public proof files contain only public on-chain information: contract address,
  transaction hash, block number, subject id, record hashes, and Polygonscan links.

During recording, do **not** show:

- wallet private keys
- env files with secrets
- `config_chain.py` contents

Keep the on-chain proof public-only.

---

## Recording and submission

Two docs cover the recording:

- `docs/recording-plan.md` — short narrative + checklist
- `docs/recording-guide.md` — full terminal walkthrough, expected output, tamper
  demo, submission-form proof block

Recommended recording flow:

1. Open the dashboard.
2. Run an identify with a probe image that has real web/social matches.
3. Show the similarity, verdict, block, and hashes.
4. Show the web/social results.
5. Show the ledger block with `web_search_results`.
6. Show the on-chain verification endpoint:
   `/api/history/<subject_id>/contract`
7. Optionally open the Polygonscan transaction or contract tab alongside the app.
8. Optionally show the tamper demo and re-verification.

Submission checklist:

- GitHub repo is public or accessible to the reviewers.
- README explains the pipeline, the blockchains used, and the known limitations.
- One screen recording shows face scan → web/social result → on-chain write → on-chain
  verification.
- The on-chain proof note matches what the recording shows.
- No wallet private key is committed or visible in the recording.

Submission form:

https://forms.gle/oZbQGuwiNeHVcHWo8

---

## Roadmap

After shortlisting, possible extensions include:

- Make the on-chain record a per-post append-only registry instead of one record per
  subject
- Submit the actual discovered post fingerprint more explicitly, not just the search
  count
- Add a live re-verification button that queries the contract during the demo
- Improve the UI theme and add a dedicated demo route for recording
- Verify the contract source on Polygonscan
- Add another subject and another on-chain record to show repeatability
- Deploy the Flask app privately for a live walk-through
