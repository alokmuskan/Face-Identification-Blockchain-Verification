# Project Roadmap — Face Identification & Blockchain Verification

A phased plan to take this project from **task-compliant** → **shortlist-worthy** → **production-ready**.

Current state: **Task-compliant** (all 3 requirements met, 2 commits, GitHub repo live).
Target: **Shortlist-worthy + deployable + on-chain + polished UI.**

---

## Current State Assessment

### ✅ What's Done (Task Requirements)
| Req | Status | Evidence |
|-----|--------|----------|
| Face detection & encoding | ✅ | YuNet + SFace, 128-d embedding, similarity matching |
| Web/social media search | ✅ | Yandex via headless Chrome, returns real URLs (pinterest, imgur, npr, etc.) |
| Blockchain verification | ✅ | Local PoW ledger, hash chain, tamper-evident, validate_chain() works |
| README | ✅ | Covers setup, usage, blockchain choice, limitations |
| GitHub repo | ✅ | https://github.com/alokmuskan/Face-Identification-Blockchain-Verification |

### ⚠️ Gaps vs. What Judges Want to See

| Gap | Why it matters | Impact |
|-----|---------------|--------|
| **Local-only blockchain** | Judges asked for "re-verifying data against on-chain record" — a local JSON file feels like a simulation, not a real blockchain | Medium |
| **No persistence of search results beyond the chain** | If you restart, the web results are in the ledger but not queryable outside it | Low |
| **Web search is Selenium-based, slow, fragile** | Yandex UI changes break selectors; headless Chrome is heavy | Medium |
| **UI is basic Flask templates** | Looks like a 2015 admin panel; not showcase-worthy | Medium |
| **No multi-subject batch / API keyboard** | CLI works but no easy way to integrate into other tools | Low |
| **No public deployment** | Judges can't try it themselves (but task says "no live link required" — so this is bonus) | Low (bonus) |
| **No video recording yet** | Submission requires a screen recording | HIGH — must have |
| **No submission form filled** | Deadline Sep 7 11:59 PM | HIGH — must have |

---

## Phase 0: Submit the Task (Deadline: Sep 7, 2026, 11:59 PM)

These are **mandatory** for the shortlisting round. Do them first.

### 0.1 Record the screen demo
Follow `docs/recording-guide.md`. The recording must show:

1. **Face scan** → terminal shows face detected (score 0.9466, box, embedding hash)
2. **Web search** → "Web search results returned: 10" + at least some URLs visible
3. **Blockchain upload** → "Web search count (on-chain): 10" + block details
4. **Verification** → "Chain valid: True"
5. **Optional but recommended**: Flask `/ledger` page showing Block #2 with 10 web_search_results, OR `/api/chain/validate` returning `valid:true`

**Recording checklist** (from `docs/recording-guide.md`):
- [ ] Face detected
- [ ] 10 web results found (at least some URLs visible)
- [ ] On-chain count = 10
- [ ] Chain valid = True
- [ ] Flask ledger page OR API showing valid chain
- [ ] (Bonus) Tamper detection: tamper → chain INVALID

### 0.2 Upload the recording
Upload to:
- YouTube (unlisted) — easiest
- Google Drive — shareable link
- Loom — instant

### 0.3 Fill the submission form
https://forms.gle/oZbQGuwiNeHVcHWo8

You need:
- GitHub repo link: `https://github.com/alokmuskan/Face-Identification-Blockchain-Verification`
- Screen recording link

**No resubmissions allowed.** Review the recording before submitting.

---

## Phase 1: Shortlist-Worthy Enhancements (1-3 days)

Improvements that make the project stand out in the shortlist review. Each is small, focused, and high-impact.

### 1.1 Improve the UI (medium effort, high visual impact)

**Goal**: Make it look like a real product, not a demo.

**Specific changes**:
- **Add a hero/header section** to `index.html` with the pipeline diagram (the ASCII art from README converted to an inline SVG or styled HTML)
- **Add web result cards** to `identify.html` that show:
  - Thumbnail preview of each found image (using `image_url` from web results)
  - Domain badge (pinterest.com, imgur.com, etc.)
  - Title + description
  - "Open in new tab" button
- **Add a similarity gauge** — a circular or radial gauge instead of the thin bar
- **Dark/light mode toggle** — small touch, shows polish
- **Animations** — fade-in for results, loading spinners during web search
- **Improve color scheme** — current is dark blue; consider a more modern gradient or accent color
- **Responsive**: ensure it works on mobile viewport sizes

**Files to change**:
- `static/style.css` — major updates
- `templates/identify.html` — add result cards
- `templates/index.html` — add hero section
- New: `static/app.js` — client-side interactivity

