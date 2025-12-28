#!/bin/bash
# Run all tests

set -e

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║              Running Full Test Suite                         ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# Test 1: Build system
echo "📦 TEST SUITE 1: Build System"
echo "────────────────────────────────────────────────────────────────"
./scripts/test_build.sh
echo ""

# Test 2: Installation
echo "⚙️  TEST SUITE 2: Installation"
echo "────────────────────────────────────────────────────────────────"
./scripts/test_install.sh

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║          🎉 ALL TESTS PASSED - PRODUCTION READY              ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo "✅ Build system verified"
echo "✅ Installation structure verified"
echo "✅ Engine location verified"
echo "✅ All dependencies included"
echo ""
echo "📋 Next steps for deployment:"
echo "────────────────────────────────────────────────────────────────"
echo "1. Copy files to device:"
echo "   scp test-update.tar.gz root@DEVICE:/tmp/"
echo "   scp -r src/ scripts/ root@DEVICE:/tmp/framework/"
echo ""
echo "2. SSH to device:"
echo "   ssh root@DEVICE"
echo ""
echo "3. Install framework:"
echo "   cd /tmp/framework/scripts"
echo "   sudo ./install.sh --base-dir /app/app/update"
echo ""
echo "4. Apply update:"
echo "   update-bootstrap /tmp/test-update.tar.gz"
echo ""

