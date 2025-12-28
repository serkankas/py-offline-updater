# py-offline-updater

Manifest-driven, offline update framework for embedded Linux systems (ARM64/x86_64).

## Features

- 📦 **Offline Updates** - No internet required on target device
- 🔄 **Self-Update Engine** - Bootstrap handles engine versioning
- ✅ **Pre/Post Checks** - Verify system state before and after
- 🔙 **Auto Rollback** - Revert on failure
- 💾 **Power-Safe** - Recovers from interruptions
- 🌐 **Web UI** - Real-time progress with drag & drop
- 🐳 **Docker Support** - Load images, manage containers

## Quick Start

### 1. Prepare (Development Machine)

```bash
# Clone repository
git clone https://github.com/serkankas/py-offline-updater.git
cd py-offline-updater

# Download offline wheels for ARM64
./scripts/download_wheels.sh

# Create test package
./scripts/create_test_package.sh
# Output: test-update.tar.gz
```

### 2. Deploy (Target Device)

```bash
# Copy files to device
scp test-update.tar.gz root@DEVICE:/tmp/
scp -r src/ scripts/ root@DEVICE:/tmp/framework/

# SSH to device
ssh root@DEVICE

# Install framework
cd /tmp/framework/scripts
sudo ./install.sh --base-dir /app/app/update
```

### 3. Update (Target Device)

**Option A: Command Line**
```bash
update-bootstrap /tmp/test-update.tar.gz
```

**Option B: Web UI**
```
http://DEVICE_IP:8123
```
- Upload `test-update.tar.gz`
- Click "Apply Update"
- Watch real-time progress

## How It Works

1. **Package** - Create `.tar.gz` with manifest, wheels, Docker images
2. **Extract** - Bootstrap extracts and verifies engine version
3. **Execute** - Engine runs actions (install packages, load images, etc.)
4. **Verify** - Post-checks ensure system health
5. **Cleanup** - Remove temp files, create backups

## Manifest Example

```yaml
description: "Install Python dependencies offline"
required_engine_version: "1.0.0"

pre_checks:
  - type: disk_space
    path: /tmp
    required_mb: 100

actions:
  - name: "Install packages"
    type: command
    command: "pip3 install --no-index --find-links=wheels/ pyyaml requests"
    timeout: 300

post_checks:
  - type: command
    command: "python3 -c 'import yaml; import requests'"
```

## Scripts

- `download_wheels.sh` - Download Python wheels for ARM64 offline install
- `create_test_package.sh` - Quick test package creation
- `build_package.sh` - Build production update packages
- `install.sh` - Install framework on target device

## Project Structure

```
py-offline-updater/
├── src/
│   ├── bootstrap.py           # Entry point, handles engine updates
│   ├── update_engine/         # Core update logic
│   │   ├── engine.py          # Main orchestrator
│   │   ├── actions.py         # Update actions (command, docker, files)
│   │   ├── checks.py          # Pre/post checks
│   │   ├── backup.py          # Backup/restore
│   │   └── state.py           # Power-safe state management
│   └── update_service/        # FastAPI web service
├── scripts/                   # Deployment & build scripts
└── examples/                  # Example manifests
```

## Requirements

- **Target Device**: Python 3.8+, systemd (optional)
- **Dev Machine**: Node.js 16+ (for versioning)

## Documentation

- Full examples in `examples/`
- Manifest reference: `docs/manifest-reference.md`
- Installation guide: `docs/installation.md`

## Author

**Serkan KAŞ**
- GitHub: [@serkankas](https://github.com/serkankas)
- Email: serkankas98@gmail.com

## License

MIT - See [LICENSE](LICENSE) for details
