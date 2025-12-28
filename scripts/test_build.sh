#!/bin/bash
# Test that build system works correctly

set -e

echo "======================================"
echo "Testing Build System"
echo "======================================"

# Clean
rm -rf wheels/ test-update.tar.gz test_manifest.yml

# Download wheels
echo "1. Testing download_wheels.sh..."
./scripts/download_wheels.sh

# Verify wheels downloaded
WHEEL_COUNT=$(find wheels -name "*.whl" 2>/dev/null | wc -l)
if [ $WHEEL_COUNT -lt 10 ]; then
    echo "❌ FAIL: Only $WHEEL_COUNT wheels downloaded, expected 10+"
    exit 1
fi
echo "✅ PASS: $WHEEL_COUNT wheels downloaded"

# Check critical wheels
for pkg in requests urllib3 certifi pyyaml; do
    if ! ls wheels/ | grep -qi "$pkg"; then
        echo "❌ FAIL: Missing critical wheel: $pkg"
        exit 1
    fi
done
echo "✅ PASS: All critical wheels present"

# Build package
echo ""
echo "2. Testing create_test_package.sh..."
./scripts/create_test_package.sh

# Verify package created
if [ ! -f test-update.tar.gz ]; then
    echo "❌ FAIL: Package not created"
    exit 1
fi
echo "✅ PASS: Package created"

# Verify wheels in package
PACKAGED_WHEELS=$(tar -tzf test-update.tar.gz | grep -c "\.whl$" || echo 0)
if [ $PACKAGED_WHEELS -lt 10 ]; then
    echo "❌ FAIL: Only $PACKAGED_WHEELS wheels in package"
    exit 1
fi
echo "✅ PASS: $PACKAGED_WHEELS wheels in package"

# Verify manifest
if ! tar -tzf test-update.tar.gz | grep -q "manifest.yml"; then
    echo "❌ FAIL: No manifest.yml in package"
    exit 1
fi
echo "✅ PASS: manifest.yml present"

# Verify checksums
if ! tar -tzf test-update.tar.gz | grep -q "checksums.md5"; then
    echo "❌ FAIL: No checksums.md5 in package"
    exit 1
fi
echo "✅ PASS: checksums.md5 present"

echo ""
echo "======================================"
echo "✅ ALL BUILD TESTS PASSED"
echo "======================================"

