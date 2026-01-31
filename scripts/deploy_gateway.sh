#!/bin/bash
# RLM MCP Gateway Deployment Script
# Deploys the gateway in HTTP mode for remote isolation

set -e

# Configuration
GATEWAY_HOST="${GATEWAY_HOST:-0.0.0.0}"
GATEWAY_PORT="${GATEWAY_PORT:-8080}"
REPO_PATH="${REPO_PATH:-/repo/rlm-kit}"
API_KEY="${RLM_GATEWAY_API_KEY:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}RLM MCP Gateway Deployment${NC}"
echo "================================"

# Check if API key is set
if [ -z "$API_KEY" ]; then
    echo -e "${YELLOW}WARNING: RLM_GATEWAY_API_KEY not set. Authentication will be disabled.${NC}"
    echo -e "${YELLOW}This is not recommended for production.${NC}"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

# Check if repo path exists
if [ ! -d "$REPO_PATH" ]; then
    echo -e "${RED}ERROR: Repository path does not exist: $REPO_PATH${NC}"
    exit 1
fi

# Check if gateway dependencies are installed
echo "Checking dependencies..."
if ! python -c "import fastapi, uvicorn" 2>/dev/null; then
    echo -e "${YELLOW}FastAPI/uvicorn not found. Installing...${NC}"
    pip install fastapi uvicorn || {
        echo -e "${RED}ERROR: Failed to install dependencies${NC}"
        exit 1
    }
fi

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GATEWAY_SCRIPT="$SCRIPT_DIR/rlm_mcp_gateway.py"

if [ ! -f "$GATEWAY_SCRIPT" ]; then
    echo -e "${RED}ERROR: Gateway script not found: $GATEWAY_SCRIPT${NC}"
    exit 1
fi

# Build command
CMD="python $GATEWAY_SCRIPT --mode http --host $GATEWAY_HOST --port $GATEWAY_PORT --repo-path $REPO_PATH"

if [ -n "$API_KEY" ]; then
    CMD="$CMD --api-key $API_KEY"
fi

echo ""
echo -e "${GREEN}Starting RLM MCP Gateway...${NC}"
echo "Host: $GATEWAY_HOST"
echo "Port: $GATEWAY_PORT"
echo "Repository: $REPO_PATH"
if [ -n "$API_KEY" ]; then
    echo "Authentication: ENABLED"
else
    echo "Authentication: DISABLED"
fi
echo ""
echo "Command: $CMD"
echo ""

# Run gateway
exec $CMD
