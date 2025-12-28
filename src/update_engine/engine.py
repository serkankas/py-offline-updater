"""Main update engine implementation."""
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

from .utils import load_manifest, setup_logging
from .state import StateManager
from .backup import BackupManager
from .checks import execute_check, CheckError
from .actions import execute_action, ActionError


logger = logging.getLogger('update_engine')


class UpdateEngine:
    """Main update engine class."""
    
    def __init__(self, package_path: Path, base_dir: Path = None):
        """Initialize update engine.
        
        Args:
            package_path: Path to extracted update package
            base_dir: Base directory for engine data (default: /opt/updater)
        """
        self.package_path = Path(package_path)
        self.base_dir = base_dir or Path('/opt/updater')
        
        # Setup paths
        self.backup_dir = self.base_dir / 'backups'
        self.log_dir = self.base_dir / 'logs'
        self.state_file = self.base_dir / 'state.json'
        
        # Create directories
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup logging
        log_file = self.log_dir / 'update_engine.log'
        setup_logging(log_file)
        
        # Initialize managers
        self.state_manager = StateManager(self.state_file)
        self.backup_manager = BackupManager(self.backup_dir)
        
        # Load manifest
        manifest_path = self.package_path / 'manifest.yml'
        self.manifest = load_manifest(manifest_path)
        
        logger.info(f"UpdateEngine initialized for package: {package_path}")
        logger.info(f"Update: {self.manifest.get('description')}")
    
    def run(self) -> bool:
        """Execute the update process.
        
        Returns:
            True if update succeeds, False otherwise
        """
        try:
            # Check for incomplete update
            previous_state = self.state_manager.load()
            if previous_state and self.state_manager.is_update_in_progress():
                logger.warning("Found incomplete update, resuming...")
                return self._resume_update()
            
            # Start new update
            self._initialize_state()
            
            # Pre-checks
            if not self._run_checks('pre_checks'):
                logger.error("Pre-checks failed")
                return False
            
            # Execute actions
            if not self._run_actions():
                logger.error("Actions failed")
                if self._should_auto_rollback():
                    logger.info("Auto-rollback enabled, initiating rollback...")
                    self.rollback()
                return False
            
            # Post-checks
            if not self._run_checks('post_checks'):
                logger.error("Post-checks failed")
                if self._should_auto_rollback():
                    logger.info("Auto-rollback enabled, initiating rollback...")
                    self.rollback()
                return False
            
            # Cleanup
            self.cleanup()
            
            # Mark as complete
            self.state_manager.mark_update_complete(success=True)
            logger.info("Update completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Update failed with exception: {e}", exc_info=True)
            self.state_manager.mark_update_complete(success=False)
            
            if self._should_auto_rollback():
                logger.info("Auto-rollback enabled, initiating rollback...")
                self.rollback()
            
            return False
    
    def _resume_update(self) -> bool:
        """Resume an incomplete update.
        
        Returns:
            True if update completes successfully
        """
        state = self.state_manager.state
        completed_actions = set(state.get('completed_actions', []))
        
        logger.info(f"Resuming update from action {len(completed_actions)}")
        
        # Continue from where we left off
        actions = self.manifest.get('actions', [])
        
        for i, action in enumerate(actions):
            if i in completed_actions:
                logger.info(f"Skipping completed action {i}: {action.get('name', action['type'])}")
                continue
            
            # Execute action
            try:
                self.state_manager.mark_action_started(i, action.get('name', action['type']))
                success = execute_action(action, self.package_path, self.backup_manager)
                
                if success:
                    self.state_manager.mark_action_complete(i)
                else:
                    logger.error(f"Action {i} failed")
                    return False
                    
            except ActionError as e:
                logger.error(f"Action {i} failed: {e}")
                return False
        
        # Post-checks
        if not self._run_checks('post_checks'):
            logger.error("Post-checks failed after resume")
            return False
        
        # Cleanup and complete
        self.cleanup()
        self.state_manager.mark_update_complete(success=True)
        logger.info("Update resumed and completed successfully")
        return True
    
    def _initialize_state(self) -> None:
        """Initialize state for new update."""
        self.state_manager.save({
            'status': 'in_progress',
            'package_path': str(self.package_path),
            'description': self.manifest.get('description'),
            'completed_actions': []
        })
    
    def _run_checks(self, check_type: str) -> bool:
        """Run pre or post checks.
        
        Args:
            check_type: 'pre_checks' or 'post_checks'
            
        Returns:
            True if all checks pass
        """
        checks = self.manifest.get(check_type, [])
        
        if not checks:
            logger.info(f"No {check_type} defined")
            return True
        
        logger.info(f"Running {check_type} ({len(checks)} checks)")
        
        for i, check in enumerate(checks):
            check_name = check.get('type', f'check_{i}')
            
            try:
                logger.info(f"Check {i+1}/{len(checks)}: {check_name}")
                execute_check(check)
                logger.info(f"Check passed: {check_name}")
                
            except CheckError as e:
                logger.error(f"Check failed: {check_name} - {e}")
                return False
            except Exception as e:
                logger.error(f"Check error: {check_name} - {e}", exc_info=True)
                return False
        
        logger.info(f"All {check_type} passed")
        return True
    
    def _run_actions(self) -> bool:
        """Execute all actions.
        
        Returns:
            True if all actions succeed
        """
        actions = self.manifest.get('actions', [])
        
        if not actions:
            logger.warning("No actions defined in manifest")
            return True
        
        logger.info(f"Executing {len(actions)} actions")
        
        for i, action in enumerate(actions):
            action_name = action.get('name', action['type'])
            
            try:
                logger.info(f"Action {i+1}/{len(actions)}: {action_name}")
                
                # Mark action as started
                self.state_manager.mark_action_started(i, action_name)
                
                # Execute action
                success = execute_action(action, self.package_path, self.backup_manager)
                
                if success:
                    self.state_manager.mark_action_complete(i)
                    logger.info(f"Action completed: {action_name}")
                else:
                    logger.error(f"Action failed: {action_name}")
                    return False
                    
            except ActionError as e:
                logger.error(f"Action failed: {action_name} - {e}")
                return False
            except Exception as e:
                logger.error(f"Action error: {action_name} - {e}", exc_info=True)
                return False
        
        logger.info("All actions completed successfully")
        return True
    
    def _should_auto_rollback(self) -> bool:
        """Check if auto-rollback is enabled.
        
        Returns:
            True if auto-rollback should be performed
        """
        rollback_config = self.manifest.get('rollback', {})
        return (
            rollback_config.get('enabled', False) and
            rollback_config.get('auto_rollback_on_failure', False)
        )
    
    def rollback(self) -> bool:
        """Rollback the update.
        
        Returns:
            True if rollback succeeds
        """
        logger.info("Starting rollback...")
        
        rollback_config = self.manifest.get('rollback', {})
        
        if not rollback_config.get('enabled', False):
            logger.error("Rollback is not enabled in manifest")
            return False
        
        # Execute rollback steps if defined
        rollback_steps = rollback_config.get('steps', [])
        
        if rollback_steps:
            logger.info(f"Executing {len(rollback_steps)} rollback steps")
            
            for i, step in enumerate(rollback_steps):
                step_name = step.get('name', step['type'])
                
                try:
                    logger.info(f"Rollback step {i+1}/{len(rollback_steps)}: {step_name}")
                    execute_action(step, self.package_path, self.backup_manager)
                    logger.info(f"Rollback step completed: {step_name}")
                    
                except Exception as e:
                    logger.error(f"Rollback step failed: {step_name} - {e}", exc_info=True)
                    return False
        else:
            # Default rollback: restore latest backup
            logger.info("No rollback steps defined, restoring latest backup...")
            
            try:
                self.backup_manager.restore_backup('latest')
            except Exception as e:
                logger.error(f"Failed to restore backup: {e}", exc_info=True)
                return False
        
        logger.info("Rollback completed successfully")
        self.state_manager.update(status='rolled_back')
        return True
    
    def cleanup(self) -> None:
        """Cleanup after successful update."""
        logger.info("Running cleanup...")
        
        cleanup_config = self.manifest.get('cleanup', {})
        
        # Remove old backups
        if cleanup_config.get('remove_old_backups', False):
            keep_last_n = cleanup_config.get('keep_last_n', 3)
            logger.info(f"Cleaning up old backups (keeping last {keep_last_n})")
            self.backup_manager.cleanup_old_backups(keep_last_n)
        
        # Remove temp files
        if cleanup_config.get('remove_temp_files', False):
            logger.info("Removing temporary files")
            # Package directory will be removed by bootstrap
        
        # Remove old Docker images
        if cleanup_config.get('remove_old_images', False):
            logger.info("Pruning old Docker images")
            try:
                import subprocess
                subprocess.run(
                    ['docker', 'image', 'prune', '-f'],
                    capture_output=True
                )
            except Exception as e:
                logger.warning(f"Failed to prune Docker images: {e}")
        
        logger.info("Cleanup completed")
    
    def get_progress(self) -> Dict[str, Any]:
        """Get current update progress.
        
        Returns:
            Progress information dictionary
        """
        state = self.state_manager.state
        total_actions = len(self.manifest.get('actions', []))
        completed_actions = len(state.get('completed_actions', []))
        
        return {
            'status': state.get('status', 'unknown'),
            'total_actions': total_actions,
            'completed_actions': completed_actions,
            'current_action': state.get('current_action'),
            'current_action_name': state.get('current_action_name'),
            'description': self.manifest.get('description')
        }

