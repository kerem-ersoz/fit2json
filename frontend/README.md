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

To point a build at an API on another HTTPS origin, set the complete API base URL:

```bash
VITE_API_BASE_URL=https://computer.example.ts.net/api npm run build
```

`VITE_API_BASE_URL` is embedded in the public JavaScript bundle. It must contain only a
URL, never a token or other secret.

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

## GitHub Pages frontend + private phone access

The production SPA is served from `https://www.ker.ooo/fitsift/` while the API, workout
files, and analysis tools remain on this computer. The phone must be signed into the same
Tailscale network.

### 1. Connect the local API to the tailnet

Install the Tailscale macOS app, sign in, and approve its VPN configuration. Start the
host-mode web service so FastAPI remains bound to loopback, then configure a persistent
private HTTPS proxy:

```bash
./scripts/fitsift web up
TAILSCALE=/Applications/Tailscale.app/Contents/MacOS/Tailscale
"$TAILSCALE" serve --bg 8000
"$TAILSCALE" serve status
```

The status output reports a URL such as `https://computer.example.ts.net`. Verify it from
another device on the tailnet:

```bash
curl https://computer.example.ts.net/api/health
```

Use Tailscale **Serve**, not Funnel. Funnel would make the unauthenticated FastAPI service
public. Install Tailscale on the phone and sign into the same tailnet.

### 2. Build for the `/fitsift/` path

The production build needs both the GitHub Pages base path and the private API endpoint:

```bash
VITE_BASE_PATH=/fitsift/ \
VITE_API_BASE_URL=https://computer.example.ts.net/api \
npm run build
```

This repository owns production deployment through
`.github/workflows/github-pages.yml`. On relevant pushes to `main` (or manual dispatch),
the workflow builds the SPA and deploys `frontend/dist` as an ephemeral Pages artifact.
Built files are not committed. The active tailnet API is configured through the
repository Actions variable `VITE_API_BASE_URL`.

The repository slug `fitsift` makes GitHub Pages mount this project site automatically
at `/fitsift/` beneath the account-level `www.ker.ooo` custom domain. The workflow copies
`index.html` to `404.html`, matching the Brolonist deployment pattern so BrowserRouter
can recover direct client-route navigation.

### 3. Restrict the API origin

Put the exact Pages origin in the repo-root `.env` used by the local backend:

```dotenv
FITSIFT_CORS_ORIGINS=https://www.ker.ooo
```

Restart the local web process after changing it:

```bash
./scripts/fitsift web down
./scripts/fitsift web up
```

The static shell is public because GitHub Pages has no built-in private-site
authentication. The API and personal data remain tailnet-only: devices outside the
tailnet cannot resolve a working connection to the Tailscale Serve endpoint. The shell
remains available when this computer is offline, but API-backed screens cannot load
until the computer and Tailscale are online.

## Scripts

- `npm run dev` – Vite dev server
- `npm run build` – type-check + production build
- `npm run typecheck` – TypeScript only
