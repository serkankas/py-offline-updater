"""Action implementations for update engine."""
import logging
import subprocess
import shutil
import os
from pathlib import Path
from typing import Dict, Any, List
from dotenv import dotenv_values

from .backup import BackupManager
from .utils import calculate_checksum, verify_checksum


logger = logging.getLogger('update_engine')


class ActionError(Exception):
    """Exception raised when an action fails."""
    pass


def execute_action(action: Dict[str, Any], package_path: Path, backup_manager: BackupManager) -> bool:
    """Execute an action based on its type.
    
    Args:
        action: Action configuration dictionary
        package_path: Path to extracted update package
        backup_manager: BackupManager instance
        
    Returns:
        True if action succeeds
        
    Raises:
        ActionError: If action fails
        ValueError: If action type is unknown
    """
    action_type = action.get('type')
    action_name = action.get('name', action_type)
    
    logger.info(f"Executing action: {action_name} ({action_type})")
    
    try:
        if action_type == 'command':
            return action_command(action, package_path)
        elif action_type == 'backup':
            return action_backup(action, backup_manager)
        elif action_type == 'restore_backup':
            return action_restore_backup(action, backup_manager)
        elif action_type == 'docker_compose_down':
            return action_docker_compose_down(action)
        elif action_type == 'docker_compose_up':
            return action_docker_compose_up(action)
        elif action_type == 'docker_load':
            return action_docker_load(action, package_path)
        elif action_type == 'docker_prune':
            return action_docker_prune(action)
        elif action_type == 'file_copy':
            return action_file_copy(action, package_path)
        elif action_type == 'file_sync':
            return action_file_sync(action, package_path)
        elif action_type == 'file_merge':
            return action_file_merge(action, package_path)
        else:
            raise ValueError(f"Unknown action type: {action_type}")
            
    except Exception as e:
        if action.get('continue_on_error', False):
            logger.warning(f"Action failed but continue_on_error=True: {e}")
            return True
        raise ActionError(f"Action '{action_name}' failed: {e}")


def action_command(action: Dict[str, Any], package_path: Path) -> bool:
    """Execute a shell command.
    
    Args:
        action: Action configuration with 'command', optional 'cwd', 'timeout'
        package_path: Path to extracted update package (used as default cwd)
        
    Returns:
        True if command succeeds
        
    Raises:
        ActionError: If command fails
    """
    command = action['command']
    cwd = action.get('cwd', str(package_path))  # Default to package path if not specified
    timeout = action.get('timeout', 300)
    
    logger.info(f"Running command: {command}")
    if cwd:
        logger.debug(f"Working directory: {cwd}")
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        if result.stdout:
            logger.debug(f"Command output: {result.stdout}")
        
        if result.returncode != 0:
            logger.error(f"Command failed with exit code {result.returncode}")
            if result.stderr:
                logger.error(f"Command stderr: {result.stderr}")
            raise ActionError(f"Command failed with exit code {result.returncode}")
        
        logger.info("Command executed successfully")
        return True
        
    except subprocess.TimeoutExpired:
        raise ActionError(f"Command timed out after {timeout}s")


def action_backup(action: Dict[str, Any], backup_manager: BackupManager) -> bool:
    """Create a backup.
    
    Args:
        action: Action configuration with 'sources'
        backup_manager: BackupManager instance
        
    Returns:
        True if backup succeeds
    """
    sources = action['sources']
    name = action.get('name')
    
    backup_manager.create_backup(sources, name)
    return True


def action_restore_backup(action: Dict[str, Any], backup_manager: BackupManager) -> bool:
    """Restore from backup.
    
    Args:
        action: Action configuration with optional 'backup_name'
        backup_manager: BackupManager instance
        
    Returns:
        True if restore succeeds
    """
    backup_name = action.get('backup_name', 'latest')
    
    backup_manager.restore_backup(backup_name)
    return True


