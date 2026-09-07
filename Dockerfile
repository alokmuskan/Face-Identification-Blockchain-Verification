# Face Identification & Blockchain Verification — container image.
#
# The web search drives a headless Chrome via Selenium, so Chrome must be
# installed in the image. Selenium 4.6+ auto-downloads the matching
# chromedriver at runtime via Selenium Manager, so no manual chromedriver
# install is needed here.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=5000 \
    FLASK_ENV=production

# ── System dependencies + Google Chrome (stable) ─────────────────────────
# The .deb is fetched directly, avoiding the deprecated apt-key keyring flow.
RUN apt-get update && apt-get install -y --no-install-recommends \
        wget \
        ca-certificates \
        fonts-liberation \
        libasound2 \
        libatk-bridge2.0-0 \
        libatk1.0-0 \
        libcups2 \
        libdbus-1-3 \
        libdrm2 \
        libgbm1 \
        libgtk-3-0 \
        libnspr4 \
        libnss3 \
        libx11-xcb1 \
        libxcomposite1 \
        libxdamage1 \
        libxrandr2 \
        libxss1 \
        libxtst6 \
        xdg-utils \
    && wget -q -O /tmp/chrome.deb \
        https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get install -y --no-install-recommends /tmp/chrome.deb \
    && rm -f /tmp/chrome.deb \
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies ───────────────────────────────────────────────────
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    # Optional on-chain bridge deps: Keccak backend + gunicorn for serving.
    && pip install --no-cache-dir eth-hash[pycryptodome] gunicorn

# ── Application code ──────────────────────────────────────────────────────
COPY . .

# Download ONNX models (YuNet + SFace). Failure is non-fatal: the app still
# boots and reports /health as degraded until the models are present.
RUN python tools/fetch_models.py || true

# Runtime libs for OpenCV (imdecode/imencode/DNN headless) and for headless
# Chrome, where some Mesa/GTK components are still pulled at runtime by
# Chrome's sandbox and by libGL-linked libraries.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 libgthread-2.0-0 libgbm1 libasound2 libatk1.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Runtime data (git-ignored in the repo, but needed by the app).
RUN mkdir -p data/faces data/probes data/webcache

# Seed a fresh data dir on boot (registers the bundled demo subject and
# mines a demo block) so an ephemeral deploy is demo-ready immediately.
# Set SEED_DEMO=0 to disable.
ENV SEED_DEMO=1

EXPOSE 5000

# gunicorn with a long timeout because the reverse image search can take
# 30-60 seconds per request. Single worker by default: the free tiers of
# PaaS platforms (Render ~512MB) are memory-constrained and each OpenCV
# worker loads its own model copies. Override via GUNICORN_WORKERS.
# The bind port honors $PORT, which Render injects at runtime.
ENV GUNICORN_WORKERS=1
CMD ["sh", "-c", "if [ \"$SEED_DEMO\" = \"1\" ]; then python tools/seed_demo.py || true; fi; exec gunicorn --bind 0.0.0.0:${PORT:-5000} --workers ${GUNICORN_WORKERS} --timeout 120 --threads 4 app:app"]