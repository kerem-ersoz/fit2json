# ── Build stage ───────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --no-cache-dir --prefix=/install .

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/kerem-ersoz/fit2json"
LABEL org.opencontainers.image.description="Pull workouts from Garmin/Strava and store them as lossless JSON"
LABEL org.opencontainers.image.licenses="MIT"

COPY --from=builder /install /usr/local

WORKDIR /data

ENTRYPOINT ["fit2json"]
CMD ["--help"]
