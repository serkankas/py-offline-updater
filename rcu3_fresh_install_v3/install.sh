#!/bin/bash
###############################################################################
# RCU3 Fresh Install Script
# Sıfırdan kurulum - Offline cihaz için
# Platform: Yocto Linux ARM64
###############################################################################

set -euo pipefail

# Colors (terminal only, stripped from log file)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="/app/app"
DOCKER_FILES_DIR="${APP_DIR}/docker-files"
SERVICE_BACKEND_DIR="${APP_DIR}/service_backend/backend"
UPDATER_DIR="${APP_DIR}/update"
SYSTEMD_DIR="/etc/systemd/system"

# Logging - ANSI stripped for log file
LOG_FILE="/tmp/rcu3_fresh_install_$(date +%Y%m%d_%H%M%S).log"

log() {
    local msg="[$(date '+%H:%M:%S')] $1"
    echo -e "${msg}"
    echo -e "${msg}" | sed 's/\x1b\[[0-9;]*m//g' >> "$LOG_FILE"
}

log_ok() { log "${GREEN}[OK]${NC} $1"; }
log_warn() { log "${YELLOW}[WARN]${NC} $1"; }
log_err() { log "${RED}[ERROR]${NC} $1"; }
log_step() { log "${CYAN}[STEP]${NC} $1"; }

die() {
    log_err "$1"
    exit 1
}

# Header
echo ""
echo -e "${BLUE}=================================================================${NC}"
echo -e "${BLUE}          RCU3 Fresh Install - Sifirdan Kurulum                  ${NC}"
echo -e "${BLUE}=================================================================${NC}"
echo ""
echo -e "  Log: ${LOG_FILE}"
echo ""

###############################################################################
# Pre-checks
###############################################################################
log_step "Pre-checks..."

if [ "$EUID" -ne 0 ]; then
    die "Bu script root olarak calistirilmali. Kullanim: sudo $0"
fi

if [ "$(uname -m)" != "aarch64" ]; then
    log_warn "Bu makine aarch64 degil ($(uname -m)). Devam ediliyor ama sorun cikabilir."
fi

# Verify package contents
for dir in docker-engine docker-images docker-files wheels systemd service-backend updater network ssh backup-fix; do
    if [ ! -d "${SCRIPT_DIR}/${dir}" ]; then
        die "Eksik klasor: ${dir}/"
    fi
done

log_ok "Paket icerigi dogrulandi"

###############################################################################
# Pre-cleanup: host nginx (Docker frontend port 80 ile cakisir)
###############################################################################
echo ""
log_step "Host nginx kontrol ediliyor (Docker frontend ile cakisma onleme)..."

NGINX_FOUND=0
for unit in nginx.service nginx; do
    if systemctl list-unit-files "${unit}" 2>/dev/null | grep -q "^${unit}"; then
        NGINX_FOUND=1
        if systemctl is-active --quiet "${unit}" 2>/dev/null; then
            systemctl stop "${unit}" && log_ok "${unit} durduruldu" || log_warn "${unit} durdurulamadi"
        fi
        if systemctl is-enabled --quiet "${unit}" 2>/dev/null; then
            systemctl disable "${unit}" 2>/dev/null && log_ok "${unit} disable edildi" || log_warn "${unit} disable edilemedi"
        fi
        break
    fi
done

if [ "$NGINX_FOUND" = "0" ]; then
    log_ok "Host nginx servisi bulunamadi (atlandi)"
fi

###############################################################################
# Step 1: Network Configuration
###############################################################################
echo ""
log_step "1/11 - Network yapilandirmasi..."

NETWORK_DIR="/etc/systemd/network"
NETWORK_FILE="${NETWORK_DIR}/00-eth.network"

mkdir -p "${NETWORK_DIR}"

if [ -f "${NETWORK_FILE}" ]; then
    log_warn "Network config zaten mevcut: ${NETWORK_FILE}"
    log "Mevcut config yedekleniyor..."
    cp "${NETWORK_FILE}" "${NETWORK_FILE}.bak.$(date +%Y%m%d_%H%M%S)"
fi

# Get MAC address of eth0 (or leave empty if not available yet)
ETH0_MAC=$(cat /sys/class/net/eth0/address 2>/dev/null || echo "")

if [ -n "$ETH0_MAC" ]; then
    # Write config with MAC address
    cat > "${NETWORK_FILE}" << EOF
