"""
Full RCU3 System Update Orchestrator

Manages the complete update process for RCU3 devices:
1. Relocation (if needed): /opt/update → /app/app/update
2. Docker containers update (backend, frontend, redis, celery)
3. Service Backend update (RCU_Service)
4. Updater self-update (py-offline-updater)

Includes:
- Persistent backups (/app/app/backups/)
- Rollback on failure
- Health checks after each update
- Cleanup on success
- WatchdogKeeper integration
"""

import sys
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

from .watchdog_keeper import WatchdogKeeper, get_watchdog_keeper
from .systemd_utils import (
    stop_service, start_service, restart_service,
    is_service_active, wait_for_service_active,
    get_service_status, run_systemctl, get_service_logs,
    reload_daemon,
    SERVICE_BACKEND, UPDATE_SERVICE, CHROMIUM_KIOSK
)
from .docker_utils import (
    compose_down, compose_up, docker_load, docker_save,
    wait_for_containers_healthy
)

logger = logging.getLogger(__name__)


# =============================================================================
# RCU3 Paths
# =============================================================================

DOCKER_FILES_DIR = Path("/app/app/docker-files")
SERVICE_BACKEND_DIR = Path("/app/app/service_backend")
UPDATER_DIR = Path("/app/app/update")
UPDATER_OLD_DIR = Path("/opt/updater")  # Legacy location
SPLASH_HTML_DEST = Path("/app/app/splash.html")
CHROMIUM_SERVICE_PATH = Path("/etc/systemd/system/chromium-kiosk.service")

BACKUP_ROOT = Path("/app/app/backups")
BACKUP_DOCKER = BACKUP_ROOT / "docker"
BACKUP_SERVICE_BACKEND = BACKUP_ROOT / "service_backend"
BACKUP_UPDATER = BACKUP_ROOT / "updater"


# =============================================================================
# Health Check URLs
# =============================================================================

FRONTEND_URL = "http://localhost:80/"
BACKEND_API_URL = "http://localhost:8000/api/health"
SERVICE_BACKEND_URL = "http://localhost:8001/status"
UPDATER_URL = "http://localhost:8123/api/system-info"


# =============================================================================
# Utility Functions
# =============================================================================

