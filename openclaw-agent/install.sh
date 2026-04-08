#!/usr/bin/env bash
# =============================================================================
# OpenClaw Code Reviewer Agent — Setup Script
# Installs the code-reviewer agent for use with OpenClaw.
# =============================================================================

set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# Defaults
WORKSPACE_DIR="$HOME/.openclaw/workspace-code-reviewer"
CONFIG_DIR="$HOME/.openclaw"
WEBHOOK_TOKEN=""
SETUP_SYSTEMD=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --token)
            WEBHOOK_TOKEN="$2"
            shift 2
            ;;
        --workspace-dir)
            WORKSPACE_DIR="$2"
            shift 2
            ;;
        --systemd)
            SETUP_SYSTEMD=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --token TOKEN       Webhook token (generated if not provided)"
            echo "  --workspace-dir DIR Custom workspace directory"
            echo "  --systemd           Set up systemd service for the gateway"
            echo "  -h, --help          Show this help message"
            exit 0
            ;;
        *)
            error "Unknown option: $1. Use --help for usage."
            ;;
    esac
done

# Resolve script directory to find workspace files
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---------------------------------------------------------------------------
# 1. Check prerequisites
# ---------------------------------------------------------------------------
info "Checking prerequisites..."

if ! command -v node &>/dev/null; then
    error "Node.js not found. Install Node 22+ first:\n  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - && sudo apt install -y nodejs"
fi

NODE_MAJOR=$(node -v | sed 's/v//' | cut -d. -f1)
if [ "$NODE_MAJOR" -lt 22 ]; then
    error "Node.js $NODE_MAJOR found, but 22+ required."
fi

info "Node.js $(node -v) detected"

# ---------------------------------------------------------------------------
# 2. Install OpenClaw
# ---------------------------------------------------------------------------
if command -v openclaw &>/dev/null; then
    info "OpenClaw already installed: $(openclaw --version 2>/dev/null || echo 'unknown version')"
    info "Updating to latest..."
    npm update -g openclaw@latest 2>/dev/null || warn "Could not auto-update. Run: npm install -g openclaw@latest"
else
    info "Installing OpenClaw..."
    npm install -g openclaw@latest
fi

# ---------------------------------------------------------------------------
# 3. Set up the code-reviewer agent workspace
# ---------------------------------------------------------------------------
AGENT_DIR="$CONFIG_DIR/agents/code-reviewer/agent"

info "Setting up code-reviewer agent workspace at $WORKSPACE_DIR..."

mkdir -p "$WORKSPACE_DIR/skills"
mkdir -p "$AGENT_DIR"

# Copy workspace files
if [ -d "$SCRIPT_DIR/workspace" ]; then
    cp -r "$SCRIPT_DIR/workspace/SOUL.md" "$WORKSPACE_DIR/SOUL.md"
    cp -r "$SCRIPT_DIR/workspace/AGENTS.md" "$WORKSPACE_DIR/AGENTS.md"
    cp -r "$SCRIPT_DIR/workspace/TOOLS.md" "$WORKSPACE_DIR/TOOLS.md"

    # Copy skills
    if [ -d "$SCRIPT_DIR/workspace/skills" ]; then
        cp -r "$SCRIPT_DIR/workspace/skills/"* "$WORKSPACE_DIR/skills/" 2>/dev/null || true
    fi

    info "Workspace files copied to $WORKSPACE_DIR"
else
    error "Workspace files not found at $SCRIPT_DIR/workspace"
fi

# ---------------------------------------------------------------------------
# 4. Generate openclaw.json with webhook token
# ---------------------------------------------------------------------------
info "Configuring openclaw.json..."

if [ -z "$WEBHOOK_TOKEN" ]; then
    WEBHOOK_TOKEN=$(openssl rand -hex 32)
    warn "Generated new webhook token. Save this for your .env file:"
    echo -e "  ${BOLD}OPENCLAW_WEBHOOK_TOKEN=${WEBHOOK_TOKEN}${NC}"
fi

# Generate config from template, replacing the token placeholder
if [ -f "$SCRIPT_DIR/openclaw.json" ]; then
    sed "s|YOUR_WEBHOOK_TOKEN_HERE|$WEBHOOK_TOKEN|g" "$SCRIPT_DIR/openclaw.json" \
        | sed "s|~/.openclaw/workspace-code-reviewer|$WORKSPACE_DIR|g" \
        > "$CONFIG_DIR/openclaw.json"
    info "openclaw.json written to $CONFIG_DIR/openclaw.json"
else
    error "openclaw.json template not found at $SCRIPT_DIR/openclaw.json"
fi

# ---------------------------------------------------------------------------
# 5. Optionally set up systemd service
# ---------------------------------------------------------------------------
if [ "$SETUP_SYSTEMD" = true ]; then
    info "Setting up OpenClaw gateway as systemd service..."

    OPENCLAW_BIN=$(which openclaw)

    sudo tee /etc/systemd/system/openclaw-gateway.service > /dev/null << SERVICEEOF
[Unit]
Description=OpenClaw Gateway — Code Reviewer Agent
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME
Environment=HOME=$HOME
Environment=NODE_ENV=production
ExecStart=$OPENCLAW_BIN gateway start --foreground
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=openclaw

[Install]
WantedBy=multi-user.target
SERVICEEOF

    sudo systemctl daemon-reload
    sudo systemctl enable openclaw-gateway.service
    sudo systemctl start openclaw-gateway.service
    info "Systemd service created, enabled, and started"
fi

# ---------------------------------------------------------------------------
# 6. Verify
# ---------------------------------------------------------------------------
echo ""
echo -e "${BOLD}============================================${NC}"
echo -e "${GREEN}  OpenClaw Code Reviewer — Setup Complete  ${NC}"
echo -e "${BOLD}============================================${NC}"
echo ""
echo "  Agent workspace: $WORKSPACE_DIR"
echo "  Config:          $CONFIG_DIR/openclaw.json"
echo "  Gateway:         http://127.0.0.1:18789"
echo "  Webhook:         POST http://127.0.0.1:18789/hooks/pr-review"
echo ""
echo "  Webhook token:   $WEBHOOK_TOKEN"
echo ""
echo "  Useful commands:"
echo "    openclaw gateway start             # start the gateway"
echo "    openclaw agents list --bindings    # verify agent routing"
echo "    openclaw gateway status            # check gateway health"
echo ""
echo "  Test the webhook:"
echo "    curl -X POST http://127.0.0.1:18789/hooks/pr-review \\"
echo "      -H 'Authorization: Bearer $WEBHOOK_TOKEN' \\"
echo "      -H 'Content-Type: application/json' \\"
echo '      -d '"'"'{"repo":"test/repo","pr_number":1,"pr_title":"Test","pr_description":"test","pr_author":"dev","action":"opened","scope":"full","diff":"--- a/hello.py\n+++ b/hello.py\n@@ -1 +1 @@\n-print(\"hello\")\n+print(\"world\")","context_md":""}'"'"
echo ""
echo -e "${YELLOW}  Add these to your PR Review Bot .env:${NC}"
echo "    OPENCLAW_ENABLED=true"
echo "    OPENCLAW_BASE_URL=http://127.0.0.1:18789"
echo "    OPENCLAW_WEBHOOK_TOKEN=$WEBHOOK_TOKEN"
echo ""
