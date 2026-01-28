"""
WatchdogKeeper - Update süresi boyunca hardware watchdog'u canlı tutan sınıf.

RCU3 cihazlarında /dev/watchdog hardware watchdog device'ı bulunur.
Service Backend normalde bu watchdog'u kick eder. Update sırasında Service Backend
durduğunda veya restart olduğunda, WatchdogKeeper devreye girer ve watchdog'u
kick etmeye devam eder.

Kullanım:
    keeper = WatchdogKeeper(kick_interval=3)
    keeper.start()
    # ... update işlemleri ...
    keeper.stop()
"""

import threading
import time
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class WatchdogKeeper:
    """
    Hardware watchdog'u belirli aralıklarla kick ederek canlı tutar.

    Thread-safe implementation:
    - start() çağrıldığında _running=True ve thread başlar
    - stop() çağrıldığında _running=False ve thread durur
    - Thread daemon olarak çalışır, ana process ölürse otomatik ölür
    """

    DEFAULT_KICK_INTERVAL = 3  # seconds
    DEFAULT_WATCHDOG_DEVICE = '/dev/watchdog'

    def __init__(
        self,
        kick_interval: int = DEFAULT_KICK_INTERVAL,
        watchdog_device: str = DEFAULT_WATCHDOG_DEVICE,
        enabled: bool = True
    ):
        """
        Args:
            kick_interval: Watchdog kick aralığı (saniye). Default: 3
            watchdog_device: Watchdog device path. Default: /dev/watchdog
            enabled: False ise watchdog kick yapılmaz (test için). Default: True
        """
        self._kick_interval = kick_interval
        self._watchdog_device = watchdog_device
        self._enabled = enabled
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._kick_count = 0
        self._last_error: Optional[str] = None

    def _kick_loop(self):
        """
        Watchdog kick döngüsü.

        _running True olduğu sürece çalışır.
        Her kick_interval saniyede bir watchdog'a '1' yazar.
        """
        logger.debug("WatchdogKeeper kick loop started")

        while self._running:
            try:
                if self._enabled:
                    self._do_kick()
                else:
                    logger.debug("Watchdog kick skipped (disabled mode)")

                self._kick_count += 1
                self._last_error = None

            except PermissionError as e:
                self._last_error = f"Permission denied: {e}"
                logger.error(f"Watchdog kick failed - {self._last_error}")
                logger.error("Hint: Run with sudo or add user to appropriate group")

            except FileNotFoundError as e:
                self._last_error = f"Device not found: {e}"
                logger.warning(f"Watchdog device not found: {self._watchdog_device}")
                logger.warning("This is normal on development machines without hardware watchdog")

            except Exception as e:
                self._last_error = str(e)
                logger.error(f"Watchdog kick failed: {e}")

            # Sleep in small increments for responsive shutdown
            sleep_time = self._kick_interval
            while sleep_time > 0 and self._running:
                time.sleep(min(0.5, sleep_time))
                sleep_time -= 0.5

        logger.debug("WatchdogKeeper kick loop ended")

    def _do_kick(self):
        """
        Gerçek watchdog kick işlemi.

        /dev/watchdog'a '1' yazarak kick atar.
        """
        with open(self._watchdog_device, 'w') as f:
            f.write('1')
        logger.debug(f"Watchdog kicked (count: {self._kick_count + 1})")

    def start(self):
        """
        WatchdogKeeper'ı başlat.

        - Zaten çalışıyorsa warning loglar ve döner
        - _running=True set eder
        - Yeni daemon thread başlatır
        """
        if self._running:
            logger.warning("WatchdogKeeper already running")
            return

        logger.info(f"Starting WatchdogKeeper (interval: {self._kick_interval}s, device: {self._watchdog_device})")

        self._running = True
        self._kick_count = 0
        self._last_error = None

        self._thread = threading.Thread(
            target=self._kick_loop,
            name="WatchdogKeeper",
            daemon=True
        )
        self._thread.start()

        logger.info("WatchdogKeeper started")

    def stop(self):
        """
        WatchdogKeeper'ı durdur.

        - Zaten durmulşsa warning loglar ve döner
        - _running=False set eder (while loop durur)
        - Thread'in bitmesini bekler (timeout ile)
        """
        if not self._running:
            logger.warning("WatchdogKeeper not running")
            return

        logger.info(f"Stopping WatchdogKeeper (total kicks: {self._kick_count})")

        self._running = False

        if self._thread:
            # Thread'in bitmesini bekle
            join_timeout = self._kick_interval + 2
            self._thread.join(timeout=join_timeout)

            if self._thread.is_alive():
                logger.warning(f"WatchdogKeeper thread did not stop within {join_timeout}s")
            else:
                logger.debug("WatchdogKeeper thread joined successfully")

            self._thread = None

        logger.info("WatchdogKeeper stopped")

    @property
    def is_running(self) -> bool:
        """WatchdogKeeper çalışıyor mu?"""
        return self._running

    @property
    def kick_count(self) -> int:
        """Toplam kick sayısı"""
        return self._kick_count

    @property
    def last_error(self) -> Optional[str]:
        """Son hata mesajı (varsa)"""
        return self._last_error

    @property
    def status(self) -> dict:
        """WatchdogKeeper durumu (dict olarak)"""
        return {
            'running': self._running,
            'enabled': self._enabled,
            'kick_interval': self._kick_interval,
            'watchdog_device': self._watchdog_device,
            'kick_count': self._kick_count,
            'last_error': self._last_error
        }

    def __enter__(self):
        """Context manager support: with WatchdogKeeper() as keeper: ..."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager support: cleanup on exit"""
        self.stop()
        return False  # Don't suppress exceptions


# Singleton instance for easy access
_default_keeper: Optional[WatchdogKeeper] = None


def get_watchdog_keeper(
    kick_interval: int = WatchdogKeeper.DEFAULT_KICK_INTERVAL,
    watchdog_device: str = WatchdogKeeper.DEFAULT_WATCHDOG_DEVICE,
    enabled: bool = True
) -> WatchdogKeeper:
    """
    Singleton WatchdogKeeper instance döndürür.

    İlk çağrıda yeni instance oluşturur, sonraki çağrılarda aynı instance'ı döndürür.
    """
    global _default_keeper

    if _default_keeper is None:
        _default_keeper = WatchdogKeeper(
            kick_interval=kick_interval,
            watchdog_device=watchdog_device,
            enabled=enabled
        )

    return _default_keeper


if __name__ == '__main__':
    # Test mode
    import sys

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("WatchdogKeeper Test Mode")
    print("=" * 40)

    # Development modunda disable ile test et
    keeper = WatchdogKeeper(kick_interval=2, enabled=False)

    print(f"Status: {keeper.status}")

    print("\nStarting keeper...")
    keeper.start()

    print("Running for 5 seconds...")
    time.sleep(5)

    print(f"Status: {keeper.status}")

    print("\nStopping keeper...")
    keeper.stop()

    print(f"Final status: {keeper.status}")
    print("\nTest completed!")
