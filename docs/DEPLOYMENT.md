# Deployment Guide — Live Face Verification App

Deploy the Flask app so judges (and anyone) can try it live.

---

## Overview

The app has two parts that need to work together in production:
1. **Flask app** — the web UI and API
2. **Headless Chrome + Selenium** — for the reverse image search

The challenge: most PaaS platforms (Heroku, Render, Railway) don't come with Chrome pre-installed. You need to either:
- Use a Docker container with Chrome
- Use a platform that supports custom Dockerfiles
- Use a headless browser service (SaaS)

**Recommended**: Docker + a platform that supports it (Render, Railway, or a VPS).

---

## Option A: Docker + Render/Railway (easiest PaaS)

### Dockerfile

A working `Dockerfile` is committed at the repo root. It installs Google Chrome
(direct `.deb`, no deprecated `apt-key`), downloads the ONNX models at build
time, and serves the app with gunicorn:

```dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=5000 \
    FLASK_ENV=production

# Google Chrome (stable) + runtime libs for headless Selenium.
RUN apt-get update && apt-get install -y --no-install-recommends \
        wget ca-certificates fonts-liberation libasound2 libatk-bridge2.0-0 \
        libatk1.0-0 libcups2 libdbus-1-3 libdrm2 libgbm1 libgtk-3-0 libnspr4 \
        libnss3 libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 libxss1 \
        libxtst6 xdg-utils \
    && wget -q -O /tmp/chrome.deb \
        https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get install -y --no-install-recommends /tmp/chrome.deb \
    && rm -f /tmp/chrome.deb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir eth-hash[pycryptodome] gunicorn

COPY . .
RUN python tools/fetch_models.py || true
RUN mkdir -p data/faces data/probes data/webcache

EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "app:app"]
```

Selenium 4.6+ downloads the matching chromedriver automatically (Selenium
Manager), so no manual chromedriver install is needed. The `--timeout 120`
matters because the reverse image search can take 30-60 seconds.

### Build and run locally (test before deploying)

```bash
docker build -t face-verify .
docker run -p 5000:5000 -e FLASK_ENV=production face-verify
```

Then open `http://localhost:5000`.

### Deploy to Render (free tier works)

The repo includes a **Render Blueprint** (`render.yaml`) and a **seed script**
(`tools/seed_demo.py`) so a fresh deploy is demo-ready in one click:

1. Push your code to GitHub (the `main` branch)
2. Go to https://dashboard.render.com → **New +** → **Blueprint**
3. Select this repository — Render reads `render.yaml` automatically
4. Add these environment variables when prompted (all optional):
   - `WEB3_RPC_URL`, `CONTRACT_ADDRESS`, `PRIVATE_KEY` — enables live on-chain
     writes (use a **testnet-only** key; POL for gas comes from the faucet)
   - Leave them unset for local-ledger-only operation (still fully demonstrable)
5. Click **Apply** — the first build takes ~8–12 min (Chrome + ONNX models)
6. Render assigns a URL like `https://face-chain-verify.onrender.com`

**Free-tier facts (verified):**
- 512 MB RAM — the Dockerfile is tuned for this (gunicorn with 1 worker;
  Chrome + ONNX fit but leave little headroom)
- **Ephemeral disk** — the ledger/faces reset on every restart or sleep.
  The seed script runs at container start (`SEED_DEMO=1`) and re-registers the
  bundled Obama probe + a demo block, so `/demo` always works
- **Spins down after ~15 min idle** — the next request takes ~50s to wake
- Free instances do **not** have outbound-port restrictions, so Yandex works

**One caveat for judges testing live:** headless-Chrome reverse search may be
bot-flagged from datacenter IPs more often than from your home machine. If the
web-search step returns 0 results on the live URL, the local ledger + on-chain
record still work, and the recording (made locally) shows the search working.

### Deploy to Railway

1. Go to https://railway.app
2. New Project → Deploy from GitHub repo
3. Railway auto-detects the Dockerfile
4. Add environment variables (same list as Render)
5. Set `SEED_DEMO=1` so the demo probe is registered on boot

### Deploy to a VPS (most reliable)

Use a cheap VPS (DigitalOcean $4-6/mo, Hetzner, etc.):

```bash
# On the VPS:
apt update && apt install -y python3 python3-pip python3-venv wget gnupg2
wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list
apt update && apt install -y google-chrome-stable

# Clone your repo
git clone https://github.com/alokmuskan/Face-Identification-Blockchain-Verification.git
cd Face-Identification-Blockchain-Verification

# Set up venv
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install gunicorn

# Download models
.venv/bin/python tools/fetch_models.py

# Create data dirs
mkdir -p data/faces data/probes

# Run with gunicorn
.venv/bin/gunicorn --bind 0.0.0.0:5000 --workers 2 app:app
```

