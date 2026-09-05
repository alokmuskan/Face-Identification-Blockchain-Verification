# HH Goa 2026 — Face Identification & Blockchain Verification

What to build
A pipeline that takes a face scan as input, identifies matching content on the web/social media, and then verifies that discovered data using a blockchain — end to end. Pipeline shape: Face scan input → Web/social media search (find matching post) → Blockchain upload/verification of the discovered data

Technical requirements
1. Face identification Detect and encode a face from an input image (any face detection/recognition library or API is acceptable).

2. Social media / web search Use the face to search the web and find at least one real, matching social media post (via reverse image search, an API, or a scripted search approach). This should be a genuine search step, not a hardcoded/pre-picked result.

3. Blockchain verification Once a matching post is found, upload the post (or a hash/fingerprint of it, e.g. the image, text, or metadata) to a blockchain to create a verifiable, tamper-evident record. Any blockchain may be used — public testnet, mainnet, or a local/simulated chain — as long as you can demonstrate re-verifying the data against the on-chain record.

4. No website required You do not need to build or host a project website. Focus your time on the pipeline itself.

5. GitHub repo required Your full source code must be in a GitHub repo, with a README covering what the project does, how to run it, which blockchain you used, and any known limitations.

Submission requirements
● GitHub repo link
● A screen recording of the working project (no live working link required)
● Submission form link : https://forms.gle/oZbQGuwiNeHVcHWo8  (No resubmissions will be allowed — submit only when your build is final.)
Screen recording
● Record your screen showing the pipeline working end to end: face scan → social post found → blockchain upload/verification.
● No editing or production needed — a plain screen recording is enough.
● Upload it anywhere (YouTube unlisted, Google Drive, Loom, etc.) and share a working link.
Timeline
● Task launch: August 31, 2026
● Deadline: Sept 7, 2026, 11:59 PM

## What this project does

A fully local pipeline that takes **one face image** and runs it end to end:

1. **Face detection & encoding** — YuNet finds the largest face, SFace produces a 128-d embedding.
2. **Face identification** — the embedding is matched against enrolled subjects using cosine similarity; a `VERIFIED` / `REJECTED` verdict is recorded.
3. **Web / social media search** — when a match is found, the probe image is uploaded to a **headless Yandex Images** reverse-image search over a Selenium-driven Chrome browser. Matching URLs (social media posts, image hosts, blogs) are extracted and classified by page type.
4. **Blockchain verification** — the face verification result **and the web search results** are mined as a transaction into a **SHA-256 hash-chained, proof-of-work local ledger** (`data/ledger.json`). The chain is re-validated on demand: any tampered transaction breaks the hash chain.
5. **Demo script** — `tools/demo_pipeline.py` drives the whole pipeline from the command line and prints a readable transcript suitable for screen recording.

## Pipeline shape

```
Face scan (image bytes)
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
      ├─ NOT matched → REJECTED, recorded on-chain (no web search)
      │
      ▼ MATCHED
[ WebSearchEngine (Selenium + Chrome headless) ]
      │   upload probe image to Yandex Images
      │   extract matching URLs → classify social_media / image_host / blog / web
      ▼
[ Blockchain ] → FACE_VERIFICATION tx + web_search_results[] mined into hash chain
      │
      ▼
[ validate_chain() ] → recompute every hash → tamper-evident proof
```

## What’s in the repo

```
app.py                  Flask web UI (dashboard, register, identify, ledger, verify)
config.py               All knobs: model paths, blockchain difficulty, matching threshold
services/verification_service.py   workflow layer (register / identify / history)
blockchain/             hash-chained PoW ledger (block.py + ledger.py)
faceid/                 YuNet detection, SFace embedding, subject JSON registry
websearch/              headless reverse-image search (Yandex via Selenium)
tools/fetch_models.py   downloads ONNX models from OpenCV Zoo
tools/demo_pipeline.py  end-to-end CLI demo / screen-recording script
tests/                  pytest suite for blockchain, face store, similarity, HTTP layer
```

## How to run

### 1. Set up the environment

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe tools\fetch_models.py
```

- `requirements.txt` now also pulls in `playwright`, `selenium` and the browser driver support needed for the web search step.
- The model fetcher downloads **YuNet** and **SFace** ONNX files (~37 MB into `models/`).

### 2. (Optional) Install Chrome / Chromium

The web search module drives a **headless Chrome** via Selenium. If Chrome is already installed on the machine, Selenium’s built-in driver manager usually picks it up. Otherwise, install the matching Chromium/ChromeDriver, or point `websearch/search.py` at a known binary through an env var if needed.

### 3. Run the pipeline demo (screen-recording friendly)

```bash
.venv\Scripts\python.exe tools\demo_pipeline.py
```

This will:

- load or generate a probe image (a simple drawn face is created automatically if nothing is enrolled),
- run detection + embedding,
- identify or register a subject,
- run the reverse image search through Yandex,
- mine the result into the blockchain,
- validate the chain,
- print a step-by-step transcript.

You can also point it at your own photo:

```bash
.venv\Scripts\python.exe tools\demo_pipeline.py --probe mypic.jpg
```

If you want a silent re-verification only:

```bash
.venv\Scripts\python.exe tools\demo_pipeline.py --probe mypic.jpg
```

### 4. Run the web UI (optional)

```bash
.venv\Scripts\python.exe app.py
```

Then open `http://127.0.0.1:5000`.

