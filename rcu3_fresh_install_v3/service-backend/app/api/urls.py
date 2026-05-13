"""
API Routes Configuration
"""
from app.api.endpoints import (
    get_status,
    get_vdr_status,
    get_watchdog_status,
    get_docker_status,
    get_usb_status,
    kick_watchdog,
)

routes = [
    {
        "path": "/status",
        "endpoint": get_status,
        "methods": ["GET"]
    },
    {
        "path": "/vdr/status",
        "endpoint": get_vdr_status,
        "methods": ["GET"]
    },
    {
        "path": "/watchdog/status",
        "endpoint": get_watchdog_status,
        "methods": ["GET"]
    },
    {
        "path": "/docker/status",
        "endpoint": get_docker_status,
        "methods": ["GET"]
    },
    {
        "path": "/usb",
        "endpoint": get_usb_status,
        "methods": ["GET"]
    },
    {
        "path": "/kick",
        "endpoint": kick_watchdog,
        "methods": ["POST"]
    },
]