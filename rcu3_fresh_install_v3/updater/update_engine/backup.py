"""Backup management for update engine."""
import shutil
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from .utils import calculate_checksum, verify_checksum


logger = logging.getLogger('update_engine')


class BackupManager:
    """Manages backup creation and restoration."""
    
    def __init__(self, backup_dir: Path):
        """Initialize backup manager.
        
        Args:
            backup_dir: Base directory for backups
        """
        self.backup_dir = backup_dir
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def create_backup(self, sources: List[str], name: Optional[str] = None) -> Path:
        """Create a backup of specified sources.
        
        Args:
            sources: List of file/directory paths to backup
            name: Optional custom backup name
            
        Returns:
            Path to backup directory
            
        Raises:
            FileNotFoundError: If source doesn't exist
        """
        # Generate sequential backup name
        if name is None:
            name = self._get_next_backup_name()
        
        backup_path = self.backup_dir / name
        backup_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Creating backup: {name}")
        
        metadata = {
            'created_at': datetime.now().isoformat(),
            'sources': [],
            'checksums': {}
        }
        
        # Backup each source
        for source in sources:
            source_path = Path(source)
            
            if not source_path.exists():
                raise FileNotFoundError(f"Source not found: {source}")
            
            # Determine destination path
            dest_name = source_path.name
            dest_path = backup_path / dest_name
            
            # Copy file or directory
            if source_path.is_file():
                shutil.copy2(source_path, dest_path)
                checksum = calculate_checksum(dest_path)
                metadata['checksums'][str(dest_path.relative_to(backup_path))] = checksum
                logger.debug(f"Backed up file: {source} -> {dest_path}")
            elif source_path.is_dir():
                shutil.copytree(source_path, dest_path, symlinks=True)
                # Calculate checksums for all files in directory
                for file_path in dest_path.rglob('*'):
                    if file_path.is_file():
                        checksum = calculate_checksum(file_path)
                        rel_path = str(file_path.relative_to(backup_path))
                        metadata['checksums'][rel_path] = checksum
                logger.debug(f"Backed up directory: {source} -> {dest_path}")
            
            metadata['sources'].append({
                'original_path': str(source_path.absolute()),
                'backup_path': dest_name,
                'type': 'file' if source_path.is_file() else 'directory'
            })
        
        # Write metadata
        metadata_path = backup_path / 'metadata.json'
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Calculate and write directory checksum
        logger.info("Calculating backup directory checksum...")
        checksum_data = []
        for file_path in sorted(backup_path.rglob('*')):
            if file_path.is_file() and file_path.name not in ['CHECKSUM', 'metadata.json']:
                checksum = calculate_checksum(file_path)
                rel_path = str(file_path.relative_to(backup_path))
                checksum_data.append(f"{checksum}  {rel_path}")
        
        checksum_file = backup_path / 'CHECKSUM'
        with open(checksum_file, 'w') as f:
            f.write('\n'.join(checksum_data))
        
        logger.info(f"Backup checksum file created with {len(checksum_data)} entries")
        
        # Update "latest" symlink
        latest_link = self.backup_dir / 'latest'
        if latest_link.exists() or latest_link.is_symlink():
            latest_link.unlink()
        latest_link.symlink_to(name)
        
        logger.info(f"Backup created successfully: {backup_path}")
        return backup_path
    
    def restore_backup(self, backup_name: str = 'latest', verify: bool = True) -> bool:
        """Restore from a backup.
        
        Args:
            backup_name: Name of backup to restore (default: 'latest')
            verify: Whether to verify checksums before restoring
            
        Returns:
            True if restore successful
            
        Raises:
            FileNotFoundError: If backup doesn't exist
            ValueError: If checksum verification fails
        """
        backup_path = self.backup_dir / backup_name
        
        # Resolve symlink if necessary
        if backup_path.is_symlink():
            backup_path = backup_path.resolve()
        
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup not found: {backup_name}")
        
        logger.info(f"Restoring backup: {backup_path.name}")
        
        # Load metadata
        metadata_path = backup_path / 'metadata.json'
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        # Verify checksums if requested
        if verify:
            logger.info("Verifying backup checksums...")
            for rel_path, expected_checksum in metadata['checksums'].items():
                file_path = backup_path / rel_path
                if not verify_checksum(file_path, expected_checksum):
                    raise ValueError(f"Checksum verification failed for: {rel_path}")
            logger.info("Checksum verification passed")
        
        # Restore each source
        for source_info in metadata['sources']:
            original_path = Path(source_info['original_path'])
            backup_item = backup_path / source_info['backup_path']
            
            # Remove existing file/directory
            if original_path.exists():
                if original_path.is_file():
                    original_path.unlink()
                elif original_path.is_dir():
                    shutil.rmtree(original_path)
            
            # Ensure parent directory exists
            original_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Restore
            if source_info['type'] == 'file':
                shutil.copy2(backup_item, original_path)
                logger.debug(f"Restored file: {original_path}")
            else:
                shutil.copytree(backup_item, original_path, symlinks=True)
                logger.debug(f"Restored directory: {original_path}")
        
        logger.info("Backup restored successfully")
        return True
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """List all available backups.
        
        Returns:
            List of backup information dictionaries
        """
        backups = []
        
        for backup_path in sorted(self.backup_dir.iterdir()):
            if backup_path.is_dir() and not backup_path.is_symlink():
                metadata_path = backup_path / 'metadata.json'
                if metadata_path.exists():
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                    
                    backups.append({
                        'name': backup_path.name,
                        'path': str(backup_path),
                        'created_at': metadata.get('created_at'),
                        'sources': metadata.get('sources', [])
                    })
        
        return backups
    
    def cleanup_old_backups(self, keep_last_n: int = 3) -> None:
        """Remove old backups, keeping only the most recent N.
        
        Args:
            keep_last_n: Number of recent backups to keep (0 = keep all)
        """
        if keep_last_n == 0:
            logger.info("Backup cleanup disabled (keep_last_n=0)")
            return
        
        backups = self.list_backups()
        
        if len(backups) <= keep_last_n:
            logger.info(f"No backups to clean up ({len(backups)} <= {keep_last_n})")
            return
        
        # Sort by creation date
        backups.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        # Remove old backups
        for backup in backups[keep_last_n:]:
            backup_path = Path(backup['path'])
            logger.info(f"Removing old backup: {backup['name']}")
            shutil.rmtree(backup_path)
    
    def _get_next_backup_name(self) -> str:
        """Generate next sequential backup name.
        
        Returns:
            Backup name (e.g., 'backup_001')
        """
        existing = [
            d.name for d in self.backup_dir.iterdir()
            if d.is_dir() and d.name.startswith('backup_') and not d.is_symlink()
        ]
        
        if not existing:
            return 'backup_001'
        
        # Extract numbers and find max
        numbers = []
        for name in existing:
            try:
                num = int(name.split('_')[1])
                numbers.append(num)
            except (IndexError, ValueError):
                continue
        
        next_num = max(numbers) + 1 if numbers else 1
        return f'backup_{next_num:03d}'

