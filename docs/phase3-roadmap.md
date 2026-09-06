# Phase 3 roadmap — stronger on-chain trace + live re-verification UI

Phase 3 is about making the on-chain part stronger and easier to prove in a demo.
It should build on the existing deployed contract and the existing local ledger, not
replace them.

The current state is already good:

- `FaceVerificationHub` is deployed on Polygon Amoy
- the local pipeline writes a canonical record hash on-chain
- the local ledger stores `contract_tx_hash`
- `/api/history/<subject_id>/contract` can re-verify locally against on-chain

Phase 3 improves three things:

1. richer on-chain traceability
2. clearer correspondence between one local block and one on-chain record
3. a demo-friendly live re-verification UI

---

## 1. What Phase 3 should not do

Phase 3 should avoid a few common mistakes:

- Do not dump large or biometric data directly on-chain.
- Do not use low-precision storage for similarity.
- Do not introduce unbounded string arrays on-chain unless they are explicitly
  bounded and cheap.
- Do not invent a new contract/ABI unless the current one really cannot support
  the next step.
- Do not make the local chain dependent on the on-chain bridge. The pipeline must
  still work locally when `config_chain.py` is absent.

---

## 2. What is already on-chain today

Current contract storage per subject:

- `subjectId`
- `recordHash`
- `similarity` as `round(similarity * 1_000_000)`
- `result`
- `probeImageHash`
- `webResultCount`

Current local ledger block stores much more:

- block index, timestamp, nonce
- transaction type, subject id, subject name
- image hash, embedding hash
- similarity, result
- `web_search_results[]`
- block hash, previous hash
- optionally `contract_tx_hash`

That split is actually reasonable. The on-chain part is the tamper-evident
fingerprint. The local ledger is the richer record.

---

## 3. Recommended Phase 3 on-chain model

Instead of moving everything on-chain, store a stronger and still compact on-chain
record for each verification event.

### 3.1 Keep the current fields

The current `createRecord(...)` fields are a good base:

- `subjectId`
- `recordHash`
- `similarity` scaled to `int(similarity * 1_000_000)`
- `result`
- `probeImageHash`
- `webResultCount`

These should stay. They are already useful and reasonable.

### 3.2 Add traceability fields if you want them

If you want each on-chain record to be traceable to the local ledger, add one or
both of these:

- `localBlockHash` — the hash of the local ledger block that carried the same
  verification event
- `contractTxIndex` or similar — an optional ordering identifier for the on-chain
  record, if you ever want a per-subject history on-chain

This makes it possible to say:

- this on-chain record corresponds to local block `#N`
- this local block carries `contract_tx_hash`
- both layers point at the same event

### 3.3 Be careful with web results

Do not assume the full discovered URL list should go on-chain as an unbounded
string array. That can be expensive and can fail in real demos.

Better options:

- store `webResultCount` only
- store a canonical hash of the ordered discovered result list
- store a small bounded set of post fingerprints, for example `webPostHashes[]`
  with a fixed maximum length

The safest tamper-evident choice is usually:

- keep the detailed web results in the local ledger
- store one canonical hash of the result list or a bounded fingerprint set on-chain
- verify locally against that hash when needed

If the task story is “we found a matching post and recorded proof of it”, then a
small per-post fingerprint or a canonical result-list hash is usually enough.

### 3.4 Be careful with embeddings

Do not treat a raw SFace embedding as a universal biometric identifier. It depends
on the model, detection, alignment, normalization, and array layout. That makes it
fragile as a long-lived on-chain identifier.

If you still want an embedding-related on-chain fingerprint, use the same embedding
bytes that the local store already hashes, and label it clearly as a local-model
artifact, not a stable identity credential.

### 3.5 Keep similarity precision

Do not change similarity to `uint8, 0-100`. That loses precision and weakens
verification.

Keep the current approach:

- store `round(similarity * 1_000_000)`
- compare it as an integer on-chain and locally

---

## 4. Updated pipeline shape for Phase 3

The pipeline flow should stay similar, but the on-chain submission should carry
more traceability.

```
Face scan (image bytes)
    │
    ▼
[ Face detection + embedding ]
    │
    ▼
[ Identity match ]
    │
    ▼
[ Web search ] → discovered results
    │
    ▼
[ Build canonical record payload ]
    ├── subjectId
    ├── similarity
    ├── result
    ├── probeImageHash
    ├── webResultCount
    └── optional: webResultListHash / webPostHashes[]
    │
    ▼
[ Mine local block ]
    │
    ▼
[ Submit on-chain record ]
    ├── recordHash = keccak256(canonical_payload)
    ├── localBlockHash = local block hash for this event
    └── similarity stored as scaled integer
    │
    ▼
[ Store contract_tx_hash in local block ]
    │
    ▼
Done — local block and on-chain record are cross-linked
```

Important ordering note:

- The local block should be created first.
- The on-chain submission should then reference that local block.
- The local block should store the resulting `contract_tx_hash`.

That gives a clean 1:1 correspondence.

---

## 5. Verification flow for Phase 3

Verification should be a layered cross-check, not an all-fields-equal check.

### 5.1 Primary check: record hash

