# RCU2B Backup Sorunları — Diagnostic ve Düzeltmeler

Tarih: 2026-05-11
Hedef: RCU2B üreticisi olarak, müşteri VDR'larındaki sabit `backupcheck`
script'ine dokunmadan, RCU2B tarafında wrapper'larla bug'ları bypass etmek.

## Mimari

```
┌─────────────────────────┐         ┌──────────────────────────┐
│       VDR               │         │       RCU2B              │
│       10.2.1.10         │         │       10.2.1.20          │
│  (müşteride, dokunulmaz)│         │  (bytedevkit-imx93)      │
│                         │         │  BusyBox 1.36.1          │
│  BusyBox 1.13.4 (2016)  │         │  USB (/dev/sda) burada   │
│                         │ ──SSH─▶ │                          │
│  /app/backupcheck       │ (root,  │  /mnt/usb hedef mount    │
│  daemon — her 10sn'de   │ pass:   │                          │
│  /tmp/startservicebackup│ kallepigg)                         │
│  kontrol eder           │         │                          │
└─────────────────────────┘         └──────────────────────────┘
```

**Frontend → Backend tetikleme zinciri:**

1. RCU2 Web UI'da kullanıcı Y → X (small) veya Y → Y (complete) basar
2. Browser `POST {VDR}:8080/api/backup/start` yapar (body: `small=true` veya boş)
3. VDR'ın HTTP server'ı `/tmp/startservicebackup` dosyasını oluşturur
4. VDR'da `backupcheck` daemon'u her 10 saniyede bu dosyayı kontrol eder
5. Dosya varsa içeriğine bakıp `small` veya `complete` backup başlatır
6. Daemon SSH ile RCU2B'ye bağlanır, USB'yi mount eder, tar | ssh tar ile data aktarır
7. UI 1sn'de bir `GET {VDR}:8080/api/backup/{status,info,progress,duration}` ile polling yapar
8. Status `DONE`/`STOPPED`/`ERROR` olunca polling biter

## Tespit edilen sorunlar ve sebepleri

### 1. `ERROR! USB stick not inserted.` — `cut -f 0` davranış farkı

**Script'in çağrısı** (`backupcheck:50`):
```sh
DEVICE_NAME=`$SSH_COMMAND fdisk -l | cut -d ' ' -f 0 | grep "/dev/sd" | head -n 1`
```

- `fdisk -l` RCU2B'de çalışıyor, çıktı VDR'a dönüyor
- `cut`, `grep`, `head` VDR'da işliyor
- VDR'ın BusyBox 1.13.4 `cut`'ı, **`-f 0`'ı `-f 1` gibi yorumluyor** (ilk alan)
- Modern util-linux `fdisk -l` çıktısı: `Disk /dev/sda: 7.5 GiB, ...`
- `cut -d ' ' -f 0` → "Disk" döner, `/dev/sda` değil
- `grep "/dev/sd"` "Disk"i eşlemiyor → `DEVICE_NAME` boş → "USB not inserted"

**Eski RCU2'de çalışıyordu çünkü:** muhtemelen partition'lı USB ile geliyor ve
fdisk çıktısında `/dev/sda1   2048 ...` satırı var → cut -f 1 = `/dev/sda1` ✓

**RCU2B'de çalışmıyor:** test USB superfloppy formatlı (partition table yok),
sadece `Disk /dev/sda:` satırında `/dev/sd` geçiyor → cut -f 1 = "Disk".

**Düzeltme:** RCU2B'de `fdisk` wrapper — `fdisk -l` çıktısının başına
boşluksuz bir `/dev/sda` satırı ekle. Cut bunu yakalar.

### 2. `ERROR! Unknown filesystem.` — superfloppy FAT

**Script'in çağrısı** (`backupcheck:64`):
```sh
FILESYSTEM=`$SSH_COMMAND fdisk -l | grep "$DEVICE_NAME" | grep -o -e FAT.*`
```

- USB **gerçekten FAT32** (`blkid /dev/sda` → `TYPE="vfat"`)
- Ama superfloppy formatta (partition table yok)
- Modern fdisk filesystem bilgisini sadece partition satırlarında basıyor
- Bizim USB'de partition yok → FAT geçen satır yok → script "Unknown" diyor

