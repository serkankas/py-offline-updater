# CLAUDE.md — py-offline-updater

Offline update framework for RCU3 devices. Lives at `/app/app/update/` on
the target, runs as a systemd-managed FastAPI service on port 8123.

## What this repo contains

```
src/
  bootstrap.py              # Entry point — extracts package, runs engine
  update_engine/            # GENERIC manifest-driven engine
    engine.py               # actions/pre_checks/post_checks/cleanup loop
    actions.py              # file_copy/sync/merge, command, docker_*, backup
    checks.py, backup.py, state.py
  update_service/           # FastAPI web UI (port 8123)
scripts/
  rcu3_update/              # RCU3-specific orchestration (legacy CLI path)
    update_batch.py         # CLI: --include-docker/--include-service-backend/...
    update_operations.py    # docker_update, service_backend_update, etc.
    full_system_update.py   # Orchestrator (deprecating in favor of manifest)
    docker_utils.py, systemd_utils.py
    watchdog_keeper.py      # WatchdogKeeper class (thread-based, kept for CLI)
    safe_reboot.py
rcu3_package/               # The shipping update package — manifest + files
  manifest.yml              # Engine input
  files/
    lib/                    # NEW: shared helpers for manifest steps
    config/                 # NEW: target system configs (journald, daemon.json)
    migrations/             # NEW: one-shot idempotent system hardening
    steps/                  # NEW: per-update lifecycle steps
    rcu3_update/            # Mirror of scripts/rcu3_update/ (still imported)
    docker/, service-backend/, updater/, wheels/, run_update.py
examples/                   # Test packages (simple-test, log-stream-test, batch3b1-test)
```

## Two parallel codepaths (as of May 2026 refactor)

**Legacy CLI** — `scripts/rcu3_update/update_batch.py --include-docker ...`
- Hard-coded steps inside `update_docker()`, `update_service_backend()`,
  `update_updater()` in `update_operations.py` / `full_system_update.py`.
- WatchdogKeeper is a thread in the same process as the orchestrator.
- Still works; preserved for manual operator use.

**Manifest-driven (new, in progress)** — `bootstrap.py` → engine → action list
- Each update phase is its own `type: command` action calling a script in
  `rcu3_package/files/steps/`.
- Idempotent system hardening lives in `rcu3_package/files/migrations/`.
- Watchdog runs as a detached subprocess (see `lib/watchdog_daemon.py`),
  spawned by `010_watchdog_start.py`, killed by `999_watchdog_stop.py`.

## Hard constraints on the target device

- **No RTC.** Wall clock can be 1970 at boot, can jump backwards mid-update.
  Never use timestamps for decisions (ordering, age, idempotency). Use
  monotonic clocks for delays and counters for ordering.
- **`/var/log/` is tmpfs.** Logs eat RAM, not disk. Journald is capped via
  migration 001 (Storage=volatile, RuntimeMaxUse=10M).
- **Hardware watchdog at `/dev/watchdog`.** Service Backend owns the kick
  loop normally. When SB is stopped/restarted by an update, our watchdog
  daemon must be running first.
- **`restart=always` on every compose container.** A `systemctl restart
  docker.service` brings them back automatically (used by migration 003).

## Idempotency model

Two layers, both check before doing anything mutative:

1. **Persistent ledger** at `/app/app/setup-state/applied_migrations.json`.
   - Migrations record themselves here after success; re-runs skip.
   - Step backups go under `/app/app/setup-state/step-backups/<step_id>/<NNNN>/`.
   - Counter-based, RTC-independent.
2. **Defensive `already_in_target_state()`** check inside each migration.
   - Reads real system state (config files, systemctl status) and compares
     against the target. If equal, mark ledger and skip — even if the
     ledger was missing.

## Log discipline (May 2026)

- **Helpers are silent on success.** `update_operations.py`,
  `full_system_update.py`, `docker_utils.py`, `systemd_utils.py`,
  `watchdog_keeper.py` only emit `logger.error()` on failures. All
  `logger.info`/`logger.warning` calls were stripped (AST-based,
  29 `pass` placeholders left in emptied branches).
- **Step scripts emit ~3 lines per step.** Status snapshot →
  optional context line → result. Errors get a full block.
- Target total for a 17-step update: ~67 lines stdout. Earlier
  baseline was ~370 lines, mostly noise.

## Engine — DO NOT EDIT

`src/update_engine/` is generic, version-pinned via
`required_engine_version` in every manifest. Touching it on the dev side
breaks every device whose engine version doesn't move in lockstep. New
behavior goes into:

- Manifest action scripts (under `files/steps/`)
- Shared helpers (`files/lib/`)

If something genuinely needs an engine change, plan a coordinated
engine self-update first.

## Building an update package

```bash
cd rcu3_package
tar --exclude='__pycache__' --exclude='*.pyc' \
    -czf ../rcu3_update_<tag>.tar.gz manifest.yml files/
```

Same `manifest.yml + files/` layout as `examples/simple-test/`. The
engine extracts to `<base_dir>/tmp/<uuid>/` and runs each action in
that working directory, so `python3 files/steps/X.py` resolves
correctly.

## Standalone smoke tests we keep at repo root

- `device_smoke_test.py` — Batch 1: docker_helpers (image inventory, tag
  alias, cleanup dry-run/execute)
- `device_batch2_check.py` / `device_batch2_apply.py` — Batch 2: 001/002/003
  migrations (read-only check + apply + idempotency)
- `device_batch3a_test.py` — Batch 3a: watchdog daemon start/stop/PID
  lifecycle, including SIGTERM responsiveness check
- `examples/batch3b1-test.tar.gz` — Batch 3b1: full engine roundtrip
  for system state backup + rollback tag alias

Each is single-file, self-contained, copy-paste runnable on the device
without scp.

## Wider system context

This updater is one of four components in Sealink RCU3:
- **RCU_Frontend** (Next.js, port 80 via nginx) — Docker
- **RCU_Backend** (FastAPI + Celery + Redis, port 8000) — Docker
- **RCU_Service** (FastAPI daemon, port 8001) — host bare-metal
- **py-offline-updater** (this repo, port 8123) — host bare-metal
- External VDR at 10.2.1.10:8080

The device this updater installs onto is referenced as
`bytedevkit-imx93` (the lab unit) — ARM64 Yocto Linux, 800×480 kiosk.
