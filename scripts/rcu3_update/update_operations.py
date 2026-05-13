"""
Update operations for RCU3 components.

Provides high-level update functions for:
- Docker containers (backend, frontend, redis, celery)
- Service Backend (host-level RCU_Service)
- py-offline-updater (self-update)
- Health checks
"""

import shutil
import logging
import time
import requests
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

from .watchdog_keeper import WatchdogKeeper
from .systemd_utils import (
    stop_service, start_service, restart_service,
    is_service_active, wait_for_service_active,
    check_service_logs_for_errors, get_service_logs,
    SERVICE_BACKEND, UPDATE_SERVICE, CHROMIUM_KIOSK
)
from .docker_utils import (
    compose_down, compose_up, docker_load, docker_save,
    load_all_images, copy_docker_files, docker_prune,
    wait_for_containers_healthy,
    DOCKER_FILES_DIR, DEFAULT_COMPOSE_FILE
)

logger = logging.getLogger(__name__)


# RCU3 fixed paths
SERVICE_BACKEND_DIR = Path("/app/app/service_backend")
DOCKER_FILES_DIR = Path("/app/app/docker-files")

# Possible py-offline-updater locations
UPDATER_PATHS = [
    Path("/app/app/update"),
    Path("/opt/updater"),
]


class UpdateError(Exception):
    """Exception raised for update operation failures"""
    pass


class PreCheckError(Exception):
    """Exception raised for pre-check failures"""
    pass


# =============================================================================
# Pre-checks
# =============================================================================

def check_disk_space(required_mb: int = 2000, path: str = "/") -> Tuple[bool, str]:
    """
    Check available disk space.

    Args:
        required_mb: Required space in MB
        path: Path to check

    Returns:
        Tuple of (passed, message)
    """
    import shutil
    total, used, free = shutil.disk_usage(path)
    free_mb = free // (1024 * 1024)

    if free_mb < required_mb:
        return False, f"Insufficient disk space: {free_mb}MB available, {required_mb}MB required"

    return True, f"Disk space OK: {free_mb}MB available"


def check_memory(required_mb: int = 500) -> Tuple[bool, str]:
    """
    Check available memory.

    Args:
        required_mb: Required memory in MB

    Returns:
        Tuple of (passed, message)
    """
    try:
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                if line.startswith('MemAvailable:'):
                    available_kb = int(line.split()[1])
                    available_mb = available_kb // 1024

                    if available_mb < required_mb:
                        return False, f"Insufficient memory: {available_mb}MB available, {required_mb}MB required"

                    return True, f"Memory OK: {available_mb}MB available"

        return True, "Memory check skipped (MemAvailable not found)"

    except Exception as e:
        return True, f"Memory check skipped: {e}"


def detect_updater_location() -> Path:
    """
    Detect py-offline-updater installation location.

    Returns:
        Path to updater directory

    Raises:
        PreCheckError: If updater location not found
    """
    for path in UPDATER_PATHS:
        if (path / "update_service").exists():
            return path

    raise PreCheckError(
        f"py-offline-updater location not found. Checked: {UPDATER_PATHS}"
    )


def run_prechecks(
    required_disk_mb: int = 2000,
    required_memory_mb: int = 500
) -> Dict[str, Any]:
    """
    Run all pre-checks before update.

    Args:
        required_disk_mb: Required disk space in MB
        required_memory_mb: Required memory in MB

    Returns:
        Dict with check results

    Raises:
        PreCheckError: If any critical check fails
    """

    results = {}

    # Disk space
    passed, msg = check_disk_space(required_disk_mb)
    results['disk_space'] = {'passed': passed, 'message': msg}
    if not passed:
        raise PreCheckError(msg)

    # Memory
    passed, msg = check_memory(required_memory_mb)
    results['memory'] = {'passed': passed, 'message': msg}
    if not passed:
        raise PreCheckError(msg)

    # Updater location
    try:
        updater_path = detect_updater_location()
        results['updater_location'] = {'passed': True, 'path': str(updater_path)}
    except PreCheckError as e:
        results['updater_location'] = {'passed': False, 'error': str(e)}
        # Not critical, continue

    return results


