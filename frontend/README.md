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

## Azure frontend + private phone access

This keeps the Vite SPA in Azure while the API, workout files, and analysis tools remain
on this computer. The phone must be signed into the same Tailscale network.

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

### 2. Create the Azure Static Web App

Create an empty Free-tier Static Web App. The names below are examples; the app name must
be globally unique.

```bash
az group create --name fitsift-personal --location westus2
az staticwebapp create \
  --name YOUR_UNIQUE_FITSIFT_NAME \
  --resource-group fitsift-personal \
  --location westus2 \
  --sku Free
```

In GitHub repository settings, configure:

- Actions variable `VITE_API_BASE_URL`:
  `https://computer.example.ts.net/api`
- Actions secret `AZURE_STATIC_WEB_APPS_API_TOKEN`: the deployment token from the Azure
  Static Web App's **Manage deployment token** page

The `Deploy FitSift frontend` workflow builds `frontend/dist` and deploys only on `main`
or manual dispatch. Pull-request preview sites are intentionally disabled so the API can
use one exact CORS origin.

### 3. Restrict both origins

After Azure assigns the hostname, copy the **Default hostname** from its overview page
and put that exact origin in the repo-root `.env` used by the local backend. Azure
hostnames are generated and generally do not match the resource name.

```dotenv
FITSIFT_CORS_ORIGINS=https://YOUR_GENERATED_HOSTNAME.azurestaticapps.net
```

Restart the local web process after changing it:

```bash
./scripts/fitsift web down
./scripts/fitsift web up
```

In the Static Web App's role management page, invite your GitHub account with the custom
role `fitsift_user`. `staticwebapp.config.json` redirects sign-in to GitHub and rejects
users without that role.

The Azure-hosted shell remains available when this computer is offline, but API-backed
screens cannot load until the computer and Tailscale are online.

## Scripts

- `npm run dev` – Vite dev server
- `npm run build` – type-check + production build
- `npm run typecheck` – TypeScript only
