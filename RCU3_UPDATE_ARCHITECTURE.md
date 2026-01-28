# RCU3 Update System Architecture

**Tarih:** 14 Ocak 2026
**Durum:** Implementation Ready
**Hedef:** Manifest-driven update system ile RCU3 cihazlarını güvenli şekilde güncellemek

---

## 📋 İÇİNDEKİLER

1. [Sistem Mimarisi](#sistem-mimarisi)
2. [Cihaz Konfigürasyonları](#cihaz-konfigürasyonları)
3. [Mevcut Durum ve Sorunlar](#mevcut-durum-ve-sorunlar)
4. [Güncelleme Senaryoları](#güncelleme-senaryoları)
5. [Aksiyon Planı](#aksiyon-planı)
6. [Sonuç](#sonuç)
7. [Referanslar](#referanslar)

---

## 🏗️ SISTEM MİMARİSİ

### RCU3 Cihaz Mimarisi

```
RCU3 Device (Embedded Linux)
│
├── 1. Gömülü Sistem (Host)
│   │
│   ├── 1.1. Service Backend (RCU_Service)
│   │   ├── Konum: /app/app/service_backend/
│   │   │   └── Her iki cihazda da AYNI PATH!
│   │   │
│   │   ├── Görevler:
│   │   │   ├── Watchdog yönetimi (/dev/watchdog kick)
│   │   │   ├── VDR TCP Server (Port 7000)
│   │   │   ├── RCU UDP Discovery (Port 65535)
│   │   │   ├── Dimming/DAC kontrolü
│   │   │   ├── Docker container health check
│   │   │   └── System-level operasyonlar
│   │   │
│   │   └── API Endpoint: http://0.0.0.0:8001
│   │       └── Nginx reverse proxy ile: http://localhost/service
│   │
│   ├── 1.2. py-offline-updater (Bu proje!)
│   │   ├── Standart Konum: /app/app/update/
│   │   │   └── Tüm cihazlarda aynı! (Yeni kurulumlar)
│   │   │
│   │   ├── Eski Kurulumlar (Relocation yapılacak):
│   │   │   └── Cihaz #1: /opt/updater/ → /app/app/update/
│   │   │
│   │   ├── Bileşenler:
│   │   │   ├── update_service/     → Web UI (Port 8123)
│   │   │   ├── update-engines/     → Versiyonlu engine'ler
│   │   │   ├── bootstrap/          → İlk başlatma
│   │   │   ├── backups/            → Yedekler
│   │   │   ├── logs/               → Loglar
│   │   │   └── uploads/            → Paket upload alanı
│   │   │
│   │   ├── Web UI: http://[cihaz-ip]:8123
│   │   │   └── Direkt erişim (nginx dışından!)
│   │   │
│   │   └── Manifest-driven + Python execution!
│   │
│   └── 1.3. Docker
│       │
│       ├── Docker Images Location: /app/app/docker-files/
│       │   ├── backend-v1.8.0-arm64.tar      (~1.2GB)
│       │   ├── frontend-v1.4.0-arm64.tar     (~52MB)
│       │   └── docker-compose.yml
│       │
│       └── Containers:
│           ├── backend-api        (Port 8000)
│           ├── celery-worker
│           ├── redis              (Port 6379)
│           └── frontend           (Port 80)
│               └── nginx reverse proxy:
│                   ├── /          → Frontend (Next.js static)
│                   ├── /api       → Docker Backend API (backend-api:8000)
│                   ├── /ws        → Docker Backend WebSocket (backend-api:8000)
│                   ├── /vdr       → VDR External Device (10.2.1.10:8080)
│                   └── /service   → Service Backend Host (host.docker.internal:8001)
```

**Nginx Routing Detayları:**
- Docker container'lar arası: `backend-api:8000` (Docker network)
- Host'a erişim: `host.docker.internal:8001` (Docker → Host bridge)
- External device: `10.2.1.10:8080` (Network üzerinden)
- Frontend kullanıcısı tüm servislere `/` üzerinden erişir

**Port Kullanımı:**
- `80` - Frontend nginx (docker)
- `8000` - Backend API (docker)
- `8001` - Service Backend (host) → `/service` ile erişilir
- `8123` - py-offline-updater UI (host) → Direkt erişim
- `6379` - Redis (docker)
- `7000` - VDR TCP Server (Service Backend içinde)


---

## 🖥️ CİHAZ KONFİGÜRASYONLARI

### Cihaz #1: Smart Marine Lab (imx8mp-var-dart-mdu)

```
/app/app/
├── docker-files/
│   ├── backend-v1.8.0-arm64.tar
│   ├── frontend-v1.4.0-arm64.tar
│   ├── docker-compose.yml
│   └── rcu-production-arm64-final.zip
│
├── files_from_vdr/
│
├── service_backend/                    ← RCU_Service (PORT: 8001)
│   ├── .env
│   ├── requirements.txt
│   └── backend/
│       ├── main.py
│       ├── app/
│       │   ├── api/
│       │   └── websockets/
│       └── core/
│           ├── settings.py
│           ├── startup.py
│           └── utils/
│               ├── watchdog.py    ⚠️ KRITIK!
│               ├── docker.py
│               ├── systemd.py
│               ├── tcp_server.py
│               ├── dim.py
│               └── dac.py
│
└── update/                             ← py-offline-updater (PORT: 8123)
    ├── update_service/                 [Relocation: /opt/updater → /app/app/update]
    ├── update-engines/
    │   └── current -> v1.0.0
    ├── bootstrap/
    ├── backups/
    ├── logs/
    ├── tmp/
    └── uploads/
```

**⚠️ RELOCATION GEREKLİ:** `/opt/updater/` → `/app/app/update/`

### Cihaz #2: ByteDevKit (imx93)

```
/app/app/
├── docker-files/
│   ├── docker-compose.yml
│   ├── sealink-backend-v1.8.0-arm64.tar
│   └── sealink-frontend-v1.4.0-arm64-FINAL.tar
│
├── files_from_vdr/
│   └── dimming.json
│
├── service_backend/                    ← RCU_Service (PORT: 8001)
│
└── update/                             ← py-offline-updater (PORT: 8123)
    ├── update_service/                 ✅ Standart konum!
    ├── update-engines/
    ├── bootstrap/
    ├── backups/
    ├── logs/
    ├── tmp/
    └── uploads/
```

**✅ STANDART KONUM:** `/app/app/update/` (Tüm cihazlar için hedef)

**✅ AYNILAR:**
- **Service Backend**: `/app/app/service_backend/` (PORT: 8001)
- **Docker files**: `/app/app/docker-files/`
- **VDR files**: `/app/app/files_from_vdr/`
- **py-offline-updater**: `/app/app/update/` (PORT: 8123)

---

## ❌ MEVCUT DURUM VE SORUNLAR

### Problem #1: py-offline-updater Path Inconsistency ✅ ÇÖZÜM BELİRLENDİ

**Mevcut Durum:**
- Cihaz #1 (Smart Marine Lab): `/opt/updater/` ❌ Eski konum
- Cihaz #2 (ByteDevKit): `/app/app/update/` ✅ Standart konum

**ÖNEMLİ:** Service Backend her iki cihazda da `/app/app/service_backend/` konumunda! ✅

**✅ ÇÖZÜM: Path Standardizasyonu**
- **Hedef path:** `/app/app/update/` (Tüm cihazlar için)
- **Relocation gerekli:** Cihaz #1'de `/opt/updater/` → `/app/app/update/`
- **Yeni kurulumlar:** Doğrudan `/app/app/update/` altına kurulacak
- **Avantajlar:**
  - Tüm servisler `/app/app/` altında organize
  - Sistemd service path'leri sabit
  - Deployment scriptleri basitleşir
  - Bakım kolaylaşır

### Problem #2: Watchdog Conflict ✅ ÇÖZÜM BELİRLENDİ

```python
# /app/app/service_backend/backend/core/utils/watchdog.py
class WatchdogManager:
    def __init__(self):
        self.state = WatchdogState.DISABLED if settings.DEBUG else WatchdogState.BOOT_GRACE
        
    async def _kick(self):
        if not settings.WATCHDOG_ENABLED:
            return
        with open('/dev/watchdog', 'w') as f:
            f.write('1')
```

**Sorun:**
- Update sırasında Service Backend watchdog'u kick atmaya devam ediyor
- Manifest action'lar uzun sürüyor (docker load, file sync, etc.)
- Watchdog kick atılmazsa sistem reboot oluyor (hardware watchdog)
- Boot grace period: 120 saniye (update bundan uzun sürebilir)

**Ne zaman sorun çıkıyor:**
- Docker-compose down yapıldığında (Service Backend kick atamıyor)
- Service Backend'i restart ettiğimizde
- Uzun süren işlemlerde (>120s boot grace period)

**✅ ÇÖZÜM: Python-based Execution with Built-in Watchdog**

**Yaklaşım:** Manifest sadece "ne yapılacak" tanımlar, Python execution engine tüm işlemleri yapar ve watchdog'u kendi thread'inde yönetir.

```python
# src/update_engine/watchdog_keeper.py

import threading
import time
import logging

logger = logging.getLogger(__name__)


class WatchdogKeeper:
    """
    Update süresi boyunca watchdog'u canlı tutan sınıf.

    Kullanım:
        keeper = WatchdogKeeper(kick_interval=3)
        keeper.start()
        # ... update işlemleri ...
        keeper.stop()
    """

    def __init__(self, kick_interval: int = 3, watchdog_device: str = '/dev/watchdog'):
        self._kick_interval = kick_interval
        self._watchdog_device = watchdog_device
        self._running = False
        self._thread: threading.Thread | None = None

    def _kick_loop(self):
        """Watchdog kick döngüsü - _running True olduğu sürece çalışır"""
        while self._running:
            try:
                with open(self._watchdog_device, 'w') as f:
                    f.write('1')
                logger.debug("Watchdog kicked")
            except Exception as e:
                logger.error(f"Watchdog kick failed: {e}")
            time.sleep(self._kick_interval)

    def start(self):
        """Watchdog keeper'ı başlat"""
        if self._running:
            logger.warning("WatchdogKeeper already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._kick_loop, daemon=True)
        self._thread.start()
        logger.info(f"WatchdogKeeper started (interval: {self._kick_interval}s)")

    def stop(self):
        """Watchdog keeper'ı durdur"""
        if not self._running:
            logger.warning("WatchdogKeeper not running")
            return

        self._running = False  # while döngüsü bu flag'i kontrol eder ve çıkar
        if self._thread:
            self._thread.join(timeout=self._kick_interval + 2)
            self._thread = None
        logger.info("WatchdogKeeper stopped")

    @property
    def is_running(self) -> bool:
        """Watchdog keeper çalışıyor mu?"""
        return self._running
```

```python
# src/update_engine/engine.py

from .watchdog_keeper import WatchdogKeeper


class UpdateEngine:
    def __init__(self, ...):
        self.watchdog_keeper = WatchdogKeeper(kick_interval=3)

    def run(self) -> bool:
        """Execute the update process"""
        try:
            # Watchdog keeper'ı başlat
            self.watchdog_keeper.start()

            # Pre-checks
            if not self._run_checks('pre_checks'):
                return False

            # Execute actions (Python fonksiyonları olarak)
            # Docker, systemd, file operations - hepsi Python içinde
            if not self._run_actions():
                return False

            # Post-checks
            if not self._run_checks('post_checks'):
                return False

            # Cleanup
            self.cleanup()

            return True

        finally:
            # Watchdog keeper'ı durdur
            self.watchdog_keeper.stop()
```

**Avantajlar:**
1. **Service Backend'e API eklemeye gerek yok** - Watchdog ownership transferi yok
2. **Basit ve güvenli** - Python thread watchdog'u kesintisiz kick atar
3. **Manifest-driven kalır** - Manifest sadece "ne yapılacak" tanımlar
4. **Her action Python** - `docker-compose`, `systemd`, `file_copy` Python ile
5. **Rollback güvenli** - Watchdog her zaman korunur

**Dezavantajlar:**
- ❌ Yok! En basit ve güvenli çözüm.

### Problem #3: Relocation Requirement

**Hedef:** Cihaz #1'de `/opt/updater/` → `/app/app/update/` taşıma

**⚠️ MEVCUT DURUM:** 
- ❌ `relocation` action tipi henüz yok
- ❌ `systemd` action'ları henüz yok
- ✅ `file_sync`, `file_copy`, `command` action'ları mevcut

**Relocation Yaklaşımları:**

#### Yaklaşım 1: Manuel Script (Önerilen - İlk kurulum için)
```bash
#!/bin/bash
# scripts/relocate_to_standard_path.sh

OLD_PATH="/opt/updater"
NEW_PATH="/app/app/update"

if [ ! -d "$OLD_PATH" ]; then
    echo "Already relocated or not exists: $OLD_PATH"
    exit 0
fi

echo "Relocating from $OLD_PATH to $NEW_PATH..."

# Stop service (if exists)
systemctl stop update-service 2>/dev/null || true

# Create parent directory
mkdir -p /app/app

# Move files
mv "$OLD_PATH" "$NEW_PATH"

# Create symlink for backward compatibility
ln -sf "$NEW_PATH" "$OLD_PATH"

# Update systemd service WorkingDirectory if needed
# sed -i "s|/opt/updater|/app/app/update|g" /etc/systemd/system/update-service.service
# systemctl daemon-reload

# Start service
systemctl start update-service

echo "Relocation completed!"
```

**Kullanım:**
```bash
chmod +x scripts/relocate_to_standard_path.sh
./scripts/relocate_to_standard_path.sh
```

#### Yaklaşım 2: Manifest ile (Gelecekte - İhtiyaç olursa)

Eğer sık relocation yapılacaksa yeni action eklenebilir:

**YENİ Action'lar gerekli:**
```python
# src/update_engine/actions.py - EKLENECEK

def action_systemd_stop(action: Dict, package_path: Path) -> bool:
    """Stop systemd service"""
    service = action['service']
    timeout = action.get('timeout', 30)
    
    logger.info(f"Stopping systemd service: {service}")
    result = subprocess.run(['systemctl', 'stop', service], 
                          capture_output=True, timeout=timeout)
    
    if result.returncode != 0:
        raise ActionError(f"Failed to stop service: {result.stderr}")
    
    return True


def action_systemd_start(action: Dict, package_path: Path) -> bool:
    """Start systemd service"""
    service = action['service']
    timeout = action.get('timeout', 30)
    
    logger.info(f"Starting systemd service: {service}")
    result = subprocess.run(['systemctl', 'start', service],
                          capture_output=True, timeout=timeout)
    
    if result.returncode != 0:
        raise ActionError(f"Failed to start service: {result.stderr}")
    
    # Wait for service to be active
    wait_healthy = action.get('wait_healthy', False)
    if wait_healthy:
        time.sleep(5)
        status = subprocess.run(['systemctl', 'is-active', service], 
                              capture_output=True, text=True)
        if status.stdout.strip() != 'active':
            raise ActionError(f"Service not active: {service}")
    
    return True


def action_relocation(action: Dict, package_path: Path) -> bool:
    """Relocate directory with optional service management"""
    old_path = Path(action['old_path'])
    new_path = Path(action['new_path'])
    service = action.get('service_name')
    create_symlink = action.get('create_symlink', False)
    
    if not old_path.exists():
        logger.info(f"Already relocated: {new_path}")
        return True
    
    logger.info(f"Relocating: {old_path} → {new_path}")
    
    # Stop service if specified
    if service:
        subprocess.run(['systemctl', 'stop', service], 
                      capture_output=True)
    
    # Create parent directory
    new_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Move directory
    shutil.move(str(old_path), str(new_path))
    logger.info(f"Moved to: {new_path}")
    
    # Create symlink for backward compatibility
    if create_symlink:
        os.symlink(new_path, old_path)
        logger.info(f"Created symlink: {old_path} → {new_path}")
    
    # Start service if specified
    if service:
        subprocess.run(['systemctl', 'start', service],
                      capture_output=True)
    
    return True
```

**execute_action'a ekle:**
```python
def execute_action(action: Dict[str, Any], package_path: Path, backup_manager: BackupManager) -> bool:
    action_type = action.get('type')
    
    # ... existing actions ...
    
    elif action_type == 'systemd_stop':
        return action_systemd_stop(action, package_path)
    elif action_type == 'systemd_start':
        return action_systemd_start(action, package_path)
    elif action_type == 'relocation':
        return action_relocation(action, package_path)
    else:
        raise ValueError(f"Unknown action type: {action_type}")
```

**Manifest örneği (gelecekte):**
```yaml
actions:
  - type: relocation
    old_path: /opt/updater
    new_path: /app/app/update
    service_name: update-service.service
    create_symlink: true
```

**ÖNERİ:** İlk aşamada manuel script kullan, eğer sık relocation gerekirse action implement et.

### Problem Özeti ve Çözümler

| Problem | Durum | Çözüm |
|---------|-------|-------|
| **Path Inconsistency** | ✅ Belirlendi | Standardizasyon: `/app/app/update/` (tüm cihazlar) |
| **Watchdog Conflict** | ✅ Belirlendi | Python thread içinde watchdog keeper |
| **Relocation** | ⚠️ Manuel script | İlk kurulum için bash script (sık yapılmayacak) |

### Mevcut Action Desteği

**✅ Implement Edilmiş Action'lar:**
1. `command` - Shell komutları
2. `backup` - Backup oluştur
3. `restore_backup` - Backup'tan geri yükle
4. `docker_compose_down` - Docker servisleri durdur
5. `docker_compose_up` - Docker servisleri başlat
6. `docker_load` - Docker image yükle (tar'dan)
7. `docker_prune` - Eski Docker image'leri temizle
8. `file_copy` - Dosya kopyala (checksum ile)
9. `file_sync` - Dizin senkronize et (mirror/add_only/overwrite)
10. `file_merge` - Dosya merge (.env gibi)

**❌ Henüz Yok (Gerekirse eklenecek):**
- `systemd_stop` / `systemd_start` / `systemd_restart`
- `relocation` - Dizin taşıma
- `watchdog_takeover` / `watchdog_release` (Artık gerekli değil!)

**Ana Prensipler:**
1. **Manifest-driven orchestration** - Ne yapılacak manifest'te tanımlı
2. **Python-based execution** - Nasıl yapılacak Python'da implement
3. **Built-in watchdog keeper** - Service Backend'e dokunmadan güvenli update
4. **Standardized paths** - `/app/app/` altında tüm servisler
5. **Backward compatibility** - Symlink ile eski path'ler desteklenir

---

## 🔄 GÜNCELLEME SENARYOLARI

### Unified Update CLI Tool

Tek bir CLI aracı ile tüm update senaryoları yönetilir. Hangi bileşenlerin güncelleneceği flag'lerle belirlenir:

```bash
# Kullanım örnekleri

# Docker Backend + Frontend (en yaygın senaryo)
python3 update_batch.py --include-docker \
    --docker-images /path/to/images/ \
    --compose-file /path/to/docker-compose.yml

# Service Backend (Host üzerindeki RCU_Service)
python3 update_batch.py --include-service-backend \
    --service-backend-path /path/to/service_backend/

# Sadece Frontend health check (sistem ayakta mı kontrolü)
python3 update_batch.py --include-frontend \
    --frontend-health-check

# py-offline-updater (Self-update)
python3 update_batch.py --include-updater \
    --updater-path /path/to/py-offline-updater/

# Full update - hepsi birden
python3 update_batch.py \
    --include-docker \
    --include-service-backend \
    --include-updater \
    --docker-images /path/to/images/ \
    --compose-file /path/to/docker-compose.yml \
    --service-backend-path /path/to/service_backend/ \
    --updater-path /path/to/py-offline-updater/
```

**Flag Açıklamaları:**
| Flag | Açıklama |
|------|----------|
| `--include-docker` | Docker container'ları güncelle (backend-api, celery-worker, redis, frontend) |
| `--include-service-backend` | Host üzerindeki Service Backend'i güncelle |
| `--include-frontend` | Frontend health check yap (sistem ayakta mı?) |
| `--include-updater` | py-offline-updater self-update |

**Neden path veriyoruz?**
- Docker image dosya isimleri değişebilir (örn: `sealink-backend-v1.8.0-arm64.tar`)
- docker-compose.yml içeriği `RCU_Deploy` tarafından oluşturuluyor
- Esneklik: Farklı cihazlar için farklı dosya yapıları

---

### RCU_Deploy Entegrasyonu

Docker image'lar ve docker-compose.yml, `RCU_Deploy` projesi tarafından oluşturulur:

```bash
# 1. RCU_Deploy ile manifest ve docker image'lar oluştur
cd /path/to/RCU_Deploy
python scripts/build_manifests.py \
  --backend-repository git@github.com:user/RCU_Backend.git \
  --backend-tag v1.8.1 \
  --frontend-repository git@github.com:user/RCU_Frontend.git \
  --frontend-tag v1.4.0

# 2. Deploy script ile build et
python scripts/deploy.py --manifest manifests/2026-01-14/[MANIFEST_ID].yaml

# 3. Image'ları export et
docker save -o sealink-backend-v1.8.1-arm64.tar sealink-backend:v1.8.1
docker save -o sealink-frontend-v1.4.0-arm64.tar sealink-frontend:v1.4.0

# 4. Update paketi hazırla
tar -czf rcu-update-v1.8.1.tar.gz \
  sealink-backend-v1.8.1-arm64.tar \
  sealink-frontend-v1.4.0-arm64.tar \
  docker-compose.yml
```

**Docker Image İsimlendirme Kuralı:**
- Backend: `sealink-backend-v{VERSION}-arm64.tar`
- Frontend: `sealink-frontend-v{VERSION}-arm64.tar`

**docker-compose.yml Servisleri:**
| Servis | Port | Açıklama |
|--------|------|----------|
| `backend-api` | 8000 | FastAPI backend |
| `celery-worker` | - | Background task worker |
| `redis` | 6379 | Cache ve message broker |
| `frontend` | 80 | Next.js + nginx |

---

### Senaryo 1: Docker Update (Backend/Frontend/Redis)

**Adımlar:**
1. ✅ Paket indirilir (py-offline-updater uploads/ klasörüne)
2. ✅ Pre-checks çalışır (disk space, memory)
3. ✅ **Docker container'lar backup edilir** - `docker save` ile mevcut image'lar
4. ⚡ **WatchdogKeeper.start()** - Update boyunca watchdog kick başlar
5. 🛑 `docker-compose down` (backup olan yerden de çalışır)
6. 📦 Yeni docker dosyaları (tar image'ları) hedef konuma yerleştirilir
7. 📥 `docker load` - Yeni image'lar yüklenir
8. 📄 `docker-compose.yml` doğru yere yerleştirilir
9. 🚀 `docker-compose up -d`
10. ⏳ **Health check'ler beklenir** - Tüm container'lar healthy olana kadar
    - ⚠️ Backend health check hatası ignore edilebilir (geçici)
11. 🔄 `chromium-kiosk.service` restart edilir
12. ✅ Hata yoksa Docker update tamamlanır
13. ⚡ **WatchdogKeeper.stop()** - Watchdog keeper durdurulur

```python
# Docker Update Flow (Pseudo-code)
def docker_update(docker_images_path: Path, compose_file: Path):
    # Pre-checks
    run_prechecks()

    # Backup mevcut container'lar
    backup_current_containers()  # docker save

    # Watchdog başlat
    watchdog_keeper.start()

    try:
        # Down
        docker_compose_down(compose_file)

        # Dosyaları yerleştir
        copy_docker_files(docker_images_path, DOCKER_FILES_DIR)

        # Load images
        for tar_file in docker_images_path.glob("*.tar"):
            docker_load(tar_file)

        # Compose file yerleştir
        copy_file(compose_file, DOCKER_FILES_DIR / "docker-compose.yml")

        # Up
        docker_compose_up(DOCKER_FILES_DIR / "docker-compose.yml")

        # Health checks
        wait_for_health_checks(ignore_backend_errors=True)

        # Chromium kiosk restart
        systemctl_restart("chromium-kiosk.service")

    finally:
        watchdog_keeper.stop()
```

---

### Senaryo 2: Service Backend Update

**Eğer update paketinde service backend varsa:**

⚠️ **KRİTİK:** Service Backend watchdog'u yöneten servis! Restart sırasında WatchdogKeeper mutlaka çalışıyor olmalı, yoksa sistem reboot olur.

1. ⚡ **WatchdogKeeper.start()** - Watchdog kick başlar (Service Backend durmadan ÖNCE!)
2. 📦 Önceki service backend dosyaları backup klasörüne yerleştirilir
3. 🛑 `service-backend.service` stop edilir (artık watchdog kick atmıyor ama WatchdogKeeper devrede)
4. 📥 Yeni service backend dosyaları `/app/app/service_backend/` konumuna kopyalanır
5. 🚀 `service-backend.service` start edilir
6. ⏳ Health check:
   - Service hayatta mı? (`systemctl is-active`)
   - Loglarda error var mı?
   - `curl http://localhost:8001/api/health` cevap veriyor mu?
7. ✅ Hata yoksa Service Backend update tamamlanır
8. ⚡ **WatchdogKeeper.stop()** - Watchdog keeper durdurulur (Service Backend artık kendi kick atıyor)

```python
# Service Backend Update Flow
def service_backend_update(backend_path: Path):
    BACKEND_DIR = Path("/app/app/service_backend")

    # ⚠️ KRİTİK: Watchdog keeper ÖNCE başlamalı!
    # Service Backend restart olurken biz kick atmaya devam edeceğiz
    watchdog_keeper.start()

    try:
        # Backup mevcut dosyalar
        backup_directory(BACKEND_DIR, "service_backend_backup")

        # Service'i durdur (watchdog keeper devrede, sistem reboot olmaz)
        systemctl_stop("service-backend.service")

        # Yeni dosyaları kopyala
        sync_directory(backend_path, BACKEND_DIR, mode="mirror")

        # Service'i başlat
        systemctl_start("service-backend.service")

        # Health check
        wait_for_service_healthy(
            service_name="service-backend.service",
            health_url="http://localhost:8001/api/health",
            check_logs_for_errors=True
        )

    finally:
        # Service Backend artık kendi watchdog'u kick atıyor
        # Biz durabiliriz
        watchdog_keeper.stop()
```

---

### Senaryo 3: py-offline-updater Update (Self-Update)

**Eğer update paketinde py-offline-updater varsa:**

⚠️ **Pre-check gerekli:** Updater farklı konumlarda olabilir:
- Cihaz #1: `/opt/updater/` (eski kurulum, relocation yapılacak)
- Cihaz #2: `/app/app/update/` (standart konum)

```python
# py-offline-updater location detection (pre-check)
def detect_updater_location() -> Path:
    possible_paths = [
        Path("/app/app/update"),
        Path("/opt/updater"),
    ]

    for path in possible_paths:
        if (path / "update_service").exists():
            return path

    raise UpdateError("py-offline-updater konumu bulunamadı!")
```

**Adımlar:**
1. 🔍 Pre-check: Mevcut updater konumu tespit edilir
2. 📦 Önceki updater dosyaları backup klasörüne yerleştirilir
3. 📥 Yeni updater dosyaları mevcut konuma kopyalanır
4. 🔄 `update-service.service` restart edilir
5. ⏳ Health check:
   - Service hayatta mı?
   - Loglarda error var mı?
   - `curl http://localhost:8123/api/health` cevap veriyor mu?
6. ✅ Hata yoksa py-offline-updater update tamamlanır

```python
# py-offline-updater Update Flow
def updater_update(updater_path: Path):
    # Pre-check: Konum tespit
    UPDATER_DIR = detect_updater_location()

    # Backup mevcut dosyalar
    backup_directory(UPDATER_DIR, "updater_backup")

    # Yeni dosyaları kopyala
    sync_directory(updater_path, UPDATER_DIR, mode="mirror")

    # Service restart
    systemctl_restart("update-service.service")

    # Health check
    wait_for_service_healthy(
        service_name="update-service.service",
        health_url="http://localhost:8123/api/health",
        check_logs_for_errors=True
    )
```

---

### Senaryo 4: Full System Update (Kombine)

Tüm bileşenler tek pakette güncellenebilir. **Sıralama önemli:**

```
1. Docker Update (önce)
   └── Container'lar güncellenir
   └── Frontend/Backend yeni versiyonlar

2. Service Backend Update
   └── Host üzerindeki servis güncellenir
   └── Watchdog yönetimi bu serviste

3. py-offline-updater Update (en son)
   └── Kendini günceller
   └── Self-update sonrası restart
```

**Neden bu sıra?**
- Docker update sırasında Service Backend watchdog kick atmaya devam eder
- Service Backend update sırasında WatchdogKeeper devreye girer
- Updater en son güncellenir çünkü kendi restart'ı gerekir

```python
# Full Update Flow
def full_update(
    docker_images_path: Path = None,
    compose_file: Path = None,
    backend_path: Path = None,
    updater_path: Path = None
):
    watchdog_keeper.start()

    try:
        # 1. Docker Update
        if docker_images_path and compose_file:
            docker_update(docker_images_path, compose_file)

        # 2. Service Backend Update
        if backend_path:
            service_backend_update(backend_path)

        # 3. py-offline-updater Update (en son)
        if updater_path:
            updater_update(updater_path)
            # NOT: Bu noktadan sonra servis restart olacak

    finally:
        watchdog_keeper.stop()
```

---

### CLI Tool Tasarımı

```python
# update_batch.py

import argparse
from pathlib import Path
from watchdog_keeper import WatchdogKeeper

# Sabit path'ler
DOCKER_FILES_DIR = Path("/app/app/docker-files")
SERVICE_BACKEND_DIR = Path("/app/app/service_backend")


def main():
    parser = argparse.ArgumentParser(description="RCU3 Update Batch Runner")

    # Bileşen seçimi
    parser.add_argument("--include-docker", action="store_true",
                        help="Docker container'ları güncelle")
    parser.add_argument("--include-service-backend", action="store_true",
                        help="Service Backend'i güncelle")
    parser.add_argument("--include-frontend", action="store_true",
                        help="Frontend health check yap")
    parser.add_argument("--include-updater", action="store_true",
                        help="py-offline-updater self-update")

    # Path'ler
    parser.add_argument("--docker-images", type=Path,
                        help="Docker image tar dosyalarının bulunduğu klasör")
    parser.add_argument("--compose-file", type=Path,
                        help="docker-compose.yml dosyası path'i")
    parser.add_argument("--service-backend-path", type=Path,
                        help="Service Backend dosyaları path'i")
    parser.add_argument("--updater-path", type=Path,
                        help="py-offline-updater dosyaları path'i")

    # Opsiyonel
    parser.add_argument("--frontend-health-check", action="store_true",
                        help="Sadece frontend health check yap")
    parser.add_argument("--dry-run", action="store_true",
                        help="Gerçekte çalıştırma, sadece planı göster")

    args = parser.parse_args()

    # Validation
    if args.include_docker and (not args.docker_images or not args.compose_file):
        parser.error("--include-docker için --docker-images ve --compose-file gerekli")

    if args.include_service_backend and not args.service_backend_path:
        parser.error("--include-service-backend için --service-backend-path gerekli")

    if args.include_updater and not args.updater_path:
        parser.error("--include-updater için --updater-path gerekli")

    # Update çalıştır
    run_update(args)


def run_update(args):
    """
    Update batch'i çalıştır.
    WatchdogKeeper tüm süre boyunca aktif.
    """
    watchdog_keeper = WatchdogKeeper(kick_interval=3)

    # Pre-checks
    run_prechecks()

    # Watchdog başlat
    watchdog_keeper.start()

    try:
        # 1. Docker Update
        if args.include_docker:
            docker_update(args.docker_images, args.compose_file)

        # 2. Service Backend Update
        if args.include_service_backend:
            service_backend_update(args.service_backend_path)

        # 3. Frontend Health Check
        if args.include_frontend:
            frontend_health_check()

        # 4. py-offline-updater Update (en son)
        if args.include_updater:
            updater_update(args.updater_path)

        print("✅ Update tamamlandı!")

    except Exception as e:
        print(f"❌ Update hatası: {e}")
        # Rollback logic here
        raise

    finally:
        watchdog_keeper.stop()


if __name__ == "__main__":
    main()
```

---

### Update Akış Diyagramı

```
┌─────────────────────────────────────────────────────────────────┐
│                    UPDATE BATCH BAŞLAT                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      PRE-CHECKS                                 │
│  • Disk space kontrolü                                          │
│  • Memory kontrolü                                              │
│  • py-offline-updater konum tespiti (relocation için)           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 WatchdogKeeper.start()                          │
│  • _running = True                                              │
│  • Thread başlar, while döngüsü kick atmaya başlar              │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ --include-docker │ │--include-service-│ │ --include-updater│
│                  │ │     backend      │ │                  │
│ 1. docker save   │ │ 1. backup files  │ │ 1. detect path   │
│ 2. compose down  │ │ 2. copy new files│ │ 2. backup files  │
│ 3. copy files    │ │ 3. restart svc   │ │ 3. copy new files│
│ 4. docker load   │ │ 4. health check  │ │ 4. restart svc   │
│ 5. copy compose  │ │    - is-active   │ │ 5. health check  │
│ 6. compose up    │ │    - no errors   │ │    - is-active   │
│ 7. health check  │ │    - curl health │ │    - no errors   │
│ 8. kiosk restart │ └──────────────────┘ │    - curl health │
└──────────────────┘                      └──────────────────┘
          │                   │                   │
          └───────────────────┼───────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 WatchdogKeeper.stop()                           │
│  • _running = False                                             │
│  • while döngüsü durur, thread join                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    UPDATE TAMAMLANDI                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📝 AKSİYON PLANI

### Phase 1: WatchdogKeeper Implementation ✅ TAMAMLANDI

**Çözüm:** Update sırasında py-offline-updater kendi WatchdogKeeper thread'i ile watchdog'u kick eder. Service Backend'e API eklemeye gerek yok.

**Avantajlar:**
- Service Backend'e dokunmaya gerek yok
- Basit ve güvenilir
- Her senaryoda çalışır (Docker update, Service Backend update, Self-update)

### Phase 2: Update Script Implementation 🔄 SIRADA

**Hedef:** Unified CLI tool ile tüm update senaryolarını yönetmek

**Görevler:**
1. [ ] `WatchdogKeeper` class'ı implement et
2. [ ] Docker update fonksiyonları
3. [ ] Service Backend update fonksiyonları
4. [ ] py-offline-updater self-update fonksiyonları
5. [ ] CLI argument parser

### Phase 3: Testing & Validation

**Test Senaryoları:**

1. **Test 1: Docker-only update**
   - Backend/Frontend image update
   - WatchdogKeeper aktif

2. **Test 2: Service Backend update**
   - Code update
   - WatchdogKeeper Service Backend restart boyunca çalışıyor

3. **Test 3: Full system update**
   - Docker + Service Backend + Updater
   - Sıralı güncelleme

4. **Test 4: Failure scenarios**
   - Update fails midway
   - Rollback mechanism
   - Watchdog failsafe

### Phase 4: Production Deployment

1. [ ] Smart Marine Lab cihazına deploy
2. [ ] ByteDevKit cihazına deploy
3. [ ] Monitoring setup

---

## 🎯 SONUÇ

### Çözülen Sorunlar

| Problem | Çözüm |
|---------|-------|
| **Watchdog conflict** | WatchdogKeeper - Update sırasında kendi thread'imiz kick atar |
| **Path inconsistency** | Auto-detection ile runtime'da tespit |
| **Long-running updates** | WatchdogKeeper tüm update boyunca çalışır |

### Sabit Path'ler (Tüm Cihazlarda)

- **Service Backend**: `/app/app/service_backend/` (PORT: 8001)
- **Docker files**: `/app/app/docker-files/`
- **py-offline-updater**: `/app/app/update/` veya `/opt/updater/` (PORT: 8123)

### Riskler ve Risk Azaltma

| Risk | Azaltma |
|------|---------|
| WatchdogKeeper başlamazsa | Pre-check ile kontrol, fail-fast |
| Service Backend restart uzun sürerse | Timeout + retry mekanizması |
| Disk space yetersiz | Pre-check ile alan kontrolü |
| Docker load hata verirse | Rollback mekanizması |

---

## 📚 REFERANSLAR

### Kod Tabanları

| Proje | Konum | Açıklama |
|-------|-------|----------|
| **py-offline-updater** | `/home/serkan/Desktop/py-offline-updater/` | Bu proje - Update sistemi |
| **RCU_Service** | `/home/serkan/Desktop/sealink_rcu/RCU_Service/` | Service Backend (Host) |
| **RCU_Deploy** | `/home/serkan/Desktop/sealink_rcu/RCU_Deploy/` | Docker build & deploy scripts |
| **RCU_Backend** | GitHub repo | Docker Backend (FastAPI) |
| **RCU_Frontend** | GitHub repo | Docker Frontend (Next.js) |

### Cihaz Konfigürasyonları

| Cihaz | py-offline-updater | Service Backend | Docker Files |
|-------|-------------------|-----------------|--------------|
| **Smart Marine Lab** (imx8mp) | `/opt/updater/` | `/app/app/service_backend/` | `/app/app/docker-files/` |
| **ByteDevKit** (imx93) | `/app/app/update/` | `/app/app/service_backend/` | `/app/app/docker-files/` |

### Kritik Dosyalar

**Service Backend:**
- `backend/core/utils/watchdog.py` - WatchdogManager class (async, production'da kick atar)
- `backend/core/settings.py` - WATCHDOG_ENABLED, DEBUG, BOOT_GRACE_PERIOD
- Systemd service: `service-backend.service`

**RCU_Deploy:**
- `scripts/build_manifests.py` - Manifest oluşturma (git tag'den)
- `scripts/deploy.py` - Docker build ve compose oluşturma
- `dockerfiles/backend.Dockerfile` - Backend image
- `dockerfiles/frontend.Dockerfile` - Frontend image (Next.js + nginx)

**py-offline-updater (Bu proje):**
- `update_service/` - Web UI (Port 8123)
- `update_batch.py` - CLI update tool (yazılacak)
- `watchdog_keeper.py` - WatchdogKeeper class (yazılacak)

### Port Kullanımı

| Port | Servis | Konum |
|------|--------|-------|
| 80 | Frontend (nginx) | Docker |
| 8000 | Backend API | Docker |
| 8001 | Service Backend | Host |
| 8123 | py-offline-updater | Host |
| 6379 | Redis | Docker |
| 7000 | VDR TCP Server | Host (Service Backend içinde) |

---

**Son Güncelleme:** 14 Ocak 2026
**Durum:** Implementation Ready - Yarın script yazımına başlanacak
