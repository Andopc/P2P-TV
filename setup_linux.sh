#!/usr/bin/env bash
# setup_linux.sh – one-command setup for P2P TV hub on Linux x86-64
#
# Usage:
#   chmod +x setup_linux.sh
#   ./setup_linux.sh
#
# What it does:
#   1. Checks for Python 3.11+ and offers install instructions for common distros
#   2. Creates a Python virtual environment in .venv/
#   3. Installs hub Python dependencies
#   4. Creates .env from .env.example with local-friendly defaults
#   5. Creates data/content/ directory
#   6. Prints the command to start the hub

set -euo pipefail

RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
CYAN=$'\033[0;36m'
NC=$'\033[0m' # No Color

info()    { echo -e "${CYAN}[P2P-TV]${NC} $*"; }
success() { echo -e "${GREEN}[P2P-TV]${NC} $*"; }
warn()    { echo -e "${YELLOW}[P2P-TV]${NC} $*"; }
error()   { echo -e "${RED}[P2P-TV]${NC} $*" >&2; }

# ── 1. Check Python version ────────────────────────────────────────────────────

PYTHON=""
for cmd in python3.13 python3.12 python3.11 python3; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" -c 'import sys; print(sys.version_info[:2])')
        # ver looks like "(3, 11)" – check major >= 3 and minor >= 11
        if "$cmd" -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' 2>/dev/null; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [[ -z "$PYTHON" ]]; then
    error "Python 3.11 or newer is required but was not found."
    echo ""
    echo "Install it for your distribution:"
    echo ""
    echo "  Debian / Ubuntu:"
    echo "    sudo apt update && sudo apt install -y python3.11 python3.11-venv python3-pip"
    echo ""
    echo "  Fedora / RHEL / CentOS (dnf):"
    echo "    sudo dnf install -y python3.11"
    echo ""
    echo "  Arch Linux:"
    echo "    sudo pacman -S python"
    echo ""
    echo "  openSUSE:"
    echo "    sudo zypper install python311"
    echo ""
    echo "  Any distro (pyenv):"
    echo "    curl https://pyenv.run | bash"
    echo "    pyenv install 3.11 && pyenv global 3.11"
    echo ""
    exit 1
fi

PYTHON_VER=$("$PYTHON" -c 'import sys; v=sys.version_info; print(f"{v.major}.{v.minor}.{v.micro}")')
success "Found $PYTHON  (Python $PYTHON_VER)"

# ── 2. Create virtual environment ─────────────────────────────────────────────

VENV_DIR=".venv"
if [[ -d "$VENV_DIR" ]]; then
    warn "Virtual environment '$VENV_DIR' already exists – reusing it."
else
    info "Creating virtual environment in $VENV_DIR/ …"
    "$PYTHON" -m venv "$VENV_DIR"
    success "Virtual environment created."
fi

# Activate it for the remainder of the script
# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"

# ── 3. Install hub dependencies ───────────────────────────────────────────────

info "Installing hub dependencies from p2ptv_hub/requirements.txt …"
pip install --quiet --upgrade pip
pip install --quiet -r p2ptv_hub/requirements.txt
success "Dependencies installed."

# ── 4. Create .env ────────────────────────────────────────────────────────────

if [[ -f ".env" ]]; then
    warn ".env already exists – skipping creation. Edit it manually if needed."
else
    info "Creating .env from .env.example …"
    cp .env.example .env

    # Generate a random API key
    API_KEY=$("$PYTHON" -c "import secrets; print(secrets.token_urlsafe(32))")

    # Patch the two values most important for local-only use
    sed -i "s|^P2PTV_API_KEY=.*|P2PTV_API_KEY=${API_KEY}|" .env
    sed -i "s|^P2PTV_BASE_URL=.*|P2PTV_BASE_URL=http://localhost:8000|" .env
    # Node points to localhost when not using Docker
    sed -i "s|^P2PTV_HUB_URL=.*|P2PTV_HUB_URL=http://localhost:8000|" .env

    success ".env created with a random API key."
    echo ""
    echo "  Your API key: ${YELLOW}${API_KEY}${NC}"
    echo "  (also written to .env – keep it secret)"
fi

# ── 5. Ensure data directories exist ─────────────────────────────────────────

info "Creating data/content/ directory …"
mkdir -p data/content
success "data/content/ is ready.  Drop video files here to serve them."

# ── 6. Roll sample schedule dates to today ────────────────────────────────────

info "Rolling sample schedule dates to today …"
"$PYTHON" tools/refresh_sample_schedules.py
success "Sample schedules updated – /api/v1/channels/<id>/schedule will show today's entries."

# ── 7. Done – print run instructions ─────────────────────────────────────────

echo ""
success "Setup complete!  Next steps:"
echo ""
echo "  1. Activate the virtual environment (in every new terminal):"
echo "       ${CYAN}source .venv/bin/activate${NC}"
echo ""
echo "  2. Start the hub:"
echo "       ${CYAN}uvicorn p2ptv_hub.main:app --host 0.0.0.0 --port 8000${NC}"
echo ""
echo "  3. Verify it is running (in another terminal):"
API_KEY_HINT=$(grep "^P2PTV_API_KEY=" .env | cut -d= -f2-)
echo "       ${CYAN}curl -H \"Authorization: Bearer ${API_KEY_HINT}\" http://localhost:8000/api/v1/health${NC}"
echo ""
echo "  4. Browse the interactive API docs:"
echo "       ${CYAN}http://localhost:8000/docs${NC}"
echo ""
echo "  5. Add your own content file to the schedule:"
echo "       ${CYAN}python tools/add_content.py data/content/my-video.mkv --title \"My Video\"${NC}"
echo ""
echo "  6. Play a file with mpv:"
echo "       ${CYAN}mpv --http-header-fields=\"Authorization: Bearer ${API_KEY_HINT}\" \\"
echo "           http://localhost:8000/api/v1/content/<content_id>/file${NC}"
echo ""