# =============================================================================
# Backup Operations
# =============================================================================

def backup_directory(
    source_dir: Path,
    backup_name: str,
    backup_base_dir: Optional[Path] = None
) -> Path:
    """
    Create backup of a directory.

    Args:
        source_dir: Directory to backup
        backup_name: Name for backup
        backup_base_dir: Base directory for backups (default: source_dir/../backups)

    Returns:
        Path to backup directory
    """
    if backup_base_dir is None:
        backup_base_dir = source_dir.parent / "backups"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = backup_base_dir / f"{backup_name}_{timestamp}"


    backup_dir.parent.mkdir(parents=True, exist_ok=True)

    if source_dir.exists():
        shutil.copytree(source_dir, backup_dir)
    else:
        backup_dir.mkdir(parents=True)
        (backup_dir / ".empty_backup").touch()

    return backup_dir


def sync_directory(
    source_dir: Path,
    dest_dir: Path,
    mode: str = "mirror",
    exclude: Optional[List[str]] = None
) -> bool:
    """
    Sync directory contents.

    Args:
        source_dir: Source directory
        dest_dir: Destination directory
        mode: Sync mode - 'mirror' (replace), 'merge' (add/update), 'add_only' (add new)
        exclude: List of patterns to exclude

    Returns:
        True if successful
    """
    if exclude is None:
        exclude = []

    if not source_dir.exists():
        raise UpdateError(f"Source directory not found: {source_dir}")


    if mode == "mirror":
        # Remove destination and copy everything
        if dest_dir.exists():
            shutil.rmtree(dest_dir)
        shutil.copytree(source_dir, dest_dir)

    elif mode == "merge":
        # Copy all, overwriting existing
        dest_dir.mkdir(parents=True, exist_ok=True)
        for item in source_dir.rglob('*'):
            if item.is_file():
                rel_path = item.relative_to(source_dir)

                # Check exclusions
                if any(rel_path.match(pattern) for pattern in exclude):
                    continue

                dest_file = dest_dir / rel_path
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest_file)

    elif mode == "add_only":
        # Only add new files
        dest_dir.mkdir(parents=True, exist_ok=True)
        for item in source_dir.rglob('*'):
            if item.is_file():
                rel_path = item.relative_to(source_dir)
                dest_file = dest_dir / rel_path

                if not dest_file.exists():
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dest_file)

    else:
        raise UpdateError(f"Unknown sync mode: {mode}")

    return True


# =============================================================================
# Health Checks
# =============================================================================

def http_health_check(
    url: str,
    timeout: int = 10,
    expected_status: int = 200
) -> Tuple[bool, str]:
    """
    Perform HTTP health check.

    Args:
        url: Health check URL
        timeout: Request timeout
        expected_status: Expected HTTP status code

    Returns:
        Tuple of (healthy, message)
    """
    try:
        response = requests.get(url, timeout=timeout)

        if response.status_code == expected_status:
            return True, f"HTTP {response.status_code} OK"
        else:
            return False, f"HTTP {response.status_code} (expected {expected_status})"

    except requests.exceptions.ConnectionError:
        return False, "Connection refused"
    except requests.exceptions.Timeout:
        return False, f"Timeout after {timeout}s"
    except Exception as e:
        return False, str(e)


def wait_for_http_healthy(
    url: str,
    timeout: int = 60,
    poll_interval: float = 2.0,
    expected_status: int = 200
) -> bool:
    """
    Wait for HTTP endpoint to become healthy.

    Args:
        url: Health check URL
        timeout: Maximum time to wait
        poll_interval: Time between checks
        expected_status: Expected HTTP status code

    Returns:
        True if endpoint became healthy
    """

    start_time = time.time()

    while time.time() - start_time < timeout:
        healthy, msg = http_health_check(url, expected_status=expected_status)

        if healthy:
            return True

        logger.debug(f"Health check pending: {msg}")
        time.sleep(poll_interval)

    return False


