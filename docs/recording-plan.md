# Screen-recording plan

This is the **short narrative + checklist** for the recording flow.

For the full step-by-step terminal commands, expected output samples, tamper demo, and
submission-form notes, see `docs/recording-guide.md`.
Goal: show the pipeline end to end in one continuous recording:

1. face scan
2. web / social media search
3. blockchain upload
4. on-chain verification

No editing needed. A plain screen recording is enough.

## Recommended recording flow

### 1. Open the dashboard

- Show `http://127.0.0.1:5000`
- Point out:
  - registered subjects
  - blocks mined
  - chain integrity status

### 2. Run an identify

- Use the Identify page
- Upload a probe image of a public figure that has real web/social matches
- Submit the form

Show in order:

- similarity score
- matched subject
- block number and block hash
- web / social media results list
- at least one external link opening in a new tab

### 3. Show the on-chain record

- Open the ledger page
- Expand the latest block
- Show:
  - block hash
  - previous hash
  - transaction body
  - `web_search_results`
  - if present, `contract_tx_hash`

### 4. Show the on-chain verification

- Open the contract verification endpoint in the browser or via `curl`:
  `/api/history/barack-obama-ee8f7c/contract`
- Show:
  - `local_record_hash`: `0x97189e2976e5009b8d221605aacb00398100d7974363eab455e6f006d970a456`
  - `on_chain_record_hash`: `0x97189e2976e5009b8d221605aacb00398100d7974363eab455e6f006d970a456`
  - `on_chain_match: true`
  - `contract_tx_hash`: `0x0abb16c8429166476a85aa2606fb743404d264e98129fbf2938a6208c9ebb9ae`

If possible, also open the Polygonscan transaction or contract address in a
second tab so the grader can see the same record on the public chain explorer.

Polygonscan transaction link:
`https://amoy.polygonscan.com/tx/0x0abb16c8429166476a85aa2606fb743404d264e98129fbf2938a6208c9ebb9ae`

### 5. Tamper-evidence follow-up, if you want it

- Run `tools/tamper_demo.py`
- Reload `/verify` or `/api/chain/validate`
- Show the chain now reports INVALID
- Restore with `tools/tamper_demo.py --restore` if you want to end clean

This is optional, but it makes the tamper-evidence claim concrete.

## What makes the recording convincing

- One continuous flow, not jumps between unrelated screens
- Real probe image, real web results, real on-chain tx
- A visible link between the app and the public chain explorer
- A clear on-chain match result, not just a local “recorded” message

## What not to show

- Do not show or type the wallet private key
- Do not show env files with secrets
- Do not expose `config_chain.py` contents on screen

Keep the on-chain proof public-only:
tx hash, block number, contract address, hashes, and the verification result.

## Optional command-line alternative

If the web UI is not convenient during recording, you can also use:

- `tools/demo_pipeline.py`
- `curl` against `/api/identify` and `/api/history/<subject_id>/contract`

The important part is that the recording makes all four pipeline stages visible:
scan, search, on-chain write, on-chain verify.

## Suggested narration points

- “This is the face scan input.”
- “The system detects the face and matches it against enrolled subjects.”
- “On a match, it performs a reverse image search to find matching web/social posts.”
- “The result, probe hash, and discovered web matches are written on-chain.”
- “We then re-verify the local payload against the on-chain record hash.”
- “Local and on-chain hashes match, which is the tamper-evident proof.”

## Recording checklist

- [ ] dashboard visible at the start
- [ ] probe image submitted
- [ ] similarity and verdict visible
- [ ] web/social results visible
- [ ] block and hashes visible
- [ ] on-chain verification result visible
- [ ] optional: Polygonscan tab open for the same tx/contract
- [ ] optional: tamper demo + re-verify
- [ ] no secrets visible on screen
