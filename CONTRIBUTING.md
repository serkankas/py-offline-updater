# Contributing to py-offline-updater

Thank you for considering contributing to py-offline-updater!

## Development Setup

1. Clone the repository:
```bash
git clone https://github.com/serkankas/py-offline-updater.git
cd py-offline-updater
```

2. Install dependencies:
```bash
pip3 install -r requirements.txt
pip3 install -r src/update_service/requirements.txt
npm install
```

3. Run tests (when implemented):
```bash
pytest tests/
```

## Commit Messages

We use [Conventional Commits](https://www.conventionalcommits.org/) for semantic versioning:

- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `chore:` - Maintenance tasks
- `refactor:` - Code refactoring
- `test:` - Adding tests

Examples:
```
feat: add file_merge action for .env files
fix: correct checksum verification in backup restore
docs: update manifest reference with new examples
```

## Adding New Actions

1. Add action implementation to `src/update_engine/actions.py`
2. Update `execute_action()` dispatcher
3. Add documentation to `docs/manifest-reference.md`
4. Create example in `examples/`

## Adding New Checks

1. Add check implementation to `src/update_engine/checks.py`
2. Update `execute_check()` dispatcher
3. Add documentation to `docs/manifest-reference.md`
4. Add examples to existing manifests

## Code Style

- Follow PEP 8 for Python code
- Use type hints where appropriate
- Add docstrings to all functions
- Keep functions focused and small

## Testing

Before submitting a PR:

1. Test your changes locally
2. Ensure all existing tests pass
3. Add tests for new features
4. Update documentation

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/amazing-feature`)
3. Commit your changes with conventional commits
4. Push to your fork
5. Open a Pull Request

## Questions?

Open an issue for discussion!
