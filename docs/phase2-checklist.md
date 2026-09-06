# Phase 2 hardening checklist

Use this as the final pre-submission review for the on-chain work.

## 1) Contract and deployment

- [ ] `contracts/FaceVerificationHub.sol` matches the deployed bytecode/source
- [ ] `contracts/FaceVerificationHub.abi.json` matches the deployed contract
- [ ] Contract is verified on Polygonscan, or at least easily verifiable
- [ ] Contract address is correct in:
  - `config_chain.py` used for demo runs
  - `docs/onchain-proof.md`
  - README deployment block

## 2) Bridge and hashing

- [ ] The on-chain `recordHash` is Keccak-256 of a deterministic canonical JSON payload
- [ ] The same canonical payload shape is used for:
  - submission
  - local hash computation
  - verification
- [ ] `verifyRecord(...)` compares the local payload hash against the on-chain hash
- [ ] No secret is logged or exposed in terminal output during demo

## 3) Proof artifact

- [ ] `docs/onchain-proof.md` exists
- [ ] It includes only public data:
  - contract address: `0x7fc71404Ce10f84B5C467AB3c9806507D422fEf4`
  - tx hash: `0x0abb16c8429166476a85aa2606fb743404d264e98129fbf2938a6208c9ebb9ae`
  - block number: `46874016`
  - subject id: `barack-obama-ee8f7c`
  - local record hash: `0x97189e2976e5009b8d221605aacb00398100d7974363eab455e6f006d970a456`
  - on-chain record hash: `0x97189e2976e5009b8d221605aacb00398100d7974363eab455e6f006d970a456`
  - verification result: `True`
  - Polygonscan link: `https://amoy.polygonscan.com/tx/0x0abb16c8429166476a85aa2606fb743404d264e98129fbf2938a6208c9ebb9ae`
- [ ] It does not contain private keys, signed payloads, or biometric images

## 4) Backend integration

- [ ] `/api/history/<subject_id>/contract` returns:
  - `local_record_hash`
  - `on_chain_record_hash`
  - `on_chain_match`
  - `contract_tx_hash`
- [ ] The local ledger block stores `contract_tx_hash` when the bridge is active
- [ ] The pipeline still works in local-only mode when `config_chain.py` is absent

## 5) Recording readiness

- [ ] `docs/recording-plan.md` matches the actual app screens you intend to show
- [ ] You have a public-figure probe that returns real web/social results
- [ ] You can open the Polygonscan tx/contract tab alongside the app during recording
- [ ] No secrets appear on screen

## 6) Submission hygiene

- [ ] `.gitignore` excludes `config_chain.py`
- [ ] `data/` is not committed
- [ ] No undocumented secret files are in the repo
- [ ] README clearly states which blockchain is used and how verification works

## 7) Optional stronger guarantees

If you want to improve the submission further before the deadline:

- [ ] Verify the contract source on Polygonscan
- [ ] Add one more subject + one more on-chain record to show repeatability
- [ ] Record a short tamper-evidence follow-up:
  - tamper the local ledger
  - show `/api/chain/validate` fail
  - restore and re-verify
- [ ] Add a small note clarifying the current contract stores one latest record per subject

## 8) Future phases you can add after shortlisting

If the team is shortlisted and you want to go further:

- [ ] Make the on-chain record a per-post append-only registry instead of one record per subject
- [ ] Submit the actual discovered post fingerprint more explicitly, not just the search count
- [ ] Add a chain explorer view inside the app for the on-chain records
- [ ] Add a re-verification button that queries the contract live during the demo
- [ ] Improve the UI theme and add a dedicated demo route for recording
- [ ] Deploy the Flask app itself somewhere private for a live walk-through
