# Installation Guide

## Prerequisites

- Linux system (tested on Ubuntu 20.04+, Debian 10+)
- Python 3.8 or higher
- pip3
- systemd (optional, for service management)
- Docker (optional, if using Docker actions)

## Installation

### 1. Clone or Download

```bash
git clone https://github.com/serkankas/py-offline-updater.git
cd py-offline-updater
```

### 2. Install Node.js Dependencies (for semantic versioning)

```bash
npm install
```

### 3. Run Installation Script

```bash
sudo ./scripts/install.sh
```

By default, this installs to `/opt/updater`. To specify a custom location:

```bash
sudo ./scripts/install.sh --base-dir /custom/path
```

### 4. Verify Installation

Check that the command is available:

```bash
update-bootstrap --help
```

Check the service status:

```bash
systemctl status py-updater
```

Access the web UI:

```
http://localhost:8123
```

## Manual Installation

If you prefer to install manually:

### 1. Create Directory Structure

```bash
sudo mkdir -p /opt/updater/{engine,backups,uploads,tmp,logs}
```

### 2. Copy Engine Files

```bash
sudo cp -r src/update_engine /opt/updater/engine/
sudo cp src/bootstrap.py /opt/updater/
sudo chmod +x /opt/updater/bootstrap.py
```

### 3. Install Python Dependencies

```bash
pip3 install -r requirements.txt
```

### 4. Install Update Service

```bash
sudo cp -r src/update_service /opt/updater/
pip3 install -r /opt/updater/update_service/requirements.txt
```

### 5. Create Systemd Service (optional)

Create `/etc/systemd/system/py-updater.service`:

```ini
[Unit]
Description=py-offline-updater Web Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/updater/update_service
Environment="PYTHONPATH=/opt/updater"
ExecStart=/usr/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8123
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable py-updater
sudo systemctl start py-updater
```

## Configuration

### Change Web Service Port

Edit `/etc/systemd/system/py-updater.service` and change the port in `ExecStart`:

```
ExecStart=/usr/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8080
```

Then reload:

```bash
sudo systemctl daemon-reload
sudo systemctl restart py-updater
```

### Change Base Directory

If you installed to a custom directory, update the service file's `WorkingDirectory` and `PYTHONPATH`.

## Uninstallation

```bash
# Stop and disable service
sudo systemctl stop py-updater
sudo systemctl disable py-updater
sudo rm /etc/systemd/system/py-updater.service
sudo systemctl daemon-reload

# Remove files
sudo rm -rf /opt/updater
sudo rm /usr/local/bin/update-bootstrap
```

## Troubleshooting

### Service Won't Start

Check logs:

```bash
journalctl -u py-updater -n 50
```

Check Python dependencies:

```bash
pip3 list | grep -E "(fastapi|uvicorn|pyyaml)"
```

### Permission Errors

Ensure the base directory is writable:

```bash
sudo chmod -R 755 /opt/updater
```

### Port Already in Use

Check what's using port 8123:

```bash
sudo lsof -i :8123
```

Change the port in the service configuration.

## Next Steps

- Read the [Manifest Reference](manifest-reference.md)
- Check out the [examples](../examples/)
- Build your first update package

