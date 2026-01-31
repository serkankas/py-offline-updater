# RCU3 Full System Update - Deployment Guide

**Package:** `rcu3_full_update.tar.gz`
**Size:** ~104MB (compressed), ~289MB (extracted)
**Date:** 2026-01-29

---

## Package Contents

```
build/
├── docker/                         (289MB)
│   ├── docker-compose.yml          # New Docker Compose config
│   ├── redis-7-alpine-arm64.tar    # Redis image
│   ├── sealink-backend-v1.8.2-arm64.tar   # Backend API + Celery
│   └── sealink-frontend-v1.5.0-arm64.tar  # Frontend (nginx)
│
├── service-backend/                (124KB - 26 files)
│   ├── main.py
│   ├── app/                        # FastAPI app
│   ├── core/                       # Settings, startup, utils
│   └── services/
│
└── updater/                        (180KB - 22 files)
    ├── bootstrap.py
    ├── update_engine/              # Update engine
    └── update_service/             # Web UI + API
```

---

## Pre-Deployment Checklist

Before deploying to RCU3 device:

- [ ] RCU3 device is accessible (SSH/serial)
- [ ] Device has `/app/app/` directory structure
- [ ] At least **500MB** free disk space
- [ ] `systemctl` and `docker` commands available
- [ ] Python 3.8+ installed with `requests` library
- [ ] Update script dependencies installed: `scripts/rcu3_update/requirements.txt`

---

## Deployment Steps

### 1. Transfer Package to Device

```bash
# Via SCP
scp rcu3_full_update.tar.gz root@<RCU3_IP>:/tmp/

# Or via USB, etc.
```

### 2. Extract Package on Device

```bash
ssh root@<RCU3_IP>

# Extract to /tmp
cd /tmp
tar -xzf rcu3_full_update.tar.gz

# Verify extraction
ls -lh build/
```

### 3. Copy Update Scripts to Device

**Option A: If py-offline-updater already on device**

```bash
# Assuming updater is at /app/app/update/
cp -r /path/to/scripts/rcu3_update /app/app/update/scripts/

# Install dependencies
pip3 install -r /app/app/update/scripts/rcu3_update/requirements.txt
```

**Option B: Standalone execution**

```bash
# Copy scripts to temp location
cp -r /path/to/scripts/rcu3_update /tmp/

# Install dependencies
pip3 install -r /tmp/rcu3_update/requirements.txt

# Run from temp
cd /tmp
python3 -m rcu3_update.full_system_update --help
```

---

## Running the Update

### Full System Update (All Components)

```bash
cd /tmp

python3 -m rcu3_update.full_system_update \
    --docker-dir build/docker \
    --docker-compose build/docker/docker-compose.yml \
    --service-backend-dir build/service-backend \
    --updater-dir build/updater \
    --verbose
```

**What it does:**
1. ✅ Relocates updater from `/opt/update` to `/app/app/update` (if needed)
2. ✅ Starts WatchdogKeeper (keeps hardware watchdog alive)
3. ✅ Stops Service Backend
4. ✅ Updates Docker containers (backend, frontend, redis, celery)
5. ✅ Updates Service Backend
6. ✅ Updates Updater (self-update)
7. ✅ Runs health checks after each update
8. ✅ Rolls back on failure
9. ✅ Cleans up backups on success
10. ✅ Stops WatchdogKeeper

### Partial Updates

**Docker only:**
```bash
python3 -m rcu3_update.full_system_update \
    --docker-dir build/docker \
    --docker-compose build/docker/docker-compose.yml \
    --service-backend-dir build/service-backend \
    --updater-dir build/updater \
    --skip-service-backend \
    --skip-updater \
    -v
```

**Service Backend only:**
```bash
python3 -m rcu3_update.full_system_update \
    --docker-dir build/docker \
    --docker-compose build/docker/docker-compose.yml \
    --service-backend-dir build/service-backend \
    --updater-dir build/updater \
    --skip-docker \
    --skip-updater \
    -v
```

**Updater only:**
```bash
python3 -m rcu3_update.full_system_update \
    --docker-dir build/docker \
    --docker-compose build/docker/docker-compose.yml \
    --service-backend-dir build/service-backend \
    --updater-dir build/updater \
    --skip-docker \
    --skip-service-backend \
    -v
```

### Development/Test Mode

Disable WatchdogKeeper for testing:

```bash
python3 -m rcu3_update.full_system_update \
    --docker-dir build/docker \
    --docker-compose build/docker/docker-compose.yml \
    --service-backend-dir build/service-backend \
    --updater-dir build/updater \
    --no-watchdog \
    -v
```

---

## Monitoring Update Progress

### Real-time Logs

```bash
# Watch logs during update
tail -f /var/log/syslog | grep -E "rcu3_update|docker|systemd"

# Or if script is logging to file
tail -f /tmp/update.log
```

### Health Check Endpoints

After update completes, verify services:

```bash
# Frontend (port 80)
curl -f http://localhost:80/

# Backend API (port 8000)
curl http://localhost:8000/api/health

# Service Backend (port 8001)
curl http://localhost:8001/status

# Updater (port 8123)
curl http://localhost:8123/api/system-info
```

