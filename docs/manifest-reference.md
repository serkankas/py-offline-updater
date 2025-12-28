# Manifest Reference

The manifest file (`manifest.yml`) defines the update process. It uses YAML format and includes metadata, checks, actions, rollback configuration, and cleanup settings.

## Structure

```yaml
description: string              # Human-readable update description
date: string                     # Date in YYYY-MM-DD format
required_engine_version: string  # Semantic version (e.g., "1.0.0")

pre_checks: []                   # List of checks before update
actions: []                      # List of actions to perform
post_checks: []                  # List of checks after update
rollback: {}                     # Rollback configuration
cleanup: {}                      # Cleanup configuration
```

## Pre/Post Checks

Checks verify system state before and after the update.

### disk_space

Check available disk space.

```yaml
- type: disk_space
  path: /opt/myapp
  required_mb: 500
```

**Parameters:**
- `path` (string, required): Path to check
- `required_mb` (integer, required): Required space in megabytes

### docker_running

Verify Docker daemon is running.

```yaml
- type: docker_running
```

**Parameters:** None

### file_exists

Check if a file or directory exists.

```yaml
- type: file_exists
  path: /opt/myapp/config.yml
```

**Parameters:**
- `path` (string, required): Path to check

### docker_health

Check Docker container health status.

```yaml
- type: docker_health
  container_name: myapp
```

**Parameters:**
- `container_name` (string): Container name (one of container_name or container_id required)
- `container_id` (string): Container ID

### http_check

Check HTTP endpoint availability.

```yaml
- type: http_check
  url: http://localhost:8080/health
  retries: 5
  delay: 5
  timeout: 10
  expected_status: 200
```

**Parameters:**
- `url` (string, required): URL to check
- `retries` (integer, default: 1): Number of retry attempts
- `delay` (integer, default: 5): Seconds between retries
- `timeout` (integer, default: 10): Request timeout in seconds
- `expected_status` (integer, default: 200): Expected HTTP status code

### service_running

Check if a systemd service is running.

```yaml
- type: service_running
  service_name: nginx
```

**Parameters:**
- `service_name` (string, required): Name of systemd service

## Actions

Actions perform the actual update operations.

### command

Execute a shell command.

```yaml
- name: "Install dependencies"
  type: command
  command: pip3 install -r requirements.txt
  cwd: /opt/myapp
  timeout: 300
  continue_on_error: false
```

**Parameters:**
- `command` (string, required): Shell command to execute
- `cwd` (string, optional): Working directory
- `timeout` (integer, default: 300): Command timeout in seconds
- `continue_on_error` (boolean, default: false): Continue if command fails

### backup

Create a backup of files or directories.

```yaml
- name: "Backup configuration"
  type: backup
  sources:
    - /opt/myapp/config
    - /opt/myapp/.env
  name: custom_backup_name
```

**Parameters:**
- `sources` (list, required): List of paths to backup
- `name` (string, optional): Custom backup name (default: auto-generated)

### restore_backup

Restore from a backup.

```yaml
- name: "Restore configuration"
  type: restore_backup
  backup_name: latest
```

**Parameters:**
- `backup_name` (string, default: "latest"): Name of backup to restore

### docker_compose_down

Stop Docker Compose services.

```yaml
- name: "Stop services"
  type: docker_compose_down
  compose_file: /opt/myapp/docker-compose.yml
  timeout: 60
```

**Parameters:**
- `compose_file` (string, required): Path to docker-compose.yml
- `timeout` (integer, default: 60): Shutdown timeout in seconds

### docker_compose_up

Start Docker Compose services.

```yaml
- name: "Start services"
  type: docker_compose_up
  compose_file: /opt/myapp/docker-compose.yml
  detach: true
  build: false
```

**Parameters:**
- `compose_file` (string, required): Path to docker-compose.yml
- `detach` (boolean, default: true): Run in detached mode
- `build` (boolean, default: false): Build images before starting

### docker_load

Load Docker image from tar file.

```yaml
- name: "Load image"
  type: docker_load
  image_tar: docker/myapp-v2.tar
```

**Parameters:**
- `image_tar` (string, required): Path to image tar file (relative to package)

### docker_prune

Cleanup old Docker images.

```yaml
- name: "Cleanup images"
  type: docker_prune
  all: false
  force: true
```

**Parameters:**
- `all` (boolean, default: false): Remove all unused images
- `force` (boolean, default: true): Force removal without confirmation

### file_copy

Copy a single file with checksum verification.

```yaml
- name: "Update config"
  type: file_copy
  source: files/config.yml
  destination: /opt/myapp/config.yml
  checksum: a1b2c3d4e5f6...
```

