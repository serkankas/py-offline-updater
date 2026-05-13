"""
Docker utility functions for RCU3 update operations.

Provides functions for:
- Docker compose operations (up/down)
- Docker image operations (load/save)
- Container health checks
- Docker cleanup (prune)
"""

import subprocess
import time
import logging
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


# Default paths for RCU3
DOCKER_FILES_DIR = Path("/app/app/docker-files")
DEFAULT_COMPOSE_FILE = DOCKER_FILES_DIR / "docker-compose.yml"

# Docker Compose command (will be auto-detected)
_DOCKER_COMPOSE_CMD = None  # None = not yet detected


class ContainerState(Enum):
    """Docker container states"""
    RUNNING = "running"
    EXITED = "exited"
    PAUSED = "paused"
    RESTARTING = "restarting"
    DEAD = "dead"
    CREATED = "created"
    UNKNOWN = "unknown"


@dataclass
class ContainerStatus:
    """Container status information"""
    name: str
    state: ContainerState
    health: Optional[str]  # healthy, unhealthy, starting, none
    image: str
    created: str
    ports: List[str]


class DockerError(Exception):
    """Exception raised for Docker operation failures"""
    pass


def _detect_docker_compose_command() -> str:
    """
    Detect which docker compose command is available.

    Tries both:
    - 'docker compose' (Docker Compose V2, built into Docker CLI)
    - 'docker-compose' (Docker Compose V1, standalone binary)

    Returns:
        'compose' for V2 or 'docker-compose' for V1

    Raises:
        DockerError: If neither command is available
    """
    global _DOCKER_COMPOSE_CMD

    if _DOCKER_COMPOSE_CMD is not None:
        return _DOCKER_COMPOSE_CMD

    # Try Docker Compose V2 (docker compose)
    try:
        result = subprocess.run(
            ['docker', 'compose', 'version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version_info = result.stdout.strip()
            _DOCKER_COMPOSE_CMD = 'compose'
            return 'compose'
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        logger.debug(f"Docker Compose V2 not available: {e}")

    # Try Docker Compose V1 (docker-compose)
    try:
        result = subprocess.run(
            ['docker-compose', 'version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version_info = result.stdout.strip()
            _DOCKER_COMPOSE_CMD = 'docker-compose'
            return 'docker-compose'
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        logger.debug(f"Docker Compose V1 not available: {e}")

    # Neither is available
    raise DockerError(
        "Docker Compose not found. Please install either:\n"
        "  - Docker Compose V2 (docker compose)\n"
        "  - Docker Compose V1 (docker-compose)"
    )


def run_docker(args: List[str], timeout: int = 300, cwd: Optional[Path] = None) -> Tuple[int, str, str]:
    """
    Run docker command with automatic docker-compose compatibility.

    Auto-detects and uses the correct Docker Compose command:
    - Docker Compose V2: 'docker compose'
    - Docker Compose V1: 'docker-compose' (standalone)

    Args:
        args: Command arguments (e.g., ['compose', 'up', '-d'])
        timeout: Command timeout in seconds
        cwd: Working directory

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    # Auto-detect and convert compose commands
    if args and args[0] == 'compose':
        compose_cmd = _detect_docker_compose_command()

        if compose_cmd == 'docker-compose':
            # V1: Use standalone docker-compose binary
            cmd = ['docker-compose'] + args[1:]
        else:
            # V2: Use docker compose subcommand
            cmd = ['docker', 'compose'] + args[1:]
    else:
        # Regular docker command
        cmd = ['docker'] + args

    logger.debug(f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd
        )
        return result.returncode, result.stdout, result.stderr

    except subprocess.TimeoutExpired:
        raise DockerError(f"Docker command timed out after {timeout}s: {' '.join(cmd)}")


def compose_down(
    compose_file: Path = DEFAULT_COMPOSE_FILE,
    timeout: int = 60,
    remove_volumes: bool = False,
    remove_orphans: bool = True,
    cwd: Optional[Path] = None
) -> bool:
    """
    Stop Docker Compose services.

    Args:
        compose_file: Path to docker-compose.yml
        timeout: Timeout for container stop
        remove_volumes: Remove named volumes
        remove_orphans: Remove containers for services not in compose file
        cwd: Working directory for command

    Returns:
        True if successful

    Raises:
        DockerError: If operation fails
    """
    if not compose_file.exists():
        raise DockerError(f"Compose file not found: {compose_file}")


    args = ['compose', '-f', str(compose_file), 'down', '--timeout', str(timeout)]

    if remove_volumes:
        args.append('--volumes')
    if remove_orphans:
        args.append('--remove-orphans')

    rc, stdout, stderr = run_docker(args, timeout=timeout + 30, cwd=cwd)

    if rc != 0:
        logger.error(f"Docker compose down failed: {stderr}")
        raise DockerError(f"Failed to stop services: {stderr}")

    return True


def compose_up(
    compose_file: Path = DEFAULT_COMPOSE_FILE,
    detach: bool = True,
    build: bool = False,
    force_recreate: bool = False,
    timeout: int = 120,
    cwd: Optional[Path] = None
) -> bool:
    """
    Start Docker Compose services.

    Args:
        compose_file: Path to docker-compose.yml
        detach: Run in background
        build: Build images before starting
        force_recreate: Recreate containers even if unchanged
        timeout: Timeout for operation
        cwd: Working directory for command

    Returns:
        True if successful

    Raises:
        DockerError: If operation fails
    """
    if not compose_file.exists():
        raise DockerError(f"Compose file not found: {compose_file}")


    args = ['compose', '-f', str(compose_file), 'up']

    if detach:
        args.append('-d')
    if build:
        args.append('--build')
    if force_recreate:
        args.append('--force-recreate')

    rc, stdout, stderr = run_docker(args, timeout=timeout, cwd=cwd)

    if rc != 0:
        logger.error(f"Docker compose up failed: {stderr}")
        raise DockerError(f"Failed to start services: {stderr}")

    return True


def docker_load(image_tar: Path, timeout: int = 600) -> str:
    """
    Load Docker image from tar file.

    Args:
        image_tar: Path to image tar file
        timeout: Timeout for load operation (default 10 min for large images)

    Returns:
        Loaded image name/tag

    Raises:
        DockerError: If load fails
    """
    if not image_tar.exists():
        raise DockerError(f"Image tar file not found: {image_tar}")

    file_size_mb = image_tar.stat().st_size / (1024 * 1024)

    rc, stdout, stderr = run_docker(['load', '-i', str(image_tar)], timeout=timeout)

    if rc != 0:
        logger.error(f"Docker load failed: {stderr}")
        raise DockerError(f"Failed to load image: {stderr}")

    # Parse loaded image name from output
    # Output format: "Loaded image: image:tag" or "Loaded image ID: sha256:..."
    loaded_image = "unknown"
    for line in stdout.split('\n'):
        if 'Loaded image:' in line:
            loaded_image = line.split('Loaded image:')[1].strip()
            break
        elif 'Loaded image ID:' in line:
            loaded_image = line.split('Loaded image ID:')[1].strip()
            break

    return loaded_image


def docker_save(image_name: str, output_path: Path, timeout: int = 600) -> bool:
    """
    Save Docker image to tar file.

    Args:
        image_name: Image name/tag to save
        output_path: Path for output tar file
        timeout: Timeout for save operation

    Returns:
        True if successful

    Raises:
        DockerError: If save fails
    """

    output_path.parent.mkdir(parents=True, exist_ok=True)

    rc, stdout, stderr = run_docker(['save', '-o', str(output_path), image_name], timeout=timeout)

    if rc != 0:
        logger.error(f"Docker save failed: {stderr}")
        raise DockerError(f"Failed to save image: {stderr}")

    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    return True


def docker_prune(
    all_images: bool = False,
    volumes: bool = False,
    force: bool = True
) -> Dict[str, Any]:
    """
    Cleanup unused Docker resources.

    Args:
        all_images: Remove all unused images (not just dangling)
        volumes: Also prune volumes
        force: Don't prompt for confirmation

    Returns:
        Dict with prune statistics
    """

    results = {}

    # Prune containers
    args = ['container', 'prune']
    if force:
        args.append('--force')
    rc, stdout, stderr = run_docker(args)
    results['containers'] = stdout

    # Prune images
    args = ['image', 'prune']
    if all_images:
        args.append('--all')
    if force:
        args.append('--force')
    rc, stdout, stderr = run_docker(args)
    results['images'] = stdout

    # Prune volumes if requested
    if volumes:
        args = ['volume', 'prune']
        if force:
            args.append('--force')
        rc, stdout, stderr = run_docker(args)
        results['volumes'] = stdout

    return results


def get_container_status(container_name: str) -> Optional[ContainerStatus]:
    """
    Get container status.

    Args:
        container_name: Container name

    Returns:
        ContainerStatus or None if container not found
    """
    rc, stdout, stderr = run_docker([
        'inspect', container_name,
        '--format', '{{.State.Status}}|{{.State.Health.Status}}|{{.Config.Image}}|{{.Created}}'
    ])

    if rc != 0:
        return None

    parts = stdout.strip().split('|')
    if len(parts) < 4:
        return None

    try:
        state = ContainerState(parts[0])
    except ValueError:
        state = ContainerState.UNKNOWN

    health = parts[1] if parts[1] else None

    return ContainerStatus(
        name=container_name,
        state=state,
        health=health,
        image=parts[2],
        created=parts[3],
        ports=[]
    )


def get_compose_services(compose_file: Path = DEFAULT_COMPOSE_FILE) -> List[str]:
    """
    Get list of services defined in compose file.

    Args:
        compose_file: Path to docker-compose.yml

    Returns:
        List of service names
    """
    if not compose_file.exists():
        return []

    rc, stdout, stderr = run_docker(
        ['compose', '-f', str(compose_file), 'config', '--services']
    )

    if rc != 0:
        return []

    return [s.strip() for s in stdout.strip().split('\n') if s.strip()]


def wait_for_containers_healthy(
    compose_file: Path = DEFAULT_COMPOSE_FILE,
    timeout: int = 120,
    poll_interval: float = 5.0,
    ignore_services: Optional[List[str]] = None,
    cwd: Optional[Path] = None
) -> Tuple[bool, Dict[str, str]]:
    """
    Wait for all containers to be healthy/running.

    Args:
        compose_file: Path to docker-compose.yml
        timeout: Maximum time to wait
        poll_interval: Time between checks
        ignore_services: Services to ignore in health check
        cwd: Working directory for command (optional, not used in this function)

    Returns:
        Tuple of (all_healthy, service_statuses)
    """
    if ignore_services is None:
        ignore_services = []

    services = get_compose_services(compose_file)
    services = [s for s in services if s not in ignore_services]

    if not services:
        return True, {}


    start_time = time.time()

    while time.time() - start_time < timeout:
        statuses = {}
        all_healthy = True

        for service in services:
            # Get container name (usually project_service_1)
            rc, stdout, stderr = run_docker([
                'compose', '-f', str(compose_file), 'ps', '-q', service
            ])

            if rc != 0 or not stdout.strip():
                statuses[service] = 'not_found'
                all_healthy = False
                continue

            container_id = stdout.strip().split('\n')[0]

            # Get status
            status = get_container_status(container_id)
            if status is None:
                statuses[service] = 'unknown'
                all_healthy = False
                continue

            if status.health:
                statuses[service] = status.health
                if status.health not in ['healthy']:
                    all_healthy = False
            else:
                # No health check defined, check if running
                statuses[service] = status.state.value
                if status.state != ContainerState.RUNNING:
                    all_healthy = False

        logger.debug(f"Container statuses: {statuses}")

        if all_healthy:
            return True, statuses

        time.sleep(poll_interval)

    return False, statuses


def copy_docker_files(
    source_dir: Path,
    dest_dir: Path = DOCKER_FILES_DIR,
    file_patterns: Optional[List[str]] = None
) -> List[Path]:
    """
    Copy Docker files (tar images, compose file) to destination.

    Args:
        source_dir: Source directory containing Docker files
        dest_dir: Destination directory (default: /app/app/docker-files)
        file_patterns: File patterns to copy (default: *.tar, *.yml, *.yaml)

    Returns:
        List of copied file paths
    """
    if file_patterns is None:
        file_patterns = ['*.tar', '*.yml', '*.yaml']

    if not source_dir.exists():
        raise DockerError(f"Source directory not found: {source_dir}")

    dest_dir.mkdir(parents=True, exist_ok=True)

    copied_files = []

    for pattern in file_patterns:
        for src_file in source_dir.glob(pattern):
            dest_file = dest_dir / src_file.name
            shutil.copy2(src_file, dest_file)
            copied_files.append(dest_file)

    return copied_files


def load_all_images(
    source_dir: Path,
    timeout_per_image: int = 600
) -> List[str]:
    """
    Load all Docker images from tar files in directory.

    Args:
        source_dir: Directory containing .tar files
        timeout_per_image: Timeout per image load

    Returns:
        List of loaded image names
    """
    tar_files = list(source_dir.glob('*.tar'))

    if not tar_files:
        return []


    loaded_images = []
    for tar_file in tar_files:
        try:
            image_name = docker_load(tar_file, timeout=timeout_per_image)
            loaded_images.append(image_name)
        except DockerError as e:
            logger.error(f"Failed to load {tar_file}: {e}")
            raise

    return loaded_images


# RCU3 specific container names
RCU3_CONTAINERS = {
    'backend-api': 'Backend API (FastAPI)',
    'celery-worker': 'Celery Background Worker',
    'redis': 'Redis Cache/Broker',
    'frontend': 'Frontend (Next.js + nginx)'
}


if __name__ == '__main__':
    # Test mode
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("Docker Utils Test Mode")
    print("=" * 40)

    # Test basic docker command
    print("\nTesting docker version...")
    rc, stdout, stderr = run_docker(['version', '--format', '{{.Server.Version}}'])
    if rc == 0:
        print(f"Docker version: {stdout.strip()}")
    else:
        print(f"Docker not available: {stderr}")

    print("\nTest completed!")