The strongest check is:

- recompute the canonical payload locally
- keccak256 it
- compare with the on-chain `recordHash`

If that matches, the on-chain record is bound to the exact local payload.

### 5.2 Secondary checks: traceability

If you added traceability fields, also check:

- `localBlockHash` matches the local block
- `contract_tx_hash` is present in that local block
- subject id matches

These checks make the correspondence explicit.

### 5.3 Optional field-level checks

You can also compare individual fields when it is safe:

- `similarity` as scaled integer
- `probeImageHash`
- `webResultCount`
- optional: a canonical hash of the discovered result list

Avoid fragile exact comparisons if the on-chain representation may differ due to
truncation, ordering, or normalization.

### 5.4 Public proof

For the demo and submission, the public proof should show:

- the Polygonscan transaction
- the contract address
- the record hash
- the local block hash it corresponds to
- the local `contract_tx_hash`
- the live re-verification result

That gives reviewers two independent views of the same event.

---

## 6. Suggested files and changes

Do not over-engineer the file list. A clean Phase 3 likely needs:

### 6.1 Docs

- `docs/phase3-roadmap.md` — this file
- update `docs/SMART_CONTRACT.md` if the record shape changes
- update `docs/onchain-proof.md` after any new on-chain submission
- update `README.md` if the deployment model changes

### 6.2 Contract

One of these two approaches:

- extend `FaceVerificationHub` with a second record function and/or extra fields, if
  the current contract is still acceptable for the next step
- or create a small new contract for a richer per-event registry, if you want a
  separate audit trail

If you extend the existing contract, keep backward compatibility in mind so the
current deployment and proof note still make sense.

### 6.3 Bridge

- update `blockchain/contract.py` if the contract interface changes
- keep the canonical payload logic in `blockchain/_keccak.py`
- keep the bridge lazy and optional
- keep secrets out of code

### 6.4 Service layer

- update `services/verification_service.py` to:
  - compute any new canonical fields
  - submit the richer record
  - store `contract_tx_hash` and/or `localBlockHash` in the local block
  - support the new cross-check logic

### 6.5 App / UI

- add a live re-verification UI path
- optionally add a per-subject on-chain record list
- keep the UI focused on proof, not decoration

---

## 7. Live re-verification UI concept

The clearest demo improvement is a UI that re-verifies on demand and shows the
result in plain language.

### 7.1 What the UI should show

For a subject or a local block:

- local record hash
- on-chain record hash
- local block hash
- `contract_tx_hash`
- Polygonscan link
- on-chain match: True / False
- which fields matched, if you show field-level detail
- timestamp and block numbers from both layers

### 7.2 How it should behave

- The user opens a subject or block view.
- The UI loads the local data.
- The UI queries the contract live.
- The UI compares and shows the result.
- The UI should not hide failures. If the bridge is not configured, show that
  clearly instead of pretending the on-chain check ran.

### 7.3 Suggested routes

- `/history/<subject_id>` could show on-chain records and a re-verify action
- `/chain/block/<block_index>` or similar could show the cross-link
- `/api/history/<subject_id>/contract` already exists and can be reused as the
  backend for the new UI

---

## 8. Proof packaging

Phase 3 should make the proof easier to export and reuse.

A good proof artifact includes:

- contract address
- transaction hash
- local block index and local block hash
- `contract_tx_hash`
- subject id
- local record hash
- on-chain record hash
- timestamp
- similarity
- web result count
- live re-verification result
- Polygonscan links

That can be in `docs/onchain-proof.md`, or in a small machine-readable export, or
both.

---

## 9. Safe rollout order

Do this in order so nothing breaks silently:

1. Decide whether Phase 3 extends the current contract or creates a new one.
2. Update the ABI and bridge first.
3. Update the service layer second.
4. Add the UI view last.
5. Run one fresh local + on-chain submission.
6. Verify that:
   - the local block has the expected cross-link fields
   - the on-chain record matches
   - the UI re-verification returns the same result
7. Update the proof note and README.

---

## 10. Risks to watch

- Unbounded on-chain arrays can make deployment and interaction fragile.
- Changing the record shape can invalidate older proof notes if you are not careful.
- Embedding bytes are not stable across environments, so they are a weak on-chain
  biometric anchor.
- If the local block is mined after the on-chain call, the cross-link is weaker.
  Keep the local-first ordering.
- If the bridge is optional, the UI must degrade gracefully when it is missing.

---

## 11. Minimum viable Phase 3

If you want the safest and most efficient version, Phase 3 should probably be:

1. keep the existing contract
2. add `localBlockHash` and/or a result-list hash to the on-chain record
3. keep detailed data local
4. add one live re-verification UI view
5. update the proof note and README

That gives you:

- stronger traceability
- a clearer demo story
- less risk than a full on-chain data dump
- a natural path to a per-post registry later if needed

---

## 12. Optional later extension

After Phase 3, a natural extension is a separate per-post append-only registry for
the actually discovered social media posts. That would let you show:

- one verification event
- multiple discovered post fingerprints
- an immutable audit trail

But that is a later step. Phase 3 first should make the current one-event,
two-layer model cleaner and more demonstrable.