def get_timestamp() -> str:
    """Get current timestamp for backup naming."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _patch_chromium_service():
    """
    Patch existing chromium-kiosk.service in-place:
    - URL → file:///app/app/splash.html
    - After=docker.service → After=service-backend.service
    - Wants=docker.service → Wants=service-backend.service
    - Remove ExecStartPre lines (splash handles waiting)
    """
    if not CHROMIUM_SERVICE_PATH.exists():
        return

    content = CHROMIUM_SERVICE_PATH.read_text()
    original = content

    # URL değiştir (http://localhost → file:///app/app/splash.html)
    import re
    content = re.sub(
        r'(--kiosk.*\n\s*.*--incognito.*\n\s*.*--ozone-platform=wayland.*\n\s*.*--remote-debugging-port=\d+.*\n\s*.*--remote-debugging-address=[\d.]+.*\n\s*)http://\S+',
        r'\1file:///app/app/splash.html',
        content
    )

    # Eğer regex çalışmadıysa basit replace dene
    if 'file:///app/app/splash.html' not in content:
        content = content.replace('http://localhost', 'file:///app/app/splash.html')

    # Dependency değiştir
    content = content.replace('After=docker.service', 'After=service-backend.service')
    content = content.replace('Wants=docker.service', 'Wants=service-backend.service')

    # ExecStartPre satırlarını kaldır (splash beklemeyi hallediyor)
    lines = content.split('\n')
    lines = [l for l in lines if not l.strip().startswith('ExecStartPre=')]
    # TimeoutStartSec de gereksiz artık
    lines = [l for l in lines if not l.strip().startswith('TimeoutStartSec=')]
    content = '\n'.join(lines)

    if content != original:
        CHROMIUM_SERVICE_PATH.write_text(content)
        reload_daemon()
    else:
        pass  # logger.info/warning stripped


def http_health_check(url: str, timeout: int = 10, max_wait: int = 60, retry_interval: int = 3) -> bool:
    """
    Check HTTP endpoint health with retry logic.

    Args:
        url: URL to check
        timeout: Request timeout per attempt in seconds
        max_wait: Maximum time to wait for service to be healthy (seconds)
        retry_interval: Time between retry attempts (seconds)

    Returns:
        True if healthy (status 200), False otherwise
    """
    import requests
    import time

    start_time = time.time()
    attempt = 0

    while time.time() - start_time < max_wait:
        attempt += 1
        try:
            logger.debug(f"Health check attempt {attempt}: {url}")
            response = requests.get(url, timeout=timeout)
            if response.status_code == 200:
                elapsed = time.time() - start_time
                return True
            else:
                logger.debug(f"Health check returned status {response.status_code}")
        except Exception as e:
            logger.debug(f"Health check attempt {attempt} failed: {e}")

        # Wait before next attempt
        if time.time() - start_time < max_wait:
            time.sleep(retry_interval)

    elapsed = time.time() - start_time
    logger.error(f"Health check failed for {url} after {elapsed:.1f}s ({attempt} attempts)")
    return False


def _schedule_service_restart(service_name: str, delay_seconds: int = 10) -> bool:
    """
    Schedule a deferred service restart using systemd-run.

    This creates a transient timer that fires after the specified delay,
    independent of the current process tree. Used for self-update scenarios
    where the service can't restart itself during the update.

    Args:
        service_name: Systemd service to restart
        delay_seconds: Delay before restart in seconds

    Returns:
        True if scheduling succeeded
    """
    try:
        cmd = [
            'systemd-run', '--on-active={}s'.format(delay_seconds),
            'systemctl', 'restart', service_name
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            return True
        else:
            logger.error(f"Failed to schedule restart: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"Failed to schedule restart: {e}")
        return False


def _schedule_safe_reboot(delay_seconds: int = 10) -> bool:
    """
    Schedule a deferred safe reboot using systemd-run.

    Runs safe_reboot.py (os.sync + sleep + systemctl reboot) after the
    specified delay, giving the update process time to report success.

    Args:
        delay_seconds: Delay before reboot in seconds

    Returns:
        True if scheduling succeeded
    """
    safe_reboot_script = UPDATER_DIR / 'scripts' / 'rcu3_update' / 'safe_reboot.py'

    if not safe_reboot_script.exists():
        # Fallback: direct reboot
        cmd = [
            'systemd-run', '--on-active={}s'.format(delay_seconds),
            'systemctl', 'reboot'
        ]
    else:
        cmd = [
            'systemd-run', '--on-active={}s'.format(delay_seconds),
            'python3', str(safe_reboot_script)
        ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            return True
        else:
            logger.error(f"Failed to schedule reboot: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"Failed to schedule reboot: {e}")
        return False


ENV_FILE = Path("/etc/environment")

# Environment variable keys for version tracking
ENV_VERSION_KEYS = ("RCU_SW_VERSION", "RCU_HW_VERSION", "RCU_FW_VERSION")


def set_environment_versions(
    sw_version: Optional[str] = None,
    hw_version: Optional[str] = None,
    fw_version: Optional[str] = None,
) -> bool:
    """
    Set RCU version environment variables in /etc/environment.

    Only updates variables for which a non-None value is provided.
    Existing non-RCU lines in /etc/environment are preserved.

    Args:
        sw_version: Software version (e.g. "daffb14f - 39.1")
        hw_version: Hardware version (e.g. "1.0.0")
        fw_version: Firmware version (e.g. "1.3.2")

    Returns:
        True if file was updated, False on error
    """
    versions = {
        "RCU_SW_VERSION": sw_version,
        "RCU_HW_VERSION": hw_version,
        "RCU_FW_VERSION": fw_version,
    }

    # Filter out None values - only set what was provided
    versions = {k: v for k, v in versions.items() if v is not None}

    if not versions:
        return True

    try:
        # Read existing content
        existing_lines: list[str] = []
        if ENV_FILE.exists():
            existing_lines = ENV_FILE.read_text().strip().splitlines()

        # Keep lines that are NOT RCU version variables
        kept_lines = [
            line for line in existing_lines
            if not any(line.startswith(f"{key}=") for key in ENV_VERSION_KEYS)
        ]

        # Append new version lines
        for key, value in versions.items():
            kept_lines.append(f'{key}="{value}"')

        # Write back
        ENV_FILE.write_text("\n".join(kept_lines) + "\n")

        for key, value in versions.items():
            pass  # logger.info/warning stripped

        return True

    except PermissionError:
        logger.error(f"Permission denied writing to {ENV_FILE} (need root)")
        return False
    except Exception as e:
        logger.error(f"Failed to update {ENV_FILE}: {e}")
        return False


def ensure_backup_dirs():
    """Create backup directories if they don't exist."""
    for backup_dir in [BACKUP_DOCKER, BACKUP_SERVICE_BACKEND, BACKUP_UPDATER]:
        backup_dir.mkdir(parents=True, exist_ok=True)


