# Production System Update

This manifest updates the complete RCU system including:
- Docker containers (backend, frontend, redis, celery)
- Service backend (FastAPI application)
- Python dependencies (pip install)
- Environment configuration
- Removes deprecated dimming_control component

## Critical Features

### Watchdog Handling
The system has a hardware watchdog that reboots the system if not kicked every 3 seconds.
The manifest disables it FIRST before stopping services to prevent automatic reboot during update.

### Manual Reboot Required
System does NOT auto-reboot. **Manually reboot after update completes** to ensure clean state.

### Backup & Rollback
- Creates backup before any changes
- Automatic rollback on failure
- Keeps last backup only (disk space limited)

### Safe Image Cleanup
Only removes old backend/frontend images, preserves redis/celery/other images.

## Deployment Package Requirements

Your deployment zip MUST contain:

```
rcu-deployment-v1.7.3-v1.3.2-v1.0.2-arm64.zip
├── RCU_Deploy/
│   ├── rcu-backend-v*.tar     # REQUIRED - Backend docker image
│   ├── rcu-frontend-v*.tar    # REQUIRED - Frontend docker image
│   └── docker-compose.yml     # REQUIRED
└── RCU_Service/
    ├── requirements.txt       # REQUIRED - Python dependencies
    └── backend/               # Backend source code
        ├── app/
        ├── core/
        ├── main.py
        └── services/
```

**Note:** `.env` file will be automatically created by the build script if not present.

## Building Update Package

### Automatic build from deployment zip:

```bash
cd /path/to/py-offline-updater

./scripts/build_production_package.sh rcu-deployment-v1.7.3-v1.3.2-v1.0.2-arm64.zip
```

This will:
1. Extract and verify deployment zip
2. Rename docker images to generic names (backend.tar, frontend.tar)
3. Verify required files (.env, requirements.txt, docker-compose.yml)
4. Build update package using manifest

**Output:** `rcu-deployment-v1.7.3-v1.3.2-v1.0.2-arm64-update.tar.gz`

## Deploying to Device

### Via CLI:

```bash
scp rcu-deployment-*-update.tar.gz root@DEVICE:/tmp/
ssh root@DEVICE
update-bootstrap /tmp/rcu-deployment-*-update.tar.gz

# After update completes successfully:
sudo reboot
```

### Via Web UI:

1. Open http://DEVICE_IP:8123
2. Upload .tar.gz file
3. Click "Apply Update"
4. Monitor progress
5. **Manually reboot device after completion**

## Update Sequence

1. Disable watchdog (prevents auto-reboot)
2. Stop chromium-kiosk
3. Stop service-backend
4. Create backup
5. Stop docker containers
6. Load new docker images
7. Update docker-compose.yml
8. Sync service-backend files
9. Merge .env (keeps existing values)
10. Install Python dependencies
11. Remove old dimming_control
12. Start docker containers
13. Start service-backend
14. Start chromium-kiosk
15. Cleanup old backend/frontend images

## Post-Update Checks

- Docker health (backend-api, frontend)
- HTTP check: http://localhost:8000/health
- HTTP check: http://localhost:80/
- Service running: service-backend

## Rollback

If update fails, automatic rollback will:
1. Stop services
2. Stop docker
3. Restore from backup
4. Start docker
5. Start services

**Manual reboot recommended after rollback.**

