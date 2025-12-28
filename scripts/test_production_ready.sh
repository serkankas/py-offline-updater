#!/bin/bash
# Production readiness test script

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}     py-offline-updater Production Readiness Test${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Test 1: Download wheels
echo -e "${GREEN}Test 1: Downloading wheels...${NC}"
./scripts/download_wheels.sh
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Wheels downloaded${NC}"
else
    echo -e "${RED}✗ Failed to download wheels${NC}"
    exit 1
fi
echo ""

# Test 2: Count wheels
echo -e "${GREEN}Test 2: Verifying wheel count...${NC}"
WHEEL_COUNT=$(find wheels -name "*.whl" 2>/dev/null | wc -l)
echo "Found $WHEEL_COUNT wheel files"
if [ $WHEEL_COUNT -ge 10 ]; then
    echo -e "${GREEN}✓ Sufficient wheels ($WHEEL_COUNT >= 10)${NC}"
else
    echo -e "${RED}✗ Insufficient wheels ($WHEEL_COUNT < 10)${NC}"
    exit 1
fi
echo ""

# Test 3: Check critical wheels
echo -e "${GREEN}Test 3: Checking critical engine dependencies...${NC}"
CRITICAL_PKGS=("requests" "urllib3" "certifi" "charset-normalizer" "pyyaml")
ALL_FOUND=true
for pkg in "${CRITICAL_PKGS[@]}"; do
    if ls wheels/${pkg}*.whl 1> /dev/null 2>&1; then
        echo -e "   ${GREEN}✓${NC} $pkg"
    else
        echo -e "   ${RED}✗${NC} $pkg (MISSING!)"
        ALL_FOUND=false
    fi
done

if [ "$ALL_FOUND" = true ]; then
    echo -e "${GREEN}✓ All critical dependencies present${NC}"
else
    echo -e "${RED}✗ Missing critical dependencies${NC}"
    exit 1
fi
echo ""

# Test 4: Create test package
echo -e "${GREEN}Test 4: Creating test package...${NC}"
./scripts/create_test_package.sh
if [ $? -eq 0 ] && [ -f "test-update.tar.gz" ]; then
    echo -e "${GREEN}✓ Test package created${NC}"
else
    echo -e "${RED}✗ Failed to create test package${NC}"
    exit 1
fi
echo ""

# Test 5: Verify package contents
echo -e "${GREEN}Test 5: Verifying package contents...${NC}"
WHEELS_IN_PKG=$(tar -tzf test-update.tar.gz | grep -c "wheels/.*\.whl$" || echo "0")
echo "Wheels in package: $WHEELS_IN_PKG"
if [ $WHEELS_IN_PKG -ge 10 ]; then
    echo -e "${GREEN}✓ Package contains wheels ($WHEELS_IN_PKG)${NC}"
else
    echo -e "${RED}✗ Package missing wheels ($WHEELS_IN_PKG)${NC}"
    exit 1
fi
echo ""

# Test 6: Check manifest in package
echo -e "${GREEN}Test 6: Checking manifest in package...${NC}"
if tar -tzf test-update.tar.gz | grep -q "manifest.yml"; then
    echo -e "${GREEN}✓ Manifest present${NC}"
else
    echo -e "${RED}✗ Manifest missing${NC}"
    exit 1
fi
echo ""

# Test 7: Check checksums
echo -e "${GREEN}Test 7: Checking checksums file...${NC}"
if tar -tzf test-update.tar.gz | grep -q "checksums.md5"; then
    echo -e "${GREEN}✓ Checksums file present${NC}"
else
    echo -e "${RED}✗ Checksums file missing${NC}"
    exit 1
fi
echo ""

# Test 8: Verify source structure
echo -e "${GREEN}Test 8: Verifying source structure...${NC}"
CHECKS=0
PASSED=0

if [ -d "src/update_engine" ]; then
    echo -e "   ${GREEN}✓${NC} src/update_engine exists"
    ((CHECKS++))
    ((PASSED++))
else
    echo -e "   ${RED}✗${NC} src/update_engine missing"
    ((CHECKS++))
fi

if [ -f "src/bootstrap.py" ]; then
    echo -e "   ${GREEN}✓${NC} src/bootstrap.py exists"
    ((CHECKS++))
    ((PASSED++))
else
    echo -e "   ${RED}✗${NC} src/bootstrap.py missing"
    ((CHECKS++))
fi

if [ -f "src/update_engine/requirements.txt" ]; then
    echo -e "   ${GREEN}✓${NC} src/update_engine/requirements.txt exists"
    ((CHECKS++))
    ((PASSED++))
else
    echo -e "   ${RED}✗${NC} src/update_engine/requirements.txt missing"
    ((CHECKS++))
fi

if [ $PASSED -eq $CHECKS ]; then
    echo -e "${GREEN}✓ Source structure valid ($PASSED/$CHECKS)${NC}"
else
    echo -e "${RED}✗ Source structure incomplete ($PASSED/$CHECKS)${NC}"
    exit 1
fi
echo ""

# Test 9: Extract and validate manifest
echo -e "${GREEN}Test 9: Validating test manifest...${NC}"
tar -xzf test-update.tar.gz manifest.yml -O > /tmp/test_manifest.yml 2>/dev/null
if grep -q "Install engine dependencies" /tmp/test_manifest.yml; then
    echo -e "${GREEN}✓ Engine dependencies action present${NC}"
else
    echo -e "${RED}✗ Engine dependencies action missing${NC}"
    exit 1
fi
rm -f /tmp/test_manifest.yml
echo ""

# Final summary
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ ALL PRODUCTION READINESS TESTS PASSED!${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Package ready for deployment:${NC}"
echo -e "  File: test-update.tar.gz"
echo -e "  Size: $(du -h test-update.tar.gz | cut -f1)"
echo -e "  Wheels: $WHEELS_IN_PKG"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo -e "1. Copy to device:"
echo -e "   ${BLUE}scp test-update.tar.gz root@DEVICE:/tmp/${NC}"
echo -e "   ${BLUE}scp -r src/ scripts/ root@DEVICE:/tmp/framework/${NC}"
echo ""
echo -e "2. On device, install:"
echo -e "   ${BLUE}cd /tmp/framework/scripts${NC}"
echo -e "   ${BLUE}sudo ./install.sh --base-dir /app/app/update${NC}"
echo ""
echo -e "3. Apply update:"
echo -e "   ${BLUE}update-bootstrap /tmp/test-update.tar.gz${NC}"
echo ""