**Düzeltme:** fdisk wrapper'a sahte bir "partition" satırı eklendi:
```
/dev/sda  W95 FAT32 (LBA)
```
Sadece `blkid` gerçekten `vfat` derse ekleniyor (yalan söylememek için).
`mount /dev/sda /mnt/usb` zaten superfloppy FAT'i mount edebiliyor.

### 3. `ERROR! Could not mount USB stick.` — eksik mount target

**Script'in çağrısı** (`backupcheck:80`):
```sh
$SSH_COMMAND mount "$DEVICE_NAME $REMOTE_MOUNT_DIRECTORY"
```
RCU2B'de `/mnt/usb` klasörü yoktu, sadece `/mnt/emmc` ve `/mnt/psplash_fifo` vardı.
Script `mkdir` yapmıyor, doğrudan mount deniyor → ENOENT → fail.

**Düzeltme:** RCU2B'de bir kez `mkdir -p /mnt/usb`. Boş klasör, sistemde
diğer hiçbir şeyi etkilemiyor. Bunu RCU2B firmware imajına dahil etmek gerekiyor
(reboot'ta gitmediğinden emin olmak için `df /mnt` ile rootfs'te olduğunu doğrula).

### 4. `Not enough space, Required: 8MB, Available: 7MB` — birim hatası

**Script'in çağrısı** (`backupcheck:105-127`):
```sh
local MAX_MINUTE_DIRECTORY_SIZE_IN_BYTES=8000 #8MB (a very, very large minute folder)
REQUIRED_SPACE=$(($NUMBER_OF_MINUTES*$MAX_MINUTE_DIRECTORY_SIZE_IN_BYTES))
AVAILABLE_SPACE=`$SSH_COMMAND df -m | grep "$REMOTE_MOUNT_DIRECTORY" | tr -s | xargs | cut -d ' ' -f 4`
```

- Sabit `8000` — değişken adı `_IN_BYTES` ama yorum "8MB"; gerçekte **8000 KB** anlamına geliyor (≈ 8 MB)
- `df -m` ile **MB** değer alıyor (7648 gibi)
- Karşılaştırma: `8000 (KB) > 7648 (MB)` — birimler tutmuyor, küçük backup'ta bile fail
- Display'deki `%???` (son 3 karakter strip) `8000 KB → "8"`, `7648 MB → "7"` — "8MB vs 7MB" yanıltıcı çıktı

**Düzeltme:** RCU2B'de `df` wrapper — `-m` argümanını içeride `-k` ile
değiştir. Böylece script'in beklediği KB ölçeği gelir, karşılaştırma doğru
çalışır. Display'de "Available: 7848MB" yazacak (aslında KB ama %3 hata
ile MB'a denk geliyor — kabul edilebilir kozmetik).

---

## Uygulanan değişiklikler (RCU2B üzerinde)

### A. `/mnt/usb` klasörü

```sh
mkdir -p /mnt/usb
```

> Production: bu klasör RCU2B image'ında olmalı. Yoksa `/etc/tmpfiles.d/` veya
> init script'i ile boot'ta oluştur.

### B. fdisk wrapper

- Path: `/usr/sbin/fdisk` (eski util-linux symlink yerine script)
- Real binary: `/usr/sbin/fdisk.util-linux`
- Backup: `/usr/sbin/fdisk.original-symlink` (eski symlink hedefi)

