#!/bin/bash
# Download Python wheels for offline installation
# Platform: ARM64 Linux (manylinux2014_aarch64)
# Python: 3.12

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}    Python Wheels Downloader for Offline Installation${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}Target Platform:${NC} ARM64 Linux (manylinux2014_aarch64)"
echo -e "${GREEN}Python Version:${NC} 3.12"
echo ""

# Create wheels directory
WHEELS_DIR="wheels"
echo -e "${YELLOW}Creating wheels directory...${NC}"
mkdir -p "$WHEELS_DIR"

# Platform and Python version
PLATFORM="manylinux2014_aarch64"
PYTHON_VERSION="312"
ABI="cp312"

# Packages to download
PACKAGES=(
    "pyyaml>=6.0"
    "sse-starlette>=1.8"
    "python-dotenv>=1.0"
    "requests>=2.31"
    "urllib3>=2.0"
    "certifi>=2023.7.22"
    "charset-normalizer>=3.0"
)

echo -e "${YELLOW}Downloading packages with all dependencies...${NC}"
echo ""

# Download each package with all dependencies
for package in "${PACKAGES[@]}"; do
    echo -e "${GREEN}Downloading: ${package}${NC}"
    pip download \
        --dest "$WHEELS_DIR" \
        --platform "$PLATFORM" \
        --python-version "$PYTHON_VERSION" \
        --abi "$ABI" \
        --only-binary=:all: \
        "$package"
    echo ""
done

# Also download universal wheels (pure Python packages)
echo -e "${YELLOW}Downloading universal/pure Python wheels...${NC}"
for package in "${PACKAGES[@]}"; do
    pip download \
        --dest "$WHEELS_DIR" \
        --platform any \
        --python-version "$PYTHON_VERSION" \
        --no-deps \
        "$package" 2>/dev/null || true
done

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Download completed!${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""

# List downloaded wheels
WHEEL_COUNT=$(find "$WHEELS_DIR" -name "*.whl" | wc -l)
echo -e "${GREEN}Total wheels downloaded: ${WHEEL_COUNT}${NC}"
echo ""
echo -e "${YELLOW}Downloaded wheels:${NC}"
find "$WHEELS_DIR" -name "*.whl" -exec basename {} \; | sort

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Installation Instructions:${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""
echo "On the target ARM64 system, run:"
echo -e "${YELLOW}  pip install --no-index --find-links=wheels/ pyyaml sse-starlette python-dotenv${NC}"
echo ""
echo "Or install all wheels:"
echo -e "${YELLOW}  pip install --no-index --find-links=wheels/ wheels/*.whl${NC}"
echo ""

# Calculate total size
TOTAL_SIZE=$(du -sh "$WHEELS_DIR" | cut -f1)
echo -e "${GREEN}Total size:${NC} $TOTAL_SIZE"
echo ""