[Match]
Name=eth0
MACAddress=${ETH0_MAC}

[Network]
Address=10.2.1.20/24

[Link]
RequiredForOnline=no
EOF
    log_ok "Network config yazildi (MAC: ${ETH0_MAC})"
else
    # Write config without MAC (match by name only)
    cp "${SCRIPT_DIR}/network/00-eth.network" "${NETWORK_FILE}"
    log_warn "eth0 MAC adresi alinamadi, MAC'siz config yazildi"
fi

# Restart networkd to apply
systemctl restart systemd-networkd 2>/dev/null || true

# Verify
sleep 2
ETH0_IP=$(ip -4 addr show eth0 2>/dev/null | grep -oP '(?<=inet\s)\d+\.\d+\.\d+\.\d+' || echo "")
if [ -n "$ETH0_IP" ]; then
    log_ok "eth0 IP: ${ETH0_IP}"
else
    log_warn "eth0 henuz IP almamis olabilir, reboot sonrasi aktif olacak"
fi

###############################################################################
# Step 2: Docker Engine
###############################################################################
echo ""
log_step "2/11 - Docker Engine kurulumu..."

if command -v docker &>/dev/null && command -v dockerd &>/dev/null; then
    CURRENT_DOCKER=$(docker --version 2>/dev/null || echo "unknown")
    log_warn "Docker zaten kurulu: ${CURRENT_DOCKER}"
    log_ok "Docker kurulumu atlandi"
