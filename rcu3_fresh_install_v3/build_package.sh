#!/bin/bash
###############################################################################
# RCU3 Fresh Install - Package Builder
# Bu scripti gelistirme makinasinda calistir (x86_64 olabilir)
# Sonuc: rcu3_fresh_install.tar.gz
###############################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_FILE="${SCRIPT_DIR}/rcu3_fresh_install_v3.tar.gz"

echo "RCU3 Fresh Install v3 paketi olusturuluyor..."
echo ""

# Verify all required dirs/files exist
MISSING=""
for item in install.sh docker-engine/docker-25.0.3.tgz docker-engine/docker-compose \
            docker-images/frontend.tar docker-images/backend.tar docker-images/redis.tar \
            docker-files/docker-compose.yml docker-files/service.env \
            wheels systemd service-backend updater network \
            ssh/10-legacy-rsa.conf \
            backup-fix/rcu2b-backup-fix-install.sh \
            backup-fix/rcu2b-backup-fix-uninstall.sh; do
    if [ ! -e "${SCRIPT_DIR}/${item}" ]; then
        MISSING="${MISSING}\n  - ${item}"
    fi
done

if [ -n "$MISSING" ]; then
    echo "HATA: Eksik dosyalar:${MISSING}"
    exit 1
fi

# Count contents
WHEEL_COUNT=$(ls "${SCRIPT_DIR}/wheels/"*.whl 2>/dev/null | wc -l)
SERVICE_COUNT=$(ls "${SCRIPT_DIR}/systemd/"*.service 2>/dev/null | wc -l)

echo "  Wheels:          ${WHEEL_COUNT} paket"
echo "  Docker images:   3 (frontend, backend, redis)"
echo "  Docker engine:   25.0.3 (aarch64)"
echo "  Docker Compose:  v2.26.0 (aarch64)"
echo "  Systemd:         ${SERVICE_COUNT} servis"
echo ""

# Build tar.gz (exclude build script, guide, and __pycache__)
cd "${SCRIPT_DIR}"
tar czf "${OUTPUT_FILE}" \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    install.sh \
    docker-engine/ \
    docker-images/ \
    docker-files/ \
    wheels/ \
    systemd/ \
    service-backend/ \
    updater/ \
    network/ \
    ssh/ \
    backup-fix/

SIZE=$(du -h "${OUTPUT_FILE}" | cut -f1)
echo "Paket olusturuldu: ${OUTPUT_FILE}"
echo "Boyut: ${SIZE}"
echo ""
echo "Cihaza kopyala ve calistir:"
echo "  scp ${OUTPUT_FILE} root@<device-ip>:/tmp/"
echo "  ssh root@<device-ip>"
echo "  cd /tmp && tar xzf rcu3_fresh_install_v3.tar.gz && sudo ./install.sh"
