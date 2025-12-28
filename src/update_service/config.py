"""Configuration for update service."""
from pathlib import Path
from typing import Optional


class Config:
    """Configuration settings for update service."""
    
    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8123
    
    # Base directories
    BASE_DIR: Path = Path("/opt/updater")
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    TEMP_DIR: Path = BASE_DIR / "tmp"
    BACKUP_DIR: Path = BASE_DIR / "backups"
    LOG_DIR: Path = BASE_DIR / "logs"
    
    # Update engine
    ENGINE_DIR: Path = BASE_DIR / "engine"
    STATE_FILE: Path = BASE_DIR / "state.json"
    
    # File upload settings
    MAX_UPLOAD_SIZE: int = 2 * 1024 * 1024 * 1024  # 2GB
    ALLOWED_EXTENSIONS: set = {".tar.gz", ".tgz"}
    
    # Job settings
    MAX_CONCURRENT_JOBS: int = 1
    
    @classmethod
    def ensure_directories(cls):
        """Create required directories."""
        for dir_path in [cls.UPLOAD_DIR, cls.TEMP_DIR, cls.BACKUP_DIR, cls.LOG_DIR]:
            dir_path.mkdir(parents=True, exist_ok=True)


config = Config()