### Docker Container Status

```bash
docker ps

# Expected output:
# - frontend (port 80)
# - backend-api (port 8000)
# - celery-worker
# - redis (port 6379)
```

### Systemd Service Status

```bash
systemctl status service-backend.service
systemctl status update-service.service
systemctl status chromium-kiosk.service
```

---

## Backup Locations

During update, backups are created at:

```
/app/app/backups/
├── docker/
│   └── YYYYMMDD_HHMMSS/
│       ├── docker-compose.yml
│       ├── redis-*.tar
│       ├── backend-*.tar
│       └── frontend-*.tar
├── service_backend/
│   └── YYYYMMDD_HHMMSS/
│       └── [all files]
└── updater/
    └── YYYYMMDD_HHMMSS/
        └── [all files]
```

**Note:** Backups are automatically deleted on successful update. On failure, backups are preserved for manual recovery.

---

## Rollback / Recovery

### Automatic Rollback

The update script automatically rolls back if:
- Health checks fail
- Service fails to start
- Any error occurs during update

### Manual Recovery (Power Loss / Crash)

If power is lost during update, backups are preserved:

```bash
# Check available backups
ls -la /app/app/backups/docker/
ls -la /app/app/backups/service_backend/
ls -la /app/app/backups/updater/

# Restore Docker (example)
BACKUP_DIR="/app/app/backups/docker/20260129_120000"
cd /app/app/docker-files
docker compose down
cp $BACKUP_DIR/docker-compose.yml .
docker load -i $BACKUP_DIR/*.tar
docker compose up -d

# Restore Service Backend (example)
BACKUP_DIR="/app/app/backups/service_backend/20260129_120100"
systemctl stop service-backend
rm -rf /app/app/service_backend
cp -r $BACKUP_DIR /app/app/service_backend
systemctl start service-backend

# Restore Updater (example)
BACKUP_DIR="/app/app/backups/updater/20260129_120200"
systemctl stop update-service
rm -rf /app/app/update
cp -r $BACKUP_DIR /app/app/update
systemctl start update-service
```

---

## Troubleshooting

### Update Fails with "Insufficient disk space"

```bash
# Check disk usage
df -h /app

# Clean old Docker images
docker image prune -a -f

# Clean old backups
rm -rf /app/app/backups/docker/*
rm -rf /app/app/backups/service_backend/*
rm -rf /app/app/backups/updater/*
```

### Containers Fail Health Check

```bash
# Check container logs
docker logs backend-api
docker logs frontend
docker logs celery-worker
docker logs redis

# Restart containers
cd /app/app/docker-files
docker compose restart
```

### Service Backend Fails to Start

```bash
# Check service logs
journalctl -u service-backend.service -n 50

# Check if port 8001 is in use
netstat -tulpn | grep 8001

# Restart service
systemctl restart service-backend
```

### Updater Fails to Start

```bash
# Check service logs
journalctl -u update-service.service -n 50

# Check if port 8123 is in use
netstat -tulpn | grep 8123

# Restart service
systemctl restart update-service
```

### Watchdog Timeout

If device reboots unexpectedly during update:
- WatchdogKeeper might have failed
- Run update with `--no-watchdog` flag (for testing only)
- Check `/dev/watchdog` permissions

```bash
# Check watchdog device
ls -la /dev/watchdog

# Expected: crw-rw---- 1 root root
```

---

## Post-Update Verification

After successful update:

1. **Check all services are running:**
   ```bash
   systemctl status service-backend.service
   systemctl status update-service.service
   docker ps
   ```

2. **Verify web interfaces:**
   - Frontend: http://<RCU3_IP>:80/
   - Updater: http://<RCU3_IP>:8123/

3. **Test functionality:**
   - Upload a test update package
   - Check VDR connection
   - Test dimming controls

4. **Clean up:**
   ```bash
   # Remove extracted files
   rm -rf /tmp/build/
   rm /tmp/rcu3_full_update.tar.gz

   # Backups are auto-deleted on success
   # Verify:
   ls /app/app/backups/
   ```

---

## Known Limitations

1. **No automatic power-loss recovery**
   - Manual rollback required if power is lost during update
   - Backups are preserved at `/app/app/backups/`

2. **Docker image size**
   - Large images may take 5-10 minutes to load
   - Ensure sufficient disk space (500MB+)

3. **Sequential updates**
   - Components are updated sequentially (Docker → Service Backend → Updater)
   - Total time: ~10-15 minutes for full update

4. **No concurrent updates**
   - Only one update can run at a time
   - If another update is running, wait for completion

---

## Support

For issues during deployment:

1. Check logs: `journalctl -xe`
2. Check backups: `ls /app/app/backups/`
3. Manual recovery: See "Rollback / Recovery" section above

For questions or bugs: https://github.com/anthropics/py-offline-updater/issues

---

**Last Updated:** 2026-01-29
**Script Version:** 1.0.0
**Target Devices:** RCU3 (imx8mp-var-dart-mdu, imx93)
