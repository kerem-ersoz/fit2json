# fit2json

Pull your workouts from Garmin Connect or Strava, store them as **faithful, lossless JSON**, and **analyze them with an LLM** — GitHub Copilot CLI or a local model (Ollama / LM Studio) — using your own prompt. Every analysis is saved to a **training-memory corpus** so the model can revisit past workouts and reason about your progress over time.

## What It Does

**fit2json** is a command-line harness with three stages:

1. **Fetch / convert** — decode `.fit` files (Garmin, Wahoo, etc.) losslessly, or pull recent activities straight from Garmin Connect / Strava.
2. **Store** — write a **complete, human-readable** JSON dump: every FIT message and every field, at native resolution. Nothing is downsampled or dropped.
3. **Analyze** — send a workout (plus your custom prompt) to the **GitHub Copilot CLI** or a **local LLM**, and keep the result in a searchable memory corpus for trend analysis.

> **What changed in 0.2:** older versions produced a compact, lossy "LLM-ready" JSON and called the OpenAI/GitHub Models API directly. Capable models no longer need pre-digested data, so fit2json now keeps a **lossless** archive and **orchestrates** analysis through Copilot / local models instead. See [Migrating from 0.1](#migrating-from-01).

---

## Installation

### Option 1: Docker (no Python required)

```bash
docker pull ghcr.io/kerem-ersoz/fit2json:latest
docker run --rm ghcr.io/kerem-ersoz/fit2json --version
```

> The Docker image covers `convert` and `fetch`. The `analyze` command's `copilot` backend needs the Copilot CLI on the host, so run analysis outside the container (or point `--base-url` at a reachable local LLM). See [Docker usage](#docker-usage).

### Option 2: Install from source

Requires **Python 3.9+**.

```bash
git clone https://github.com/kerem-ersoz/fit2json.git
cd fit2json
python3 -m venv .venv
source .venv/bin/activate
pip install -e .            # add ".[dev]" for tests
fit2json --version
```

### For the `analyze` command

Pick whichever backend you like — no API key required for any of these:

- **GitHub Copilot CLI** — install the [`copilot` CLI](https://github.com/github/copilot-cli) and sign in. Auto-detected if on your `PATH`.
- **Ollama** — [ollama.com](https://ollama.com), then `ollama pull llama3.1`.
- **LM Studio** — [lmstudio.ai](https://lmstudio.ai); start its local server and load a model.

---

## Quick Start

```bash
# Convert a single .fit file to lossless JSON (stdout)
fit2json convert my_run.fit -o run.json

# Convert a folder of .fit files → one JSON file per activity, into ./workouts/
fit2json convert ~/Downloads/garmin-export/ -o workouts/

# Pull the last 7 days from Garmin → ./workouts/
fit2json fetch garmin --days 7 -o workouts/

# Analyze one workout with your prompt (auto-detects Copilot CLI, else Ollama)
fit2json analyze run.json -p "How was my pacing strategy?"

# Analyze against a local model and build up training memory over time
fit2json analyze workouts/ -p "How is my fitness trending?" --backend ollama
```

---

## Commands

### `fit2json convert`

Decode local `.fit` file(s) into lossless JSON.

```bash
fit2json convert activity.fit                     # → stdout
fit2json convert activity.fit -o out.json         # → single combined file
fit2json convert ./export/ -o workouts/           # → one file per activity
fit2json convert ./export/ -o workouts/ --gzip    # → .json.gz (≈25× smaller)
```

| Option | Description |
|--------|-------------|
| `-o, --output PATH` | A `.json`/`.json.gz` file (combined) or a **directory** (one file per activity). Default: stdout. |
| `--gzip` | Gzip the output. Recommended for archives — a long activity compresses to less than the original `.fit`. |
| `--indent INT` | JSON indentation (default: 2). |
| `--compact` | No indentation — smallest plain-text files. |

### `fit2json fetch garmin`

Download and decode recent Garmin Connect activities.

```bash
fit2json fetch garmin --days 30 -o workouts/
fit2json fetch garmin --days 7 --raw-dir ./raw-fits/ -o workouts/
```

| Option | Description |
|--------|-------------|
| `--days INT` | Days of history to fetch (default: 30). |
| `-o, --output PATH` | Output directory (default: `./workouts/`) or a `.json` file. |
| `--gzip` | Gzip the output. |
| `--email` / `--password` | Garmin credentials (or `GARMIN_EMAIL` / `GARMIN_PASSWORD`). |
| `--raw-dir PATH` | Keep the raw `.fit` files too. |

### `fit2json fetch strava`

Download and decode recent Strava activities.

> **Lower fidelity:** Strava's API returns processed time-series *streams*, not raw `.fit` files, so this path **cannot be truly lossless**. For full fidelity, use Strava's [bulk export](https://support.strava.com/hc/en-us/articles/216918437) and `fit2json convert` on the `.fit` files.

```bash
fit2json fetch strava --days 30 -o workouts/
```

Options mirror `fetch garmin`, with `--client-id` / `--client-secret` / `--refresh-token` (or the matching `STRAVA_*` env vars).

### `fit2json analyze`

Send a workout (and your prompt) to an LLM backend, using and updating training memory.

```bash
# Auto-detect backend (Copilot CLI if installed, else Ollama)
fit2json analyze run.json -p "Write a race report"

# Explicit backends
fit2json analyze run.json -p "Analyze my HR zones" --backend ollama --model llama3.1
fit2json analyze run.json -p "Any red flags?"       --backend lmstudio
fit2json analyze run.json -p "Coach me"             --backend copilot --model auto

# Any OpenAI-compatible endpoint
fit2json analyze run.json -p "Summarize" --base-url http://my-server:8080/v1

# A whole directory of workouts, or piped from convert
fit2json analyze workouts/ -p "Summarize my training week"
fit2json convert run.fit | fit2json analyze -p "Race report"
```

| Option | Description |
|--------|-------------|
| `SOURCE` | Workout JSON file or directory. Omit to read JSON from stdin. |
| `-p, --prompt TEXT` | **(Required)** Your analysis question. |
| `--backend` | `copilot`, `ollama`, or `lmstudio`. Auto-detected if omitted. |
| `--base-url TEXT` | Any OpenAI-compatible endpoint (overrides `--backend`). |
| `--model TEXT` | Model name (backend-specific; local backends auto-pick if omitted). |
| `--api-key TEXT` | Only for a custom `--base-url` that requires auth. |
| `--no-stream` | Disable streaming output. |
| `--max-chars INT` | Max workout JSON chars inlined for local models (default: 200K). Large activities are auto-thinned to fit. |
| `--memory PATH` | Memory corpus location (default: `./fit2json-memory/`). |
| `--no-memory` | Don't read or write memory for this run. |
| `--recall {auto,same-sport,all,none}` | Which past analyses to recall as context (default: `auto`). |
| `--recall-days INT` | Only recall memories within N days. |
| `--recall-limit INT` | Max memories to recall (default: 8). |

**How backends handle data:**

- **`copilot`** — the workout file(s) and the memory directory are passed **by path**; Copilot reads them with its own file tools, so even huge lossless files fit fine.
- **`ollama` / `lmstudio` / `--base-url`** — the workout JSON is inlined and automatically **thinned** to fit `--max-chars`; recalled memories are added as a compact digest.

### `fit2json memory`

Inspect the training-memory corpus.

```bash
fit2json memory path                       # print the corpus location
fit2json memory list                       # list all analyses, newest first
fit2json memory list --sport running --days 30
fit2json memory show <entry_id>            # print one saved analysis
```

---

## Training memory

Every `analyze` run saves its result to a filesystem corpus (default `./fit2json-memory/`):

```
fit2json-memory/
├── running/
│   └── 2024-03-10T0730-00Z_2024-03-10_run_3195e283.md
├── cycling/
│   └── 2024-03-12T1800-00Z_2024-03-12_ride_982710f5.md
└── index.jsonl
```

- Each analysis is a Markdown file with a front-matter block (date, sport, key metrics, prompt, model) followed by the AI's write-up — readable on its own or by any LLM.
- `index.jsonl` is a one-line-per-analysis index for fast filtering by sport and date.
- Files are partitioned by sport and date-prefixed, so you can revisit **memories from different activity types and time ranges**.
- On each run, fit2json **recalls** the relevant past analyses (see `--recall*`) and feeds them back as context so the model can comment on progress and trends. With the `copilot` backend, Copilot browses the corpus directly with its file tools.

---

## Lossless JSON schema

The output is a faithful decode of the `.fit` file — every message type, every field, at native resolution:

```json
{
  "metadata": { "generated_at": "…", "tool_version": "0.2.0", "source": "local", "schema": "lossless-fit" },
  "activities": [
    {
      "source_file": "2024-03-10_run.fit",
      "sport": "running",
      "start_time": "2024-03-10T07:30:00+00:00",
      "message_counts": { "record": 2809, "lap": 4, "session": 1, "event": 7 },
      "field_units": { "distance": "m", "speed": "m/s", "heart_rate": "bpm" },
      "messages": {
        "session": [ { "sport": "running", "total_distance": 10234.0, "avg_heart_rate": 152, "…": "…" } ],
        "lap": [ { "total_distance": 1001.0, "avg_heart_rate": 145, "…": "…" } ],
        "record": [
          { "timestamp": "2024-03-10T07:30:00+00:00", "heart_rate": 120, "cadence": 84, "speed": 2.9, "distance": 0.02 }
        ]
      }
    }
  ]
}
```

- **Messages** are grouped by FIT message name; order is preserved within each group and every record keeps its `timestamp`.
- **Units** for each field are listed once in `field_units` to keep records readable.
- **Developer / unknown fields** are preserved (named where the file defines them, otherwise `unknown_<n>`).
- Values are decoded to human units (datetimes → ISO 8601, byte blobs → hex).

**File size:** a lossless dump is ~10× larger than the binary `.fit` (e.g. a 1 h ride ≈ 4 MB). Per-activity output keeps each file bounded, and `--gzip` shrinks it below the original `.fit`. For context-limited local models, `analyze` thins the data automatically.

---

## Docker usage

The container's working directory is `/data`. Mount your files in.

```bash
# Convert local .fit files
docker run --rm -v "$(pwd)":/data ghcr.io/kerem-ersoz/fit2json convert /data/my_run.fit -o /data/workouts/

# Fetch from Garmin
docker run --rm \
  -e GARMIN_EMAIL=you@email.com -e GARMIN_PASSWORD=yourpassword \
  -v "$(pwd)":/data \
  ghcr.io/kerem-ersoz/fit2json fetch garmin --days 7 -o /data/workouts/

# Analyze against a local LLM running on the host (Ollama / LM Studio)
docker run --rm --network host -v "$(pwd)":/data \
  ghcr.io/kerem-ersoz/fit2json analyze /data/workouts/ --backend ollama -p "Weekly summary"
```

> The `copilot` backend isn't available inside the image — run `fit2json analyze … --backend copilot` from a host install instead.

---

## Configuration

Create a `.env` file (see `.env.example`); it's loaded automatically from the current directory.

```bash
GARMIN_EMAIL=your@email.com          # for `fetch garmin`
GARMIN_PASSWORD=your_password

STRAVA_CLIENT_ID=your_client_id      # for `fetch strava`
STRAVA_CLIENT_SECRET=your_client_secret
STRAVA_REFRESH_TOKEN=your_refresh_token
```

The `analyze` command needs **no API key** for the Copilot CLI or local models. Only set `OPENAI_API_KEY` if you point `--base-url` at an OpenAI-compatible endpoint that requires auth.

<details>
<summary>Garmin Connect setup</summary>

Use your normal Garmin Connect email/password (via env vars or `--email`/`--password`). Garmin may require 2FA/CAPTCHA for unfamiliar logins — sign in on the website first, or use **Activities → ⚙️ → Export Original** and `fit2json convert`.
</details>

<details>
<summary>Strava API setup</summary>

1. Create an app at [strava.com/settings/api](https://www.strava.com/settings/api) (callback `http://localhost`); note the Client ID and Secret.
2. Authorize with `activity:read_all` scope and exchange the code for a **refresh token**:
   ```bash
   curl -X POST https://www.strava.com/oauth/token \
     -d client_id=YOUR_ID -d client_secret=YOUR_SECRET \
     -d code=AUTH_CODE -d grant_type=authorization_code
   ```
3. Set `STRAVA_CLIENT_ID` / `STRAVA_CLIENT_SECRET` / `STRAVA_REFRESH_TOKEN`.

For full-fidelity data, prefer the bulk `.fit` export + `fit2json convert`.
</details>

---

## Supported activity types

Sport is read directly from the FIT `session` message (e.g. `running`, `cycling`, `swimming`, `hiking`, `walking`, `rowing`, `strength_training`, `multi_sport`, …). Unrecognized values fall back to `sport_<n>`. Because the schema is lossless, **all** sports and every field are preserved regardless of type.

---

## Migrating from 0.1

- **`convert` output is now lossless**, not the old compact summary/lap/1-min schema. Downstream code that read `summary`/`time_series_1min` should read the `messages` tree instead.
- **`analyze` no longer calls the OpenAI or GitHub Models API directly.** Use `--backend copilot|ollama|lmstudio` or `--base-url`. `OPENAI_API_KEY`/`GITHUB_TOKEN` are no longer required.
- **Removed:** the `--deep` multi-pass mode and its checkpointing (Copilot's large context + per-activity files make it unnecessary).
- **`fetch`** now writes one JSON file per activity into a directory by default (`./workouts/`).

---

## Troubleshooting

- **"No .fit files found"** — point at a `.fit` file or a directory containing them (searched recursively).
- **"copilot CLI was not found"** — install the Copilot CLI and sign in, or use `--backend ollama|lmstudio`.
- **Ollama/LM Studio connection refused** — make sure the local server is running (`ollama serve`; LM Studio → *Local Server → Start*) on its default port (11434 / 1234).
- **Huge JSON files** — use `--gzip`, or per-activity output; for local-model analysis the data is thinned automatically to `--max-chars`.

---

## Development

```bash
pip install -e ".[dev]"
pytest -q
```

## License

MIT