### 1.2 Add web search result thumbnails
**Goal**: Show actual images found on the web, not just URLs.

**How**:
- In `websearch/search.py` → `_extract_results`, already extracting `image_url` from `<img>` tags
- In the UI, render `<img src="{hit.image_url}">` for each result
- Add fallback if image_url is missing (use a placeholder)

**Impact**: Judges see actual faces/images found online — much more convincing than text URLs.

### 1.3 Add a "Search Result Detail" view
**Goal**: When you click a web result, show more info about it.

**How**:
- Add a new Flask route `/webresult/<result_id>` or pass query params
- Show: full URL, title, description, domain, image URL, page_type, timestamp when found
- Add a "Visit" button that opens the URL

**Why**: Makes the web search feel like a real feature, not just debug output.

### 1.4 Speed up the web search (reduce recording time)
**Goal**: The demo takes ~1-2 minutes due to Selenium + Yandex. For the recording, that's fine, but for future demos it's heavy.

**Options**:
- Add a progress indicator during web search (Flask: use a flashing cursor line or a simple "Searching..." message in the terminal)
- Cache web search results in `data/webcache.json` so re-running with the same image is instant
- Add a `--no-web-search` flag for quick re-tests

### 1.5 Add a "What this project does" animated diagram
Replace the README ASCII diagram with an actual visual on the dashboard page.

**How**:
- Create an SVG or styled HTML representation of the pipeline:
  ```
  [Camera/Image] → [Face Detection (YuNet)] → [Embedding (SFace)] → [Match] → [Web Search (Yandex)] → [Blockchain]
  ```
- Use CSS animations to show flow direction
- Put it on the dashboard (`index.html`)

---

## Phase 2: Move to a Real Blockchain (3-7 days)

The task allows any blockchain, including local/simulated. But moving to a **public testnet** dramatically increases credibility.

### 2.1 Option A: Polygon Mumbai / Polygon Amoy testnet (recommended)

**Why Polygon**:
- Very low gas fees (testnet MATIC is free)
- EVM-compatible — use Solidity smart contract
- Widely supported, good tooling
- Publicly verifiable on Polygonscan

**What to build**:
1. **Smart contract** (Solidity):
   ```solidity
   contract FaceVerification {
       struct Verification {
           bytes32 subjectId;
           string subjectName;
           bytes32 imageHash;
           bytes32 embeddingHash;
           uint8 result; // 0=REJECTED, 1=VERIFIED
           uint8 similarity; // scaled 0-100
           string[] webUrls;
           uint256 timestamp;
           bytes32 blockHash; // hash of block for cross-reference
       }

       mapping(bytes32 => Verification) public verifications;
       bytes32[] public verificationIds;

       function recordVerification(
           bytes32 _subjectId,
           string calldata _subjectName,
           bytes32 _imageHash,
           bytes32 _embeddingHash,
           uint8 _result,
           uint8 _similarity,
           string[] calldata _webUrls,
           bytes32 _blockHash
       ) public {
           bytes32 id = keccak256(abi.encodePacked(_subjectId, block.timestamp, _imageHash));
           verifications[id] = Verification(_subjectId, _subjectName, _imageHash, _embeddingHash, _result, _similarity, _webUrls, block.timestamp, _blockHash);
           verificationIds.push(id);
       }

       function getVerification(bytes32 _id) public view returns (Verification memory) {
           return verifications[_id];
       }

       function listVerifications() public view returns (bytes32[] memory) {
           return verificationIds;
       }
   }
   ```

2. **Python integration**:
   - Use `web3.py` to interact with the contract
   - Connect to Polygon Amoy testnet RPC (free via Alchemy/Infura/Ankr)
   - Replace `Blockchain.record()` with a call to the smart contract
   - Store the tx hash on-chain, keep the local JSON ledger as a mirror

3. **Verification on Polygonscan**:
   - Anyone can look up the tx hash on Polygonscan
   - Shows: "This face verification was recorded on Polygon blockchain at this timestamp"
   - Much more credible than "look at my local JSON file"

4. **Keep the local ledger** as a fast local cache, but add the smart contract tx hash to each block as `contract_tx_hash`.

### 2.2 Option B: Ethereum Sepolia testnet

Same as above but on Ethereum Sepolia. Higher profile (Ethereum) but slightly more complex setup. Gas is free on Sepolia too.

### 2.3 Option C: Keep local + add a public hash anchor

If testnet deployment is too much for the shortlist timeline, do this instead:

