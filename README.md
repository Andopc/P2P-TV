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
