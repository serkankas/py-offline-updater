#!/usr/bin/env python3
"""
RCU3 Update Batch Runner

Unified CLI tool for updating RCU3 components:
- Docker containers (backend, frontend, redis, celery)
- Service Backend (host-level RCU_Service)
- py-offline-updater (self-update)

Usage examples:

    # Docker-only update
    python3 update_batch.py --include-docker \\
        --docker-images /path/to/images/ \\
        --compose-file /path/to/docker-compose.yml

    # Service Backend update
    python3 update_batch.py --include-service-backend \\
        --service-backend-path /path/to/service_backend/

    # Full update
    python3 update_batch.py \\
        --include-docker \\
        --include-service-backend \\
        --include-updater \\
        --docker-images /path/to/images/ \\
        --compose-file /path/to/docker-compose.yml \\
        --service-backend-path /path/to/service_backend/ \\
        --updater-path /path/to/py-offline-updater/

    # Dry run (show plan without executing)
    python3 update_batch.py --include-docker --dry-run \\
        --docker-images /path/to/images/ \\
        --compose-file /path/to/docker-compose.yml
"""

import argparse
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from watchdog_keeper import WatchdogKeeper
from update_operations import (
    run_prechecks,
    docker_update,
    service_backend_update,
    updater_self_update,
    frontend_health_check,
    UpdateError,
    PreCheckError
)

# Version
__version__ = "1.0.0"

# Setup logging
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(verbose: bool = False, log_file: Optional[Path] = None):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO

    handlers = [logging.StreamHandler(sys.stdout)]

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
        handlers=handlers
    )


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        description="RCU3 Update Batch Runner - Unified update tool for RCU3 components",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    # Version
    parser.add_argument(
        "--version", "-V",
        action="version",
        version=f"%(prog)s {__version__}"
    )

    # Component selection
    component_group = parser.add_argument_group("Component Selection")
    component_group.add_argument(
        "--include-docker",
        action="store_true",
        help="Update Docker containers (backend-api, celery-worker, redis, frontend)"
    )
    component_group.add_argument(
        "--include-service-backend",
        action="store_true",
        help="Update Service Backend (host-level RCU_Service)"
    )
    component_group.add_argument(
        "--include-frontend",
        action="store_true",
        help="Run frontend health check (verify system is running)"
    )
    component_group.add_argument(
        "--include-updater",
        action="store_true",
        help="Self-update py-offline-updater"
    )

    # Paths
    path_group = parser.add_argument_group("Paths")
    path_group.add_argument(
        "--docker-images",
        type=Path,
        metavar="PATH",
        help="Directory containing Docker image tar files"
    )
    path_group.add_argument(
        "--compose-file",
        type=Path,
        metavar="PATH",
        help="Path to docker-compose.yml file"
    )
    path_group.add_argument(
        "--service-backend-path",
        type=Path,
        metavar="PATH",
        help="Directory containing Service Backend files"
    )
    path_group.add_argument(
        "--updater-path",
        type=Path,
        metavar="PATH",
        help="Directory containing py-offline-updater files"
    )

    # Options
    options_group = parser.add_argument_group("Options")
    options_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Show update plan without executing"
    )
    options_group.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip backup creation"
    )
    options_group.add_argument(
        "--no-watchdog",
        action="store_true",
        help="Disable watchdog keeper (for development/testing only)"
    )
    options_group.add_argument(
        "--health-check-timeout",
        type=int,
        default=120,
        metavar="SECONDS",
        help="Timeout for health checks (default: 120)"
    )
    options_group.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    options_group.add_argument(
        "--log-file",
        type=Path,
        metavar="PATH",
        help="Write logs to file"
    )

    return parser


def validate_args(args: argparse.Namespace, parser: argparse.ArgumentParser):
    """Validate command line arguments."""
    # Check if any component is selected
    if not any([
        args.include_docker,
        args.include_service_backend,
        args.include_frontend,
        args.include_updater
    ]):
        parser.error("At least one component must be selected (--include-*)")

    # Validate Docker args
    if args.include_docker:
        if not args.docker_images:
            parser.error("--include-docker requires --docker-images")
        if not args.compose_file:
            parser.error("--include-docker requires --compose-file")
        if not args.docker_images.exists():
            parser.error(f"Docker images path not found: {args.docker_images}")
        if not args.compose_file.exists():
            parser.error(f"Compose file not found: {args.compose_file}")

    # Validate Service Backend args
    if args.include_service_backend:
        if not args.service_backend_path:
            parser.error("--include-service-backend requires --service-backend-path")
        if not args.service_backend_path.exists():
            parser.error(f"Service backend path not found: {args.service_backend_path}")

    # Validate Updater args
    if args.include_updater:
        if not args.updater_path:
            parser.error("--include-updater requires --updater-path")
        if not args.updater_path.exists():
            parser.error(f"Updater path not found: {args.updater_path}")