İçerik:
```sh
#!/bin/sh
# fdisk wrapper — backupcheck için iki düzeltme:
#   1) cut -d ' ' -f 0 | grep /dev/sd için boşluksuz device satırı
#   2) grep $DEV | grep FAT için superfloppy FAT'li disklerde sahte
#      partition-style satır (blkid vfat doğrularsa)

REAL=/usr/sbin/fdisk.util-linux

if [ "$_FDISK_WRAPPED" = "1" ]; then
    if [ -x "$REAL" ]; then
        exec "$REAL" "$@"
    fi
    echo "fdisk wrapper: recursive call and $REAL missing" >&2
    exit 127
fi
export _FDISK_WRAPPED=1

if [ ! -x "$REAL" ]; then
    echo "fdisk wrapper: $REAL bulunamadı" >&2
    exit 127
fi

out=$("$REAL" "$@" 2>&1)
rc=$?

# Sadece -l/--list çağrılarında inject et
inject=0
for arg in "$@"; do
    case "$arg" in
        -l|--list) inject=1 ;;
    esac
done

if [ "$inject" = "1" ]; then
    sd=$(echo "$out" | sed -n 's|^Disk \(/dev/sd[a-z][0-9]*\):.*|\1|p' | head -n 1)
    if [ -n "$sd" ]; then
        echo "$sd"
        fstype=$(blkid -o value -s TYPE "$sd" 2>/dev/null)
        case "$fstype" in
            vfat|msdos)
                echo "$sd  W95 FAT32 (LBA)"
                ;;
        esac
    fi
fi
echo "$out"
exit $rc
```

### C. df wrapper

- Path: `/bin/df` (eski busybox symlink yerine script)
- Real binary: `/bin/busybox df`
- Backup: `/bin/df.original-link` (eski symlink hedefi: `busybox`)

İçerik:
```sh
#!/bin/sh
# df wrapper — backupcheck birim bug fix.
# Script `df -m` kullanıp 8000 KB sabitiyle karşılaştırıyor.
# -m'yi -k ile değiştirip değerleri KB ölçeğine getiriyoruz.

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
    if [ "$a" = "-m" ]; then
        new_args="$new_args -k"
    else
        new_args="$new_args $a"
    fi
done

exec "$REAL" df $new_args
```

---

## Setup scriptleri

### Install (RCU2B'de tek seferde)

`/usr/local/sbin/rcu2b-backup-fix-install.sh`:

```sh
#!/bin/sh
# RCU2B backup compatibility fixes — install
# Bu script idempotent: birden fazla kez çalıştırılırsa zarar vermez.

set -e

echo "==> /mnt/usb klasörünü kontrol et"
mkdir -p /mnt/usb

# ---- fdisk wrapper ----
FDISK=/usr/sbin/fdisk
FDISK_REAL=/usr/sbin/fdisk.util-linux
FDISK_BACKUP=/usr/sbin/fdisk.original-symlink

echo "==> fdisk wrapper kuruluyor"
if [ -f "$FDISK_BACKUP" ]; then
    echo "    Atlandı — fdisk wrapper zaten kurulu."
else
    if [ ! -x "$FDISK_REAL" ]; then
        echo "    HATA: $FDISK_REAL yok."
        exit 1
    fi
    if [ ! -L "$FDISK" ]; then
        if [ -f "$FDISK" ] && head -c 4 "$FDISK" 2>/dev/null | grep -q '^#!'; then
            echo "    HATA: $FDISK zaten script — manuel bak."
            exit 1
        fi
        echo "    HATA: $FDISK beklenmedik tipte."
        exit 1
    fi
    readlink "$FDISK" > "$FDISK_BACKUP"
    rm "$FDISK"
    cat > "$FDISK" <<'WRAPPER'
#!/bin/sh
REAL=/usr/sbin/fdisk.util-linux
if [ "$_FDISK_WRAPPED" = "1" ]; then
    if [ -x "$REAL" ]; then exec "$REAL" "$@"; fi
    echo "fdisk wrapper: recursive call and $REAL missing" >&2
    exit 127
fi
export _FDISK_WRAPPED=1
if [ ! -x "$REAL" ]; then
    echo "fdisk wrapper: $REAL bulunamadı" >&2
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
    echo "    Atlandı — df wrapper zaten kurulu."
else
    if [ ! -x "$DF_REAL" ]; then
        echo "    HATA: $DF_REAL yok."
        exit 1
    fi
    if [ ! -L "$DF" ]; then
        if [ -f "$DF" ] && head -c 4 "$DF" 2>/dev/null | grep -q '^#!'; then
            echo "    HATA: $DF zaten script — manuel bak."
            exit 1
        fi
        echo "    HATA: $DF beklenmedik tipte."
        exit 1
    fi
    readlink "$DF" > "$DF_BACKUP"
    rm "$DF"
    cat > "$DF" <<'WRAPPER'
#!/bin/sh
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

echo "==> Tamamlandı."
echo "Doğrulama için:"
echo "  fdisk -l | head -3       # ilk satır /dev/sda olmalı"
echo "  df -m /mnt/usb           # 4. kolon büyük (KB değeri)"
```

