"""Check implementations for update engine."""
import logging
import subprocess
import shutil
import time
from pathlib import Path
from typing import Dict, Any
import requests


logger = logging.getLogger('update_engine')


class CheckError(Exception):
    """Exception raised when a check fails."""
    pass


def execute_check(check: Dict[str, Any]) -> bool:
    """Execute a check based on its type.
    
    Args:
        check: Check configuration dictionary
        
    Returns:
        True if check passes
        
    Raises:
        CheckError: If check fails
        ValueError: If check type is unknown
    """
    check_type = check.get('type')
    
    if check_type == 'disk_space':
        return check_disk_space(check)
    elif check_type == 'docker_running':
        return check_docker_running(check)
    elif check_type == 'file_exists':
        return check_file_exists(check)
    elif check_type == 'docker_health':
        return check_docker_health(check)
    elif check_type == 'http_check':
        return check_http_endpoint(check)
    elif check_type == 'service_running':
        return check_service_running(check)
    elif check_type == 'command':
        return check_command(check)
    else:
        raise ValueError(f"Unknown check type: {check_type}")


def check_disk_space(check: Dict[str, Any]) -> bool:
    """Check available disk space.
    
    Args:
        check: Check configuration with 'path' and 'required_mb'
        
    Returns:
        True if sufficient space available
        
    Raises:
        CheckError: If insufficient space
    """
    path = Path(check['path'])
    required_mb = check['required_mb']
    
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    
    stat = shutil.disk_usage(path)
    available_mb = stat.free / (1024 * 1024)
    
    logger.info(f"Disk space check: {available_mb:.0f} MB available (required: {required_mb} MB)")
    
    if available_mb < required_mb:
        raise CheckError(
            f"Insufficient disk space at {path}: "
            f"{available_mb:.0f} MB available, {required_mb} MB required"
        )
    
    return True


def check_docker_running(check: Dict[str, Any]) -> bool:
    """Check if Docker daemon is running.
    
    Args:
        check: Check configuration
        
    Returns:
        True if Docker is running
        
    Raises:
        CheckError: If Docker is not running
    """
    try:
        result = subprocess.run(
            ['docker', 'info'],
            capture_output=True,
            timeout=10
        )
        
        if result.returncode != 0:
            raise CheckError("Docker daemon is not running")
        
        logger.info("Docker daemon is running")
        return True
        
    except subprocess.TimeoutExpired:
        raise CheckError("Docker command timed out")
    except FileNotFoundError:
        raise CheckError("Docker is not installed")


def check_file_exists(check: Dict[str, Any]) -> bool:
    """Check if a file or directory exists.
    
    Args:
        check: Check configuration with 'path'
        
    Returns:
        True if file/directory exists
        
    Raises:
        CheckError: If file/directory doesn't exist
    """
    path = Path(check['path'])
    
    if not path.exists():
        raise CheckError(f"Path does not exist: {path}")
    
    logger.info(f"Path exists: {path}")
    return True


def check_docker_health(check: Dict[str, Any]) -> bool:
    """Check Docker container health status.
    
    Args:
        check: Check configuration with 'container_name' or 'container_id'
        
    Returns:
        True if container is healthy
        
    Raises:
        CheckError: If container is not healthy
    """
    container = check.get('container_name') or check.get('container_id')
    
    if not container:
        raise ValueError("container_name or container_id required for docker_health check")
    
    try:
        result = subprocess.run(
            ['docker', 'inspect', '--format={{.State.Health.Status}}', container],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            raise CheckError(f"Container not found: {container}")
        
        health_status = result.stdout.strip()
        
        if health_status == 'healthy':
            logger.info(f"Container {container} is healthy")
            return True
        elif health_status == '<no value>':
            # Container has no health check defined, check if it's running
            result = subprocess.run(
                ['docker', 'inspect', '--format={{.State.Running}}', container],
                capture_output=True,
                text=True,
                timeout=10
            )
            is_running = result.stdout.strip() == 'true'
            if is_running:
                logger.info(f"Container {container} is running (no health check)")
                return True
            else:
                raise CheckError(f"Container {container} is not running")
        else:
            raise CheckError(f"Container {container} health status: {health_status}")
            
    except subprocess.TimeoutExpired:
        raise CheckError("Docker command timed out")


def check_http_endpoint(check: Dict[str, Any]) -> bool:
    """Check HTTP endpoint availability.
    
    Args:
        check: Check configuration with 'url', optional 'retries', 'delay', 'timeout'
        
    Returns:
        True if endpoint is accessible
        
    Raises:
        CheckError: If endpoint is not accessible
    """
    url = check['url']
    retries = check.get('retries', 1)
    delay = check.get('delay', 5)  # seconds between retries
    timeout = check.get('timeout', 10)  # request timeout
    expected_status = check.get('expected_status', 200)
    
    for attempt in range(retries):
        try:
            logger.info(f"HTTP check attempt {attempt + 1}/{retries}: {url}")
            response = requests.get(url, timeout=timeout)
            
            if response.status_code == expected_status:
                logger.info(f"HTTP check passed: {url} returned {response.status_code}")
                return True
            else:
                logger.warning(
                    f"HTTP check failed: {url} returned {response.status_code}, "
                    f"expected {expected_status}"
                )
                
        except requests.RequestException as e:
            logger.warning(f"HTTP check failed: {e}")
        
        if attempt < retries - 1:
            logger.info(f"Waiting {delay}s before retry...")
            time.sleep(delay)
    
    raise CheckError(f"HTTP endpoint not accessible after {retries} attempts: {url}")


def check_service_running(check: Dict[str, Any]) -> bool:
    """Check if a systemd service is running.
    
    Args:
        check: Check configuration with 'service_name'
        
    Returns:
        True if service is running
        
    Raises:
        CheckError: If service is not running
    """
    service_name = check['service_name']
    
    try:
        result = subprocess.run(
            ['systemctl', 'is-active', service_name],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        is_active = result.stdout.strip() == 'active'
        
        if is_active:
            logger.info(f"Service {service_name} is running")
            return True
        else:
            raise CheckError(f"Service {service_name} is not running (status: {result.stdout.strip()})")
            
    except subprocess.TimeoutExpired:
        raise CheckError("systemctl command timed out")
    except FileNotFoundError:
        raise CheckError("systemctl not found (systemd not available)")


def check_command(check: Dict[str, Any]) -> bool:
    """Execute a command and check if it succeeds.
    
    Args:
        check: Check configuration with 'command', optional 'timeout'
        
    Returns:
        True if command succeeds (exit code 0)
        
    Raises:
        CheckError: If command fails
    """
    command = check['command']
    timeout = check.get('timeout', 30)
    
    logger.debug(f"Running check command: {command}")
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        if result.returncode == 0:
            if result.stdout:
                logger.info(f"Command check output: {result.stdout.strip()}")
            return True
        else:
            error_msg = f"Command failed with exit code {result.returncode}"
            if result.stderr:
                error_msg += f": {result.stderr.strip()}"
            raise CheckError(error_msg)
            
    except subprocess.TimeoutExpired:
        raise CheckError(f"Command timed out after {timeout}s")
    except Exception as e:
        raise CheckError(f"Command execution failed: {str(e)}")

