#!/bin/bash
# Installation script for py-offline-updater

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Default values
BASE_DIR="/opt/updater"
ENGINE_VERSION="1.0.0"
INSTALL_SERVICE=true
START_SERVICE=false

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --base-dir <path>      Installation directory (default: /opt/updater)"
    echo "  --no-service           Skip web service installation"
    echo "  --start-service        Automatically start service after installation"
    echo "  -h, --help            Show this help message"
    echo ""
    echo "Example:"
    echo "  sudo $0 --base-dir /opt/updater"
    echo ""
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --base-dir)
            BASE_DIR="$2"
            shift 2
            ;;
        --no-service)
            INSTALL_SERVICE=false
            shift
            ;;
        --start-service)
            START_SERVICE=true
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

# Print header
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}        py-offline-updater Installation${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}Base directory:${NC} $BASE_DIR"
echo -e "${GREEN}Engine version:${NC} $ENGINE_VERSION"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: This script must be run as root (use sudo)${NC}"
    exit 1
fi

# Find script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Try to find project root (handle both cases)
if [ -d "$SCRIPT_DIR/../src" ]; then
    # Called from scripts/ subdirectory
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
elif [ -d "$SCRIPT_DIR/src" ]; then
    # Script copied to project root or framework dir
    PROJECT_ROOT="$SCRIPT_DIR"
else
    echo -e "${RED}Error: Cannot find src/ directory${NC}"
    echo "Looked in: $SCRIPT_DIR/../src and $SCRIPT_DIR/src"
    exit 1
fi

# Source directories (relative to project root)
ENGINE_SRC="$PROJECT_ROOT/src/update_engine"
BOOTSTRAP_SRC="$PROJECT_ROOT/src/bootstrap.py"
SERVICE_SRC="$PROJECT_ROOT/src/update_service"
REQUIREMENTS_FILE="$PROJECT_ROOT/requirements.txt"

# Validate sources exist
echo -e "${YELLOW}Validating source files...${NC}"
echo "Project root: $PROJECT_ROOT"

if [ ! -d "$ENGINE_SRC" ]; then
    echo -e "${RED}Error: Engine source not found at $ENGINE_SRC${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Engine source found"

if [ ! -f "$BOOTSTRAP_SRC" ]; then
    echo -e "${RED}Error: Bootstrap script not found at $BOOTSTRAP_SRC${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Bootstrap script found"

if [ "$INSTALL_SERVICE" = true ] && [ ! -d "$SERVICE_SRC" ]; then
    echo -e "${YELLOW}⚠${NC} Update service source not found, skipping service installation"
    INSTALL_SERVICE=false
fi

echo ""

# Create directory structure
echo -e "${GREEN}📁 Creating directory structure...${NC}"
mkdir -p "$BASE_DIR"/{backups,uploads,tmp,logs}
mkdir -p "$BASE_DIR/update-engines"
mkdir -p "$BASE_DIR/bootstrap"
echo -e "   ✓ Base directories created"

# Install update engine
echo ""
echo -e "${GREEN}⚙️  Installing update engine v${ENGINE_VERSION}...${NC}"

# Create engine directory structure with update_engine/ subdirectory
ENGINE_INSTALL_DIR="$BASE_DIR/update-engines/v${ENGINE_VERSION}"
mkdir -p "$ENGINE_INSTALL_DIR/update_engine"

