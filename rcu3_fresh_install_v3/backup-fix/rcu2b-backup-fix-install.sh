#!/bin/sh
# RCU2B backup compatibility fixes - install
# VDR backupcheck script'i icin RCU2B tarafinda fdisk/df wrapper ve /mnt/usb hazirlar.
# Idempotent: birden fazla kez calistirilirsa zarar vermez.
#
# Detay icin: RCU2B-BACKUP-FIX-NOTES.md

set -e

echo "==> /mnt/usb klasoru kontrol"
mkdir -p /mnt/usb

# ---- fdisk wrapper ----
FDISK=/usr/sbin/fdisk
FDISK_REAL=/usr/sbin/fdisk.util-linux
FDISK_BACKUP=/usr/sbin/fdisk.original-symlink

echo "==> fdisk wrapper kuruluyor"
if [ -f "$FDISK_BACKUP" ]; then
    echo "    Atlandi - fdisk wrapper zaten kurulu."
else
    # Eger gercek fdisk binary'si farkli bir konumdaysa, symlink'i takip edip
    # binary'yi $FDISK_REAL altina kopyala
    if [ ! -x "$FDISK_REAL" ]; then
        if [ -L "$FDISK" ]; then
            REAL_TARGET=$(readlink -f "$FDISK")
            if [ -x "$REAL_TARGET" ] && [ "$REAL_TARGET" != "$FDISK_REAL" ]; then
                cp "$REAL_TARGET" "$FDISK_REAL"
                chmod +x "$FDISK_REAL"
            fi
        fi
    fi
    if [ ! -x "$FDISK_REAL" ]; then
        echo "    HATA: $FDISK_REAL yok ve $FDISK uzerinden cikartilamiyor."
        exit 1
    fi
    if [ -L "$FDISK" ]; then
        readlink "$FDISK" > "$FDISK_BACKUP"
        rm "$FDISK"
    elif [ -f "$FDISK" ]; then
        if head -c 4 "$FDISK" 2>/dev/null | grep -q '^#!'; then
            echo "    HATA: $FDISK zaten script - manuel kontrol gerekiyor."
            exit 1
        fi
        # Regular binary (symlink degil): kaynak olarak yedekle
        cp "$FDISK" "${FDISK}.original-binary"
        echo "ORIGINAL_BINARY" > "$FDISK_BACKUP"
        rm "$FDISK"
    else
        echo "    HATA: $FDISK bulunamadi."
        exit 1
    fi
    cat > "$FDISK" <<'WRAPPER'
#!/bin/sh
# fdisk wrapper - backupcheck icin iki duzeltme:
#   1) cut -d ' ' -f 0 | grep /dev/sd icin bosluksuz device satiri
#   2) grep $DEV | grep FAT icin superfloppy FAT'li disklerde sahte
#      partition-style satir (blkid vfat dogrularsa)
REAL=/usr/sbin/fdisk.util-linux
if [ "$_FDISK_WRAPPED" = "1" ]; then
    if [ -x "$REAL" ]; then exec "$REAL" "$@"; fi
    echo "fdisk wrapper: recursive call and $REAL missing" >&2
    exit 127
fi
export _FDISK_WRAPPED=1
if [ ! -x "$REAL" ]; then
    echo "fdisk wrapper: $REAL bulunamadi" >&2
    exit 127
fi
out=$("$REAL" "$@" 2>&1)
rc=$?
inject=0
for arg in "$@"; do
    case "$arg" in -l|--list) inject=1 ;; esac
done
if [ "$inject" = "1" ]; then
    sd=$(echo "$out" | sed -n 's|^Disk \(/dev/sd[a-z][0-9]*\):.*|\1|p' | head -n 1)
    if [ -n "$sd" ]; then
        echo "$sd"
        fstype=$(blkid -o value -s TYPE "$sd" 2>/dev/null)
        case "$fstype" in vfat|msdos) echo "$sd  W95 FAT32 (LBA)" ;; esac
    fi
fi
echo "$out"
exit $rc
WRAPPER
    chmod +x "$FDISK"
    echo "    OK"
fi

# ---- df wrapper ----
DF=/bin/df
DF_REAL=/bin/busybox
DF_BACKUP=/bin/df.original-link

echo "==> df wrapper kuruluyor"
if [ -f "$DF_BACKUP" ]; then
    echo "    Atlandi - df wrapper zaten kurulu."
else
    if [ ! -x "$DF_REAL" ]; then
        echo "    HATA: $DF_REAL yok."
        exit 1
    fi
    if [ -L "$DF" ]; then
        readlink "$DF" > "$DF_BACKUP"
        rm "$DF"
    elif [ -f "$DF" ]; then
        if head -c 4 "$DF" 2>/dev/null | grep -q '^#!'; then
            echo "    HATA: $DF zaten script - manuel kontrol gerekiyor."
            exit 1
        fi
        echo "    HATA: $DF beklenmedik tipte (symlink degil)."
        exit 1
    else
        echo "    HATA: $DF bulunamadi."
        exit 1
    fi
    cat > "$DF" <<'WRAPPER'
#!/bin/sh
# df wrapper - backupcheck birim bug fix.
# Script `df -m` kullanip 8000 KB sabitiyle karsilastiriyor.
# -m'yi -k ile degistirip degerleri KB olcegine getiriyoruz.
REAL=/bin/busybox
if [ "$_DF_WRAPPED" = "1" ]; then
    exec "$REAL" df "$@"
fi
export _DF_WRAPPED=1
if [ ! -x "$REAL" ]; then
    echo "df wrapper: $REAL yok" >&2
    exit 127
fi
new_args=
for a in "$@"; do
    if [ "$a" = "-m" ]; then new_args="$new_args -k"
    else new_args="$new_args $a"
    fi
done
exec "$REAL" df $new_args
WRAPPER
    chmod +x "$DF"
    echo "    OK"
fi

echo "==> Tamamlandi."
echo "Dogrulama icin:"
echo "  fdisk -l | head -3       # USB takiliysa ilk satir /dev/sda olmali"
echo "  df -m /mnt/usb           # 4. kolon buyuk (KB degeri)"
