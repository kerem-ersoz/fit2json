# fit2json

Convert Garmin Connect and Strava `.fit` files into structured, LLM-ready JSON — then analyze your workouts with AI using GitHub Models API.

## What It Does

**fit2json** is a command-line tool that:

1. **Parses** `.fit` files (the binary format used by Garmin, Wahoo, and other fitness devices)
2. **Converts** them to compact, structured JSON optimized for LLM context windows
3. **Fetches** activities directly from Garmin Connect or Strava APIs
4. **Analyzes** your workout data using AI (powered by GitHub Models API)

The output JSON includes activity summaries, lap splits, and 1-minute time-series samples (heart rate, cadence, speed, power) — detailed enough for meaningful AI analysis while staying compact enough to fit in an LLM prompt.

---

## Installation

### Option 1: Docker (Recommended — no Python required)

```bash
docker pull ghcr.io/kerem-ersoz/fit2json:latest

# Verify
docker run --rm ghcr.io/kerem-ersoz/fit2json --version
```

### Option 2: Install from source

### Prerequisites

- Python 3.9 or later
- A GitHub account with Copilot subscription (for the `analyze` command)

### Install from source

```bash
git clone https://github.com/kerem-ersoz/fit2json.git
cd fit2json
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Install dev dependencies (for running tests)

```bash
pip install -e ".[dev]"
```

### Verify installation

```bash
fit2json --version
# fit2json, version 0.1.0
```

---

## Quick Start

```bash
# Convert a single .fit file
fit2json convert my_run.fit -o run.json

# Convert a whole directory of .fit files
fit2json convert ~/Downloads/garmin-export/ -o all-activities.json

# Fetch from Garmin Connect and convert
fit2json fetch garmin --days 7 -o this-week.json

# Analyze with AI
fit2json analyze run.json --prompt "How was my pacing strategy?"

# Pipeline: convert and analyze in one shot
fit2json convert my_run.fit | fit2json analyze --prompt "Give me a race report"
```

---

## Docker Usage

The Docker image lets you run fit2json on any platform without installing Python. The container's working directory is `/data`.

### Convert local .fit files

Mount your `.fit` files into the container:

```bash
# Single file
docker run --rm -v "$(pwd)":/data ghcr.io/kerem-ersoz/fit2json convert /data/my_run.fit -o /data/output.json

# Entire directory
docker run --rm -v ~/Downloads/garmin-export:/data ghcr.io/kerem-ersoz/fit2json convert /data/ -o /data/all-activities.json

# Output to stdout (pipe-friendly)
docker run --rm -v "$(pwd)":/data ghcr.io/kerem-ersoz/fit2json convert /data/my_run.fit
```

### Fetch from Garmin Connect

Pass credentials via environment variables:

```bash
docker run --rm \
  -e GARMIN_EMAIL=you@email.com \
  -e GARMIN_PASSWORD=yourpassword \
  -v "$(pwd)":/data \
  ghcr.io/kerem-ersoz/fit2json fetch garmin --days 7 -o /data/this-week.json
```

### Fetch from Strava

```bash
docker run --rm \
  -e STRAVA_CLIENT_ID=your_id \
  -e STRAVA_CLIENT_SECRET=your_secret \
  -e STRAVA_REFRESH_TOKEN=your_token \
  -v "$(pwd)":/data \
  ghcr.io/kerem-ersoz/fit2json fetch strava --days 30 -o /data/recent.json
```

### Analyze with AI

```bash
docker run --rm \
  -e GITHUB_TOKEN=ghp_your_token \
  -v "$(pwd)":/data \
  ghcr.io/kerem-ersoz/fit2json analyze /data/output.json --prompt "How was my pacing?"
```

### Pipeline: convert + analyze

```bash
docker run --rm -v "$(pwd)":/data ghcr.io/kerem-ersoz/fit2json convert /data/my_run.fit \
  | docker run --rm -i -e GITHUB_TOKEN=ghp_your_token ghcr.io/kerem-ersoz/fit2json analyze --prompt "Race report"
```

### Using a .env file

```bash
docker run --rm --env-file .env -v "$(pwd)":/data ghcr.io/kerem-ersoz/fit2json fetch garmin --days 7 -o /data/week.json
```

### Shell alias (optional)

Add to your `~/.bashrc` or `~/.zshrc` for convenience:

```bash
alias fit2json='docker run --rm --env-file ~/.fit2json.env -v "$(pwd)":/data ghcr.io/kerem-ersoz/fit2json'

