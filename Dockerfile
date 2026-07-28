# ── Frontend build stage ──────────────────────────────────────────────────────
# Built on the *build* platform (not the target arch) — the output is static assets,
# so there is no need to run npm/Vite under slow QEMU emulation for arm64.
FROM --platform=$BUILDPLATFORM node:20-slim AS frontend

WORKDIR /web

# Install deps first (cached until the lockfile changes), then build the SPA.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build          # → /web/dist

# ── Python build stage ────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

COPY pyproject.toml README.md ./
COPY src/ src/

# `.[web]` pulls in FastAPI + uvicorn + python-multipart so the image can serve the UI.
RUN pip install --no-cache-dir --prefix=/install ".[web]"

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/kerem-ersoz/fit2json"
LABEL org.opencontainers.image.description="Pull workouts from Garmin/Strava, store them as lossless JSON, and serve the FitSift web UI"
LABEL org.opencontainers.image.licenses="MIT"

COPY --from=builder /install /usr/local
COPY --from=frontend /web/dist /opt/fitsift/frontend/dist

# Data (library JSON, memory corpus, athlete profile) is expected under /data — mount
# your ~/.fit2json here. These defaults line up with the fit2json CLI's own layout.
ENV FITSIFT_FRONTEND_DIST=/opt/fitsift/frontend/dist \
    FITSIFT_LIBRARY=/data/library/json \
    FITSIFT_MEMORY=/data/memory \
    FITSIFT_PROFILE=/data/profile.json

WORKDIR /data
EXPOSE 8000

# Keep `fit2json` as the entrypoint so every subcommand (convert/fetch/analyze/serve)
# is still available; default to serving the web UI on all interfaces.
ENTRYPOINT ["fit2json"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000"]
