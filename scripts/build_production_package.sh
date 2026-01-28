#!/bin/bash
# Build production update package from deployment zip

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check arguments
if [ -z "$1" ]; then
    echo -e "${RED}Usage: $0 <deployment-zip>${NC}"
    echo ""
    echo "Example:"
    echo "  $0 rcu-deployment-v1.7.3-v1.3.2-v1.0.2-arm64.zip"
    exit 1
fi

DEPLOYMENT_ZIP="$1"

if [ ! -f "$DEPLOYMENT_ZIP" ]; then
    echo -e "${RED}Error: File not found: $DEPLOYMENT_ZIP${NC}"
    exit 1
fi

echo -e "${GREEN}Building production update package...${NC}"
echo "Source: $DEPLOYMENT_ZIP"
echo ""

# Create temp directory
TEMP_DIR=$(mktemp -d)

# Extract deployment zip
echo "Extracting deployment package..."
unzip -q "$DEPLOYMENT_ZIP" -d "$TEMP_DIR"

echo -e "${GREEN}✓ Extracted${NC}"
echo ""

# Verify required directories
echo "Verifying package contents..."

if [ ! -d "$TEMP_DIR/RCU_Deploy" ]; then
    echo -e "${RED}Error: Missing RCU_Deploy/ directory${NC}"
    rm -rf "$TEMP_DIR"
    exit 1
fi

if [ ! -d "$TEMP_DIR/RCU_Service" ]; then
    echo -e "${RED}Error: Missing RCU_Service/ directory${NC}"
    rm -rf "$TEMP_DIR"
    exit 1
fi

if [ ! -f "$TEMP_DIR/RCU_Deploy/docker-compose.yml" ]; then
    echo -e "${RED}Error: docker-compose.yml not found in RCU_Deploy/${NC}"
    rm -rf "$TEMP_DIR"
    exit 1
fi

if [ ! -f "$TEMP_DIR/RCU_Service/requirements.txt" ]; then
    echo -e "${RED}Error: requirements.txt not found in RCU_Service/${NC}"
    rm -rf "$TEMP_DIR"
    exit 1
fi

# Check for docker images
BACKEND_TAR=$(find "$TEMP_DIR/RCU_Deploy" -name "rcu-backend-*.tar" | head -1)
FRONTEND_TAR=$(find "$TEMP_DIR/RCU_Deploy" -name "rcu-frontend-*.tar" | head -1)

if [ -z "$BACKEND_TAR" ]; then
    echo -e "${RED}Error: No backend docker image found (rcu-backend-*.tar)${NC}"
    rm -rf "$TEMP_DIR"
    exit 1
fi

if [ -z "$FRONTEND_TAR" ]; then
    echo -e "${RED}Error: No frontend docker image found (rcu-frontend-*.tar)${NC}"
    rm -rf "$TEMP_DIR"
    exit 1
fi

echo -e "${GREEN}✓ Package structure verified${NC}"
echo ""

# Create .env file if not exists
if [ ! -f "$TEMP_DIR/RCU_Service/.env" ]; then
    echo "Creating .env file..."
    cat > "$TEMP_DIR/RCU_Service/.env" << 'EOF'
DEBUG=0

HOST=0.0.0.0
PORT=8001

VDR_TCP_PORT=7000
VDR_TCP_HOST=0.0.0.0

WATCHDOG_ENABLED=1
WATCHDOG_KICK_INTERVAL=3
WATCHDOG_BOOT_GRACE_PERIOD=120

RCU_BACKEND_URL=http://localhost:8000
RCU_HEALTH_CHECK_INTERVAL=10
RCU_HEALTH_CHECK_TIMEOUT=5

DOCKER_COMPOSE_PATH=/app/app/docker-files
EOF
    echo -e "${GREEN}✓ .env file created${NC}"
else
    echo -e "${GREEN}✓ .env file already exists${NC}"
fi

echo ""

# Generate output filename (absolute path)
if [[ "$DEPLOYMENT_ZIP" = /* ]]; then
    OUTPUT="${DEPLOYMENT_ZIP%.zip}-update.tar.gz"
else
    OUTPUT="$(pwd)/${DEPLOYMENT_ZIP%.zip}-update.tar.gz"
fi

# Build update package
echo "Building update package..."
echo ""

cd "$TEMP_DIR"

# Create manifest copy
cp "$PROJECT_ROOT/examples/production-system/manifest.yml" manifest.yml

# Generate checksums
echo "Generating checksums..."
find . -type f ! -name checksums.md5 -exec md5sum {} \; | sort > checksums.md5

# Create tar.gz
tar -czf "$OUTPUT" -C . .

# Cleanup
rm -rf "$TEMP_DIR"

# Verify output
if [ ! -f "$OUTPUT" ]; then
    echo -e "${RED}Error: Failed to create update package${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Production update package ready!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Package: $OUTPUT${NC}"
echo -e "${YELLOW}Size: $(du -h "$OUTPUT" | cut -f1)${NC}"
echo ""
echo -e "${YELLOW}Deploy to device:${NC}"
echo "  scp $OUTPUT root@DEVICE_IP:/tmp/"
echo "  ssh root@DEVICE_IP"
echo "  update-bootstrap /tmp/$(basename "$OUTPUT")"
echo ""
echo -e "${YELLOW}Or via Web UI:${NC}"
echo "  http://DEVICE_IP:8123"
echo ""
echo -e "${RED}⚠️  IMPORTANT: Manually reboot device after update completes!${NC}"
echo ""