# Then use normally:
fit2json convert my_run.fit -o output.json
fit2json analyze output.json --prompt "How was my run?"
```

---

## Commands

### `fit2json convert`

Parse local `.fit` file(s) and output structured JSON.

```bash
# Single file → stdout
fit2json convert activity.fit

# Single file → file
fit2json convert activity.fit -o output.json

# Directory (batch) → file
fit2json convert ./garmin-export/ -o all-activities.json

# Custom indentation
fit2json convert activity.fit -o output.json --indent 4
```

**Options:**

| Option | Description |
|--------|-------------|
| `-o, --output PATH` | Output file path. Defaults to stdout. |
| `--indent INT` | JSON indentation level (default: 2). |

---

### `fit2json fetch garmin`

Download and convert recent activities from Garmin Connect.

```bash
# Fetch last 30 days (default)
fit2json fetch garmin -o recent.json

# Fetch last 7 days
fit2json fetch garmin --days 7 -o this-week.json

# Keep raw .fit files
fit2json fetch garmin --days 30 --raw-dir ./raw-fits/ -o activities.json

# Explicit credentials (otherwise uses env vars)
fit2json fetch garmin --email you@email.com --password yourpass -o activities.json
```

**Options:**

| Option | Description |
|--------|-------------|
| `--days INT` | Days of history to fetch (default: 30). |
| `-o, --output PATH` | Output JSON file path. |
| `--email TEXT` | Garmin Connect email (or set `GARMIN_EMAIL`). |
| `--password TEXT` | Garmin Connect password (or set `GARMIN_PASSWORD`). |
| `--raw-dir PATH` | Directory to save raw `.fit` files. |

---

### `fit2json fetch strava`

Download and convert recent activities from Strava.

> **Note:** Strava's API provides stream data (time-series), not raw `.fit` files. The tool fetches streams and converts them to the same JSON format. For actual `.fit` files, use [Strava's bulk export](https://support.strava.com/hc/en-us/articles/216918437-Exporting-your-Data-and-Bulk-Export) and the `convert` command.

```bash
# Fetch last 30 days
fit2json fetch strava -o recent.json

# Fetch last 90 days
fit2json fetch strava --days 90 -o quarter.json
```

**Options:**

| Option | Description |
|--------|-------------|
| `--days INT` | Days of history to fetch (default: 30). |
| `-o, --output PATH` | Output JSON file path. |
| `--client-id TEXT` | Strava client ID (or set `STRAVA_CLIENT_ID`). |
| `--client-secret TEXT` | Strava client secret (or set `STRAVA_CLIENT_SECRET`). |
| `--refresh-token TEXT` | Strava refresh token (or set `STRAVA_REFRESH_TOKEN`). |
| `--raw-dir PATH` | Directory to save raw activity files. |

---

### `fit2json analyze`

Send activity JSON to an LLM via GitHub Models API for AI-powered analysis.

```bash
# Analyze a JSON file
fit2json analyze output.json --prompt "How is my running fitness trending?"

# Pipe from convert
fit2json convert activity.fit | fit2json analyze --prompt "Give me a race report"

# Use a specific model
fit2json analyze output.json --prompt "Analyze my HR zones" --model gpt-4o

