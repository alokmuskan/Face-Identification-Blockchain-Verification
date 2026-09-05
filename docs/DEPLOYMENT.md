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

Create `Dockerfile`:

```dockerfile
FROM python:3.13-slim

# ── System dependencies ─────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg2 \
    ca-certificates \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub \
       | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" \
       >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# ── Python deps ─────────────────────────────────────────────────────────
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Browser ─────────────────────────────────────────────────────────────
# Try to install Playwright's bundled Chromium as fallback
RUN pip install playwright 2>/dev/null || true
RUN python -m playwright install chromium 2>/dev/null || true

# ── App code ────────────────────────────────────────────────────────────
COPY . .

# Download ONNX models (cached layer — won't re-download if models/ exists)
RUN python tools/fetch_models.py || true

# ── Runtime config ──────────────────────────────────────────────────────
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV HOST=0.0.0.0
ENV PORT=5000

# Create data directories
RUN mkdir -p data/faces data/probes

EXPOSE 5000

# Use gunicorn for production (install if not in requirements)
# RUN pip install gunicorn
# CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]

# For simplicity, use Flask dev server (only for demo purposes)
CMD [".venv/bin/python", "app.py"]
```

**Note**: For a production deployment, use `gunicorn` instead of the Flask dev server. Add `gunicorn` to `requirements.txt`.

### Build and run locally (test before deploying)

```bash
docker build -t face-verify .
docker run -p 5000:5000 -e FLASK_ENV=production face-verify
```

Then open `http://localhost:5000`.

### Deploy to Render

1. Push your code to GitHub
2. Go to https://render.com
3. New Web Service → connect your repo
4. Build command: `docker build -t face-verify .` (or use Dockerfile)
5. Start command: `docker run -p 5000:5000 face-verify`
6. Add environment variables in Render dashboard:
   - `FLASK_ENV=production`
   - Any blockchain env vars if using smart contract

**Problem**: Render's free tier may not have enough resources for Chrome + Selenium + ONNX models. The app might be slow or fail.

### Deploy to Railway

1. Go to https://railway.app
2. New Project → Deploy from GitHub repo
3. Railway auto-detects Dockerfiles
4. Add environment variables
5. Railway has more compute resources than Render free tier — better chance of Chrome working

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