**Parameters:**
- `source` (string, required): Source file path (relative to package)
- `destination` (string, required): Destination file path
- `checksum` (string, optional): Expected MD5 checksum

### file_sync

Synchronize directory contents (rsync-like).

```yaml
- name: "Sync files"
  type: file_sync
  source: files/app
  destination: /opt/myapp/app
  mode: overwrite_existing
```

**Parameters:**
- `source` (string, required): Source directory (relative to package)
- `destination` (string, required): Destination directory
- `mode` (string, default: "mirror"): Sync mode
  - `mirror`: Remove destination and copy everything
  - `add_only`: Only add new files, don't overwrite
  - `overwrite_existing`: Overwrite existing files, add new ones

### file_merge

Merge configuration files (for .env files).

```yaml
- name: "Merge environment"
  type: file_merge
  source: files/.env
  destination: /opt/myapp/.env
  strategy: keep_existing
```

**Parameters:**
- `source` (string, required): Source file (relative to package)
- `destination` (string, required): Destination file
- `strategy` (string, default: "keep_existing"): Merge strategy
  - `keep_existing`: Keep existing values, add new keys
  - `overwrite_all`: Source values override destination
  - `merge_keys`: All keys from both, destination takes precedence

## Rollback Configuration

```yaml
rollback:
  enabled: true
  auto_rollback_on_failure: true
  steps:
    - name: "Stop service"
      type: command
      command: systemctl stop myapp
    
    - name: "Restore files"
      type: restore_backup
      backup_name: latest
    
    - name: "Start service"
      type: command
      command: systemctl start myapp
```

**Parameters:**
- `enabled` (boolean, required): Enable rollback support
- `auto_rollback_on_failure` (boolean, default: false): Automatically rollback on failure
- `steps` (list, optional): Custom rollback steps (if not specified, restores latest backup)

## Cleanup Configuration

```yaml
cleanup:
  remove_old_backups: true
  keep_last_n: 3
  remove_temp_files: true
  remove_old_images: true
```

**Parameters:**
- `remove_old_backups` (boolean, default: false): Remove old backups after successful update
- `keep_last_n` (integer, default: 3): Number of backups to keep (0 = keep all)
- `remove_temp_files` (boolean, default: false): Remove temporary files
- `remove_old_images` (boolean, default: false): Prune old Docker images

## Engine Version Requirements

The `required_engine_version` field specifies the minimum engine version needed for this update. If the installed engine is older, the update package must include the new engine in an `update_engine/` directory.

```yaml
required_engine_version: "2.0.0"
```

To include the engine in your package:

```bash
./scripts/build_package.sh \
  --manifest manifest.yml \
  --include-engine \
  --output update.tar.gz
```

## Complete Example

```yaml
description: "Update application to v2.0.0"
date: "2025-01-15"
required_engine_version: "1.0.0"

pre_checks:
  - type: disk_space
    path: /opt/myapp
    required_mb: 500
  
  - type: docker_running
  
  - type: file_exists
    path: /opt/myapp/docker-compose.yml

actions:
  - name: "Backup configuration"
    type: backup
    sources:
      - /opt/myapp/config
      - /opt/myapp/.env
  
  - name: "Stop services"
    type: docker_compose_down
    compose_file: /opt/myapp/docker-compose.yml
    timeout: 30
  
  - name: "Load new image"
    type: docker_load
    image_tar: docker/myapp-v2.tar
  
  - name: "Update config"
    type: file_copy
    source: files/config.yml
    destination: /opt/myapp/config.yml
  
  - name: "Start services"
    type: docker_compose_up
    compose_file: /opt/myapp/docker-compose.yml

post_checks:
  - type: docker_health
    container_name: myapp
  
  - type: http_check
    url: http://localhost:8080/health
    retries: 5
    delay: 5

rollback:
  enabled: true
  auto_rollback_on_failure: true
  steps:
    - type: docker_compose_down
      compose_file: /opt/myapp/docker-compose.yml
    - type: restore_backup
    - type: docker_compose_up
      compose_file: /opt/myapp/docker-compose.yml

cleanup:
  remove_old_backups: true
  keep_last_n: 3
  remove_temp_files: true
  remove_old_images: true
```

## Best Practices

1. **Always use pre-checks** to validate system state before starting
2. **Create backups** before making changes
3. **Enable rollback** for production updates
4. **Use post-checks** to verify the update succeeded
5. **Set appropriate timeouts** for long-running commands
6. **Use checksums** for critical files
7. **Test updates** in a staging environment first
8. **Document updates** with clear descriptions and dates

