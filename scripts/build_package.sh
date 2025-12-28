#!/bin/bash
# Build update package script with offline wheels support

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Default values
MANIFEST=""
OUTPUT=""
DOCKER_DIR=""
SERVICE_DIR=""
WHEELS_DIR="./wheels"
INCLUDE_ENGINE=false

# Function to show usage
show_usage() {
    echo "Usage: $0 --manifest <manifest.yml> --output <file> [options]"
    echo ""
    echo "Required arguments:"
    echo "  --manifest <file>      Path to manifest.yml"
    echo "  --output <file>        Output filename (e.g., update-1.0.0.tar.gz)"
    echo ""
    echo "Optional arguments:"
    echo "  --docker <dir>         Directory containing Docker images (.tar files)"
    echo "  --service <dir>        Service backend directory"
    echo "  --wheels <dir>         Wheels directory (default: ./wheels)"
    echo "  --include-engine       Include update_engine in package"
    echo ""
    echo "Example:"
    echo "  $0 \\"
    echo "    --manifest examples/full-system/manifest.yml \\"
    echo "    --docker /path/to/docker-images/ \\"
    echo "    --service /path/to/service-backend/ \\"
    echo "    --wheels ./wheels \\"
    echo "    --output maritime-update-1.0.0.tar.gz"
    echo ""
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --manifest)
            MANIFEST="$2"
            shift 2
            ;;
        --output)
            OUTPUT="$2"
            shift 2
            ;;
        --docker)
            DOCKER_DIR="$2"
            shift 2
            ;;
        --service)
            SERVICE_DIR="$2"
            shift 2
            ;;
        --wheels)
            WHEELS_DIR="$2"
            shift 2
            ;;
        --include-engine)
            INCLUDE_ENGINE=true
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            echo -e "${RED}Error: Unknown option: $1${NC}"
            echo ""
            show_usage
            exit 1
            ;;
    esac
done

