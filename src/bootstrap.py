#!/usr/bin/env python3
"""Bootstrap script for py-offline-updater.

This script:
1. Extracts the update package
2. Reads manifest.yml
3. Verifies/installs required engine version
4. Executes update_engine
5. Handles incomplete updates
"""
import sys
import tarfile
import shutil
import logging
from pathlib import Path
from typing import Optional

# Add update_engine to path
sys.path.insert(0, str(Path(__file__).parent))

from update_engine import __version__ as ENGINE_VERSION
from update_engine.utils import (
    load_manifest, 
    compare_versions, 
    calculate_checksum,
    verify_checksum,
    setup_logging
)
from update_engine.engine import UpdateEngine
from update_engine.state import StateManager


logger = logging.getLogger('bootstrap')


class BootstrapError(Exception):
    """Exception raised during bootstrap."""
    pass


class Bootstrap:
    """Bootstrap class for update process."""
    
    def __init__(self, package_file: Path, base_dir: Path = None):
        """Initialize bootstrap.
        
        Args:
            package_file: Path to update package (.tar.gz)
            base_dir: Base directory (default: /opt/updater)
        """
        self.package_file = Path(package_file)
        self.base_dir = base_dir or Path('/opt/updater')
        self.temp_dir = self.base_dir / 'tmp'
        self.engine_dir = self.base_dir / 'engine'
        
        # Setup logging
        log_dir = self.base_dir / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        setup_logging(log_dir / 'bootstrap.log')
        
        logger.info(f"Bootstrap initialized for: {package_file}")
        logger.info(f"Current engine version: {ENGINE_VERSION}")
    
    def run(self) -> bool:
        """Run bootstrap process.
        
        Returns:
            True if update succeeds
        """
        try:
            # Check for incomplete updates
            if self._check_incomplete_update():
                logger.info("Found incomplete update")
                response = input("Incomplete update detected. (C)ontinue or (R)ollback? [C/r]: ")
                
                if response.lower() == 'r':
                    return self._handle_rollback()
                else:
                    logger.info("Continuing incomplete update...")
                    # Will be handled by engine
            
            # Extract package
            extracted_path = self._extract_package()
            
            # Load manifest
            manifest = load_manifest(extracted_path / 'manifest.yml')
            logger.info(f"Update: {manifest['description']}")
            
            # Check engine version
            required_version = manifest['required_engine_version']
            if not self._verify_engine_version(required_version, extracted_path):
                return False
            
            # Execute update
            engine = UpdateEngine(extracted_path, self.base_dir)
            success = engine.run()
            
            # Cleanup temp directory on success
            if success:
                logger.info("Cleaning up temporary files...")
                self._cleanup_temp()
            
            return success
            
        except Exception as e:
            logger.error(f"Bootstrap failed: {e}", exc_info=True)
            return False
    
    def _check_incomplete_update(self) -> bool:
        """Check if there's an incomplete update.
        
        Returns:
            True if incomplete update found
        """
        state_file = self.base_dir / 'state.json'
        if not state_file.exists():
            return False
        
        state_manager = StateManager(state_file)
        state = state_manager.load()
        
        if state and state_manager.is_update_in_progress():
            logger.warning(f"Incomplete update found: {state.get('description')}")
            return True
        
        return False
    
    def _handle_rollback(self) -> bool:
        """Handle rollback of incomplete update.
        
        Returns:
            True if rollback succeeds
        """
        logger.info("Initiating rollback...")
        
        state_manager = StateManager(self.base_dir / 'state.json')
        state = state_manager.load()
        
        if not state:
            logger.error("No state found for rollback")
            return False
        
        package_path = Path(state.get('package_path', ''))
        
        if not package_path.exists():
            logger.error(f"Package path not found: {package_path}")
            return False
        
        engine = UpdateEngine(package_path, self.base_dir)
        success = engine.rollback()
        
        if success:
            state_manager.clear()
        
        return success
    
    def _extract_package(self) -> Path:
        """Extract update package to temp directory.
        
        Returns:
            Path to extracted package
            
        Raises:
            BootstrapError: If extraction fails
        """
        if not self.package_file.exists():
            raise BootstrapError(f"Package file not found: {self.package_file}")
        
        logger.info(f"Extracting package: {self.package_file}")
        
        # Clean temp directory
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
        self.temp_dir.mkdir(parents=True)
        
        # Extract
        try:
            with tarfile.open(self.package_file, 'r:gz') as tar:
                tar.extractall(self.temp_dir)
            
            logger.info(f"Package extracted to: {self.temp_dir}")
            return self.temp_dir
            
        except Exception as e:
            raise BootstrapError(f"Failed to extract package: {e}")
    
    def verify_engine(self, engine_path: Path) -> bool:
        """Verify engine integrity using CHECKSUM file.
        
        Args:
            engine_path: Path to engine directory
            
        Returns:
            True if engine is valid, False otherwise
        """
        checksum_file = engine_path / 'CHECKSUM'
        
        if not checksum_file.exists():
            logger.warning(f"No CHECKSUM file found in {engine_path}")
            return True  # Consider valid if no checksum file
        
        logger.info(f"Verifying engine at {engine_path}...")
        
        try:
            with open(checksum_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    parts = line.split(None, 1)
                    if len(parts) != 2:
                        continue
                    
                    expected_checksum, rel_path = parts
                    file_path = engine_path / rel_path
                    
                    if not file_path.exists():
                        logger.error(f"Engine file missing: {rel_path}")
                        return False
                    
                    if not verify_checksum(file_path, expected_checksum):
                        logger.error(f"Engine checksum mismatch: {rel_path}")
                        return False
            
            logger.info("Engine verification passed")
            return True
            
        except Exception as e:
            logger.error(f"Engine verification failed: {e}")
            return False
    
    def get_valid_engine(self) -> Optional[Path]:
        """Get a valid engine, with fallback to previous versions.
        
        Returns:
            Path to valid engine directory, or None if none found
        """
        # Try current engine
        if self.engine_dir.exists():
            if self.verify_engine(self.engine_dir):
                logger.info(f"Current engine is valid: {self.engine_dir}")
                return self.engine_dir
            else:
                logger.warning("Current engine is corrupted")
        
        # Try backup engines
        backup_pattern = self.engine_dir.parent / 'engine_backup_*'
        backup_dirs = sorted(
            [p for p in self.engine_dir.parent.glob('engine_backup_*') if p.is_dir()],
            reverse=True  # Try newest backups first
        )
        
        for backup_dir in backup_dirs:
            logger.info(f"Trying backup engine: {backup_dir}")
            if self.verify_engine(backup_dir):
                logger.info(f"Valid backup engine found: {backup_dir}")
                return backup_dir
        
        logger.error("No valid engine found")
        return None
    
    def _verify_engine_version(self, required_version: str, package_path: Path) -> bool:
        """Verify engine version and upgrade if needed.
        
        Args:
            required_version: Required engine version
            package_path: Path to extracted package
            
        Returns:
            True if version is satisfied
            
        Raises:
            BootstrapError: If version cannot be satisfied
        """
        current_version = ENGINE_VERSION
        
        logger.info(f"Required engine version: {required_version}")
        logger.info(f"Current engine version: {current_version}")
        
        comparison = compare_versions(current_version, required_version)
        
        if comparison >= 0:
            logger.info("Engine version satisfied")
            return True
        
        # Need to upgrade engine
        logger.info("Engine upgrade required")
        
        engine_package = package_path / 'update_engine'
        
        if not engine_package.exists():
            raise BootstrapError(
                f"Engine upgrade required but engine package not found in update. "
                f"Required: {required_version}, Current: {current_version}"
            )
        
        # Verify new engine checksum
        if not self.verify_engine(engine_package):
            logger.error("New engine package is corrupted")
            
            # Try to fallback to a valid engine
            valid_engine = self.get_valid_engine()
            if valid_engine:
                logger.info(f"Falling back to valid engine: {valid_engine}")
                if valid_engine != self.engine_dir:
                    # Restore valid engine
                    if self.engine_dir.exists():
                        shutil.rmtree(self.engine_dir)
                    shutil.copytree(valid_engine, self.engine_dir)
                    logger.info("Valid engine restored")
            
            raise BootstrapError(
                f"Engine package is corrupted and cannot be installed. "
                f"Required: {required_version}, Current: {current_version}"
            )
        
        logger.info("New engine package verification passed")
        
        # Verify engine checksum if checksums.md5 exists
        checksums_file = package_path / 'checksums.md5'
        if checksums_file.exists():
            logger.info("Verifying engine checksums from package...")
            
            with open(checksums_file, 'r') as f:
                checksums = {}
                for line in f:
                    line = line.strip()
                    if line:
                        checksum, filepath = line.split(None, 1)
                        checksums[filepath] = checksum
            
            # Verify engine files
            for engine_file in engine_package.rglob('*.py'):
                rel_path = str(engine_file.relative_to(package_path))
                
                if rel_path in checksums:
                    expected = checksums[rel_path]
                    if not verify_checksum(engine_file, expected):
                        logger.warning(f"Checksum mismatch for {rel_path}, but continuing...")
                        # Don't fail on checksum mismatch, just warn
        
        # Backup current engine
        logger.info("Backing up current engine...")
        backup_dir = self.engine_dir.parent / f'engine_backup_{current_version}'
        if self.engine_dir.exists():
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            shutil.copytree(self.engine_dir, backup_dir)
        
        # Install new engine
        logger.info(f"Installing engine version {required_version}...")
        
        if self.engine_dir.exists():
            shutil.rmtree(self.engine_dir)
        
        shutil.copytree(engine_package, self.engine_dir)
        
        logger.info("Engine upgraded successfully")
        logger.warning("Please restart the bootstrap script to use the new engine")
        
        # Note: In a real implementation, we might want to re-exec with the new engine
        # For now, we'll just return False to indicate a restart is needed
        return False
    
    def _cleanup_temp(self) -> None:
        """Cleanup temporary directory."""
        if self.temp_dir.exists():
            try:
                shutil.rmtree(self.temp_dir)
                logger.info("Temporary files cleaned up")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp directory: {e}")


def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: bootstrap.py <update-package.tar.gz>")
        sys.exit(1)
    
    package_file = Path(sys.argv[1])
    
    bootstrap = Bootstrap(package_file)
    success = bootstrap.run()
    
    if success:
        print("\n✓ Update completed successfully")
        sys.exit(0)
    else:
        print("\n✗ Update failed")
        sys.exit(1)


if __name__ == '__main__':
    main()

