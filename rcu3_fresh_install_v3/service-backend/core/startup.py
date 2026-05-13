"""
Startup and Shutdown Handlers
"""
from core.settings import settings
from core.utils.watchdog import watchdog_manager
from core.utils.tcp_server import vdr_tcp_server
from core.utils.udp_discovery import rcu_discovery_server


async def initialize_system():
    """Initialize all services on startup"""
    print(f"\n{'='*50}")
    print(f"VDR Service Starting...")
    print(f"{'='*50}")
    print(f"[DEBUG]:\t{settings.DEBUG}")
    print(f"[HOST]:\t\t{settings.HOST}:{settings.PORT}")
    print(f"[VDR TCP]:\t{settings.VDR_TCP_HOST}:{settings.VDR_TCP_PORT}")
    print(f"[RCU UDP]:\t0.0.0.0:{settings.RCU_UDP_PORT}")
    print(f"[WATCHDOG]:\t{'ENABLED' if settings.WATCHDOG_ENABLED else 'DISABLED'}")
    
    # Start services
    watchdog_manager.start()
    await vdr_tcp_server.start()
    await rcu_discovery_server.start()
    
    print(f"{'='*50}\n")


async def shutdown_system():
    """Cleanup on shutdown"""
    print("\n[SHUTDOWN] VDR Service stopping...")
    
    await watchdog_manager.stop()
    await vdr_tcp_server.stop()
    await rcu_discovery_server.stop()
    
    print("[SHUTDOWN] Complete\n")


def print_registered_routes(app):
    """Print all registered API routes"""
    from fastapi.routing import APIRoute
    
    print(f"{'='*50}")
    print("Registered APIs")
    print(f"{'='*50}")
    for route in app.routes:
        if isinstance(route, APIRoute):
            print(f"{route.path}")
    print(f"{'='*50}\n")