else
    log "Docker 25.0.3 static binary'leri kuruluyor..."
    rm -rf /tmp/docker
    tar xzf "${SCRIPT_DIR}/docker-engine/docker-25.0.3.tgz" -C /tmp/
    cp /tmp/docker/* /usr/bin/
    rm -rf /tmp/docker

    if [ ! -f /usr/bin/dockerd ]; then
        die "Docker binary kurulumu basarisiz"
    fi

    log_ok "Docker binary'leri /usr/bin/ altina kuruldu"
fi
###############################################################################
# Step 2: Docker Compose
###############################################################################
log_step "3/11 - Docker Compose kurulumu..."

mkdir -p /usr/libexec/docker/cli-plugins

if [ -x /usr/libexec/docker/cli-plugins/docker-compose ]; then
    log_warn "Docker Compose zaten kurulu, yeniden kopyalaniyor..."
fi

cp "${SCRIPT_DIR}/docker-engine/docker-compose" /usr/libexec/docker/cli-plugins/docker-compose
chmod +x /usr/libexec/docker/cli-plugins/docker-compose

ln -sf /usr/libexec/docker/cli-plugins/docker-compose /usr/local/bin/docker-compose 2>/dev/null || \
ln -sf /usr/libexec/docker/cli-plugins/docker-compose /usr/bin/docker-compose 2>/dev/null || true

log_ok "Docker Compose v2.26.0 kuruldu"

###############################################################################
# Step 3: Systemd services for Docker
###############################################################################
log_step "4/11 - Docker systemd servisleri kurulumu..."

cp "${SCRIPT_DIR}/systemd/containerd.service" "${SYSTEMD_DIR}/containerd.service"
cp "${SCRIPT_DIR}/systemd/docker.service" "${SYSTEMD_DIR}/docker.service"
cp "${SCRIPT_DIR}/systemd/docker.socket" "${SYSTEMD_DIR}/docker.socket"

systemctl daemon-reload

# Enable and start Docker
systemctl enable containerd.service
systemctl enable docker.service
systemctl enable docker.socket

systemctl start containerd.service
log "containerd baslatildi, docker baslatiliyor..."

systemctl start docker.socket
systemctl start docker.service

# Wait for Docker to be ready (max 30s)
log "Docker daemon'un hazir olmasi bekleniyor..."
for i in $(seq 1 30); do
    if docker info &>/dev/null 2>&1; then
        break
    fi
    sleep 1
done

if ! docker info &>/dev/null 2>&1; then
    die "Docker daemon baslatılamadi. 'journalctl -u docker' ile kontrol edin."
fi

log_ok "Docker Engine calisiyor: $(docker --version)"

###############################################################################
# Step 4: Python Packages
###############################################################################
echo ""
log_step "5/11 - Python paketleri kurulumu..."

if ! command -v pip3 &>/dev/null; then
    die "pip3 bulunamadi. Yocto image'da python3-pip olmali."
fi

# Sürüm sabitleme yok; pip wheel klasöründeki tek sürümü kullanir (ResolutionImpossible onlenir)
pip3 install --no-index --find-links="${SCRIPT_DIR}/wheels/" -r "${SCRIPT_DIR}/wheels/requirements.txt" 2>&1 | tail -20 | tee -a "$LOG_FILE"

# Verify key packages
FAILED_PKGS=""
for pkg in fastapi uvicorn pydantic requests yaml psutil; do
    if ! python3 -c "import ${pkg}" &>/dev/null 2>&1; then
        FAILED_PKGS="${FAILED_PKGS} ${pkg}"
    fi
done

if [ -n "$FAILED_PKGS" ]; then
    log_warn "Su paketler import edilemiyor:${FAILED_PKGS}"
    log_warn "Devam ediliyor ama sorun cikabilir."
else
    log_ok "Tum Python paketleri basariyla kuruldu ($(ls ${SCRIPT_DIR}/wheels/*.whl | wc -l) wheel)"
fi

###############################################################################
# Step 5: Directory Structure
###############################################################################
echo ""
log_step "6/11 - Dizin yapisi olusturuluyor..."

mkdir -p "${APP_DIR}"
mkdir -p "${APP_DIR}/backups"
mkdir -p "${APP_DIR}/docker-files"
mkdir -p "${APP_DIR}/files_from_vdr"
mkdir -p "${APP_DIR}/logs"
mkdir -p "${APP_DIR}/service_backend/backend"
mkdir -p "${UPDATER_DIR}"/{uploads,tmp,backups,logs,update-engines,bootstrap}

log_ok "Dizin yapisi olusturuldu"

###############################################################################
# Step 6: Docker Images & Compose
###############################################################################
echo ""
log_step "7/11 - Docker image'lari ve compose kurulumu..."

# Load Docker images
for img in frontend.tar backend.tar redis.tar; do
    if [ -f "${SCRIPT_DIR}/docker-images/${img}" ]; then
        log "Yukleniyor: ${img}..."
        docker load < "${SCRIPT_DIR}/docker-images/${img}" 2>&1 | tee -a "$LOG_FILE"
        log_ok "${img} yuklendi"
    else
        die "${img} bulunamadi! Docker image eksik."
    fi
done

# Copy docker-compose.yml and service.env
cp "${SCRIPT_DIR}/docker-files/docker-compose.yml" "${DOCKER_FILES_DIR}/docker-compose.yml"
cp "${SCRIPT_DIR}/docker-files/service.env" "${DOCKER_FILES_DIR}/service.env"

log_ok "Docker dosyalari ${DOCKER_FILES_DIR}/ altina kopyalandi"

# Start containers
log "Docker container'lar baslatiliyor..."
cd "${DOCKER_FILES_DIR}"
docker compose up -d 2>&1 | tee -a "$LOG_FILE"

# Wait for containers to be healthy (max 90s)
# 3 container has healthcheck (redis, backend-api, frontend), celery-worker has none
log "Container'larin hazir olmasi bekleniyor (max 90s)..."
HEALTHY_OK=false
for i in $(seq 1 90); do
    HEALTHY=$(docker ps --filter "health=healthy" --format "{{.Names}}" 2>/dev/null | wc -l)
    TOTAL=$(docker ps --format "{{.Names}}" 2>/dev/null | wc -l)
    if [ "$HEALTHY" -ge 3 ] && [ "$TOTAL" -ge 4 ]; then
        HEALTHY_OK=true
        break
    fi
    sleep 1
done

RUNNING=$(docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null)
log "Container durumlari:\n${RUNNING}"

if [ "$HEALTHY_OK" = true ]; then
    log_ok "Tum container'lar saglıklı"
else
    log_warn "Bazi container'lar henuz hazir degil. 'docker ps' ile kontrol edin."
fi

###############################################################################
# Step 7: Service Backend
###############################################################################
echo ""
log_step "8/11 - Service Backend kurulumu..."

# Copy service-backend files
cp -r "${SCRIPT_DIR}/service-backend/"* "${SERVICE_BACKEND_DIR}/"
# Clean __pycache__ if any
find "${SERVICE_BACKEND_DIR}" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Copy .env file for service-backend
if [ -f "${DOCKER_FILES_DIR}/service.env" ]; then
    cp "${DOCKER_FILES_DIR}/service.env" "${SERVICE_BACKEND_DIR}/.env"
    log_ok "Service .env dosyasi kopyalandi"
fi

# Set ownership for /app/app (device uses weston:weston)
if id "weston" &>/dev/null; then
    chown -R weston:weston "${APP_DIR}"
    log_ok "/app/app ownership weston:weston olarak ayarlandi"
else
    log_warn "'weston' kullanicisi bulunamadi, ownership root olarak kaldi"
fi

# Install systemd service
cp "${SCRIPT_DIR}/systemd/service-backend.service" "${SYSTEMD_DIR}/service-backend.service"
systemctl daemon-reload
systemctl enable service-backend.service
systemctl start service-backend.service

# Wait and verify
sleep 3
if systemctl is-active --quiet service-backend.service; then
    log_ok "Service Backend calisiyor (port 8001)"
else
    log_warn "Service Backend baslatılamadi. 'journalctl -u service-backend' ile kontrol edin."
fi

###############################################################################
# Step 8: py-offline-updater
###############################################################################
echo ""
log_step "9/11 - py-offline-updater kurulumu..."

# Copy updater files
cp -r "${SCRIPT_DIR}/updater/"* "${UPDATER_DIR}/"
# Clean __pycache__ if any
find "${UPDATER_DIR}" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Create update engine directory
mkdir -p "${UPDATER_DIR}/update-engines/v1.0.0/update_engine"
if [ -d "${UPDATER_DIR}/update_engine" ]; then
    cp -r "${UPDATER_DIR}/update_engine/"* "${UPDATER_DIR}/update-engines/v1.0.0/update_engine/"
fi

# Create 'current' symlink
ln -sfn "v1.0.0" "${UPDATER_DIR}/update-engines/current"

# Copy bootstrap to correct location
cp "${UPDATER_DIR}/bootstrap.py" "${UPDATER_DIR}/bootstrap/bootstrap.py"
chmod +x "${UPDATER_DIR}/bootstrap/bootstrap.py"

# Create bootstrap wrapper (/usr/local/bin may not exist on minimal/embedded systems)
mkdir -p /usr/local/bin
cat > /usr/local/bin/update-bootstrap << WRAPPER_EOF
#!/bin/bash
UPDATER_DIR="${UPDATER_DIR:-/app/app/update}"
ENGINE_DIR="\${UPDATER_DIR}/update-engines/current"
export PYTHONPATH="\$ENGINE_DIR"
exec python3 "\${UPDATER_DIR}/bootstrap/bootstrap.py" "\$@"
WRAPPER_EOF
chmod +x /usr/local/bin/update-bootstrap

# Install systemd service
cp "${SCRIPT_DIR}/systemd/py-updater.service" "${SYSTEMD_DIR}/py-updater.service"
systemctl daemon-reload
systemctl enable py-updater.service
systemctl start py-updater.service

sleep 2
if systemctl is-active --quiet py-updater.service; then
    log_ok "py-offline-updater calisiyor (port 8123)"
else
    log_warn "py-updater baslatılamadi. 'journalctl -u py-updater' ile kontrol edin."
fi

###############################################################################
# Step 10: SSH legacy RSA algorithm support (VDR uyumlulugu)
###############################################################################
echo ""
log_step "10/11 - SSH legacy RSA algoritma destegi..."

# VDR'in eski BusyBox SSH client'i ssh-rsa host key + pubkey kullaniyor.
# Modern OpenSSH (>= 8.8) ssh-rsa'yi default'tan kaldirdi. Drop-in ile aktif et.
SSHD_DROPIN_DIR="/etc/ssh/sshd_config.d"
SSHD_DROPIN_FILE="${SSHD_DROPIN_DIR}/10-legacy-rsa.conf"
SSHD_CONFIG="/etc/ssh/sshd_config"

if [ -d "$SSHD_DROPIN_DIR" ] && grep -qE '^\s*Include\s+/etc/ssh/sshd_config\.d/' "$SSHD_CONFIG" 2>/dev/null; then
    cp "${SCRIPT_DIR}/ssh/10-legacy-rsa.conf" "$SSHD_DROPIN_FILE"
    chmod 644 "$SSHD_DROPIN_FILE"
    log_ok "sshd drop-in yazildi: ${SSHD_DROPIN_FILE}"
else
    # Drop-in desteklenmiyor: dogrudan sshd_config'e idempotent ekleme
    if [ ! -f "$SSHD_CONFIG" ]; then
        log_warn "${SSHD_CONFIG} yok, SSH legacy ayar atlandi"
    else
        if ! grep -qE '^\s*HostKeyAlgorithms\s+\+ssh-rsa' "$SSHD_CONFIG"; then
            cp "$SSHD_CONFIG" "${SSHD_CONFIG}.bak.$(date +%Y%m%d_%H%M%S)"
            {
                echo ""
                echo "# RCU3 fresh-install: VDR (eski BusyBox SSH) uyumlulugu icin legacy RSA"
                echo "HostKeyAlgorithms +ssh-rsa"
                echo "PubkeyAcceptedAlgorithms +ssh-rsa"
            } >> "$SSHD_CONFIG"
            log_ok "sshd_config'e legacy RSA satirlari eklendi (yedek: ${SSHD_CONFIG}.bak.*)"
        else
            log_warn "sshd_config'de HostKeyAlgorithms +ssh-rsa zaten var, atlandi"
        fi
    fi
fi

# sshd config dogrula ve reload
if command -v sshd &>/dev/null; then
    if sshd -t 2>/dev/null; then
        # Reload (active degilse atla)
        if systemctl is-active --quiet sshd.service 2>/dev/null; then
            systemctl reload sshd.service 2>/dev/null || systemctl restart sshd.service
            log_ok "sshd reload edildi"
        elif systemctl is-active --quiet ssh.service 2>/dev/null; then
            systemctl reload ssh.service 2>/dev/null || systemctl restart ssh.service
            log_ok "ssh reload edildi"
        else
            log_warn "sshd servisi aktif degil, reload atlandi (config gecerli)"
        fi
    else
        log_err "sshd config dogrulama hatasi (sshd -t fail). Yedekten geri al ve kontrol edin."
    fi
else
    log_warn "sshd binary bulunamadi, reload atlandi"
fi

###############################################################################
# Step 11: RCU2B backup compatibility fixes (fdisk/df wrapper + /mnt/usb)
###############################################################################
echo ""
log_step "11/11 - RCU2B backup compatibility fixes..."

# VDR'in 'backupcheck' script'i RCU2B uzerinde:
#   - fdisk -l ciktisinda /dev/sda satiri (cut -f 0 bug fix)
#   - superfloppy FAT diskler icin sahte partition satiri
#   - df -m yerine -k (8000 KB vs MB birim hatasi)
#   - /mnt/usb mount target
# bekliyor. Wrapper'lari idempotent install script'i ile kuruyoruz.
# Detay: RCU2B-BACKUP-FIX-NOTES.md

BACKUP_FIX_TARGET_DIR="/usr/local/sbin"
mkdir -p "$BACKUP_FIX_TARGET_DIR"

cp "${SCRIPT_DIR}/backup-fix/rcu2b-backup-fix-install.sh" "${BACKUP_FIX_TARGET_DIR}/rcu2b-backup-fix-install.sh"
cp "${SCRIPT_DIR}/backup-fix/rcu2b-backup-fix-uninstall.sh" "${BACKUP_FIX_TARGET_DIR}/rcu2b-backup-fix-uninstall.sh"
chmod +x "${BACKUP_FIX_TARGET_DIR}/rcu2b-backup-fix-install.sh"
chmod +x "${BACKUP_FIX_TARGET_DIR}/rcu2b-backup-fix-uninstall.sh"

log "Backup-fix wrapper'lari uygulaniyor..."
if "${BACKUP_FIX_TARGET_DIR}/rcu2b-backup-fix-install.sh" 2>&1 | tee -a "$LOG_FILE"; then
    log_ok "Backup-fix wrapper'lari kuruldu (fdisk, df, /mnt/usb)"
else
    log_warn "Backup-fix install hatali bitti. Manuel kontrol: ${BACKUP_FIX_TARGET_DIR}/rcu2b-backup-fix-install.sh"
fi

###############################################################################
# Chromium Kiosk (enable only, starts after reboot)
###############################################################################
echo ""
log_step "Chromium Kiosk servisi aktif ediliyor..."

cp "${SCRIPT_DIR}/systemd/chromium-kiosk.service" "${SYSTEMD_DIR}/chromium-kiosk.service"
systemctl daemon-reload
systemctl enable chromium-kiosk.service

log_ok "chromium-kiosk.service etkinlestirildi (reboot sonrasi baslar)"

###############################################################################
# Final Verification
###############################################################################
echo ""
echo -e "${BLUE}=================================================================${NC}"
echo -e "${BLUE}                    Kurulum Ozeti                                ${NC}"
echo -e "${BLUE}=================================================================${NC}"
echo ""

# Docker
DOCKER_VER=$(docker --version 2>/dev/null || echo "HATA")
COMPOSE_VER=$(docker compose version 2>/dev/null || echo "HATA")
echo -e "  Docker Engine:    ${GREEN}${DOCKER_VER}${NC}"
echo -e "  Docker Compose:   ${GREEN}${COMPOSE_VER}${NC}"
echo ""

# Containers
echo -e "  ${CYAN}Docker Container'lar:${NC}"
docker ps --format "    {{.Names}}: {{.Status}}" 2>/dev/null || echo "    HATA"
echo ""

# Services
echo -e "  ${CYAN}Systemd Servisleri:${NC}"
for svc in docker service-backend py-updater chromium-kiosk; do
    STATUS=$(systemctl is-active ${svc}.service 2>/dev/null || echo "inactive")
    ENABLED=$(systemctl is-enabled ${svc}.service 2>/dev/null || echo "disabled")
    if [ "$STATUS" = "active" ]; then
        echo -e "    ${svc}: ${GREEN}${STATUS}${NC} (${ENABLED})"
    else
        echo -e "    ${svc}: ${YELLOW}${STATUS}${NC} (${ENABLED})"
    fi
done
echo ""

# Network
echo -e "  ${CYAN}Network:${NC}"
ETH0_IP=$(ip -4 addr show eth0 2>/dev/null | grep -oP '(?<=inet\s)\d+\.\d+\.\d+/\d+' || echo "N/A")
echo -e "    eth0: ${ETH0_IP}"
echo ""

# SSH legacy RSA
echo -e "  ${CYAN}SSH legacy RSA:${NC}"
if [ -f /etc/ssh/sshd_config.d/10-legacy-rsa.conf ]; then
    echo -e "    drop-in: ${GREEN}OK${NC} (/etc/ssh/sshd_config.d/10-legacy-rsa.conf)"
elif grep -qE '^\s*HostKeyAlgorithms\s+\+ssh-rsa' /etc/ssh/sshd_config 2>/dev/null; then
    echo -e "    inline:  ${GREEN}OK${NC} (/etc/ssh/sshd_config)"
else
    echo -e "    ${YELLOW}eksik${NC} - VDR baglantisinda sorun cikabilir"
fi
echo ""

# RCU2B backup compatibility
echo -e "  ${CYAN}RCU2B backup-fix:${NC}"
[ -d /mnt/usb ] && MNT_USB="${GREEN}var${NC}" || MNT_USB="${YELLOW}YOK${NC}"
[ -f /usr/sbin/fdisk.original-symlink ] && FDISK_WRAP="${GREEN}aktif${NC}" || FDISK_WRAP="${YELLOW}pasif${NC}"
[ -f /bin/df.original-link ] && DF_WRAP="${GREEN}aktif${NC}" || DF_WRAP="${YELLOW}pasif${NC}"
echo -e "    /mnt/usb:        ${MNT_USB}"
echo -e "    fdisk wrapper:   ${FDISK_WRAP}"
echo -e "    df wrapper:      ${DF_WRAP}"
echo ""

# Ports
echo -e "  ${CYAN}Portlar:${NC}"
echo -e "    80   - Frontend (nginx)"
echo -e "    8000 - Backend API"
echo -e "    8001 - Service Backend"
echo -e "    8123 - py-offline-updater"
echo -e "    6379 - Redis"
echo ""

# Disk usage
INSTALL_SIZE=$(du -sh "${APP_DIR}" 2>/dev/null | cut -f1)
echo -e "  ${CYAN}Disk Kullanimi:${NC}"
echo -e "    ${APP_DIR}: ${INSTALL_SIZE}"
echo ""

echo -e "  Log: ${LOG_FILE}"
echo ""
echo -e "${GREEN}Kurulum tamamlandi!${NC}"
echo -e "${YELLOW}Chromium kiosk icin reboot onerilir: sudo reboot${NC}"
echo ""
echo -e "${BLUE}=================================================================${NC}"