# Copy engine files into update_engine/ subdirectory
cp -r "$ENGINE_SRC"/* "$ENGINE_INSTALL_DIR/update_engine/"
echo -e "   ✓ Engine files copied to $ENGINE_INSTALL_DIR/update_engine/"

# Create CHECKSUM file for engine
echo -e "   Creating engine CHECKSUM..."
(
    cd "$ENGINE_INSTALL_DIR"
    find update_engine -type f -name "*.py" -exec md5sum {} \; | sort > CHECKSUM
)
CHECKSUM_COUNT=$(wc -l < "$ENGINE_INSTALL_DIR/CHECKSUM")
echo -e "   ${GREEN}✓${NC} CHECKSUM created ($CHECKSUM_COUNT files)"

# Create 'current' symlink
ln -sfn "v${ENGINE_VERSION}" "$BASE_DIR/update-engines/current"
echo -e "   ${GREEN}✓${NC} 'current' symlink created"

# Install bootstrap script
echo ""
echo -e "${GREEN}🚀 Installing bootstrap script...${NC}"

cp "$BOOTSTRAP_SRC" "$BASE_DIR/bootstrap/bootstrap.py"
chmod +x "$BASE_DIR/bootstrap/bootstrap.py"
echo -e "   ${GREEN}✓${NC} Bootstrap installed at $BASE_DIR/bootstrap/bootstrap.py"

# Create wrapper script for bootstrap
echo -e "   Creating command wrapper..."

# Determine wrapper location (prefer /usr/local/bin, fallback to /usr/bin)
if [ -d "/usr/local/bin" ] && [ -w "/usr/local/bin" ]; then
    WRAPPER="/usr/local/bin/update-bootstrap"
elif [ -d "/usr/bin" ] && [ -w "/usr/bin" ]; then
    WRAPPER="/usr/bin/update-bootstrap"
else
    echo -e "   ${YELLOW}⚠${NC} Neither /usr/local/bin nor /usr/bin is writable"
    WRAPPER="$BASE_DIR/bin/update-bootstrap"
    mkdir -p "$BASE_DIR/bin"
    echo -e "   ${YELLOW}→${NC} Creating wrapper in: $WRAPPER"
    echo -e "   ${YELLOW}→${NC} Add to PATH: export PATH=\$PATH:$BASE_DIR/bin"
fi

# Create wrapper script
cat > "$WRAPPER" << 'WRAPPER_EOF'
#!/bin/bash
# Auto-generated wrapper for py-offline-updater bootstrap
ENGINE_DIR="BASE_DIR_PLACEHOLDER/update-engines/current"
export PYTHONPATH="$ENGINE_DIR"
exec python3 "BASE_DIR_PLACEHOLDER/bootstrap/bootstrap.py" "$@"
WRAPPER_EOF

# Replace placeholder
sed -i "s|BASE_DIR_PLACEHOLDER|$BASE_DIR|g" "$WRAPPER"
chmod +x "$WRAPPER"

echo -e "   ${GREEN}✓${NC} Command wrapper created: $WRAPPER"

# Install Python dependencies
echo ""
echo -e "${GREEN}📦 Installing Python dependencies...${NC}"

if command -v pip3 &> /dev/null; then
    if [ -f "$REQUIREMENTS_FILE" ]; then
        pip3 install -r "$REQUIREMENTS_FILE" || echo -e "   ${YELLOW}⚠${NC} Some dependencies failed to install"
        echo -e "   ${GREEN}✓${NC} Core dependencies installed"
    else
        echo -e "   ${YELLOW}⚠${NC} requirements.txt not found"
    fi
else
    echo -e "   ${YELLOW}⚠${NC} pip3 not found. Please install dependencies manually:"
    echo -e "   ${YELLOW}→${NC} pip3 install -r $REQUIREMENTS_FILE"
fi

# Install update service
if [ "$INSTALL_SERVICE" = true ]; then
    echo ""
    echo -e "${GREEN}🌐 Installing update service...${NC}"
    
    cp -r "$SERVICE_SRC" "$BASE_DIR/"
    echo -e "   ${GREEN}✓${NC} Service files copied"
    
    # Install service dependencies
    if [ -f "$BASE_DIR/update_service/requirements.txt" ]; then
        pip3 install -r "$BASE_DIR/update_service/requirements.txt" || echo -e "   ${YELLOW}⚠${NC} Some service dependencies failed"
        echo -e "   ${GREEN}✓${NC} Service dependencies installed"
    fi
    
    # Create systemd service
    echo -e "   Creating systemd service..."
    cat > /etc/systemd/system/py-updater.service <<EOF
[Unit]
Description=py-offline-updater Web Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$BASE_DIR
Environment="PYTHONPATH=$BASE_DIR/update-engines/current"
ExecStart=/usr/bin/python3 -m uvicorn update_service.main:app --host 0.0.0.0 --port 8123
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    # Reload systemd
    systemctl daemon-reload
    
    # Enable service
    systemctl enable py-updater.service
    echo -e "   ${GREEN}✓${NC} Systemd service created and enabled"
    
    # Start service if requested
    if [ "$START_SERVICE" = true ]; then
        systemctl start py-updater.service
        echo -e "   ${GREEN}✓${NC} Service started"
    fi
fi

# Set permissions
echo ""
echo -e "${GREEN}🔒 Setting permissions...${NC}"
chmod -R 755 "$BASE_DIR"
echo -e "   ${GREEN}✓${NC} Permissions set"

# Print summary
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Installation completed successfully!${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Installation summary
echo -e "${YELLOW}📋 Installation Summary:${NC}"
echo ""
echo -e "${GREEN}Installation Directory:${NC}"
echo -e "  $BASE_DIR"
echo ""
echo -e "${GREEN}Installed Components:${NC}"
echo -e "  ✓ Update Engine v${ENGINE_VERSION}"
echo -e "    → $BASE_DIR/update-engines/v${ENGINE_VERSION}/update_engine/"
echo -e "  ✓ Bootstrap Script"
echo -e "    → $BASE_DIR/bootstrap/bootstrap.py"
if [ -f "$WRAPPER" ]; then
    echo -e "  ✓ Command Wrapper"
    echo -e "    → $WRAPPER"
fi
if [ "$INSTALL_SERVICE" = true ]; then
    echo -e "  ✓ Web Service"
    echo -e "    → $BASE_DIR/update_service/"
fi
echo ""

# Usage instructions
echo -e "${YELLOW}🚀 Quick Start:${NC}"
echo ""
echo -e "${GREEN}1. Apply update via CLI:${NC}"
echo -e "   update-bootstrap <package.tar.gz>"
echo ""

if [ "$INSTALL_SERVICE" = true ]; then
    echo -e "${GREEN}2. Access Web UI:${NC}"
    if systemctl is-active --quiet py-updater.service; then
        echo -e "   ${GREEN}✓${NC} Service is running: ${BLUE}http://localhost:8123${NC}"
    else
        echo -e "   Start service first: ${YELLOW}systemctl start py-updater${NC}"
        echo -e "   Then access: ${BLUE}http://localhost:8123${NC}"
    fi
    echo ""
    
    echo -e "${GREEN}3. Service Management:${NC}"
    echo -e "   Start:   ${YELLOW}systemctl start py-updater${NC}"
    echo -e "   Stop:    ${YELLOW}systemctl stop py-updater${NC}"
    echo -e "   Status:  ${YELLOW}systemctl status py-updater${NC}"
    echo -e "   Logs:    ${YELLOW}journalctl -u py-updater -f${NC}"
    echo ""
fi

# Next steps
echo -e "${YELLOW}📝 Next Steps:${NC}"
echo ""
echo -e "1. Download wheels for offline installation:"
echo -e "   ${YELLOW}cd $PROJECT_ROOT${NC}"
echo -e "   ${YELLOW}./scripts/download_wheels.sh${NC}"
echo ""
echo -e "2. Create a test package:"
echo -e "   ${YELLOW}./scripts/create_test_package.sh${NC}"
echo ""
echo -e "3. Test the installation:"
echo -e "   ${YELLOW}update-bootstrap test-update.tar.gz${NC}"
echo ""

# Warnings
if [ ! -f "$WRAPPER" ]; then
    echo -e "${RED}⚠ WARNING:${NC} Command wrapper not created"
    echo -e "   Manually run: $BASE_DIR/bootstrap/bootstrap.py"
    echo ""
fi

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
