#!/bin/bash
# Test that installation works

set -e

TEST_DIR="/tmp/updater-test-$$"
BASE_DIR="$TEST_DIR/install"

echo "======================================"
echo "Testing Installation"
echo "======================================"

# Setup
mkdir -p "$TEST_DIR"
trap "rm -rf $TEST_DIR" EXIT

# Test install (as non-root, skip service)
echo "1. Testing install.sh..."
sudo ./scripts/install.sh --base-dir "$BASE_DIR" --no-service

# Verify structure
echo ""
echo "2. Verifying installation structure..."

REQUIRED_DIRS=(
    "$BASE_DIR/update-engines/v1.0.0/update_engine"
    "$BASE_DIR/bootstrap"
)

for dir in "${REQUIRED_DIRS[@]}"; do
    if [ ! -d "$dir" ]; then
        echo "❌ FAIL: Missing directory: $dir"
        exit 1
    fi
done
echo "✅ PASS: Directory structure correct"

# Verify engine files
if [ ! -f "$BASE_DIR/update-engines/v1.0.0/update_engine/engine.py" ]; then
    echo "❌ FAIL: Engine files not in update_engine/ subdirectory"
    exit 1
fi
echo "✅ PASS: Engine files in correct location"

# Verify all engine files
ENGINE_FILES=("__init__.py" "engine.py" "actions.py" "checks.py" "backup.py" "state.py" "utils.py" "requirements.txt")
for file in "${ENGINE_FILES[@]}"; do
    if [ ! -f "$BASE_DIR/update-engines/v1.0.0/update_engine/$file" ]; then
        echo "❌ FAIL: Missing engine file: $file"
        exit 1
    fi
done
echo "✅ PASS: All engine files present"

# Verify symlink
if [ ! -L "$BASE_DIR/update-engines/current" ]; then
    echo "❌ FAIL: current symlink missing"
    exit 1
fi
echo "✅ PASS: current symlink exists"

# Verify CHECKSUM
if [ ! -f "$BASE_DIR/update-engines/v1.0.0/CHECKSUM" ]; then
    echo "❌ FAIL: CHECKSUM missing"
    exit 1
fi

# Verify CHECKSUM has update_engine/ prefix
if ! grep -q "update_engine/" "$BASE_DIR/update-engines/v1.0.0/CHECKSUM"; then
    echo "❌ FAIL: CHECKSUM doesn't have update_engine/ prefix"
    exit 1
fi
echo "✅ PASS: CHECKSUM created correctly"

# Verify bootstrap
if [ ! -f "$BASE_DIR/bootstrap/bootstrap.py" ]; then
    echo "❌ FAIL: bootstrap.py missing"
    exit 1
fi
echo "✅ PASS: bootstrap.py installed"

# Check if wrapper was created
WRAPPER_FOUND=false
for wrapper_path in "/usr/local/bin/update-bootstrap" "/usr/bin/update-bootstrap" "$BASE_DIR/bin/update-bootstrap"; do
    if [ -f "$wrapper_path" ]; then
        echo "✅ PASS: Wrapper found at $wrapper_path"
        WRAPPER_FOUND=true
        
        # Verify wrapper has PYTHONPATH
        if grep -q "PYTHONPATH" "$wrapper_path"; then
            echo "✅ PASS: Wrapper contains PYTHONPATH"
        else
            echo "❌ FAIL: Wrapper missing PYTHONPATH"
            exit 1
        fi
        break
    fi
done

if [ "$WRAPPER_FOUND" = false ]; then
    echo "⚠️  WARNING: Wrapper not found (might need sudo)"
fi

echo ""
echo "======================================"
echo "✅ ALL INSTALL TESTS PASSED"
echo "======================================"