# Disable streaming
fit2json analyze output.json --prompt "Summarize this week" --no-stream
```

**Options:**

| Option | Description |
|--------|-------------|
| `-p, --prompt TEXT` | **(Required)** Your analysis question or prompt. |
| `--model TEXT` | Model to use (default: `gpt-4o`). |
| `--token TEXT` | GitHub personal access token (or set `GITHUB_TOKEN`). |
| `--no-stream` | Disable streaming output. |

---

## JSON Output Schema

The output JSON is designed to be compact yet informative for LLM analysis:

```json
{
  "activities": [
    {
      "source_file": "2024-03-10_morning_run.fit",
      "sport": "running",
      "start_time": "2024-03-10T07:30:00+00:00",
      "summary": {
        "total_distance_km": 10.234,
        "total_duration_s": 3120.0,
        "avg_pace_min_per_km": 5.1,
        "max_pace_min_per_km": 4.32,
        "avg_heart_rate_bpm": 152,
        "max_heart_rate_bpm": 178,
        "avg_cadence_spm": 172,
        "avg_speed_kmh": 11.81,
        "max_speed_kmh": 13.89,
        "total_calories": 680,
        "total_ascent_m": 85.0,
        "total_descent_m": 82.0
      },
      "laps": [
        {
          "lap_number": 1,
          "distance_km": 1.001,
          "duration_s": 305.0,
          "avg_heart_rate_bpm": 145,
          "max_heart_rate_bpm": 155,
          "avg_pace_min_per_km": 5.08,
          "avg_speed_kmh": 11.81,
          "avg_cadence_spm": 170
        }
      ],
      "time_series_1min": [
        {
          "elapsed_min": 0,
          "heart_rate_bpm": 120,
          "cadence_spm": 168,
          "speed_kmh": 10.5
        },
        {
          "elapsed_min": 1,
          "heart_rate_bpm": 142,
          "cadence_spm": 172,
          "speed_kmh": 11.2
        }
      ]
    }
  ],
  "metadata": {
    "generated_at": "2024-03-10T12:00:00+00:00",
    "tool_version": "0.1.0",
    "file_count": 1
  }
}
```

### Field Reference

#### Summary Fields

| Field | Unit | Description |
|-------|------|-------------|
| `total_distance_km` | km | Total distance |
| `total_duration_s` | seconds | Total moving time |
| `avg_pace_min_per_km` | min/km | Average pace |
| `max_pace_min_per_km` | min/km | Best (fastest) pace |
| `avg_heart_rate_bpm` | bpm | Average heart rate |
| `max_heart_rate_bpm` | bpm | Maximum heart rate |
| `avg_cadence_spm` | steps/min | Average cadence (steps per minute for running) |
| `max_cadence_spm` | steps/min | Maximum cadence |
| `avg_power_w` | watts | Average power (cycling/running power meter) |
| `max_power_w` | watts | Maximum power |
| `avg_speed_kmh` | km/h | Average speed |
| `max_speed_kmh` | km/h | Maximum speed |
| `total_calories` | kcal | Total calories burned |
| `total_ascent_m` | meters | Total elevation gain |
| `total_descent_m` | meters | Total elevation loss |

#### Time Series (1-minute samples)

| Field | Unit | Description |
|-------|------|-------------|
| `elapsed_min` | minutes | Minutes since activity start |
| `heart_rate_bpm` | bpm | Average HR for that minute |
| `cadence_spm` | steps/min | Average cadence for that minute |
| `speed_kmh` | km/h | Average speed for that minute |
| `power_w` | watts | Average power for that minute |

> **Note:** Fields with no data (e.g., `power_w` for a run without a power meter) are omitted from the JSON output to keep it compact.

---

## Supported Activity Types

| Sport | FIT Sport ID | Notes |
|-------|-------------|-------|
| Running | 1 | Includes treadmill |
| Cycling | 2 | Road, MTB, indoor |
| Swimming | 5 | Pool and open water |
| Hiking | 11 | |
| Walking | 13 | |
| Rowing | 17 | Indoor and outdoor |
| Yoga | 37 | |
| Strength Training | 29 | |
| Elliptical | 53 | |
| Multi-sport | 15 | Triathlon, duathlon |
| Other | Various | Falls back to `sport_N` naming |

---

## Configuration

### Environment Variables

Create a `.env` file in your project directory (see `.env.example`):

```bash
# Required for 'analyze' command
GITHUB_TOKEN=ghp_your_github_token_here

# Required for 'fetch garmin' command
GARMIN_EMAIL=your@email.com
GARMIN_PASSWORD=your_password

