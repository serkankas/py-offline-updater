# RCU3 Fresh Install Guide (v3)

## v3 Yenilikleri
- **Step 10**: SSH legacy RSA algoritma destegi (`/etc/ssh/sshd_config.d/10-legacy-rsa.conf`).
  VDR'in eski BusyBox SSH client'i ssh-rsa host key + pubkey kullaniyor, modern OpenSSH
  (>= 8.8) default'tan kaldirdi. Drop-in destegi yoksa sshd_config'e idempotent ekleme yapilir.
- **Step 11**: RCU2B backup compatibility fixes — VDR `backupcheck` script bug'larini
  RCU2B tarafinda wrapper'larla bypass eder:
  - `/mnt/usb` mount target klasoru
  - `/usr/sbin/fdisk` wrapper (cut -f 0 bug + superfloppy FAT)
  - `/bin/df` wrapper (-m yerine -k birim hatasi)
  - Idempotent install/uninstall script'leri `/usr/local/sbin/` altinda kalir
  - Detay: `RCU2B-BACKUP-FIX-NOTES.md`

## Target Device
- **Platform**: Yocto Linux ARM64 (aarch64)
- **Python**: 3.10 (pre-installed in Yocto image)
- **Network**: Offline (no internet access)
- **Docker**: 25.0.3 (static binary install)
- **Docker Compose**: v2.26.0 (standalone binary)

## Device Directory Structure (ls -lah /app/app)
```
/app/app/                  # owner: weston:weston
├── backups/               # Update backups
├── docker-files/          # docker-compose.yml + service.env
├── files_from_vdr/        # VDR shared volume (dimming.json etc.)
├── logs/                  # Application logs
├── service_backend/
│   └── backend/           # RCU_Service (bare-metal, port 8001)
│       ├── main.py
│       ├── app/
│       ├── core/
│       └── services/
└── update/                # py-offline-updater runtime
```

## Systemd Services (all in /etc/systemd/system/)

### 1. docker.service
- Starts Docker daemon: `/usr/bin/dockerd -H fd:// --containerd=/run/containerd/containerd.sock`
- Requires: docker.socket, containerd.service
- Restart: always

### 2. service-backend.service
- Starts RCU_Service: `/usr/bin/python3 /app/app/service_backend/backend/main.py`
- WorkingDirectory: `/app/app/service_backend/backend`
- Port: 8001
- Restart: on-failure (5s)

### 3. chromium-kiosk.service
- Starts Chromium in kiosk mode on Wayland
- Waits for Docker + frontend container healthy (max 180s)
- URL: http://localhost
- After: docker.service

### 4. py-updater.service
- Starts py-offline-updater web UI: uvicorn on port 8123
- WorkingDirectory: /app/app/update
- PYTHONPATH: /app/app/update/update-engines/current

## Docker Containers
| Container | Image | Port | Notes |
|-----------|-------|------|-------|
| frontend | rcu-deploy-frontend:*-linux-arm64 | 80 | Nginx + Next.js static |
| backend-api | rcu-deploy-backend:*-linux-arm64 | 8000 | FastAPI + Celery |
| celery-worker | rcu-deploy-backend:*-linux-arm64 | - | Same image as backend |
| redis | redis:7-alpine | 6379 | Data persistence volume |

## Python Packages (pip freeze from working device)
All must be pre-downloaded as wheels for offline install (aarch64).

### Direct Dependencies
| Package | Version | Used By |
|---------|---------|---------|
| fastapi | 0.127.0 | Service Backend, Updater |
| uvicorn | 0.40.0 | Service Backend, Updater |
| aiofiles | 25.1.0 | Service Backend, Updater |
| python-dotenv | 1.2.1 | Service Backend, Updater |
| httpx | 0.28.1 | Service Backend |
| psutil | 7.2.2 | Updater (needs aarch64 wheel) |
| smbus2 | 0.6.0 | Service Backend (I2C/hardware) |
| python-multipart | 0.0.21 | Updater |
| sse-starlette | 3.1.1 | Updater |
| PyYAML | 6.0.3 | Update Engine |
| requests | 2.32.5 | Update Engine, rcu3_update |
| pydantic | 2.12.5 | FastAPI dependency |
| pydantic-settings | 2.12.0 | Service Backend |
| websockets | 15.0.1 | Service Backend (dimming WS) |
| gpiod | 2.1.3 | Hardware GPIO |
| sentry-sdk | 2.48.0 | Error tracking |