def frontend_health_check() -> Tuple[bool, str]:
    """
    Check if frontend is accessible.

    Returns:
        Tuple of (healthy, message)
    """

    # Check frontend nginx
    healthy, msg = http_health_check("http://localhost:80/", timeout=5)

    if healthy:
        return True, "Frontend is accessible"
    else:
        return False, f"Frontend not accessible: {msg}"


# =============================================================================
# Docker Update
# =============================================================================

def docker_update(
    docker_images_path: Path,
    compose_file: Path,
    watchdog_keeper: WatchdogKeeper,
    backup_images: bool = True,
    health_check_timeout: int = 120,
    restart_kiosk: bool = True
) -> bool:
    """
    Perform Docker container update.

    Steps:
    1. Backup current images (optional)
    2. docker-compose down
    3. Copy new docker files
    4. docker load for all tar files
    5. docker-compose up
    6. Wait for health checks
    7. Restart chromium-kiosk (optional)

    Args:
        docker_images_path: Path containing Docker image tar files
        compose_file: Path to new docker-compose.yml
        watchdog_keeper: WatchdogKeeper instance (should already be started)
        backup_images: Whether to backup current images
        health_check_timeout: Timeout for container health checks
        restart_kiosk: Whether to restart chromium-kiosk service

    Returns:
        True if successful

    Raises:
        UpdateError: If update fails
    """

    # Validate inputs
    if not docker_images_path.exists():
        raise UpdateError(f"Docker images path not found: {docker_images_path}")
    if not compose_file.exists():
        raise UpdateError(f"Compose file not found: {compose_file}")

    tar_files = list(docker_images_path.glob("*.tar"))
    if not tar_files:
        raise UpdateError(f"No tar files found in {docker_images_path}")


    # Step 1: Backup current images (optional)
    if backup_images and DEFAULT_COMPOSE_FILE.exists():
        backup_directory(DOCKER_FILES_DIR, "docker_backup")
    else:
        pass  # logger.info/warning stripped

    # Step 2: docker-compose down
    if DEFAULT_COMPOSE_FILE.exists():
        compose_down(DEFAULT_COMPOSE_FILE, timeout=60)
    else:
        pass  # logger.info/warning stripped

    # Step 3: Copy docker files to destination
    DOCKER_FILES_DIR.mkdir(parents=True, exist_ok=True)

    # Copy tar files
    for tar_file in tar_files:
        dest_file = DOCKER_FILES_DIR / tar_file.name
        shutil.copy2(tar_file, dest_file)

    # Copy compose file
    dest_compose = DOCKER_FILES_DIR / "docker-compose.yml"
    shutil.copy2(compose_file, dest_compose)

    # Step 4: docker load
    for tar_file in DOCKER_FILES_DIR.glob("*.tar"):
        docker_load(tar_file, timeout=600)

    # Step 5: docker-compose up
    compose_up(dest_compose, detach=True)

    # Step 6: Health checks
    healthy, statuses = wait_for_containers_healthy(
        dest_compose,
        timeout=health_check_timeout,
        ignore_services=['celery-worker']  # Celery has no health check
    )

    if not healthy:
        pass  # logger.info/warning stripped
        # Don't fail, continue

    # Step 7: Restart chromium-kiosk
    if restart_kiosk:
        try:
            restart_service(CHROMIUM_KIOSK, wait_healthy=False)
        except Exception as e:
            pass  # logger.info/warning stripped


    return True


# =============================================================================
# Service Backend Update
# =============================================================================

