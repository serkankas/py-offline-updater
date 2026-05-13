"""
Settings modülü - Environment variables ve config
"""
import os
import pathlib
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """VDR Service Configuration"""
    
    # Core
    DEBUG: bool = os.getenv("DEBUG", "0") == "1"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8001"))
    
    # VDR TCP Server
    VDR_TCP_PORT: int = int(os.getenv("VDR_TCP_PORT", "7000"))
    VDR_TCP_HOST: str = os.getenv("VDR_TCP_HOST", "0.0.0.0")
    VDR_HOST: str = os.getenv("VDR_HOST", "RCU_SERVICE")
    VDR_SERIAL: str = os.getenv("VDR_SERIAL", "RCU-001")
    
    # RCU UDP Discovery
    RCU_UDP_PORT: int = int(os.getenv("RCU_UDP_PORT", "65535"))
    RCU_HOST: str = os.getenv("RCU_HOST", "10.2.1.20")
    RCU_TCP_PORT: int = int(os.getenv("RCU_TCP_PORT", "7000"))
    RCU_TYPE: str = os.getenv("RCU_TYPE", "RCU")
    RCU_SERIAL: str = os.getenv("RCU_SERIAL", "RCU-001")
    RCU_SW_VERSION: str = os.getenv("RCU_SW_VERSION", "1.0.0")
    RCU_VERSION: str = os.getenv("RCU_VERSION", "1.0.0")
    RCU_HW_VERSION: str = os.getenv("RCU_HW_VERSION", "1.0.0")
    RCU_FW_VERSION: str = os.getenv("RCU_FW_VERSION", "1.0.0")
    RCU_OS_VERSION: str = os.getenv("RCU_OS_VERSION", "Linux")
    
    # Watchdog
    WATCHDOG_ENABLED: bool = os.getenv("WATCHDOG_ENABLED", "1") == "1"
    WATCHDOG_KICK_INTERVAL: int = int(os.getenv("WATCHDOG_KICK_INTERVAL", "3"))
    WATCHDOG_BOOT_GRACE_PERIOD: int = int(os.getenv("WATCHDOG_BOOT_GRACE_PERIOD", "120"))
    
    # RCU Backend
    RCU_BACKEND_URL: str = os.getenv("RCU_BACKEND_URL", "http://localhost:8000")
    RCU_HEALTH_CHECK_INTERVAL: int = int(os.getenv("RCU_HEALTH_CHECK_INTERVAL", "10"))
    RCU_HEALTH_CHECK_TIMEOUT: int = int(os.getenv("RCU_HEALTH_CHECK_TIMEOUT", "5"))
    
    # Paths
    MAIN_DIR = pathlib.Path(os.path.dirname(__file__)).parent.parent
    DOCKER_COMPOSE_PATH: str = os.getenv(
        "DOCKER_COMPOSE_PATH", 
        str(MAIN_DIR.parent / "sealink-rcu-backend")
    )
    
    # Dimming
    DIMMING_FILE: str = os.getenv("DIMMING_FILE", "/tmp/dimming.json")
    DAC_BUS: int = int(os.getenv("DAC_BUS", "0"))
    DAC_VALUE: float = float(os.getenv("DAC_VALUE", "0.183"))
    
    # Runtime state
    vdr_status: str = "waiting"
    vessel_info: dict = None
    
    def __repr__(self):
        return f"<Settings DEBUG={self.DEBUG}>"


settings = Settings()