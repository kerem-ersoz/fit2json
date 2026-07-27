# FitSift frontend

A mobile-first React + Vite SPA for the FitSift web UI. It talks to the FastAPI
backend that ships with the `fit2json` package (`fit2json serve`).

## Prerequisites

- Node 18+ and npm
- The backend installed with web extras: `pip install -e '.[web]'` (from the repo root)

## Develop (two processes, hot reload)

```bash
# 1) Backend API on :8000 — point --library at a folder of workout JSON
fit2json serve --dev --library ~/.fit2json/library/json
#   (or: uvicorn fit2json.web.app:app --reload)

# 2) Frontend dev server on :5173 (proxies /api → :8000)
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

### Test it on your phone

Both servers already bind all interfaces. Start the backend with `--host 0.0.0.0`,
then open `http://<your-laptop-ip>:5173` from a phone on the same Wi-Fi.

## One-command run (built SPA served by the API)

```bash
cd frontend && npm run build      # outputs frontend/dist
fit2json serve --library ~/.fit2json/library/json
# → UI + API on http://localhost:8000
```

## Serving under a path later (e.g. /fitsift)

Build with a base path and set the backend base path to match:

```bash
VITE_BASE_PATH=/fitsift/ npm run build
FITSIFT_BASE_PATH=/fitsift fit2json serve
```

## Scripts

- `npm run dev` – Vite dev server
- `npm run build` – type-check + production build
- `npm run typecheck` – TypeScript only
