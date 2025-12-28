# Full System Update Example

This example demonstrates a comprehensive system update with:
- Multiple service coordination
- System configuration updates
- Multiple backup points
- Complex rollback strategy

## Package Contents

```
update/
├── manifest.yml
├── docker/
│   ├── frontend-v2.tar
│   └── backend-v2.tar
├── files/
│   ├── nginx/
│   │   └── default.conf
│   ├── configs/
│   │   └── app.conf
│   └── scripts/
│       └── post-update.sh
└── update_engine/  (new engine version)
```

## Build Package

```bash
./scripts/build_package.sh \
  --manifest examples/full-system/manifest.yml \
  --docker examples/full-system/docker/ \
  --files examples/full-system/files/ \
  --include-engine \
  --output full-system-update.tar.gz
```

## Apply Update

```bash
update-bootstrap full-system-update.tar.gz
```