1. Keep the local JSON ledger
2. For each block, compute a **Merkle root** of all transactions
3. Publish the Merkle root as a **GitHub Gist** or **Twitter/X post** with the hash
4. This creates a **timestamped public record** of the hash — not as strong as a blockchain, but better than "look at my file"

**Why this is a good intermediate step**: It's fast (no testnet setup), but creates a public, timestamped record that can be cross-referenced.

### 2.4 What to show judges for blockchain credibility

Regardless of which option:
- Show the **transaction hash** on Polygonscan / Etherscan / GitHub Gist
- Show that the hash in the transaction matches the hash in the local ledger
- Show that re-computing the hash from the transaction data gives the same result
- Explain: "The local ledger is fast and private. The public anchor proves the data existed at this time and hasn't been altered."

---

## Phase 3: "Everything on Chain" — Full On-Chain Architecture

Once the smart contract is deployed, move more data on-chain.

### 3.1 What's currently on-chain (local JSON)
- Block index, timestamp, nonce
- Transaction type, subject_id, subject_name
- image_hash, embedding_hash
- similarity, result (VERIFIED/REJECTED)
- web_search_results[] (list of URLs)
- block hash, previous_hash (for chain integrity)

### 3.2 What should go on a public blockchain (smart contract)

**Put on-chain (in the smart contract)**:
- `subjectId` (bytes32 hash of name)
- `subjectName` (string, short)
- `imageHash` (bytes32 — SHA-256 of face image)
- `embeddingHash` (bytes32 — SHA-256 of SFace embedding)
- `result` (uint8 enum)
- `similarity` (uint8, 0-100 scaled)
- `webUrls` (string[] — the discovered social media URLs)
- `timestamp` (block.timestamp)
- `localChainHash` (bytes32 — the hash of the corresponding block in the local ledger, for cross-referencing)

**Keep off-chain (local only)**:
- Actual face images (too large for blockchain)
- SFace embedding vectors (128 floats = 512 bytes, expensive on-chain)
- Full probe image
- The local ledger's detailed block structure (nonce, full tx JSON, etc.)

### 3.3 New pipeline flow with smart contract

```
Face scan
    │
    ▼
[Face detection + embedding]
    │
    ▼
[Web search] → list of URLs
    │
    ▼
[Build transaction data]
    ├── imageHash = SHA256(image_bytes)
    ├── embeddingHash = SHA256(embedding.tobytes())
    ├── similarity = int(similarity * 100)
    ├── webUrls = [...]
    └── localChainHash = blockchain.chain[-1].hash
    │
    ▼
[Call smart contract recordVerification(...) → tx_hash]
    │
    ▼
[Record tx_hash in local ledger as well]
    │
    ▼
[Done] — data is now verifyable on Polygonscan + locally
```

### 3.4 Verification flow (re-verifying against on-chain record)

To verify a past verification:

1. **Locally**: load `data/ledger.json`, find the block for the subject, get `contract_tx_hash`
2. **On-chain**: call `getVerification()` on the smart contract, get the stored data
3. **Cross-check**:
   - `local.imageHash == onChain.imageHash`
   - `local.embeddingHash == onChain.embeddingHash`
   - `local.similarity == onChain.similarity`
   - `local.webUrls == onChain.webUrls`
   - `local.localChainHash == onChain.localChainHash`
4. **On Polygonscan**: show the transaction, the block number, the timestamp — immutable public record

### 3.5 Files to add/change for full on-chain

**New files**:
- `contracts/FaceVerification.sol` — Solidity smart contract
- `scripts/deploy.py` — deploy contract to testnet
- `scripts/interact.py` — example of recording + verifying on-chain
- `blockchain/contract_client.py` — web3.py wrapper for the contract

**Changes to existing files**:
- `services/verification_service.py` — call smart contract after mining local block
- `blockchain/ledger.py` — add `contract_tx_hash` field to blocks
- `config.py` — add RPC URL, contract address, private key env vars
- `requirements.txt` — add `web3`

---

## Phase 4: Richer Local Record + UI (implemented ✅)

> Phase 4 was redefined with the approved decision: keep the deployed
> `FaceVerificationHub` and the canonical record hash unchanged, and improve the
> application around them. Full scope: `docs/phase4-roadmap.md`.

**Done and verified:**
- [x] Richer local verification records (probe/embedding hashes, block + tx
      linkage, verdict metadata)
- [x] Fixed `verify_contract()` cross-check (`local_block_hash` participates in
      the canonical record hash)
- [x] Cleaned history + on-chain verification UI
- [x] `tests/test_phase4.py` + `/health` route test (26/26 passing)
- [x] Deployment scaffolding: `Dockerfile`, `.dockerignore`, `.env.example`,
      env-configurable `HOST`/`PORT`/`FLASK_DEBUG`