# =============================================================================
# Relocation
# =============================================================================

def relocate_updater_if_needed() -> bool:
    """
    Relocate updater from /opt/update to /app/app/update if needed.

    Returns:
        True if relocation was performed, False if not needed

    Raises:
        Exception if relocation fails
    """
    if not UPDATER_OLD_DIR.exists():
        return False

    if UPDATER_DIR.exists():
        return False


    try:
        # Create parent directory
        UPDATER_DIR.parent.mkdir(parents=True, exist_ok=True)

        # Move entire directory
        shutil.move(str(UPDATER_OLD_DIR), str(UPDATER_DIR))

        # Update systemd service file (if needed)
        service_file = Path("/etc/systemd/system/update-service.service")

        if service_file.exists():
            with open(service_file, 'r') as f:
                content = f.read()

            if '/opt/updater' in content or '/opt/update' in content:
                pass  # logger.info/warning stripped

        return True

    except Exception as e:
        logger.error(f"Relocation failed: {e}")
        raise


# =============================================================================
# Docker Update
# =============================================================================

def update_docker(
    source_dir: Path,
    compose_file: Path,
    watchdog_keeper: Optional[WatchdogKeeper] = None
) -> bool:
    """
    Update Docker containers (backend, frontend, redis, celery).

    Process:
    1. Backup current state
    2. Stop containers
    3. Save current images (backup)
    4. Copy new images and compose file
    5. Load new images
    6. Start containers with new compose
    7. Health check
    8. On success: cleanup backup
    9. On failure: rollback to backup

    Args:
        source_dir: Directory containing new docker images (*.tar)
        compose_file: New docker-compose.yml file
        watchdog_keeper: Optional WatchdogKeeper instance

    Returns:
        True if update succeeded, False otherwise
    """

    timestamp = get_timestamp()
    backup_dir = BACKUP_DOCKER / timestamp
    backup_dir.mkdir(parents=True, exist_ok=True)

    old_compose_file = DOCKER_FILES_DIR / "docker-compose.yml"

    try:
        # Step 1: Stop containers
        compose_down(cwd=DOCKER_FILES_DIR)

        # Step 2: Backup current compose file
        if old_compose_file.exists():
            shutil.copy2(old_compose_file, backup_dir / "docker-compose.yml")

        # Step 3: Save current images (backup)
        # Get image names from old compose
        running_images = [
            "redis:7-alpine",
            "rcu-deploy-backend:2cfc2bea-linux-arm64",
            "rcu-deploy-frontend:2cfc2bea-linux-arm64",
        ]

        for image_name in running_images:
            safe_name = image_name.replace(":", "-").replace("/", "-")
            output_tar = backup_dir / f"{safe_name}.tar"
            try:
                docker_save(image_name, output_tar)
            except Exception as e:
                pass  # logger.info/warning stripped

        # Step 4: Clean docker-files (except compose)
        for item in DOCKER_FILES_DIR.iterdir():
            if item.name != "docker-compose.yml" and item.name != "tmp":
                if item.is_file():
                    item.unlink()
                    logger.debug(f"  Removed file: {item.name}")
                elif item.is_dir():
                    shutil.rmtree(item)
                    logger.debug(f"  Removed dir: {item.name}")

        # Step 5: Copy new images and compose

        # Copy compose file
        shutil.copy2(compose_file, DOCKER_FILES_DIR / "docker-compose.yml")

        # Copy all .tar files
        tar_files = list(source_dir.glob("*.tar"))
        if not tar_files:
            raise UpdateError(f"No .tar files found in {source_dir}")

        for tar_file in tar_files:
            dest = DOCKER_FILES_DIR / tar_file.name
            shutil.copy2(tar_file, dest)

        # Step 6: Load new images
        for tar_file in DOCKER_FILES_DIR.glob("*.tar"):
            docker_load(tar_file)

        # Step 7: Start containers with new compose
        compose_up(cwd=DOCKER_FILES_DIR)

        # Step 8: Health checks

        # Wait for containers to be healthy
        if not wait_for_containers_healthy(
            cwd=DOCKER_FILES_DIR,
            timeout=120,
            poll_interval=2
        ):
            raise UpdateError("Containers failed to become healthy")

        # HTTP health checks
        if not http_health_check(FRONTEND_URL, timeout=5, max_wait=30, retry_interval=3):
            raise UpdateError("Frontend health check failed")

        # Backend API health check skipped - VDR connection may not be available

        # SUCCESS

        # Cleanup: Remove backup
        shutil.rmtree(backup_dir)

        return True

    except Exception as e:
        logger.error(f"Docker update failed: {e}")

        try:
            # Stop new containers
            compose_down(cwd=DOCKER_FILES_DIR)

            # Restore old compose
            old_compose_backup = backup_dir / "docker-compose.yml"
            if old_compose_backup.exists():
                shutil.copy2(old_compose_backup, DOCKER_FILES_DIR / "docker-compose.yml")

            # Load old images from backup
            for tar_file in backup_dir.glob("*.tar"):
                docker_load(tar_file)

            # Start old containers
            compose_up(cwd=DOCKER_FILES_DIR)

            # Cleanup: Remove new tar files that failed
            for tar_file in DOCKER_FILES_DIR.glob("*.tar"):
                try:
                    tar_file.unlink()
                except Exception as e:
                    pass  # logger.info/warning stripped


        except Exception as rollback_error:
            logger.error(f"Rollback failed: {rollback_error}")
            logger.error(f"Manual recovery needed - backup at: {backup_dir}")

        return False