def action_docker_compose_down(action: Dict[str, Any]) -> bool:
    """Stop Docker Compose services.
    
    Args:
        action: Action configuration with 'compose_file', optional 'timeout'
        
    Returns:
        True if services stopped successfully
        
    Raises:
        ActionError: If command fails
    """
    compose_file = action['compose_file']
    timeout = action.get('timeout', 60)
    
    cmd = ['docker', 'compose', '-f', compose_file, 'down', '--timeout', str(timeout)]
    
    logger.info(f"Stopping Docker Compose services: {compose_file}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        logger.error(f"Docker compose down failed: {result.stderr}")
        raise ActionError(f"Failed to stop services: {result.stderr}")
    
    logger.info("Docker Compose services stopped")
    return True


def action_docker_compose_up(action: Dict[str, Any]) -> bool:
    """Start Docker Compose services.
    
    Args:
        action: Action configuration with 'compose_file', optional 'detach', 'build'
        
    Returns:
        True if services started successfully
        
    Raises:
        ActionError: If command fails
    """
    compose_file = action['compose_file']
    detach = action.get('detach', True)
    build = action.get('build', False)
    
    cmd = ['docker', 'compose', '-f', compose_file, 'up']
    
    if detach:
        cmd.append('-d')
    if build:
        cmd.append('--build')
    
    logger.info(f"Starting Docker Compose services: {compose_file}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        logger.error(f"Docker compose up failed: {result.stderr}")
        raise ActionError(f"Failed to start services: {result.stderr}")
    
    logger.info("Docker Compose services started")
    return True


def action_docker_load(action: Dict[str, Any], package_path: Path) -> bool:
    """Load Docker image from tar file.
    
    Args:
        action: Action configuration with 'image_tar'
        package_path: Path to extracted update package
        
    Returns:
        True if image loaded successfully
        
    Raises:
        ActionError: If command fails
    """
    image_tar = action['image_tar']
    tar_path = package_path / image_tar
    
    if not tar_path.exists():
        raise ActionError(f"Image tar file not found: {tar_path}")
    
    logger.info(f"Loading Docker image: {tar_path}")
    
    result = subprocess.run(
        ['docker', 'load', '-i', str(tar_path)],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        logger.error(f"Docker load failed: {result.stderr}")
        raise ActionError(f"Failed to load image: {result.stderr}")
    
    logger.info(f"Docker image loaded: {result.stdout.strip()}")
    return True


def action_docker_prune(action: Dict[str, Any]) -> bool:
    """Cleanup old Docker images.
    
    Args:
        action: Action configuration with optional 'all', 'force'
        
    Returns:
        True if prune succeeds
        
    Raises:
        ActionError: If command fails
    """
    prune_all = action.get('all', False)
    force = action.get('force', True)
    
    cmd = ['docker', 'image', 'prune']
    
    if prune_all:
        cmd.append('--all')
    if force:
        cmd.append('--force')
    
    logger.info("Pruning Docker images")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        logger.error(f"Docker prune failed: {result.stderr}")
        raise ActionError(f"Failed to prune images: {result.stderr}")
    
    logger.info(f"Docker images pruned: {result.stdout.strip()}")
    return True


def action_file_copy(action: Dict[str, Any], package_path: Path) -> bool:
    """Copy a file with checksum verification.
    
    Args:
        action: Action configuration with 'source', 'destination', optional 'checksum'
        package_path: Path to extracted update package
        
    Returns:
        True if file copied successfully
        
    Raises:
        ActionError: If copy or checksum verification fails
    """
    source = action['source']
    destination = action['destination']
    expected_checksum = action.get('checksum')
    
    source_path = package_path / source
    dest_path = Path(destination)
    
    if not source_path.exists():
        raise ActionError(f"Source file not found: {source_path}")
    
    # Verify source checksum if provided
    if expected_checksum:
        if not verify_checksum(source_path, expected_checksum):
            raise ActionError(f"Source file checksum mismatch: {source_path}")
    
    # Create destination directory if needed
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Copy file
    logger.info(f"Copying file: {source_path} -> {dest_path}")
    shutil.copy2(source_path, dest_path)
    
    # Verify destination checksum
    if expected_checksum:
        if not verify_checksum(dest_path, expected_checksum):
            raise ActionError(f"Destination file checksum mismatch: {dest_path}")
    
    logger.info("File copied successfully")
    return True


def action_file_sync(action: Dict[str, Any], package_path: Path) -> bool:
    """Sync directory contents (rsync-like).
    
    Args:
        action: Action configuration with 'source', 'destination', optional 'mode'
        package_path: Path to extracted update package
        
    Returns:
        True if sync succeeds
        
    Raises:
        ActionError: If sync fails
    """
    source = action['source']
    destination = action['destination']
    mode = action.get('mode', 'mirror')  # mirror, add_only, overwrite_existing
    
    source_path = package_path / source
    dest_path = Path(destination)
    
    if not source_path.exists():
        raise ActionError(f"Source directory not found: {source_path}")
    
    if not source_path.is_dir():
        raise ActionError(f"Source is not a directory: {source_path}")
    
    logger.info(f"Syncing directory (mode={mode}): {source_path} -> {dest_path}")
    
    dest_path.mkdir(parents=True, exist_ok=True)
    
    if mode == 'mirror':
        # Remove destination and copy everything
        if dest_path.exists():
            shutil.rmtree(dest_path)
        shutil.copytree(source_path, dest_path)
        
    elif mode == 'add_only':
        # Only add new files, don't overwrite existing
        for item in source_path.rglob('*'):
            if item.is_file():
                rel_path = item.relative_to(source_path)
                dest_file = dest_path / rel_path
                
                if not dest_file.exists():
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dest_file)
                    logger.debug(f"Added: {rel_path}")
                    
    elif mode == 'overwrite_existing':
        # Overwrite existing files, add new ones
        for item in source_path.rglob('*'):
            if item.is_file():
                rel_path = item.relative_to(source_path)
                dest_file = dest_path / rel_path
                
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest_file)
                logger.debug(f"Copied: {rel_path}")
    else:
        raise ActionError(f"Unknown sync mode: {mode}")
    
    logger.info("Directory synced successfully")
    return True


def action_file_merge(action: Dict[str, Any], package_path: Path) -> bool:
    """Merge files (e.g., .env files).
    
    Args:
        action: Action configuration with 'source', 'destination', optional 'strategy'
        package_path: Path to extracted update package
        
    Returns:
        True if merge succeeds
        
    Raises:
        ActionError: If merge fails
    """
    source = action['source']
    destination = action['destination']
    strategy = action.get('strategy', 'keep_existing')  # keep_existing, overwrite_all, merge_keys
    
    source_path = package_path / source
    dest_path = Path(destination)
    
    if not source_path.exists():
        raise ActionError(f"Source file not found: {source_path}")
    
    logger.info(f"Merging file (strategy={strategy}): {source_path} -> {dest_path}")
    
    # Load source values
    source_values = dotenv_values(source_path)
    
    # Load destination values if exists
    if dest_path.exists():
        dest_values = dotenv_values(dest_path)
    else:
        dest_values = {}
    
    # Merge based on strategy
    if strategy == 'keep_existing':
        # Source values only for new keys
        merged = {**source_values, **dest_values}
        
    elif strategy == 'overwrite_all':
        # Source values override destination
        merged = {**dest_values, **source_values}
        
    elif strategy == 'merge_keys':
        # All keys from both, destination takes precedence on conflicts
        merged = {**source_values, **dest_values}
    else:
        raise ActionError(f"Unknown merge strategy: {strategy}")
    
    # Write merged file
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dest_path, 'w') as f:
        for key, value in merged.items():
            # Handle values with spaces/special characters
            if ' ' in value or '#' in value:
                value = f'"{value}"'
            f.write(f"{key}={value}\n")
    
    logger.info(f"File merged successfully ({len(merged)} keys)")
    return True