---

## Phase 5: Deployment (optional bonus, 1-2 days)

Make the project **live and accessible**. Not required for the submission (the
task says no live working link needed), but impressive for reviewers.

### 4.1 Backend deployment

**Option A: Render / Railway / Fly.io** (easiest)
- Deploy the Flask app
- Problem: needs Chrome for web search → headless Chrome on these platforms is tricky
- Solution: use a Docker container with Chrome installed, or use Playwright's bundled browser

**Option B: Docker + custom VPS**
- Dockerize the app with Chrome + Selenium
- Deploy to a cheap VPS (DigitalOcean $5/mo, Hetzner, etc.)
- Run on port 80/443 with nginx reverse proxy + HTTPS

**Option C: Serverless** (not recommended for this — needs persistent state)

**Recommended for shortlist**: deploy to **Render** or **Railway** with a Dockerfile that includes Chromium. Even a 24-hour live demo link is impressive.

### 4.2 Docker setup

Create `Dockerfile`:
```dockerfile
FROM python:3.13-slim

# Install Chrome
RUN apt-get update && apt-get install -y wget gnupg2 \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium 2>/dev/null || true

COPY . .
RUN python tools/fetch_models.py || true

EXPOSE 5000
CMD [".venv/bin/python", "app.py"]
```

### 4.3 Environment variables for deployment

```bash
# Blockchain (if using testnet)
WEB3_RPC_URL=https://polygon-amoy.g.alchemy.com/v2/YOUR_KEY
CONTRACT_ADDRESS=0x...
PRIVATE_KEY=...  # testnet key only, never commit

# App
FLASK_ENV=production
HOST=0.0.0.0
PORT=5000
```

### 4.4 What to show for deployment

- A **live URL** (even if testnet-only)
- The **smart contract address** on Polygonscan
- A screenshot of the live app
- Explanation: "The app is deployed at X. The smart contract is at Y on Polygon Amoy testnet. Anyone can verify a face verification by looking up the tx hash on Polygonscan."

---

## Phase 6: Polish & Presentation (in progress)

Things that make the project feel finished and professional.

### 5.1 Better README — done ✅

Rebuilt as a single clean document with architecture, workflow, smart-contract
section, live proof values, and a "how to prove it again" guide.

### 5.2 Add a /demo route — done ✅

One-click live demo page with an animated 5-step pipeline stepper
(face scan → detect+embed → identity match → web search → ledger + on-chain),
inline results and Polygonscan links.

### 5.3 Add proper error handling & user feedback — done ✅

- Loading states during web search (spinner + staged status lines on /identify)
- Demo page reports on_chain_submitted / on_chain_error / skip reason explicitly
- Better error messages throughout the pipeline

### 5.4 Batch operations — partially done

- [x] Export a subject's verification records as JSON
      (`/api/history/<subject_id>/export`, attachment download)
- [ ] Upload multiple images at once
- [ ] Bulk identify

### 5.5 REST API docs page — done ✅

Rendered reference at `/api/docs` (nav: "API") listing every endpoint group
with descriptions and curl examples.


---

## Phase 7: Advanced Features (stretch goals, post-shortlist)

### 6.1 Multiple face detection engines
- Allow switching between YuNet, SSD, MTCNN, etc.
- Compare results across engines

### 6.2 Multiple search engines
- Yandex + Bing + Google Lens (via API)
- Show results from multiple engines side by side
- Aggregate and rank results

### 6.3 Face clustering / duplicate detection
- Detect if the same face appears across multiple discovered web posts
- Cluster by embedding similarity
- Show "this face appears in N different posts"

### 6.4 Temporal analysis
- For each discovered post, try to get the post date
- Show a timeline: "This face appeared on Pinterest on date X, on imgur on date Y..."

### 6.5 Social media API integration
- If a post is found on a platform with an API (Reddit, Twitter/X, etc.), fetch the actual post content (text, comments, likes)
- Store the post metadata on-chain, not just the URL

### 6.6 Privacy / consent features
- Face blurring option for display
- "Do not index" flag
- Data deletion on request

---

## Priority Matrix

