"""
Systemd utility functions for RCU3 update operations.

Provides functions for:
- Starting/stopping/restarting systemd services
- Checking service status
- Waiting for service health
- Reading service logs
"""

import subprocess
import time
import logging
from typing import Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ServiceState(Enum):
    """Systemd service states"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    FAILED = "failed"
    ACTIVATING = "activating"
    DEACTIVATING = "deactivating"
    UNKNOWN = "unknown"


@dataclass
class ServiceStatus:
    """Service status information"""
    name: str
    state: ServiceState
    sub_state: str  # e.g., "running", "dead", "exited"
    pid: Optional[int]
    memory: Optional[str]
    uptime: Optional[str]
    error: Optional[str] = None


class SystemdError(Exception):
    """Exception raised for systemd operation failures"""
    pass


def run_systemctl(args: List[str], timeout: int = 30) -> Tuple[int, str, str]:
    """
    Run systemctl command.

    Args:
        args: Command arguments (e.g., ['stop', 'service-backend.service'])
        timeout: Command timeout in seconds

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    cmd = ['systemctl'] + args

    logger.debug(f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr

    except subprocess.TimeoutExpired:
        raise SystemdError(f"systemctl command timed out after {timeout}s: {' '.join(cmd)}")


def get_service_status(service_name: str) -> ServiceStatus:
    """
    Get detailed service status.

    Args:
        service_name: Service name (e.g., 'service-backend.service')

    Returns:
        ServiceStatus object
    """
    # Get state
    rc, stdout, stderr = run_systemctl(['is-active', service_name])
    state_str = stdout.strip()

    try:
        state = ServiceState(state_str)
    except ValueError:
        state = ServiceState.UNKNOWN

    # Get sub-state and other info
    rc, stdout, stderr = run_systemctl(['show', service_name,
        '--property=SubState,MainPID,MemoryCurrent,ActiveEnterTimestamp'])

    props = {}
    for line in stdout.strip().split('\n'):
        if '=' in line:
            key, value = line.split('=', 1)
            props[key] = value

    pid = int(props.get('MainPID', 0)) or None
    memory = props.get('MemoryCurrent')
    uptime = props.get('ActiveEnterTimestamp')
    sub_state = props.get('SubState', 'unknown')

    return ServiceStatus(
        name=service_name,
        state=state,
        sub_state=sub_state,
        pid=pid,
        memory=memory,
        uptime=uptime
    )


def is_service_active(service_name: str) -> bool:
    """
    Check if service is active (running).

    Args:
        service_name: Service name

    Returns:
        True if service is active
    """
    rc, stdout, _ = run_systemctl(['is-active', service_name])
    return stdout.strip() == 'active'


def stop_service(
    service_name: str,
    timeout: int = 30,
    ignore_not_found: bool = True
) -> bool:
    """
    Stop a systemd service.

    Args:
        service_name: Service name to stop
        timeout: Timeout for stop operation
        ignore_not_found: If True, don't raise error if service doesn't exist

    Returns:
        True if service stopped successfully

    Raises:
        SystemdError: If stop fails (and service exists)
    """
    logger.info(f"Stopping service: {service_name}")

    rc, stdout, stderr = run_systemctl(['stop', service_name], timeout=timeout)

    if rc != 0:
        # Check if service exists
        if 'not found' in stderr.lower() or 'does not exist' in stderr.lower():
            if ignore_not_found:
                logger.warning(f"Service not found (ignored): {service_name}")
                return True
            raise SystemdError(f"Service not found: {service_name}")

        raise SystemdError(f"Failed to stop service {service_name}: {stderr}")

    logger.info(f"Service stopped: {service_name}")
    return True


def start_service(
    service_name: str,
    timeout: int = 30,
    wait_healthy: bool = True,
    health_timeout: int = 30
) -> bool:
    """
    Start a systemd service.

    Args:
        service_name: Service name to start
        timeout: Timeout for start operation
        wait_healthy: If True, wait for service to become active
        health_timeout: Timeout for health check

    Returns:
        True if service started successfully

    Raises:
        SystemdError: If start fails
    """
    logger.info(f"Starting service: {service_name}")

    rc, stdout, stderr = run_systemctl(['start', service_name], timeout=timeout)

    if rc != 0:
        raise SystemdError(f"Failed to start service {service_name}: {stderr}")

    if wait_healthy:
        if not wait_for_service_active(service_name, timeout=health_timeout):
            raise SystemdError(f"Service {service_name} did not become active within {health_timeout}s")

    logger.info(f"Service started: {service_name}")
    return True


def restart_service(
    service_name: str,
    timeout: int = 30,
    wait_healthy: bool = True,
    health_timeout: int = 30
) -> bool:
    """
    Restart a systemd service.

    Args:
        service_name: Service name to restart
        timeout: Timeout for restart operation
        wait_healthy: If True, wait for service to become active
        health_timeout: Timeout for health check

    Returns:
        True if service restarted successfully

    Raises:
        SystemdError: If restart fails
    """
    logger.info(f"Restarting service: {service_name}")

    rc, stdout, stderr = run_systemctl(['restart', service_name], timeout=timeout)

    if rc != 0:
        raise SystemdError(f"Failed to restart service {service_name}: {stderr}")

    if wait_healthy:
        if not wait_for_service_active(service_name, timeout=health_timeout):
            raise SystemdError(f"Service {service_name} did not become active within {health_timeout}s")

    logger.info(f"Service restarted: {service_name}")
    return True


def reload_daemon():
    """
    Reload systemd daemon configuration.

    Equivalent to: systemctl daemon-reload
    """
    logger.info("Reloading systemd daemon")

    rc, stdout, stderr = run_systemctl(['daemon-reload'])

    if rc != 0:
        raise SystemdError(f"Failed to reload daemon: {stderr}")

    logger.info("Systemd daemon reloaded")


def wait_for_service_active(
    service_name: str,
    timeout: int = 30,
    poll_interval: float = 1.0
) -> bool:
    """
    Wait for service to become active.

    Args:
        service_name: Service name to wait for
        timeout: Maximum time to wait (seconds)
        poll_interval: Time between status checks (seconds)

    Returns:
        True if service became active within timeout
    """
    logger.debug(f"Waiting for service {service_name} to become active (timeout: {timeout}s)")

    start_time = time.time()

    while time.time() - start_time < timeout:
        if is_service_active(service_name):
            logger.debug(f"Service {service_name} is active")
            return True

        time.sleep(poll_interval)

    logger.warning(f"Timeout waiting for service {service_name} to become active")
    return False


def wait_for_service_stopped(
    service_name: str,
    timeout: int = 30,
    poll_interval: float = 1.0
) -> bool:
    """
    Wait for service to become inactive/stopped.

    Args:
        service_name: Service name to wait for
        timeout: Maximum time to wait (seconds)
        poll_interval: Time between status checks (seconds)

    Returns:
        True if service became inactive within timeout
    """
    logger.debug(f"Waiting for service {service_name} to stop (timeout: {timeout}s)")

    start_time = time.time()

    while time.time() - start_time < timeout:
        if not is_service_active(service_name):
            logger.debug(f"Service {service_name} is stopped")
            return True

        time.sleep(poll_interval)

    logger.warning(f"Timeout waiting for service {service_name} to stop")
    return False


def get_service_logs(
    service_name: str,
    lines: int = 50,
    since: Optional[str] = None
) -> str:
    """
    Get service logs from journalctl.

    Args:
        service_name: Service name
        lines: Number of lines to retrieve
        since: Time specification (e.g., "5 minutes ago", "2024-01-01")

    Returns:
        Log output as string
    """
    cmd = ['journalctl', '-u', service_name, '-n', str(lines), '--no-pager']

    if since:
        cmd.extend(['--since', since])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.stdout

    except subprocess.TimeoutExpired:
        return f"Timeout getting logs for {service_name}"


def check_service_logs_for_errors(
    service_name: str,
    lines: int = 20,
    error_patterns: Optional[List[str]] = None
) -> Tuple[bool, List[str]]:
    """
    Check service logs for error patterns.

    Args:
        service_name: Service name
        lines: Number of recent lines to check
        error_patterns: List of error patterns to search for
            Default: ['error', 'exception', 'traceback', 'failed']

    Returns:
        Tuple of (has_errors, list of matching lines)
    """
    if error_patterns is None:
        error_patterns = ['error', 'exception', 'traceback', 'failed', 'critical']

    logs = get_service_logs(service_name, lines=lines)
    matching_lines = []

    for line in logs.split('\n'):
        line_lower = line.lower()
        for pattern in error_patterns:
            if pattern.lower() in line_lower:
                matching_lines.append(line)
                break

    return len(matching_lines) > 0, matching_lines


# Convenience constants for RCU3 services
SERVICE_BACKEND = 'service-backend.service'
UPDATE_SERVICE = 'update-service.service'
CHROMIUM_KIOSK = 'chromium-kiosk.service'


if __name__ == '__main__':
    # Test mode
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("Systemd Utils Test Mode")
    print("=" * 40)

    # Test with a common service
    test_service = 'cron.service'

    print(f"\nGetting status of {test_service}...")
    status = get_service_status(test_service)
    print(f"  State: {status.state.value}")
    print(f"  Sub-state: {status.sub_state}")
    print(f"  PID: {status.pid}")

    print(f"\nIs {test_service} active? {is_service_active(test_service)}")

    print("\nTest completed!")