def service_backend_update(
    backend_source_path: Path,
    watchdog_keeper: WatchdogKeeper,
    backup: bool = True,
    health_check_timeout: int = 60
) -> bool:
    """
    Update Service Backend (RCU_Service).

    CRITICAL: WatchdogKeeper must be running before calling this function!
    Service Backend manages the hardware watchdog. During restart,
    WatchdogKeeper keeps the watchdog alive.

    Steps:
    1. Backup current service backend
    2. Stop service-backend.service
    3. Sync new files
    4. Start service-backend.service
    5. Health checks

    Args:
        backend_source_path: Path containing new service backend files
        watchdog_keeper: WatchdogKeeper instance (MUST be running!)
        backup: Whether to backup current files
        health_check_timeout: Timeout for health checks

    Returns:
        True if successful

    Raises:
        UpdateError: If update fails
    """

    # CRITICAL: Verify watchdog keeper is running
    if not watchdog_keeper.is_running:
        raise UpdateError(
            "WatchdogKeeper must be running before Service Backend update! "
            "Service Backend manages the hardware watchdog."
        )

    # Validate input
    if not backend_source_path.exists():
        raise UpdateError(f"Backend source path not found: {backend_source_path}")


    # Step 1: Backup
    if backup:
        backup_directory(SERVICE_BACKEND_DIR, "service_backend_backup")
    else:
        pass  # logger.info/warning stripped

    # Step 2: Stop service
    stop_service(SERVICE_BACKEND, timeout=30)

    # Step 3: Sync files
    sync_directory(
        backend_source_path,
        SERVICE_BACKEND_DIR,
        mode="mirror",
        exclude=[".env", "*.pyc", "__pycache__", ".git"]
    )

    # Preserve .env if exists
    env_backup = SERVICE_BACKEND_DIR.parent / "backups" / ".env.backup"
    if env_backup.exists():
        shutil.copy2(env_backup, SERVICE_BACKEND_DIR / ".env")

    # Step 4: Start service
    start_service(SERVICE_BACKEND, wait_healthy=True, health_timeout=30)

    # Step 5: Health checks

    # Check systemd status
    if not is_service_active(SERVICE_BACKEND):
        raise UpdateError("Service Backend failed to start")

    # Check for errors in logs
    has_errors, error_lines = check_service_logs_for_errors(SERVICE_BACKEND, lines=20)
    if has_errors:
        for line in error_lines[:5]:
            pass  # logger.info/warning stripped

    # HTTP health check
    if not wait_for_http_healthy(
        "http://localhost:8001/api/health",
        timeout=health_check_timeout
    ):
        pass  # logger.info/warning stripped
        # Don't fail, service might still be working


    return True


# =============================================================================
# py-offline-updater Self-Update
# =============================================================================

def updater_self_update(
    updater_source_path: Path,
    backup: bool = True,
    health_check_timeout: int = 60
) -> bool:
    """
    Self-update py-offline-updater.

    Note: This function will restart the update-service.service,
    which means the current process will be terminated.

    Steps:
    1. Detect current updater location
    2. Backup current files
    3. Sync new files
    4. Restart update-service.service

    Args:
        updater_source_path: Path containing new updater files
        backup: Whether to backup current files
        health_check_timeout: Timeout for health checks

    Returns:
        True if successful (though process may restart)

    Raises:
        UpdateError: If update fails
    """

    # Validate input
    if not updater_source_path.exists():
        raise UpdateError(f"Updater source path not found: {updater_source_path}")

    # Step 1: Detect location
    updater_dir = detect_updater_location()

    # Step 2: Backup
    if backup:
        backup_directory(updater_dir, "updater_backup")
    else:
        pass  # logger.info/warning stripped

    # Step 3: Sync files
    sync_directory(
        updater_source_path,
        updater_dir,
        mode="merge",  # Don't delete existing files like logs, backups
        exclude=["*.pyc", "__pycache__", ".git", "logs/*", "backups/*", "uploads/*"]
    )

    # Step 4: Restart service

    restart_service(UPDATE_SERVICE, wait_healthy=False)

    # If we get here, service restarted but we're still alive (running in different process)

    if not wait_for_http_healthy(
        "http://localhost:8123/api/health",
        timeout=health_check_timeout
    ):
        pass  # logger.info/warning stripped


    return True


if __name__ == '__main__':
    # Test mode
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("Update Operations Test Mode")
    print("=" * 40)

    print("\nRunning pre-checks...")
    try:
        results = run_prechecks()
        for check, result in results.items():
            print(f"  {check}: {result}")
    except PreCheckError as e:
        print(f"  Pre-check failed: {e}")

    print("\nTest completed!")
