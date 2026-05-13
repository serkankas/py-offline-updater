"""Utility functions for update engine."""
import hashlib
import logging
import yaml
from pathlib import Path
from typing import Dict, Any, Optional


def calculate_checksum(file_path: Path) -> str:
    """Calculate MD5 checksum of a file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        MD5 checksum as hex string
    """
    md5_hash = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            md5_hash.update(chunk)
    return md5_hash.hexdigest()


def verify_checksum(file_path: Path, expected_checksum: str) -> bool:
    """Verify file checksum.
    
    Args:
        file_path: Path to the file
        expected_checksum: Expected MD5 checksum
        
    Returns:
        True if checksum matches, False otherwise
    """
    actual = calculate_checksum(file_path)
    return actual == expected_checksum


def load_manifest(manifest_path: Path) -> Dict[str, Any]:
    """Load and validate manifest YAML file.
    
    Args:
        manifest_path: Path to manifest.yml
        
    Returns:
        Parsed manifest dictionary
        
    Raises:
        ValueError: If manifest is invalid
        FileNotFoundError: If manifest file not found
    """
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    
    with open(manifest_path, 'r') as f:
        manifest = yaml.safe_load(f)
    
    # Validate required fields
    required_fields = ['description', 'date', 'required_engine_version']
    for field in required_fields:
        if field not in manifest:
            raise ValueError(f"Missing required field in manifest: {field}")
    
    # Ensure actions is a list
    if 'actions' not in manifest:
        manifest['actions'] = []
    
    return manifest


def setup_logging(log_file: Optional[Path] = None, level: int = logging.INFO) -> logging.Logger:
    """Setup logging configuration.
    
    Args:
        log_file: Optional path to log file
        level: Logging level
        
    Returns:
        Configured logger
    """
    logger = logging.getLogger('update_engine')
    logger.setLevel(level)
    
    # Clear existing handlers
    logger.handlers = []
    
    # Format with timestamp
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def parse_version(version: str) -> tuple:
    """Parse semantic version string.
    
    Args:
        version: Version string (e.g., "1.2.3")
        
    Returns:
        Tuple of (major, minor, patch)
    """
    parts = version.split('.')
    return tuple(int(p) for p in parts[:3])


def compare_versions(version1: str, version2: str) -> int:
    """Compare two semantic versions.
    
    Args:
        version1: First version string
        version2: Second version string
        
    Returns:
        -1 if version1 < version2
         0 if version1 == version2
         1 if version1 > version2
    """
    v1 = parse_version(version1)
    v2 = parse_version(version2)
    
    if v1 < v2:
        return -1
    elif v1 > v2:
        return 1
    else:
        return 0

