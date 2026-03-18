# P2P TV

A home-hosted, internet-reachable channel hub that publishes schedules and serves SD AV1
assets, paired with a node helper that pre-fetches and seeds content via qBittorrent.

Designed to integrate with [FieldStation42](https://github.com/shane-mason/FieldStation42) as
an additional "streaming" channel source consumed via HTTP Range URLs or mpv.

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│  Home network / VPS                                  │
│                                                      │
│  ┌─────────────┐     REST/Bearer    ┌─────────────┐  │
│  │  p2ptv-hub  │◄──────────────────►│ p2ptv-node  │  │
│  │  (FastAPI)  │                    │  (Python)   │  │
│  └──────┬──────┘                    └──────┬──────┘  │
│         │  file serving                    │ WebAPI  │
│         │                          ┌───────▼──────┐  │
│         │                          │ qBittorrent  │  │
│         │                          │    (nox)     │  │
│         │                          └──────────────┘  │
└─────────┼────────────────────────────────────────────┘
          │  HTTPS (reverse proxy recommended)
          ▼
    FieldStation42 / mpv / any HTTP client
```

### Components

| Service | Description |
|---|---|
| **p2ptv-hub** | FastAPI app: publishes channel list, schedules, and serves AV1 content files with HTTP Range support |
| **p2ptv-node** | Python daemon: polls the hub schedule, pre-fetches upcoming content via qBittorrent, enforces cache size limit |
| **qbittorrent** | `linuxserver/qbittorrent` – handles all torrent activity; WebUI is **not** exposed publicly |

---

## Platform support

All Docker images are built from **multi-arch base images** and run unmodified on:

| Architecture | Example hardware |
|---|---|
| `linux/amd64` | Standard x86-64 server, desktop, VPS |
| `linux/arm64` | Raspberry Pi 4 / Pi 5 (64-bit OS, recommended) |
| `linux/arm/v7` | Raspberry Pi 3 / older Pis (32-bit Raspberry Pi OS) |

Docker automatically pulls the right image for your machine — no `--platform` flag needed
for normal use.  To cross-build (e.g. build an arm64 image on an x86 host):

```bash
docker buildx build --platform linux/arm64 -f Dockerfile.hub -t p2ptv-hub:arm64 .
```

---

## Quickstart

Choose the path that fits your situation:

| Path | Best for |
|---|---|
| [**A – Local PC (Python only)**](#quickstart-a--local-pc-python-only-no-docker) | Trying it out on Windows / macOS / Linux without Docker |
| [**B – Docker Compose**](#quickstart-b--docker-compose-recommended-for-always-on-hosting) | Always-on home server, Raspberry Pi, VPS |

---

## Quickstart A – Local PC (Python only, no Docker)

Run just the hub directly on your machine in a few minutes.  No Docker, no qBittorrent
needed to get started — you can serve content files straight from your hard drive.

### Linux x86-64 – one-command setup

Clone the repo and run the setup script.  It handles everything automatically:

```bash
git clone https://github.com/Andopc/P2P-TV.git
cd P2P-TV
chmod +x setup_linux.sh
./setup_linux.sh
```

The script:
- Checks for Python 3.11+ and prints distro-specific install instructions if it is missing
- Creates a `.venv/` virtual environment
- Installs hub dependencies
- Copies `.env.example` → `.env` and auto-generates a random `P2PTV_API_KEY`
- Creates the `data/content/` directory

When it finishes it prints the exact commands to start the hub and verify it works.
Then jump to [Step 5 – Add some content](#step-5--add-some-content-optional-but-recommended)
below if you want to serve your own video files.

> **All other platforms** (Windows, macOS) or if you prefer step-by-step instructions:
> continue with the manual steps below.

---

### Prerequisites

- **Python 3.11 or newer**
  - Windows: download from <https://www.python.org/downloads/> (tick "Add Python to PATH")
  - macOS: `brew install python` or the Python.org installer
  - Linux (Debian/Ubuntu): `sudo apt install python3.11 python3.11-venv`
  - Linux (Fedora/RHEL): `sudo dnf install python3.11`
  - Linux (Arch): `sudo pacman -S python`
- **git** (to clone the repo)
  - Windows: <https://git-scm.com/download/win>
  - macOS: `brew install git` or Xcode Command Line Tools (`xcode-select --install`)
  - Linux: `sudo apt install git` / `sudo dnf install git` / `sudo pacman -S git`

### Step 1 – Clone the repo

```bash
git clone https://github.com/Andopc/P2P-TV.git
cd P2P-TV
```

### Step 2 – Create and activate a virtual environment

**macOS / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (Command Prompt)**
```bat
python -m venv .venv
.venv\Scripts\activate.bat
```

**Windows (PowerShell)**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### Step 3 – Install hub dependencies

```bash
pip install -r p2ptv_hub/requirements.txt
```

### Step 4 – Create your `.env` file

```bash
# macOS / Linux
cp .env.example .env

# Windows
copy .env.example .env
```

Open `.env` in any text editor and set **at minimum**:

```dotenv
# Pick any password-like string (keep it secret)
P2PTV_API_KEY=my-local-secret

# For local-only use, localhost is fine
P2PTV_BASE_URL=http://localhost:8000
```

### Step 5 – Add some content (optional but recommended)

The hub serves files from `data/content/`.  Drop any video file in there, for example:

```
data/
└── content/
    └── my-show-ep1.mkv
```

The filename stem (`my-show-ep1`) becomes the `content_id` you reference in schedules.

Sample channel and schedule files are already included in `data/` so the hub will start
with two placeholder channels out of the box.

### Step 6 – Start the hub

```bash
# macOS / Linux
uvicorn p2ptv_hub.main:app --host 0.0.0.0 --port 8000

# Windows – same command, make sure your venv is active
uvicorn p2ptv_hub.main:app --host 0.0.0.0 --port 8000
```

You should see output like:
```
INFO:     Started server process [...]
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Step 7 – Verify it works

Open a new terminal (keep uvicorn running in the first one).

**macOS / Linux**
```bash
# Replace "my-local-secret" with the value you set for P2PTV_API_KEY in .env
export KEY=my-local-secret
curl -H "Authorization: Bearer $KEY" http://localhost:8000/api/v1/health
# {"status":"ok"}

curl -H "Authorization: Bearer $KEY" http://localhost:8000/api/v1/channels
```

**Windows (PowerShell)**
```powershell
# Replace "my-local-secret" with the value you set for P2PTV_API_KEY in .env
$KEY = "my-local-secret"
Invoke-RestMethod -Uri http://localhost:8000/api/v1/health `
  -Headers @{ Authorization = "Bearer $KEY" }

Invoke-RestMethod -Uri http://localhost:8000/api/v1/channels `
  -Headers @{ Authorization = "Bearer $KEY" }
```

Or just open <http://localhost:8000/docs> in your browser to explore the interactive
API docs (click the padlock icon → enter your API key as a Bearer token).

### Step 8 – Play content with mpv

Replace `my-local-secret` with your `P2PTV_API_KEY` and `my-show-ep1` with the stem of
the file you placed in `data/content/`:

```bash
mpv --http-header-fields="Authorization: Bearer my-local-secret" \
    http://localhost:8000/api/v1/content/my-show-ep1/file
```

---

## Quickstart B – Docker Compose (recommended for always-on hosting)

### 1. Prerequisites

- Docker + Docker Compose v2 (`docker compose` command)
- Port **8000** (or your chosen `P2PTV_PORT`) reachable from outside if you want remote access

### 2. Clone and configure

```bash
git clone https://github.com/Andopc/P2P-TV.git
cd P2P-TV
cp .env.example .env
```

Edit `.env` and set **at minimum**:

```dotenv
# Generate a strong token:
# python3 -c "import secrets; print(secrets.token_urlsafe(32))"
P2PTV_API_KEY=your-strong-secret-token

# The URL clients will use to reach the hub (used in schedule http_url fields)
P2PTV_BASE_URL=https://p2ptv.yourdomain.com
```

### 3. Start services

```bash
docker compose up -d
```

This starts:
- `hub` on `http://localhost:8000` (configurable via `P2PTV_PORT`)
- `qbittorrent` on the **internal** Docker network only (no public port)
- `node` polling the hub and seeding via qBittorrent

### 4. Verify the hub

```bash
curl -H "Authorization: Bearer $P2PTV_API_KEY" http://localhost:8000/api/v1/health
# {"status":"ok"}

curl -H "Authorization: Bearer $P2PTV_API_KEY" http://localhost:8000/api/v1/channels
```

---

## Home hosting notes

### Reverse proxy + TLS (recommended)

Expose the hub via nginx or Caddy with TLS.  Example Caddy snippet:

```
p2ptv.yourdomain.com {
    reverse_proxy localhost:8000
}
```

**Do not expose qBittorrent's WebUI port publicly.**
If you need to manage qBittorrent remotely, use an SSH tunnel:

```bash
ssh -L 8090:localhost:8090 your-server
# then open http://localhost:8090 in your browser
```

### Raspberry Pi specific notes

**Pi 4 / Pi 5 (64-bit OS — recommended)**
Run exactly like x86 — Docker Compose works out of the box.

```bash
# Confirm you're on 64-bit:
uname -m   # should print aarch64
docker compose up -d
```

**Pi 3 (32-bit Raspberry Pi OS)**
Still works via the `linux/arm/v7` image variant.  You may need to increase swap:

```bash
sudo dphys-swapfile swapoff
sudo sed -i 's/CONF_SWAPSIZE=.*/CONF_SWAPSIZE=512/' /etc/dphys-swapfile
sudo dphys-swapfile setup && sudo dphys-swapfile swapon
```

For best performance on Pi, point `P2PTV_CACHE_DIR` / `data/torrents` at an **external USB
drive** rather than the SD card to reduce write wear.

---

## API reference

All endpoints require:
```
Authorization: Bearer <P2PTV_API_KEY>
```

### `GET /api/v1/health`
Returns `{"status": "ok"}` when the hub is up and the API key is valid.

### `GET /api/v1/channels`
Returns a JSON array of channel objects.

```json
[
  {
    "id": "channel-1",
    "name": "P2P TV - Handheld",
    "description": "...",
    "variant": "handheld"
  }
]
```

### `GET /api/v1/channels/{channel_id}/schedule?hours=12`
Returns schedule entries whose window overlaps `[now, now + hours]`.

| Field | Type | Description |
|---|---|---|
| `start_ts` | ISO 8601 string | Programme start time (UTC) |
| `duration_seconds` | int | Length in seconds |
| `title` | string | Episode/programme title |
| `content_id` | string | Identifier for the content file |
| `variant` | string | `handheld` or `crt` |
| `magnet` | string | BitTorrent magnet URI |
| `sha256` | string | SHA-256 hex digest of the file |
| `size_bytes` | int | File size in bytes |
| `http_url` | string | Direct URL to the content endpoint |

### `GET /api/v1/content/{content_id}/file`
Streams the content file.  Supports the `Range` header for seeking (mpv-compatible).

```bash
# Fetch bytes 0-1023:
curl -H "Authorization: Bearer $KEY" \
     -H "Range: bytes=0-1023" \
     http://localhost:8000/api/v1/content/my-clip/file
```

---

## Display profiles

| Variant | Target device | Notes |
|---|---|---|
| `handheld` | Steam Deck, laptop, phone | 16:9, ~720p, AV1 codec |
| `crt` | Raspberry Pi + CRT via composite/S-Video | 4:3, SD (~480 lines), lower bitrate |

Schedule entries carry a `variant` field so the node and clients can filter by profile.

---

## FieldStation42 integration

In your FieldStation42 channel config, add a streaming entry pointing at the hub's
`http_url` for the currently-airing content, or use a script that reads the schedule and
sets the URL dynamically:

```yaml
# Example FS42 channel snippet
channels:
  - name: "P2P TV"
    network_type: streaming
    streams:
      - url: "http://your-hub/api/v1/content/<content_id>/file"
        headers:
          Authorization: "Bearer <P2PTV_API_KEY>"
```

mpv (used by FS42) handles HTTP Range requests natively, so seeking works without
buffering the entire file.

---

## Data layout

```
data/
+-- channels.json               # channel definitions
+-- schedules/
|   +-- channel-1.json          # per-channel schedule entries
|   +-- channel-crt.json
+-- content/
    +-- <content_id>.<ext>      # AV1 media files (not committed to git)
```

Content files are matched by filename stem: a file `my-show-ep1.mkv` is served for
`content_id = "my-show-ep1"`.

---

## Running tests

```bash
pip install fastapi uvicorn pydantic pydantic-settings aiofiles pytest httpx
pytest
```

---

## Configuration reference

### Hub (`p2ptv_hub`)

| Env var | Required | Default | Description |
|---|---|---|---|
| `P2PTV_API_KEY` | yes | - | Bearer token for all API endpoints |
| `P2PTV_BASE_URL` | | `http://localhost:8000` | Hub's public URL (used in `http_url` fields) |
| `P2PTV_DATA_DIR` | | `./data` | Path to the data directory |

### Node (`p2ptv_node`)

| Env var | Required | Default | Description |
|---|---|---|---|
| `P2PTV_HUB_URL` | | `http://localhost:8000` | Hub base URL |
| `P2PTV_API_KEY` | yes | - | Same key as the hub |
| `P2PTV_CHANNEL_IDS` | | (empty) | Comma-separated channel IDs to watch |
| `P2PTV_PREFETCH_HOURS` | | `6` | Lookahead window for pre-fetching |
| `P2PTV_CACHE_DIR` | | `./cache` | Directory where qBittorrent downloads to |
| `P2PTV_CACHE_MAX_GB` | | `10.0` | Maximum cache size before eviction |
| `QBT_URL` | | `http://localhost:8090` | qBittorrent WebAPI base URL |
| `QBT_USERNAME` | | `admin` | qBittorrent username |
| `QBT_PASSWORD` | | `adminadmin` | qBittorrent password |
| `POLL_INTERVAL_SECONDS` | | `300` | How often the node polls the hub |

---

## License

GPL-3.0 — see [LICENSE](LICENSE).
