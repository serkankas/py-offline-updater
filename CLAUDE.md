# CLAUDE.md — py-offline-updater

Generic manifest-driven offline update framework. Runs as a systemd-managed
FastAPI service on port 8123 on the target device.

## What this repo contains

```
src/
  bootstrap.py              # Entry point — extracts package, runs engine
  update_engine/            # Generic manifest-driven engine
    engine.py               # actions/pre_checks/post_checks/cleanup loop
    actions.py              # file_copy/sync/merge, command, docker_*, backup
    checks.py, backup.py, state.py
  update_service/           # FastAPI web UI (port 8123)
scripts/
  build_package.sh          # Build a .tar.gz update package from a directory
  build_production_package.sh
  create_test_package.sh
  install.sh                # Install the updater service on a target device
  test_*.sh                 # Various test helpers
  update_version.py
  download_wheels.sh
examples/
  simple-test/              # Minimal example package (manifest + files/)
  log-stream-test/          # SSE log streaming example
  batch3b1-test/            # Engine roundtrip: backup + rollback tag alias
docs/
  manifest-reference.md     # All manifest action types and fields
  installation.md
```

## Update package layout

An update package is a `.tar.gz` with this structure:

```
manifest.yml      # Engine input — version, actions, pre/post checks
files/
  steps/          # Per-update lifecycle scripts (type: command actions)
  lib/            # Shared helpers imported by step scripts
  migrations/     # One-shot idempotent system hardening scripts
  ...             # Any other files referenced in the manifest
```

Build a package:

```bash
tar --exclude='__pycache__' --exclude='*.pyc' \
    -czf my_update_<tag>.tar.gz manifest.yml files/
```

See `examples/simple-test/` for the minimal working layout. The engine
extracts to `<base_dir>/tmp/<uuid>/` and runs each action from that
working directory, so `python3 files/steps/X.py` resolves correctly.

## Engine — DO NOT EDIT

`src/update_engine/` is generic, version-pinned via
`required_engine_version` in every manifest. Touching it breaks every
deployed device whose engine version doesn't move in lockstep. New
behavior goes into:

- Manifest action scripts (under `files/steps/`)
- Shared helpers (`files/lib/`)

If something genuinely needs an engine change, coordinate an
engine self-update first.

## Idempotency model

Two layers, both check before doing anything mutative:

1. **Persistent ledger** at `<base_dir>/setup-state/applied_migrations.json`.
   - Migrations record themselves here after success; re-runs skip.
   - Step backups go under `<base_dir>/setup-state/step-backups/<step_id>/<NNNN>/`.
   - Counter-based, clock-independent.
2. **Defensive `already_in_target_state()`** inside each migration.
   - Reads real system state and compares against target. If equal, marks
     ledger and skips — even if the ledger was missing.

## Log discipline

- **Step scripts emit ~3 lines per step:** status snapshot → optional
  context line → result. Errors get a full block.
- **Helpers are silent on success** — only emit on error.
