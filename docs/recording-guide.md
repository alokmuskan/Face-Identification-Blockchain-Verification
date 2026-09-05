# Screen Recording Guide — Face Identification & Blockchain Verification

This guide walks you through recording a screen video that demonstrates the full pipeline end-to-end for the HH Goa 2026 shortlisting task.

## What the recording must show

The task requires a screen recording showing:

1. **Face scan input** — loading a face image
2. **Social media post found** — reverse image search returns real matching results
3. **Blockchain upload/verification** — the found data is recorded on-chain and re-verified

No editing or production is needed — a plain screen recording is enough.

---

## Preparation (do this before recording)

### 1. Make sure everything is set up

```bash
# From the project root
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe tools\fetch_models.py
```

### 2. Have a clean chain ready

```bash
.venv\Scripts\python.exe tools\tamper_demo.py --restore
```

This removes any existing ledger so the next run creates a fresh chain.

### 3. Make sure the Obama test image is present

```bash
.venv\Scripts\python.exe -c "
import urllib.request, sys
from pathlib import Path
url = 'https://upload.wikimedia.org/wikipedia/commons/8/8d/President_Barack_Obama.jpg'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, timeout=60) as resp:
    Path('data/probes/obama-probe.jpg').write_bytes(resp.read())
print('Obama photo ready')
"
```

### 4. Start your screen recorder

Open your screen recording tool (OBS, Windows Game Bar, Loom, etc.) and start recording.

---

## Part 1: Run the pipeline end-to-end (terminal)

This is the main demonstration. Open a terminal and run:

```bash
.venv\Scripts\python.exe tools\demo_pipeline.py --probe data\probes\obama-probe.jpg --subject-name "Barack Obama"
```

The script will print a step-by-step transcript. Wait for it to complete. What to highlight in the recording:

### Step 1 — Face detection & embedding
Show that the face is detected and encoded:
```
Face detected: 1 face(s)
Largest face box: [187, 44, 125, 174]
Detection score: 0.9466
Embedding: 128-d vector, hash 2e25c6ff2a25...
```

### Step 2 — Face identification
Show that the subject is enrolled and re-checked:
```
Enrolled: Barack Obama (id=barack-obama-XXXXXX)
Re-checked similarity: 1.0000
```

### Step 3 — Identify + web search (THE KEY STEP)
This is where the reverse image search happens. The recording should show:

```
Block # 2
Web search results returned: 10
```

Then it lists the 10 matching URLs found on the web. These are **real matching posts** found by Yandex Images, not hardcoded:

```
[1] web: https://upload.wikimedia.org/wikipedia/commons/8/8d/President_Barack_Obama.jpg
[2] web: https://1000logos.net/wp-content/uploads/2017/05/Barack-Obama-US-president.jpg
[3] web: https://bok365.no/wp-content/uploads/2018/06/President_Barack_Obama-e1529275409228.jpg
[4] web: http://www.birminghamtimes.com/task/wp-content/uploads/2015/12/President_Barack_Obama-e1450454524443.jpg
[5] web: https://npr.brightspotcdn.com/dims4/default/9e69960/...
[6] web: https://i.imgur.com/c9d3Eb7.jpeg?fb
[7] web: https://i.pinimg.com/originals/76/46/db/7646db273116354ecf3195fe92d70105.webp?nii=t
[8] web: https://yt3.googleusercontent.com/... (YouTube thumbnail)
...
```

Scroll through or let the full list print so the viewer can see these are actual web/social media URLs.

### Step 4 — On-chain record
Show that the face verification and the web search results are recorded on the blockchain:

```
Transaction type: FACE_VERIFICATION
Result: VERIFIED
Subject ID: barack-obama-XXXXXX
Subject name: Barack Obama
Similarity: 1.0
Probe image hash: 744dd848fbb0584229169e01...
Web search count (on-chain): 10
```

The key point: **Web search count: 10** — meaning the 10 discovered URLs were uploaded to the blockchain as part of the transaction.

### Step 5 — Chain verification
Show that the chain is valid and tamper-evident:

```
Blocks checked: 2
Chain valid: True
All hashes and links verified — the record is tamper-evident.
```

This proves that the blockchain verification step works.

---

## Part 2: Show the on-chain record in detail (Flask UI)

After the pipeline runs, you can show the on-chain data in a more visual way using the Flask web UI.

### Start the Flask server

```bash
.venv\Scripts\python.exe app.py
```

Then open `http://127.0.0.1:5000` in your browser.

### Show the Ledger page

Go to `http://127.0.0.1:5000/ledger`.

This page shows every block in the chain. Scroll to **Block #2** (the FACE_VERIFICATION block). You should see:

