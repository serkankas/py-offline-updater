"""
RCU3 Update Tools

A collection of tools for updating RCU3 embedded devices:
- WatchdogKeeper: Keep hardware watchdog alive during updates
- SystemdUtils: Manage systemd services
- DockerUtils: Docker compose and image operations
- UpdateOperations: High-level update functions

Usage:
    from rcu3_update import WatchdogKeeper, docker_update, service_backend_update

    # Start watchdog keeper
    keeper = WatchdogKeeper(kick_interval=3)
    keeper.start()

    try:
        # Perform updates
        docker_update(...)
        service_backend_update(...)
    finally:
        keeper.stop()

Or use the CLI tool:
    python3 -m rcu3_update.update_batch --include-docker --docker-images /path/to/images/ ...
"""

from .watchdog_keeper import WatchdogKeeper, get_watchdog_keeper
from .systemd_utils import (
    stop_service,
    start_service,
    restart_service,
    is_service_active,
    get_service_status,
    wait_for_service_active,
    SERVICE_BACKEND,
    UPDATE_SERVICE,
    CHROMIUM_KIOSK,
)
from .docker_utils import (
    compose_down,
    compose_up,
    docker_load,
    docker_save,
    docker_prune,
    wait_for_containers_healthy,
    DOCKER_FILES_DIR,
)
from .update_operations import (
    docker_update,
    service_backend_update,
    updater_self_update,
    run_prechecks,
    frontend_health_check,
    UpdateError,
    PreCheckError,
)

__version__ = "1.0.0"
__all__ = [
    # WatchdogKeeper
    "WatchdogKeeper",
    "get_watchdog_keeper",
    # Systemd
    "stop_service",
    "start_service",
    "restart_service",
    "is_service_active",
    "get_service_status",
    "wait_for_service_active",
    "SERVICE_BACKEND",
    "UPDATE_SERVICE",
    "CHROMIUM_KIOSK",
    # Docker
    "compose_down",
    "compose_up",
    "docker_load",
    "docker_save",
    "docker_prune",
    "wait_for_containers_healthy",
    "DOCKER_FILES_DIR",
    # Update Operations
    "docker_update",
    "service_backend_update",
    "updater_self_update",
    "run_prechecks",
    "frontend_health_check",
    "UpdateError",
    "PreCheckError",
]
