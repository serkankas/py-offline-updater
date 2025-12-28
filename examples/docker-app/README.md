# Docker Application Update Example

This example demonstrates updating a Docker-based application with:
- Docker Compose down/up
- Docker image loading
- Configuration file merge
- Health checks

## Package Contents

```
update/
├── manifest.yml
├── docker/
│   └── myapp-v2.0.0.tar
└── files/
    ├── docker-compose.yml
    └── .env
```

## Build Package

```bash
./scripts/build_package.sh \
  --manifest examples/docker-app/manifest.yml \
  --docker examples/docker-app/docker/ \
  --files examples/docker-app/files/ \
  --output docker-app-update.tar.gz
```

## Apply Update

```bash
update-bootstrap docker-app-update.tar.gz
```