- **Block #2** with:
  - Hash: `00009e728b9ebeeb...` (starts with 4 zeros = PoW satisfied)
  - Previous hash: links to Block #1
  - Nonce: 26590 (showing the mining effort)
  - Transaction type: `FACE_VERIFICATION`
  - Result: `VERIFIED`
  - Subject: Barack Obama
  - Similarity: 1.0
  - **Web search count: 10**
  - **Web search results**: a list of the 10 URLs found on the web

This is the visual proof that the discovered social media posts are recorded on the blockchain.

### Show the Verify page

Go to `http://127.0.0.1:5000/verify`.

This page runs a full chain validation and shows:

```
Chain is valid — 2 block(s) re-hashed; links and proof-of-work confirmed.
```

This is the verification step — re-hashing all blocks, checking proof-of-work difficulty, and verifying every block links to its predecessor.

### Show the API (optional)

In a separate terminal tab or browser, you can show:

```bash
curl http://127.0.0.1:5000/api/chain/validate
```

Response:
```json
{
    "ok": true,
    "valid": true,
    "blocks_checked": 2,
    "errors": []
}
```

Or show the full chain:

```bash
curl http://127.0.0.1:5000/api/chain
```

This returns the entire chain as JSON, including the `web_search_results` array in Block #2.

---

## Part 3: Tamper detection demo (proves tamper-evidence)

This is the most important part for proving the blockchain actually prevents tampering.

### 1. Run the tamper demo

```bash
.venv\Scripts\python.exe tools\tamper_demo.py
```

Output:
```
Block #2: similarity 1.0 -> 0.9999
Ledger tampered. Open the Verify page or GET /api/chain/validate to see the chain fail.
```

What happened: the script modified Block #2's recorded similarity from `1.0` to `0.9999` — a tiny change, but it broke the chain.

### 2. Re-verify the chain (shows INVALID)

Either via the Flask UI or the API:

**Via API:**
```bash
curl http://127.0.0.1:5000/api/chain/validate
```

Response:
```json
{
    "ok": true,
    "valid": false,
    "blocks_checked": 2,
    "errors": [
        {
            "index": 2,
            "reason": "stored hash does not match block content"
        }
    ]
}
```

**Via Flask UI** — go to `http://127.0.0.1:5000/verify`:
```
Chain is INVALID — 1 problem(s) detected.
- Block #2: stored hash does not match block content
```

This proves the blockchain is tamper-evident: any change to the recorded data (the similarity, the web search results, anything in the transaction) changes the block's hash and breaks the chain from that point onward.

### 3. (Optional) Restore the chain

```bash
.venv\Scripts\python.exe tools\tamper_demo.py --restore
```

This removes the ledger so a fresh chain is created on the next run. This is useful if you want to re-record the pipeline cleanly.

---

## Summary of what the recording shows

| Step | What to show | Where |
|------|-------------|-------|
| 1. Face scan | Terminal output: face detected, score 0.9466, 128-d embedding | Terminal running `demo_pipeline.py` |
| 2. Web search | "Web search results returned: 10" + list of real URLs (pinterest, imgur, npr, etc.) | Terminal |
| 3. Blockchain upload | "Web search count (on-chain): 10" + Block #2 details | Terminal |
| 4. On-chain record | Block #2 in ledger.html showing 10 web_search_results URLs | Browser: `http://127.0.0.1:5000/ledger` |
| 5. Verification | "Chain is valid" on verify page, or API returns `{"valid": true}` | Browser or terminal |
| 6. Tamper evidence | Tamper demo → re-verify → chain shows INVALID with error | Terminal + browser/API |

---

## Recording checklist

Before submitting, verify your recording shows:

- [ ] Face image loaded and face detected (Step 1 output visible)
- [ ] Web/social media search runs (Step 3 output with "Web search results returned: 10")
- [ ] At least some of the 10 result URLs visible in the terminal output
- [ ] Blockchain upload confirmed ("Web search count (on-chain): 10")
- [ ] Chain verification passes ("Chain valid: True")
- [ ] Either the Flask Ledger page showing Block #2 with 10 web_search_results, OR the API response showing valid:true
- [ ] (Recommended) Tamper detection demo: tampering makes chain INVALID

---

## Where to upload the recording

Upload to any of:
- YouTube (unlisted)
- Google Drive
- Loom
- Any video sharing service

You'll need a **working link** to include in the submission form.

---

## Submission form

Fill out: https://forms.gle/oZbQGuwiNeHVcHWo8

You'll need:
1. **GitHub repo link** — push the code to a public GitHub repo first
2. **Screen recording link** — the URL where you uploaded the video
3. Any other fields the form asks for

No resubmissions allowed — submit only when your build is final.