# =============================================================================
# Service Backend Update
# =============================================================================

def update_service_backend(
    source_dir: Path,
    watchdog_keeper: Optional[WatchdogKeeper] = None,
    env_file: Optional[Path] = None,
) -> bool:
    """
    Update Service Backend (RCU_Service).

    Process:
    1. Stop service (should already be stopped)
    2. Backup current files
    3. Sync new files
    4. Deploy .env file (if provided)
    5. Start service
    6. Health check
    7. On success: cleanup backup
    8. On failure: rollback to backup

    Args:
        source_dir: Directory containing new service backend files
        watchdog_keeper: Optional WatchdogKeeper instance
        env_file: Optional .env file to deploy to service backend root

    Returns:
        True if update succeeded, False otherwise
    """

    timestamp = get_timestamp()
    backup_dir = BACKUP_SERVICE_BACKEND / timestamp

    try:
        # Step 1: Ensure service is stopped
        if is_service_active(SERVICE_BACKEND):
            stop_service(SERVICE_BACKEND, timeout=30)

        # Step 2: Backup current files
        if SERVICE_BACKEND_DIR.exists():
            shutil.copytree(SERVICE_BACKEND_DIR, backup_dir)

        # Step 3: Sync new files (only backend/ subdir, preserve .env and other root files)
        backend_dir = SERVICE_BACKEND_DIR / 'backend'

        if backend_dir.exists():
            shutil.rmtree(backend_dir)

        shutil.copytree(source_dir, backend_dir)

        # Step 3b: Deploy .env file (replaces existing)
        if env_file and env_file.exists():
            dest_env = SERVICE_BACKEND_DIR / ".env"
            shutil.copy2(env_file, dest_env)
        elif env_file:
            pass  # logger.info/warning stripped

        # Step 4: Start service
        start_service(SERVICE_BACKEND, timeout=30)

        # Wait for service to be active
        if not wait_for_service_active(SERVICE_BACKEND, timeout=60):
            raise UpdateError("Service failed to start")

        # Step 5: Health check
        # Health check with retry (max 60s, retry every 3s)
        if not http_health_check(SERVICE_BACKEND_URL, timeout=5, max_wait=60, retry_interval=3):
            # Log detailed debug info before failing
            logger.error("=" * 60)
            logger.error("SERVICE BACKEND HEALTH CHECK FAILED - DEBUG INFO")
            logger.error("=" * 60)

            # Get service status
            try:
                status = get_service_status(SERVICE_BACKEND)
                logger.error(f"Service state: {status.state.value}, sub_state: {status.sub_state}, PID: {status.pid}")
            except Exception as e:
                logger.error(f"Failed to get service status: {e}")

            # Get systemctl status output
            try:
                rc, stdout, stderr = run_systemctl(['status', SERVICE_BACKEND])
                logger.error(f"Systemctl status:\n{stdout}")
            except Exception as e:
                logger.error(f"Failed to get systemctl status: {e}")

            # Get journalctl logs
            try:
                logs = get_service_logs(SERVICE_BACKEND, lines=50)
                logger.error(f"Service logs (last 50 lines):\n{logs}")
            except Exception as e:
                logger.error(f"Failed to get service logs: {e}")

            # Check listening ports (try multiple tools)
            try:
                # Try ss first
                result = subprocess.run(['ss', '-tulpn'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    ports = [line for line in result.stdout.split('\n') if '8001' in line or 'LISTEN' in line]
                    logger.error(f"Port status (ss):\n" + '\n'.join(ports[:10]))
                else:
                    # Try netstat as fallback
                    result = subprocess.run(['netstat', '-tulpn'], capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        ports = [line for line in result.stdout.split('\n') if '8001' in line or 'LISTEN' in line]
                        logger.error(f"Port status (netstat):\n" + '\n'.join(ports[:10]))
                    else:
                        pass  # logger.info/warning stripped
            except FileNotFoundError:
                pass  # logger.info/warning stripped
            except Exception as e:
                logger.error(f"Failed to check ports: {e}")

            raise UpdateError("Service Backend health check failed")

        # SUCCESS

        # Cleanup: Remove backup
        shutil.rmtree(backup_dir)

        return True

    except Exception as e:
        logger.error(f"Service Backend update failed: {e}")

        try:
            # Stop service
            if is_service_active(SERVICE_BACKEND):
                stop_service(SERVICE_BACKEND, timeout=30)

            # Restore from backup
            if SERVICE_BACKEND_DIR.exists():
                shutil.rmtree(SERVICE_BACKEND_DIR)
            shutil.copytree(backup_dir, SERVICE_BACKEND_DIR)

            # Start service
            start_service(SERVICE_BACKEND, timeout=30)


        except Exception as rollback_error:
            logger.error(f"Rollback failed: {rollback_error}")
            logger.error(f"Manual recovery needed - backup at: {backup_dir}")

        return False


# =============================================================================
# Updater Update
# =============================================================================

def update_updater(
    source_dir: Path,
    watchdog_keeper: Optional[WatchdogKeeper] = None
) -> bool:
    """
    Update py-offline-updater (self-update).

    IMPORTANT: This is a self-update. The update service (py-updater.service)
    is running this code via a subprocess chain. We CANNOT stop the service
    during the update because that would kill this process.

    Process:
    1. Backup current files
    2. Sync new files in-place (service keeps running with old code in memory)
    3. Skip health check (not meaningful - service runs old code until restart)
    4. Deferred restart is scheduled by the caller after all updates complete

    Args:
        source_dir: Directory containing new updater files
        watchdog_keeper: Optional WatchdogKeeper instance

    Returns:
        True if update succeeded, False otherwise
    """

    timestamp = get_timestamp()
    backup_dir = BACKUP_UPDATER / timestamp

    try:
        # Step 0: Check if target directory needs to be created
        # NOTE: We DON'T move /opt/updater because we're running FROM there!
        # Just create /app/app/update and copy new files there
        if not UPDATER_DIR.exists():
            UPDATER_DIR.mkdir(parents=True, exist_ok=True)

            # If old location exists, copy its config/state files (not code)
            if UPDATER_OLD_DIR.exists():
                old_state = UPDATER_OLD_DIR / "state.json"
                if old_state.exists():
                    shutil.copy2(old_state, UPDATER_DIR / "state.json")

        # Step 1: Backup current files
        if UPDATER_DIR.exists() and any(UPDATER_DIR.iterdir()):
            shutil.copytree(UPDATER_DIR, backup_dir)
        else:
            pass  # logger.info/warning stripped

        # Step 2: Sync new files in-place

        # Sync files by overwriting (don't remove the entire directory -
        # the running service has open file handles)
        for item in source_dir.iterdir():
            dest_item = UPDATER_DIR / item.name
            if item.is_dir():
                if dest_item.exists():
                    shutil.rmtree(dest_item)
                shutil.copytree(item, dest_item)
            else:
                shutil.copy2(item, dest_item)
            logger.debug(f"  Synced: {item.name}")


        # Step 3: Update systemd service file paths
        service_file = Path("/etc/systemd/system/py-updater.service")

        if service_file.exists():
            try:
                content = service_file.read_text()
                original_content = content

                # Fix WorkingDirectory
                content = content.replace(
                    "WorkingDirectory=/opt/updater",
                    f"WorkingDirectory={UPDATER_DIR}"
                )

                # Fix PYTHONPATH environment
                if "PYTHONPATH=/opt/updater" in content:
                    # Update to new path
                    content = content.replace(
                        "Environment=\"PYTHONPATH=/opt/updater/update-engines/current\"",
                        f"Environment=\"PYTHONPATH={UPDATER_DIR}/update-engines/current\""
                    )

                # Write back if changed
                if content != original_content:
                    service_file.write_text(content)

                    # Reload systemd daemon
                    result = subprocess.run(['systemctl', 'daemon-reload'],
                                          capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        pass  # logger.info/warning stripped
                    else:
                        pass  # logger.info/warning stripped
                else:
                    pass  # logger.info/warning stripped

            except Exception as e:
                pass  # logger.info/warning stripped
        else:
            pass  # logger.info/warning stripped

        # SUCCESS

        # Cleanup: Remove backup
        shutil.rmtree(backup_dir)

        return True

    except Exception as e:
        logger.error(f"Updater update failed: {e}")

        try:
            # Restore from backup (service is still running, just restore files)
            if backup_dir.exists():
                for item in backup_dir.iterdir():
                    dest_item = UPDATER_DIR / item.name
                    if item.is_dir():
                        if dest_item.exists():
                            shutil.rmtree(dest_item)
                        shutil.copytree(item, dest_item)
                    else:
                        shutil.copy2(item, dest_item)


        except Exception as rollback_error:
            logger.error(f"Rollback failed: {rollback_error}")
            logger.error(f"Manual recovery needed - backup at: {backup_dir}")

        return False


# =============================================================================
# Main Orchestrator
# =============================================================================

class UpdateError(Exception):
    """Exception raised for update failures."""
    pass


def run_full_system_update(
    docker_source_dir: Path,
    docker_compose_file: Path,
    service_backend_source_dir: Path,
    updater_source_dir: Path,
    enable_watchdog: bool = True,
    skip_docker: bool = False,
    skip_service_backend: bool = False,
    skip_updater: bool = False,
    sw_version: Optional[str] = None,
    hw_version: Optional[str] = None,
    fw_version: Optional[str] = None,
    service_env_file: Optional[Path] = None,
    splash_html_file: Optional[Path] = None,
) -> bool:
    """
    Run full RCU3 system update.

    Args:
        docker_source_dir: Directory with Docker images (*.tar)
        docker_compose_file: New docker-compose.yml file
        service_backend_source_dir: Service Backend source files
        updater_source_dir: Updater source files
        enable_watchdog: Enable WatchdogKeeper (default: True)
        skip_docker: Skip Docker update (default: False)
        skip_service_backend: Skip Service Backend update (default: False)
        skip_updater: Skip Updater update (default: False)
        sw_version: Software version to set in /etc/environment
        hw_version: Hardware version to set in /etc/environment
        fw_version: Firmware version to set in /etc/environment
        splash_html_file: Optional splash.html to deploy to /app/app/

    Returns:
        True if all updates succeeded, False otherwise
    """

    watchdog_keeper = None

    try:
        # Step 0: Ensure backup directories exist
        ensure_backup_dirs()

        # NOTE: Relocation is SKIPPED during update because update runs from /opt/updater/tmp
        # If relocation is needed, it should be done as a separate operation

        # Step 1: Start WatchdogKeeper
        if enable_watchdog:
            watchdog_keeper = get_watchdog_keeper()
            watchdog_keeper.start()

        # Step 2: Stop Service Backend (will be updated later)
        if is_service_active(SERVICE_BACKEND):
            stop_service(SERVICE_BACKEND, timeout=30)

        # Step 3: Docker Update
        if not skip_docker:
            success = update_docker(
                source_dir=docker_source_dir,
                compose_file=docker_compose_file,
                watchdog_keeper=watchdog_keeper
            )
            if not success:
                raise UpdateError("Docker update failed")
        else:
            pass  # logger.info/warning stripped

        # Step 3b: Deploy splash screen & patch chromium service
        if splash_html_file and splash_html_file.exists():
            shutil.copy2(splash_html_file, SPLASH_HTML_DEST)

            # Patch chromium-kiosk.service to use splash.html
            _patch_chromium_service()

        # Step 4: Service Backend Update
        if not skip_service_backend:
            success = update_service_backend(
                source_dir=service_backend_source_dir,
                watchdog_keeper=watchdog_keeper,
                env_file=service_env_file,
            )
            if not success:
                raise UpdateError("Service Backend update failed")
        else:
            pass  # logger.info/warning stripped

        # Step 5: Updater Update
        if not skip_updater:
            success = update_updater(
                source_dir=updater_source_dir,
                watchdog_keeper=watchdog_keeper
            )
            if not success:
                raise UpdateError("Updater update failed")
        else:
            pass  # logger.info/warning stripped

        # Schedule deferred restart of update service if updater was updated
        if not skip_updater:
            _schedule_service_restart(UPDATE_SERVICE, delay_seconds=10)

        # Ensure docker.service is enabled (not just socket-activated)
        result = subprocess.run(
            ['systemctl', 'enable', 'docker.service'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            pass  # logger.info/warning stripped
        else:
            pass  # logger.info/warning stripped

        # Schedule safe reboot
        _schedule_safe_reboot(delay_seconds=10)

        # SUCCESS

        return True

    except Exception as e:
        logger.error(f"Full system update failed: {e}")
        return False

    finally:
        # Always stop WatchdogKeeper
        if watchdog_keeper and watchdog_keeper.is_running:
            watchdog_keeper.stop()


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    """CLI entry point for testing."""
    import argparse

    parser = argparse.ArgumentParser(description="RCU3 Full System Update")
    parser.add_argument("--docker-dir", type=Path, required=True, help="Docker images directory")
    parser.add_argument("--docker-compose", type=Path, required=True, help="Docker compose file")
    parser.add_argument("--service-backend-dir", type=Path, required=True, help="Service Backend source directory")
    parser.add_argument("--updater-dir", type=Path, required=True, help="Updater source directory")
    parser.add_argument("--no-watchdog", action="store_true", help="Disable WatchdogKeeper")
    parser.add_argument("--skip-docker", action="store_true", help="Skip Docker update")
    parser.add_argument("--skip-service-backend", action="store_true", help="Skip Service Backend update")
    parser.add_argument("--skip-updater", action="store_true", help="Skip Updater update")
    parser.add_argument("--sw-version", type=str, default=None, help="Software version to set in /etc/environment")
    parser.add_argument("--hw-version", type=str, default=None, help="Hardware version to set in /etc/environment")
    parser.add_argument("--fw-version", type=str, default=None, help="Firmware version (legacy, unused)")
    parser.add_argument("--service-env-file", type=Path, default=None, help="Path to .env file for RCU_Service")
    parser.add_argument("--splash-html", type=Path, default=None, help="Path to splash.html for chromium startup")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Run update
    success = run_full_system_update(
        docker_source_dir=args.docker_dir,
        docker_compose_file=args.docker_compose,
        service_backend_source_dir=args.service_backend_dir,
        updater_source_dir=args.updater_dir,
        enable_watchdog=not args.no_watchdog,
        skip_docker=args.skip_docker,
        skip_service_backend=args.skip_service_backend,
        skip_updater=args.skip_updater,
        sw_version=args.sw_version,
        hw_version=args.hw_version,
        fw_version=args.fw_version,
        service_env_file=args.service_env_file,
        splash_html_file=args.splash_html,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
