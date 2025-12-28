#!/bin/bash
# Create test update package for quick testing

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Output file
OUTPUT="test-update.tar.gz"

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}          Creating Test Update Package${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Step 1: Download wheels
echo -e "${GREEN}📦 Step 1: Downloading Python wheels...${NC}"
echo ""

if [ ! -d "$PROJECT_ROOT/wheels" ] || [ -z "$(ls -A "$PROJECT_ROOT/wheels" 2>/dev/null)" ]; then
    echo -e "${YELLOW}Wheels directory is empty or doesn't exist. Downloading...${NC}"
    "$SCRIPT_DIR/download_wheels.sh"
else
    WHEEL_COUNT=$(find "$PROJECT_ROOT/wheels" -name "*.whl" 2>/dev/null | wc -l)
    echo -e "${GREEN}✓ Wheels directory exists with $WHEEL_COUNT wheel(s)${NC}"
    echo -e "${YELLOW}Skipping download. Delete ./wheels to re-download.${NC}"
fi

echo ""

# Step 2: Create test manifest
echo -e "${GREEN}📝 Step 2: Creating test manifest...${NC}"

TEST_MANIFEST="$PROJECT_ROOT/test_manifest.yml"
CURRENT_DATE=$(date +%Y-%m-%d)

cat > "$TEST_MANIFEST" << 'EOF'
description: "Wheel installation test"
date: "CURRENT_DATE_PLACEHOLDER"
required_engine_version: "1.0.0"

pre_checks:
  - type: disk_space
    path: /tmp
    required_mb: 100

actions:
  # CRITICAL: Install engine dependencies first
  - name: "Install engine dependencies"
    type: command
    command: "pip3 install --no-index --find-links=wheels/ requests urllib3 certifi charset-normalizer --break-system-packages"
    timeout: 300
    continue_on_error: false
  
  - name: "Install application dependencies"
    type: command
    command: "pip3 install --no-index --find-links=wheels/ pyyaml sse-starlette python-dotenv --break-system-packages"
    timeout: 300
    continue_on_error: false

post_checks:
  - type: command
    command: "python3 -c 'import yaml; import dotenv; import requests; print(\"✓ All packages imported successfully\")'"
    timeout: 10

rollback:
  enabled: false

cleanup:
  remove_old_backups: false
  remove_temp_files: true
EOF

# Replace date placeholder
sed -i "s/CURRENT_DATE_PLACEHOLDER/$CURRENT_DATE/g" "$TEST_MANIFEST"

echo -e "${GREEN}✓ Test manifest created: $TEST_MANIFEST${NC}"
echo ""

# Step 3: Build package
echo -e "${GREEN}📦 Step 3: Building test package...${NC}"
echo ""

"$SCRIPT_DIR/build_package.sh" \
    --manifest "$TEST_MANIFEST" \
    --wheels "$PROJECT_ROOT/wheels" \
    --output "$PROJECT_ROOT/$OUTPUT"

# Cleanup temporary manifest
rm -f "$TEST_MANIFEST"

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Test package created successfully!${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}Package:${NC} $OUTPUT"
echo ""

# Show package contents
echo -e "${YELLOW}Package contents:${NC}"
tar -tzf "$PROJECT_ROOT/$OUTPUT" | head -20
TOTAL_FILES=$(tar -tzf "$PROJECT_ROOT/$OUTPUT" | wc -l)
if [ $TOTAL_FILES -gt 20 ]; then
    echo -e "${YELLOW}... ($TOTAL_FILES total files)${NC}"
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}🚀 Testing Instructions${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo "1. Extract and inspect:"
echo -e "   ${YELLOW}tar -tzf $OUTPUT${NC}"
echo ""
echo "2. Test with bootstrap:"
echo -e "   ${YELLOW}sudo python3 src/bootstrap.py $OUTPUT${NC}"
echo ""
echo "3. Test via Web UI:"
echo -e "   ${YELLOW}http://localhost:8123${NC}"
echo -e "   Upload: ${YELLOW}$OUTPUT${NC}"
echo ""
echo "4. Verify installation:"
echo -e "   ${YELLOW}python3 -c 'import yaml; import dotenv; print(\"Success!\")'${NC}"
echo ""
echo -e "${GREEN}Expected behavior:${NC}"
echo "  • Pre-check: Disk space verification"
echo "  • Action: Install wheels offline (no internet needed)"
echo "  • Post-check: Import test for installed packages"
echo "  • Result: pyyaml, sse-starlette, python-dotenv installed"
echo ""