### Uninstall

`/usr/local/sbin/rcu2b-backup-fix-uninstall.sh`:

```sh
#!/bin/sh
set -e

# fdisk wrapper geri al
FDISK=/usr/sbin/fdisk
FDISK_BACKUP=/usr/sbin/fdisk.original-symlink
if [ -f "$FDISK_BACKUP" ]; then
    TARGET=$(cat "$FDISK_BACKUP")
    rm "$FDISK"
    ln -s "$TARGET" "$FDISK"
    rm "$FDISK_BACKUP"
    echo "fdisk: geri yüklendi -> $TARGET"
else
    echo "fdisk: yedek yok, atlandı"
fi

# df wrapper geri al
DF=/bin/df
DF_BACKUP=/bin/df.original-link
if [ -f "$DF_BACKUP" ]; then
    TARGET=$(cat "$DF_BACKUP")
    rm "$DF"
    ln -s "$TARGET" "$DF"
    rm "$DF_BACKUP"
    echo "df: geri yüklendi -> $TARGET"
else
    echo "df: yedek yok, atlandı"
fi

# /mnt/usb dokunmadan kalır (zararsız boş klasör)
echo "/mnt/usb klasörü olduğu gibi bırakıldı."
```

---

## Test prosedürü

### 1. Wrapper doğrulamaları (RCU2B üzerinde)

```sh
# fdisk wrapper
fdisk -l | head -3
# Beklenen:
# /dev/sda
# /dev/sda  W95 FAT32 (LBA)
# Disk /dev/mmcblk0: ...

# df wrapper
df -m /mnt/usb
# Beklenen: 4. kolon ~7848828 gibi büyük sayı (KB)
```

### 2. Pipeline doğrulamaları (VDR'dan)

```sh
# cut zinciri /dev/sda dönmeli:
/app/sshpass -p kallepigg ssh -oStrictHostKeyChecking=no root@10.2.1.20 "fdisk -l" \
  | cut -d ' ' -f 0 | grep "/dev/sd" | head -n 1

# Filesystem check FAT dönmeli:
/app/sshpass -p kallepigg ssh -oStrictHostKeyChecking=no root@10.2.1.20 "fdisk -l" \
  | grep "/dev/sda" | grep -o -e FAT.*

# Disk space büyük sayı dönmeli:
/app/sshpass -p kallepigg ssh -oStrictHostKeyChecking=no root@10.2.1.20 "df -m" \
  | grep /mnt/usb | tr -s | xargs | cut -d ' ' -f 4
```

### 3. End-to-end backup (VDR'da)

İzleyici (bir terminalde):
```sh
while true; do
    clear; date
    echo "--- info  ---"; cat /tmp/servicebackupinfomessage 2>/dev/null
    echo "--- err   ---"; cat /tmp/servicebackuperrormessage 2>/dev/null
    echo "--- done  ---"; cat /tmp/servicebackupfinished 2>/dev/null
    sleep 1
done
```

Tetikleyici (ayrı terminalde):
```sh
rm -f /tmp/servicebackupfinished /tmp/servicebackuperrormessage
echo "small" > /tmp/startservicebackup
```

İzleyicide beklenen final durum:
```
--- info  ---
Waiting to start backup...
--- err   ---
--- done  ---
SUCCESS
```

USB'de doğrulama:
```sh
/app/sshpass -p kallepigg ssh -oStrictHostKeyChecking=no root@10.2.1.20 \
  "ls /mnt/usb/backup-*"
```

---

## Bilinen başka script bug'ları (henüz tetiklenmedi, gelecekte sorun olabilir)

1. **`tr -s` argümansız** (`backupcheck:112`) — POSIX'te geçersiz, BusyBox 1.13.4
   tolere ediyor. Sürüm değişirse patlar.

2. **`mount "$DEVICE_NAME $REMOTE_MOUNT_DIRECTORY"`** (`backupcheck:80`) — argümanlar
   tek string olarak quoted ama SSH whitespace'te parçaladığı için tesadüfen çalışıyor.