Then put nginx in front for HTTPS:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Use Let's Encrypt for free HTTPS: `certbot --nginx -d your-domain.com`

---

## Option B: Playwright as a Service (no Chrome management)

If managing Chrome is too much, use a headless browser as a service:

- **Browserless** (https://browserless.io) — managed Chrome as a service
- **Scrapingbee** — headless browser API
- **ZenRows** — similar

You'd modify `websearch/search.py` to call the service's API instead of driving Chrome yourself.

**Pros**: no Chrome to manage, scales easily
**Cons**: costs money, adds another dependency

---

## Environment Variables

Create `.env` (never commit to git):

```bash
# Flask
FLASK_ENV=production
HOST=0.0.0.0
PORT=5000

# Blockchain (if using testnet)
WEB3_RPC_URL=https://polygon-amoy.g.alchemy.com/v2/YOUR_KEY
PRIVATE_KEY=0x...           # testnet only!
CONTRACT_ADDRESS=0x...      # set after deployment

# Web search
CHROMIUM_PATH=/usr/bin/google-chrome   # if not in PATH
WEB_SEARCH_TIMEOUT=45

# App secrets (generate your own)
SECRET_KEY=change-this-to-a-random-string
```

Add `.env` to `.gitignore`.

---

## `.gitignore` Additions

Make sure `.gitignore` includes:

```
# Environment
.env
.env.local

# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/

# Runtime data
data/
models/

# IDE
.vscode/
.repowise/
.claude/

# OS
.DS_Store
Thumbs.db
```

---

## Health Check Endpoint

Add a health check for the deployment platform:

In `app.py`, add:

```python
@app.route('/health')
def health():
    from faceid.engine import get_engine
    try:
        engine = get_engine()
        models_ok = engine.models_available()
    except Exception:
        models_ok = False
    return {
        'status': 'ok' if models_ok else 'degraded',
        'models_available': models_ok,
    }, 200 if models_ok else 503
```

Platforms like Render/Railway can ping `/health` to check if the app is alive.

---

## Production Considerations

### 1. Don't use Flask dev server in production

The Flask dev server (`app.run()`) is single-threaded and meant for development. Use gunicorn:

```bash
pip install gunicorn
gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 120 app:app
```

The `--timeout 120` is important because the web search can take 30-60 seconds.

### 2. HTTPS

Always use HTTPS in production. Let's Encrypt is free.

### 3. Data persistence

The local ledger (`data/ledger.json`) is stored on the server's filesystem. If the server restarts, the data persists (as long as the volume isn't wiped). On PaaS platforms, check if the filesystem is persistent or ephemeral.

For a more robust setup, store the ledger in a database (SQLite is fine for this scale, or PostgreSQL).

### 4. Web search rate limits

Yandex may rate-limit or block automated searches from a server IP. If that happens:
- Add delays between searches
- Rotate user agents
- Use a proxy
- Fall back to a different search engine

### 4. Private keys

**Never commit private keys to git.** Use environment variables. If using a testnet key, it's low-risk, but still don't commit it.

### 5. Scaling

The current app is single-process. For multiple concurrent users:
- Use gunicorn with multiple workers
- Make the blockchain ledger thread-safe (already done with locks)
- Consider a proper database for the face store (currently JSON file)

---

## What to Show Judges for Deployment

If you deploy:

1. **Live URL**: `https://your-app.railway.app` or `https://your-domain.com`
2. **Screenshot** of the live app
3. **Smart contract address** on Polygonscan (if deployed)
4. **Short demo video** showing the live app working

Even a 24-hour live demo link is impressive. Judges can click and try it themselves.

---

## Minimum Viable Deployment (for shortlist)

If time is tight, do the minimum:

1. **Dockerfile** — so it *can* be deployed
2. **Deploy to Railway** — get a live URL (even if web search is slow/fragile)
3. **Record a video** of the live app working
4. **Add the live URL to the README**

The video + live URL together show the project is real and deployable.

---

## Checklist

- [ ] Dockerfile works locally (`docker build` + `docker run`)
- [ ] Deployed to a platform (Render / Railway / VPS)
- [ ] Live URL is accessible
- [ ] HTTPS enabled (if custom domain)
- [ ] Health check endpoint works
- [ ] Web search works on the deployed server (test with Obama photo)
- [ ] Blockchain recording works (if using testnet)
- [ ] README updated with live URL and setup instructions
- [ ] Environment variables are set (not hardcoded)
- [ ] `.env` is in `.gitignore`
