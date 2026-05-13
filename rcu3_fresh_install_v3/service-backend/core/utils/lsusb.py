"""
USB Storage Device Detector
DEBUG mode: Mock USB data (always 1 device)
PRODUCTION mode: Check /dev/sd* block devices (same as RCU2)
"""
import os
from core.settings import settings


def get_usb_devices() -> dict:
    """USB storage cihazlarını kontrol et"""
    if settings.DEBUG:
        return _get_mock_usb_devices()
    else:
        return _get_real_usb_devices()


def _get_mock_usb_devices() -> dict:
    """DEBUG mode için mock USB data"""
    return {
        "devices": [{"name": "sda", "path": "/dev/sda"}],
        "count": 1,
        "mode": "debug"
    }


def _get_real_usb_devices() -> dict:
    """PRODUCTION mode: /dev/sd* kontrolü (RCU2 ile aynı)"""
    try:
        devices = []
        for entry in os.listdir("/dev"):
            if entry.startswith("sd"):
                devices.append({"name": entry, "path": f"/dev/{entry}"})

        return {
            "devices": devices,
            "count": len(devices),
            "mode": "production"
        }

    except Exception as e:
        return {
            "error": str(e),
            "devices": [],
            "count": 0,
            "mode": "production"
        }
