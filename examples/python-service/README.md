# Python Service Update Example

This example demonstrates updating a Python service with:
- Systemd service management
- File synchronization
- Dependency installation
- Service health checks

## Package Contents

```
update/
├── manifest.yml
└── files/
    ├── app/
    │   └── main.py
    └── requirements.txt
```

## Build Package

```bash
./scripts/build_package.sh \
  --manifest examples/python-service/manifest.yml \
  --files examples/python-service/files/ \
  --output python-service-update.tar.gz
```

## Apply Update

```bash
update-bootstrap python-service-update.tar.gz
```

