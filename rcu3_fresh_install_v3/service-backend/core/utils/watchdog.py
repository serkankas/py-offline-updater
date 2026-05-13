"""
Watchdog Manager - Sistem watchdog kontrolü
"""
import asyncio
import time
from enum import Enum
from core.settings import settings


class WatchdogState(Enum):
    """Watchdog durumları"""
    BOOT_GRACE = "boot_grace"
    ACTIVE = "active"
    DISABLED = "disabled"


class WatchdogManager:
    """Watchdog kick yöneticisi"""
    
    def __init__(self):
        self.state = WatchdogState.DISABLED if settings.DEBUG else WatchdogState.BOOT_GRACE
        self.boot_time = time.time()
        self.last_kick_time = None
        self.kick_count = 0
        self._running = False
        self._task = None
        
    def start(self):
        """Watchdog manager'ı başlat"""
        if settings.DEBUG:
            print("[WATCHDOG] Disabled (DEBUG mode)")
            return
            
        if self._running:
            return
            
        self._running = True
        self._task = asyncio.create_task(self._watchdog_loop())
        print(f"[WATCHDOG] Started (grace: {settings.WATCHDOG_BOOT_GRACE_PERIOD}s)")
        
    async def stop(self):
        """Watchdog manager'ı durdur"""
        if settings.DEBUG or not self._running:
            return
            
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
    def activate(self):
        """Watchdog'u aktif et"""
        if settings.DEBUG:
            return
        self.state = WatchdogState.ACTIVE
        print("[WATCHDOG] Active")
        
    def disable(self):
        """Watchdog'u devre dışı bırak"""
        self.state = WatchdogState.DISABLED
        print("[WATCHDOG] Disabled")
        
    async def _watchdog_loop(self):
        """Ana watchdog loop"""
        try:
            while self._running:
                elapsed = time.time() - self.boot_time
                if self.state == WatchdogState.BOOT_GRACE:
                    if elapsed >= settings.WATCHDOG_BOOT_GRACE_PERIOD:
                        self.activate()
                
                if self.state == WatchdogState.ACTIVE:
                    await self._kick()
                
                await asyncio.sleep(settings.WATCHDOG_KICK_INTERVAL)
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[WATCHDOG] ERROR: {e}")
            
    async def _kick(self):
        """Watchdog'a kick at"""
        if not settings.WATCHDOG_ENABLED:
            return
            
        try:
            with open('/dev/watchdog', 'w') as f:
                f.write('1')
            self.kick_count += 1
            self.last_kick_time = time.time()
                
        except PermissionError:
            print("[WATCHDOG] ERROR: Permission denied")
            self.disable()
        except FileNotFoundError:
            print("[WATCHDOG] ERROR: Device not found")
            self.disable()
        except Exception as e:
            print(f"[WATCHDOG] ERROR: {e}")
            
    def get_status(self) -> dict:
        """Watchdog durumunu döndür"""
        return {
            "mode": "debug" if settings.DEBUG else "production",
            "state": self.state.value,
            "enabled": settings.WATCHDOG_ENABLED and not settings.DEBUG,
            "kick_count": self.kick_count,
            "last_kick_time": self.last_kick_time,
        }


watchdog_manager = WatchdogManager()