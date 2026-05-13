"""
API Endpoint Functions
"""
from fastapi import HTTPException
from core.utils.tcp_server import vdr_tcp_server
from core.utils.watchdog import watchdog_manager
from core.utils.docker import docker_manager
from core.utils.lsusb import get_usb_devices
from core.utils.service_status import service_status_manager


async def get_status():
    """VDR ve sistem durumunu döndür"""
    vdr_status = vdr_tcp_server.get_status()
    
    # Update service phase based on VDR status
    service_status_manager.update_from_vdr(
        vdr_status=vdr_status["status"],
        tcp_running=vdr_status["tcp_running"],
        last_message_time=vdr_status["last_message_time"]
    )
    
    return {
        "service": service_status_manager.get_status(),
        "vdr": vdr_status,
        "watchdog": watchdog_manager.get_status(),
        "docker": docker_manager.get_status(),
    }


async def get_vdr_status():
    """Sadece VDR durumu"""
    return vdr_tcp_server.get_status()


async def get_watchdog_status():
    """Watchdog durumu"""
    return watchdog_manager.get_status()


async def get_docker_status():
    """Docker durumu"""
    return docker_manager.get_status()


async def get_usb_status():
    """USB cihazları"""
    return get_usb_devices()


async def kick_watchdog():
    """Frontend'den watchdog kick"""
    # Bu endpoint frontend tarafından periyodik çağrılacak
    # Gerçek kick watchdog_manager loop'unda yapılıyor
    return {
        "success": True,
        "message": "Watchdog kick received",
        "kick_count": watchdog_manager.kick_count
    }