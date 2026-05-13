#!/bin/sh
# RCU2B backup compatibility fixes - uninstall
# fdisk ve df wrapper'larini geri al, /mnt/usb dokunulmaz.

set -e

# fdisk wrapper geri al
FDISK=/usr/sbin/fdisk
FDISK_BACKUP=/usr/sbin/fdisk.original-symlink
if [ -f "$FDISK_BACKUP" ]; then
    TARGET=$(cat "$FDISK_BACKUP")
    rm "$FDISK"
    if [ "$TARGET" = "ORIGINAL_BINARY" ] && [ -f "${FDISK}.original-binary" ]; then
        mv "${FDISK}.original-binary" "$FDISK"
        chmod +x "$FDISK"
        echo "fdisk: orijinal binary geri yuklendi"
    else
        ln -s "$TARGET" "$FDISK"
        echo "fdisk: geri yuklendi -> $TARGET"
    fi
    rm "$FDISK_BACKUP"
else
    echo "fdisk: yedek yok, atlandi"
fi

# df wrapper geri al
DF=/bin/df
DF_BACKUP=/bin/df.original-link
if [ -f "$DF_BACKUP" ]; then
    TARGET=$(cat "$DF_BACKUP")
    rm "$DF"
    ln -s "$TARGET" "$DF"
    rm "$DF_BACKUP"
    echo "df: geri yuklendi -> $TARGET"
else
    echo "df: yedek yok, atlandi"
fi

# /mnt/usb dokunmadan kalir (zararsiz bos klasor)
echo "/mnt/usb klasoru oldugu gibi birakildi."