3. **`COMMAND_STATUS` boş kontrolü** (`backupcheck:180`) — tar pipeline'ın stdout'una
   bakıp boşsa "error" diyor. Remote `tar xvf -` verbose çıktısı buradan geçtiği için
   genelde boş olmuyor. Ama `-v` olmadan çağrılırsa veya verbose stderr'e giderse
   yanlış pozitif "error" verebilir.

4. **Son 3 dakikayı atlama** (`backupcheck:188`, `SKIP_MINUTES=3`) — tamamlanmamış
   minute klasörlerini almamak için ama bu sabit; veri yazım hızına göre yetersiz
   kalabilir.

5. **Hardcoded SSH şifresi** (`backupcheck:4`, `kallepigg`) — production'da ciddi
   güvenlik açığı. RCU2B firmware'inde root SSH password'unun da `kallepigg` olarak
   ayarlı olduğu unutulmamalı.

---

## Production deployment notları

### Yocto / Buildroot recipe'ine ekle

1. `/mnt/usb` klasörünü rootfs'e dahil et:
   ```bitbake
   # recipe içinde:
   do_install_append() {
       install -d ${D}/mnt/usb
   }
   ```

2. Wrapper script'leri rootfs'e koy:
   ```
   /usr/local/sbin/rcu2b-backup-fix-install.sh
   /usr/local/sbin/rcu2b-backup-fix-uninstall.sh
   ```

3. Boot'ta otomatik install için systemd unit veya init script:
   ```ini
   # /etc/systemd/system/rcu2b-backup-fix.service
   [Unit]
   Description=RCU2B backup compatibility fixes
   ConditionPathExists=!/bin/df.original-link

   [Service]
   Type=oneshot
   ExecStart=/usr/local/sbin/rcu2b-backup-fix-install.sh
   RemainAfterExit=yes

   [Install]
   WantedBy=multi-user.target
   ```

### Test matrisi

Müşteriye göndermeden önce şu kombinasyonlarda test:

| USB Format | Beklenen sonuç |
|---|---|
| Superfloppy FAT32 | ✓ Çalışır (bu setup) |
| MBR + FAT32 partition | ✓ Çalışır (wrapper sahte satır eklemese de fdisk gerçek partition basar) |
| MBR + exFAT | ✗ "Unknown filesystem" — mount da fail eder |
| MBR + ext4 | ✗ "Unknown filesystem" |
| Boş / formatsız | ✗ blkid TYPE boş, sahte satır eklenmez |

### Diğer VDR sürümleri

Script'in başka versiyonları olabilir. Karşılaşılırsa öncelikle:
- VDR'da `cat /app/backupcheck` ile gerçek script'i karşılaştır
- `busybox 2>&1 | head -1` ile cut/tr sürümünü kontrol et
- `cut -d ' ' -f 0` davranışı sürüme bağlı

### Müşteri USB stick beklentisi

Script "Please use an MBR FAT formatted USB stick" diyor ama biz superfloppy
FAT'i de destekliyoruz wrapper sayesinde. Müşteri herhangi bir FAT32 USB
takabilir.

---

## Geri dönüş

Bir wrapper bozulursa veya sistem bir sorun yaşarsa:

```sh
/usr/local/sbin/rcu2b-backup-fix-uninstall.sh
```

Bu /mnt/usb'yi silmez (boş klasör, zararsız). Wrapper'ları geri alır,
orijinal symlink'leri yeniden oluşturur.

---

## Özet — başarı sonrası yapı

```
RCU2B filesystem:
  /mnt/usb                          ← yeni boş klasör (mount target)
  /usr/sbin/fdisk                   ← wrapper script (eski symlink → util-linux)
  /usr/sbin/fdisk.util-linux        ← orijinal binary (değişmedi)
  /usr/sbin/fdisk.original-symlink  ← yedek (uninstall için)
  /bin/df                           ← wrapper script (eski symlink → busybox)
  /bin/busybox                      ← orijinal (değişmedi)
  /bin/df.original-link             ← yedek (uninstall için)
```

VDR ve `backupcheck` script'i: **değişmedi**.

Backup akışı: çalışıyor — SUCCESS alındı.