def print_plan(args: argparse.Namespace):
    """Print update plan."""
    print("\n" + "=" * 60)
    print("UPDATE PLAN")
    print("=" * 60)

    step = 1

    print(f"\n{step}. Pre-checks")
    print("   - Check disk space")
    print("   - Check memory")
    print("   - Detect updater location")
    step += 1

    print(f"\n{step}. Start WatchdogKeeper")
    print("   - Begin kicking /dev/watchdog every 3s")
    step += 1

    if args.include_docker:
        print(f"\n{step}. Docker Update")
        print(f"   - Source: {args.docker_images}")
        print(f"   - Compose: {args.compose_file}")
        print("   - Steps: backup -> down -> copy -> load -> up -> health check -> kiosk restart")
        step += 1

    if args.include_service_backend:
        print(f"\n{step}. Service Backend Update")
        print(f"   - Source: {args.service_backend_path}")
        print("   - Target: /app/app/service_backend/")
        print("   - Steps: backup -> stop -> sync -> start -> health check")
        step += 1

    if args.include_frontend:
        print(f"\n{step}. Frontend Health Check")
        print("   - Check http://localhost:80/")
        step += 1

    if args.include_updater:
        print(f"\n{step}. py-offline-updater Self-Update")
        print(f"   - Source: {args.updater_path}")
        print("   - Steps: backup -> sync -> restart service")
        print("   - WARNING: Current process may terminate!")
        step += 1

    print(f"\n{step}. Stop WatchdogKeeper")
    print("   - Service Backend resumes watchdog management")

    print("\n" + "=" * 60)

    if not args.no_backup:
        print("Backups will be created before each update.")
    else:
        print("WARNING: Backups are disabled!")

    print("=" * 60 + "\n")


def run_update(args: argparse.Namespace) -> int:
    """
    Execute the update process.

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    logger = logging.getLogger(__name__)

    start_time = datetime.now()

    logger.info("=" * 60)
    logger.info("RCU3 UPDATE BATCH STARTED")
    logger.info(f"Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # Step 1: Pre-checks
    logger.info("\n[Step 1/N] Running pre-checks...")
    try:
        precheck_results = run_prechecks()
        for check, result in precheck_results.items():
            logger.info(f"  {check}: {result.get('message', result)}")
    except PreCheckError as e:
        logger.error(f"Pre-check failed: {e}")
        return 1

    # Create watchdog keeper
    watchdog_keeper = WatchdogKeeper(
        kick_interval=3,
        enabled=not args.no_watchdog
    )

    if args.no_watchdog:
        logger.warning("Watchdog keeper is DISABLED (--no-watchdog)")

    # Step 2: Start watchdog keeper
    logger.info("\n[Step 2/N] Starting WatchdogKeeper...")
    watchdog_keeper.start()

    exit_code = 0

    try:
        current_step = 3

        # Docker Update
        if args.include_docker:
            logger.info(f"\n[Step {current_step}/N] Docker Update...")
            docker_update(
                docker_images_path=args.docker_images,
                compose_file=args.compose_file,
                watchdog_keeper=watchdog_keeper,
                backup_images=not args.no_backup,
                health_check_timeout=args.health_check_timeout
            )
            current_step += 1

        # Service Backend Update
        if args.include_service_backend:
            logger.info(f"\n[Step {current_step}/N] Service Backend Update...")
            service_backend_update(
                backend_source_path=args.service_backend_path,
                watchdog_keeper=watchdog_keeper,
                backup=not args.no_backup,
                health_check_timeout=args.health_check_timeout
            )
            current_step += 1

        # Frontend Health Check
        if args.include_frontend:
            logger.info(f"\n[Step {current_step}/N] Frontend Health Check...")
            healthy, msg = frontend_health_check()
            if healthy:
                logger.info(f"  Frontend: {msg}")
            else:
                logger.warning(f"  Frontend: {msg}")
            current_step += 1

        # py-offline-updater Self-Update (last!)
        if args.include_updater:
            logger.info(f"\n[Step {current_step}/N] py-offline-updater Self-Update...")
            logger.warning("  NOTE: Service will restart after this step!")
            updater_self_update(
                updater_source_path=args.updater_path,
                backup=not args.no_backup,
                health_check_timeout=args.health_check_timeout
            )
            current_step += 1

        logger.info("\n" + "=" * 60)
        logger.info("UPDATE COMPLETED SUCCESSFULLY")
        logger.info("=" * 60)

    except UpdateError as e:
        logger.error(f"\nUpdate failed: {e}")
        exit_code = 1

    except KeyboardInterrupt:
        logger.warning("\nUpdate interrupted by user")
        exit_code = 130

    except Exception as e:
        logger.exception(f"\nUnexpected error: {e}")
        exit_code = 1

    finally:
        # Stop watchdog keeper
        logger.info("\n[Final] Stopping WatchdogKeeper...")
        watchdog_keeper.stop()
        logger.info(f"  Total kicks: {watchdog_keeper.kick_count}")

        end_time = datetime.now()
        duration = end_time - start_time

        logger.info(f"\nDuration: {duration}")
        logger.info(f"Exit code: {exit_code}")

    return exit_code


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    # Setup logging
    setup_logging(verbose=args.verbose, log_file=args.log_file)

    # Validate arguments
    validate_args(args, parser)

    # Dry run - just show plan
    if args.dry_run:
        print_plan(args)
        print("Dry run mode - no changes will be made.")
        return 0

    # Confirm before running
    print_plan(args)

    try:
        confirm = input("Proceed with update? [y/N] ")
        if confirm.lower() not in ['y', 'yes']:
            print("Update cancelled.")
            return 0
    except KeyboardInterrupt:
        print("\nUpdate cancelled.")
        return 0

    # Run update
    return run_update(args)


if __name__ == "__main__":
    sys.exit(main())