# Convert OUTPUT to absolute path if relative
# This prevents the output file from being created in temp build directory
if [ -n "$OUTPUT" ] && [[ "$OUTPUT" != /* ]]; then
    # Convert to absolute path
    OUTPUT_DIR="$(cd "$(dirname "$OUTPUT")" 2>/dev/null && pwd)" || OUTPUT_DIR="$(pwd)"
    OUTPUT="$OUTPUT_DIR/$(basename "$OUTPUT")"
fi

# Validate required arguments
if [ -z "$MANIFEST" ]; then
    echo -e "${RED}Error: --manifest is required${NC}"
    echo ""
    show_usage
    exit 1
fi

if [ -z "$OUTPUT" ]; then
    echo -e "${RED}Error: --output is required${NC}"
    echo ""
    show_usage
    exit 1
fi

if [ ! -f "$MANIFEST" ]; then
    echo -e "${RED}Error: Manifest file not found: $MANIFEST${NC}"
    exit 1
fi

# Print header
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}           Building Update Package${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}Manifest:${NC} $MANIFEST"
echo -e "${GREEN}Output:${NC} $OUTPUT"
echo ""

# Create temporary build directory
BUILD_DIR=$(mktemp -d)
trap "rm -rf $BUILD_DIR" EXIT

echo -e "${YELLOW}Build directory: ${BUILD_DIR}${NC}"
echo ""

# Copy manifest
echo -e "${GREEN}📄 Copying manifest...${NC}"
cp "$MANIFEST" "$BUILD_DIR/manifest.yml"
echo "   ✓ manifest.yml"

# Copy Docker images if specified
if [ -n "$DOCKER_DIR" ] && [ -d "$DOCKER_DIR" ]; then
    echo ""
    echo -e "${GREEN}🐳 Copying Docker images from ${DOCKER_DIR}...${NC}"
    mkdir -p "$BUILD_DIR/docker"
    
    # Copy .tar files
    TAR_COUNT=0
    for tar_file in "$DOCKER_DIR"/*.tar; do
        if [ -f "$tar_file" ]; then
            cp "$tar_file" "$BUILD_DIR/docker/"
            echo "   ✓ $(basename "$tar_file")"
            ((TAR_COUNT++))
        fi
    done
    
    # Copy docker-compose.yml if exists
    if [ -f "$DOCKER_DIR/docker-compose.yml" ]; then
        cp "$DOCKER_DIR/docker-compose.yml" "$BUILD_DIR/docker/"
        echo "   ✓ docker-compose.yml"
    fi
    
    if [ $TAR_COUNT -eq 0 ]; then
        echo -e "   ${YELLOW}⚠ No .tar files found${NC}"
    else
        echo -e "   ${GREEN}Total: $TAR_COUNT image(s)${NC}"
    fi
elif [ -n "$DOCKER_DIR" ]; then
    echo -e "${YELLOW}⚠ Docker directory not found: $DOCKER_DIR${NC}"
fi

# Copy service backend if specified
if [ -n "$SERVICE_DIR" ] && [ -d "$SERVICE_DIR" ]; then
    echo ""
    echo -e "${GREEN}🚀 Copying service backend from ${SERVICE_DIR}...${NC}"
    mkdir -p "$BUILD_DIR/service-backend"
    cp -r "$SERVICE_DIR"/* "$BUILD_DIR/service-backend/"
    
    FILE_COUNT=$(find "$BUILD_DIR/service-backend" -type f | wc -l)
    echo -e "   ${GREEN}Total: $FILE_COUNT file(s)${NC}"
elif [ -n "$SERVICE_DIR" ]; then
    echo -e "${YELLOW}⚠ Service directory not found: $SERVICE_DIR${NC}"
fi

# Copy wheels if specified
if [ -n "$WHEELS_DIR" ] && [ -d "$WHEELS_DIR" ]; then
    echo ""
    echo -e "${GREEN}📦 Copying Python wheels from ${WHEELS_DIR}...${NC}"
    mkdir -p "$BUILD_DIR/wheels"
    
    # Copy ALL wheel files at once
    if ls "$WHEELS_DIR"/*.whl 1> /dev/null 2>&1; then
        cp "$WHEELS_DIR"/*.whl "$BUILD_DIR/wheels/" 2>/dev/null
        WHEEL_COUNT=$(find "$BUILD_DIR/wheels" -name "*.whl" | wc -l)
        echo -e "   ${GREEN}✓ Copied $WHEEL_COUNT wheel(s)${NC}"
    else
        echo -e "   ${YELLOW}⚠ No .whl files found in $WHEELS_DIR${NC}"
    fi
elif [ -n "$WHEELS_DIR" ]; then
    echo -e "${YELLOW}⚠ Wheels directory not found: $WHEELS_DIR${NC}"
fi

# Include engine if requested
if [ "$INCLUDE_ENGINE" = true ]; then
    echo ""
    echo -e "${GREEN}⚙️  Including update engine...${NC}"
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    SRC_DIR="$(dirname "$SCRIPT_DIR")/src"
    
    if [ -d "$SRC_DIR/update_engine" ]; then
        cp -r "$SRC_DIR/update_engine" "$BUILD_DIR/"
        
        # Create CHECKSUM file for engine
        echo "   Creating engine CHECKSUM..."
        (
            cd "$BUILD_DIR/update_engine"
            find . -type f -name "*.py" -exec md5sum {} \; | sed 's|^\./||' > CHECKSUM
        )
        
        PY_COUNT=$(find "$BUILD_DIR/update_engine" -name "*.py" | wc -l)
        echo -e "   ${GREEN}✓ Engine included ($PY_COUNT Python files)${NC}"
    else
        echo -e "   ${RED}✗ Engine source not found at $SRC_DIR/update_engine${NC}"
    fi
fi

# Generate checksums for all files
echo ""
echo -e "${GREEN}🔒 Generating checksums...${NC}"
(
    cd "$BUILD_DIR"
    find . -type f ! -name "checksums.md5" ! -name "CHECKSUM" -exec md5sum {} \; | sed 's|^\./||' | sort > checksums.md5
)

CHECKSUM_COUNT=$(wc -l < "$BUILD_DIR/checksums.md5")
echo -e "   ${GREEN}✓ Checksums generated: $CHECKSUM_COUNT files${NC}"

# Create package
echo ""
echo -e "${GREEN}📦 Creating package...${NC}"
tar -czf "$OUTPUT" -C "$BUILD_DIR" .

# Get package size
if command -v stat &> /dev/null; then
    PACKAGE_SIZE=$(stat -f%z "$OUTPUT" 2>/dev/null || stat -c%s "$OUTPUT" 2>/dev/null)
    PACKAGE_SIZE_MB=$(echo "scale=2; $PACKAGE_SIZE / 1024 / 1024" | bc 2>/dev/null || echo "N/A")
else
    PACKAGE_SIZE_MB="N/A"
fi

# Print summary
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Package built successfully!${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}Output:${NC} $OUTPUT"
if [ "$PACKAGE_SIZE_MB" != "N/A" ]; then
    echo -e "${GREEN}Size:${NC} ${PACKAGE_SIZE_MB} MB"
fi
echo ""

# Show package structure
echo -e "${YELLOW}Package structure:${NC}"
tar -tzf "$OUTPUT" | head -30 | while read line; do
    if [[ "$line" == */ ]]; then
        echo -e "  ${BLUE}📁 $line${NC}"
    else
        echo -e "  📄 $line"
    fi
done

TOTAL_FILES=$(tar -tzf "$OUTPUT" | wc -l)
if [ $TOTAL_FILES -gt 30 ]; then
    echo -e "  ${YELLOW}... ($TOTAL_FILES total entries)${NC}"
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}📋 Installation Instructions${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo "Via CLI:"
echo -e "  ${YELLOW}update-bootstrap $OUTPUT${NC}"
echo ""
echo "Via Web UI:"
echo -e "  ${YELLOW}http://localhost:8123${NC}"
echo ""
echo "Manual extraction:"
echo -e "  ${YELLOW}tar -xzf $OUTPUT${NC}"
echo ""