- **Dashboard** — subject count, block count, chain status, recent events.
- **Register** — type a name, upload a photo or capture a camera frame.
- **Identify** — submit a probe photo; the verdict, web-search hit list and its block are shown.
- **Ledger** — every block with its transactions, hashes, nonce and embedded web-search results.
- **Verify** — one-click integrity check of the whole chain.

## Which blockchain is used

- **Local JSON ledger** — `data/ledger.json`.
- **Proof of work**: each block hash starts with `DIFFICULTY=4` leading hex zeros (configurable in `config.py`).
- **Tamper evidence**: `validate_chain()` recomputes every block hash, checks the proof of work and verifies that every block links to its predecessor. The `/verify` page and `/api/chain/validate` report the result block by block.
- This is a **demo ledger**: the PoW demonstrates tamper evidence, not distributed consensus. The on-chain record is a hash fingerprint of the face verification event and the discovered web/social-media matches — enough to prove the data existed in this form and has not been altered.

## Reverse image search details

- Engine: **Yandex Images** (`yandex.com/images`) via a headless Chrome driven by Selenium.
- The flow in headless mode:
  1. navigate to Yandex Images,
  2. click the “Search by image” control,
  3. upload the probe image through the file input,
  4. wait for the result cards,
  5. extract the top 10 result URLs and classify each as `social_media`, `image_host`, `blog` or `web`.
- No API key is required.
- If the browser cannot start or no results are returned, the pipeline still records an **empty web-search result** on-chain — the face verification step is never blocked by a search failure.
- Known limitation: headless Chrome on some environments may need an explicit `CHROMIUM_PATH` or a manual ChromeDriver install; web UI layouts change and selectors may need updating.

## Known limitations

- The PoW ledger is local and single-writer; it demonstrates tamper evidence, not distributed consensus or a public chain.
- `data/` is git-ignored — it contains biometric data (enrollment photos, probes). Never commit or share it.
- The web search requires a working headless Chrome; if it fails, the pipeline still records the attempt on-chain but won’t have live social-media links.
- Models: YuNet (face detection) and SFace (face recognition) from OpenCV Zoo, used through `opencv-contrib-python`. They must be downloaded once with `tools/fetch_models.py`.
- Matching is against **enrolled subjects** only — the pipeline identifies a face, then (only on a match) looks the probe up on the web.
- The built-in Flask dev server is for local use only.

## Tests

```bash
.venv\Scripts\python.exe -m pytest -q
```

Covers the blockchain core (genesis, mining, linking, tamper detection, persistence), the similarity math, the subject registry and the HTTP layer through the Flask test client (with an isolated data directory).

## Configuration (config.py)

```
DIFFICULTY = 4                    leading hex zeros required per block
MATCH_THRESHOLD = 0.363           SFace cosine threshold recommended by OpenCV
MAX_EMBEDDINGS_PER_SUBJECT = 3
WEB_SEARCH_TIMEOUT = 45           seconds given to the reverse-image search
MAX_DETECT_SIDE = 640             probes are downscaled before detection
```

## Tamper demo

```bash
.venv\Scripts\python.exe tools\tamper_demo.py            # flip a recorded similarity
.venv\Scripts\python.exe tools\tamper_demo.py --restore  # fresh chain
```

After tampering, the Verify page and `/api/chain/validate` report the chain as INVALID and name the offending block.

## JSON API

```
GET  /api/status                models available, subject count, chain stats
POST /api/register              multipart form: name, image -> 201
POST /api/identify              multipart form: image -> verdict + block + web_results[]
GET  /api/chain                 full chain with all blocks
GET  /api/chain/validate        integrity report: valid, blocks_checked, errors
GET  /api/history/<subject_id>  subject record plus on-chain events
```

Example:

```bash
curl -F name=Alice -F image=@alice.jpg http://127.0.0.1:5000/api/register
curl -F image=@probe.jpg http://127.0.0.1:5000/api/identify
curl http://127.0.0.1:5000/api/chain/validate
```

The `/api/identify` response now includes `web_results[]`, each with `url`, `title`, `description`, `image_url` and `page_type`.