### All Packages (full pip freeze)
```
aiofiles==25.1.0
annotated-doc==0.0.4
annotated-types==0.7.0
anyio==4.12.0
certifi==2025.11.12
charset-normalizer==3.4.4
click==8.3.1
dnspython==2.8.0
email-validator==2.3.0
fastapi==0.127.0
fastapi-cli==0.0.20
fastapi-cloud-cli==0.8.0
fastar==0.8.0
gpiod==2.1.3
h11==0.16.0
httpcore==1.0.9
httptools==0.7.1
httpx==0.28.1
idna==3.11
Jinja2==3.1.6
markdown-it-py==4.0.0
MarkupSafe==3.0.3
mdurl==0.1.2
psutil==7.2.2
pydantic==2.12.5
pydantic-extra-types==2.10.6
pydantic-settings==2.12.0
pydantic_core==2.41.5
Pygments==2.19.2
python-dotenv==1.2.1
python-multipart==0.0.21
PyYAML==6.0.3
requests==2.32.5
rich==14.2.0
rich-toolkit==0.17.1
rignore==0.7.6
sentry-sdk==2.48.0
setuptools==69.1.1
shellingham==1.5.4
smbus2==0.6.0
sse-starlette==3.1.1
starlette==0.50.0
typer==0.21.0
typing-inspection==0.4.2
typing_extensions==4.15.0
urllib3==2.6.2
uvicorn==0.40.0
uvloop==0.22.1
watchfiles==1.1.1
websockets==15.0.1
```

## Docker Engine Installation (Static Binary)
Docker 25.0.3 static binaries for aarch64:
- Download: `https://download.docker.com/linux/static/stable/aarch64/docker-25.0.3.tgz`
- Extract to `/usr/bin/` (dockerd, docker, containerd, etc.)
- Install docker.service + docker.socket + containerd.service

## Docker Compose Installation
Docker Compose v2.26.0 standalone binary for aarch64:
- Download: `docker-compose-linux-aarch64` from GitHub releases
- Place at `/usr/libexec/docker/cli-plugins/docker-compose`
- chmod +x

## Installation Order
1. **Network** - /etc/systemd/network/00-eth.network (10.2.1.20/24)
2. **Docker Engine** - static binaries
3. **Docker Compose** - binary plugin
4. **Docker systemd services** - containerd + docker + docker.socket
5. **Python Wheels** - pip3 install --no-index --find-links=./wheels/
6. **Directory Structure** - /app/app/* hierarchy
7. **Docker Images & Compose Up** - frontend/backend/redis + docker-compose.yml
8. **Service Backend** - copy to /app/app/service_backend/backend/ + enable systemd
9. **py-offline-updater** - install + enable systemd
10. **SSH legacy RSA** (v3) - sshd_config.d/10-legacy-rsa.conf + reload sshd
11. **RCU2B backup-fix** (v3) - /usr/local/sbin/rcu2b-backup-fix-install.sh
12. **Chromium Kiosk** - enable systemd service
13. **Reboot & Verify**

## Update Package Structure (existing, for reference)
```
rcu3_update_A39.8.tar.gz
├── manifest.yml
└── files/
    ├── wheels/psutil-*.whl
    ├── docker/
    │   ├── frontend.tar
    │   ├── backend.tar
    │   ├── redis.tar
    │   ├── docker-compose.yml
    │   └── service.env
    ├── service-backend/    (RCU_Service full source)
    ├── updater/            (py-offline-updater)
    ├── rcu3_update/        (update scripts)
    └── run_update.py       (entry point)
```

## Service Environment (.env)
```
DEBUG=0
HOST=0.0.0.0
PORT=8001
VDR_TCP_PORT=7000
VDR_TCP_HOST=0.0.0.0
WATCHDOG_ENABLED=1
WATCHDOG_KICK_INTERVAL=3
WATCHDOG_BOOT_GRACE_PERIOD=120
RCU_BACKEND_URL=http://localhost:8000
RCU_HEALTH_CHECK_INTERVAL=10
RCU_HEALTH_CHECK_TIMEOUT=5
DOCKER_COMPOSE_PATH=/app/app/docker-files
RCU_HOST=10.2.1.20
RCU_TCP_PORT=7000
RCU_TYPE=VDR_RCU2B
RCU_SERIAL=N/A
RCU_SW_VERSION=5411320-A39.x
RCU_VERSION=39.x
RCU_HW_VERSION=1.0.0
RCU_FW_VERSION=<service_version>
RCU_OS_VERSION=0.1
```

## Current Versions (Mar 2026)
| Component | Version |
|-----------|---------|
| Frontend | v1.9.2 |
| Backend | v1.9.6 |
| Service | v1.4.1 |
| py-offline-updater | v1.1.0 |
| RCU Version | A39.8 |
| Manifest | 8a54bb16 |