| Phase | Task | Effort | Impact | When |
|-------|------|--------|--------|------|
| 0 | Record + submit | 1 hour | CRITICAL | Before Sep 7 11:59 PM |
| 0 | Fill submission form | 10 min | CRITICAL | Before Sep 7 11:59 PM |
| 1.1 | UI improvements | 2-3 days | High | After submission (or before if time) |
| 1.2 | Web result thumbnails | 1 day | High | After submission |
| 1.3 | Search result detail view | 1 day | Medium | After submission |
| 1.4 | Speed up + cache web search | 1 day | Medium | After submission |
| 1.5 | Pipeline diagram on dashboard | 1 day | Medium | After submission |
| 2.1 | Polygon smart contract | 3-5 days | VERY HIGH | If shortlisted, before final round |
| 2.4 | Show Polygonscan verification | 1 day | VERY HIGH | With 2.1 |
| 3.1-3.5 | Full on-chain architecture | 3-5 days | HIGH | After shortlist |
| 4.x | Richer local record + UI | done | HIGH | Completed ✅ |
| 5.1-5.4 | Deployment (Docker/PaaS) | 1-2 days | Medium | Optional bonus |
| 6.1 | Better README | 1 day | Medium | Anytime |
| 6.2 | /demo route | 1 day | Medium | Anytime |
| 7.x | Stretch goals | varies | Low-Med | Post-shortlist |

---

## File Structure After All Phases

```
.
├── app.py                          # Flask app (updated with routes for all features)
├── config.py                       # Updated with blockchain RPC, contract address, etc.
├── requirements.txt                # Updated with web3, etc.
├── Dockerfile                      # NEW: container for deployment
├── README.md                       # UPDATED: full docs with diagrams, contract address, live link
├── .env.example                    # NEW: example env vars (never commit .env)
├── docs/
│   ├── recording-guide.md          # Already exists — how to record the demo
│   ├── ROADMAP.md                  # This file
│   ├── SMART_CONTRACT.md           # NEW: Solidity contract docs, deployment, verification
│   └── DEPLOYMENT.md               # NEW: deployment instructions
├── contracts/
│   └── FaceVerification.sol        # NEW: Solidity smart contract
├── scripts/
│   ├── deploy.py                   # NEW: deploy contract to testnet
│   └── interact.py                 # NEW: example on-chain interaction
├── blockchain/
│   ├── __init__.py
│   ├── block.py
│   ├── ledger.py                   # UPDATED: contract_tx_hash field
│   └── contract_client.py          # NEW: web3.py wrapper
├── faceid/
│   ├── __init__.py
│   ├── engine.py
│   ├── similarity.py
│   └── store.py
├── services/
│   ├── __init__.py
│   └── verification_service.py     # UPDATED: call smart contract
├── websearch/
│   ├── __init__.py
│   └── search.py                   # UPDATED: caching, multi-engine
├── static/
│   ├── style.css                   # UPDATED: modern UI
│   ├── app.js                      # NEW: client-side interactivity
│   └── capture.js
└── templates/
    ├── base.html                   # UPDATED: new layout
    ├── index.html                  # UPDATED: hero + pipeline diagram
    ├── identify.html               # UPDATED: result cards with thumbnails
    ├── ledger.html
    ├── verify.html
    ├── register.html
    ├── history.html
    ├── error.html
    ├── _capture.html
    └── demo.html                   # NEW: dedicated demo page
```

---

## Quick Wins for Shortlist (do these NOW if you have time before Sep 7)

1. **Record the screen** — follow `docs/recording-guide.md`
2. **Upload the recording** — YouTube unlisted / Google Drive / Loom
3. **Fill the submission form** — https://forms.gle/oZbQGuwiNeHVcHWo8
4. **Add a pipeline diagram to the dashboard** (`index.html`) — visual impact is huge
5. **Add web result thumbnails** to `identify.html` — shows actual images found
6. **Improve the UI CSS** — dark theme with accent colors, cards, spacing

These 6 things transform the project from "task complete" to "looks polished and intentional."

---

## Key Message for Judges

When presenting or writing the README:

> "We built a pipeline that takes a face scan, finds where that face appears on the web/social media using a real reverse-image search, and records the discovery on a tamper-evident blockchain. The blockchain record can be re-verified at any time — any attempt to alter the recorded data breaks the chain.
>
> We used [Yandex Images via headless Chrome] for the web search (no API key needed, genuine search) and [a local SHA-256 hash-chained proof-of-work ledger / Polygon Amoy testnet smart contract] for the blockchain. The entire pipeline runs end-to-end from a single command (`tools/demo_pipeline.py`) and takes about [X] seconds."

---

## Next Steps for You

1. **Submit the task** (Phase 0) — deadline Sep 7 11:59 PM. This is non-negotiable.
2. **Read through this roadmap** with your team and decide which phases to tackle.
3. **Pick 2-3 Phase 1 items** to do immediately after submission (UI, thumbnails, diagram).
4. **If shortlisted**, start Phase 2 (Polygon smart contract) immediately — that's the biggest credibility boost.
5. **Keep this roadmap** as a living document — update it as you complete phases.