# Required for 'fetch strava' command
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret
STRAVA_REFRESH_TOKEN=your_refresh_token
```

The tool automatically loads `.env` files from the current directory.

---

## API Setup Guides

### GitHub Models API (for `analyze` command)

The `analyze` command uses the [GitHub Models API](https://github.com/marketplace/models), which is available to GitHub Copilot subscribers at no extra cost.

1. **Create a Personal Access Token:**
   - Go to [GitHub Settings → Tokens](https://github.com/settings/tokens)
   - Click "Generate new token (classic)"
   - No special scopes needed for GitHub Models
   - Copy the token

2. **Set the token:**
   ```bash
   export GITHUB_TOKEN=ghp_your_token_here
   # Or add to your .env file
   ```

3. **Test it:**
   ```bash
   fit2json analyze output.json --prompt "Summarize this activity"
   ```

### Garmin Connect (for `fetch garmin` command)

1. **Use your existing Garmin Connect credentials** (the same email/password you use to log in to [connect.garmin.com](https://connect.garmin.com)).

2. **Set credentials:**
   ```bash
   export GARMIN_EMAIL=your@email.com
   export GARMIN_PASSWORD=your_password
   # Or add to your .env file
   ```

3. **Alternative: Manual export**
   - Log in to [Garmin Connect](https://connect.garmin.com)
   - Go to Activities → select an activity → ⚙️ → Export Original
   - Use `fit2json convert` on the downloaded `.fit` file

### Strava API (for `fetch strava` command)

1. **Create a Strava API Application:**
   - Go to [Strava API Settings](https://www.strava.com/settings/api)
   - Create an application (use `http://localhost` as the callback URL)
   - Note your Client ID and Client Secret

2. **Get a Refresh Token:**
   - Visit: `https://www.strava.com/oauth/authorize?client_id=YOUR_CLIENT_ID&response_type=code&redirect_uri=http://localhost&scope=activity:read_all`
   - Authorize the app → you'll be redirected to `http://localhost?code=AUTHORIZATION_CODE`
   - Exchange the code:
     ```bash
     curl -X POST https://www.strava.com/oauth/token \
       -d client_id=YOUR_CLIENT_ID \
       -d client_secret=YOUR_CLIENT_SECRET \
       -d code=AUTHORIZATION_CODE \
       -d grant_type=authorization_code
     ```
   - Save the `refresh_token` from the response

3. **Set credentials:**
   ```bash
   export STRAVA_CLIENT_ID=your_client_id
   export STRAVA_CLIENT_SECRET=your_client_secret
   export STRAVA_REFRESH_TOKEN=your_refresh_token
   # Or add to your .env file
   ```

4. **Alternative: Bulk export**
   - Go to [Strava Settings](https://www.strava.com/settings/profile) → "Download or Delete Your Account" → "Request Your Archive"
   - Extract the `.fit` files from the archive
   - Use `fit2json convert` on the extracted files

---

## Examples

### Weekly training summary

```bash
fit2json fetch garmin --days 7 -o week.json
fit2json analyze week.json --prompt "Give me a weekly training summary. How was my volume, intensity distribution, and recovery?"
```

### Race analysis

```bash
fit2json convert marathon.fit -o race.json
fit2json analyze race.json --prompt "Analyze my marathon pacing strategy. Where did I slow down and why? What could I improve?"
```

### Trend analysis

```bash
fit2json fetch garmin --days 90 -o quarter.json
fit2json analyze quarter.json --prompt "How has my running fitness changed over the last 3 months? Look at pace, heart rate, and cadence trends."
```

### Compare two workouts

```bash
fit2json convert interval_workout_1.fit interval_workout_2.fit -o compare.json
fit2json analyze compare.json --prompt "Compare these two interval workouts. Did I improve?"
```

---

## Troubleshooting

### "No .fit files found"
Make sure you're pointing at a directory containing `.fit` files, or directly at a `.fit` file. The tool searches recursively in directories.

### "Failed to parse [filename]"
Some `.fit` files may be corrupted or use non-standard extensions. The tool will skip them and continue with the remaining files.

### Garmin Connect authentication issues
- Garmin may require 2FA or CAPTCHA for unfamiliar logins. Try logging in via the Garmin Connect website first.
- If authentication fails repeatedly, use the manual export method.

### Strava "Authorization Error"
- Make sure your app has the `activity:read_all` scope.
- Refresh tokens expire if unused for 6+ months — re-authorize if needed.

### Large activities produce huge JSON
The 1-minute sampling keeps output compact. A typical 1-hour activity produces ~5KB of JSON. If you need to analyze many activities at once and hit context limits, the `analyze` command automatically truncates at 100K characters.

### GitHub Models API errors
- Verify your token: `curl -H "Authorization: Bearer $GITHUB_TOKEN" https://api.github.com/user`
- Make sure you have an active GitHub Copilot subscription.

---

## Development

```bash
# Clone and setup
git clone https://github.com/kerem-ersoz/fit2json.git
cd fit2json
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=fit2json --cov-report=term-missing
```

---

## License

MIT
