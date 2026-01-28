#!/usr/bin/env python3
"""Update version in Python source files.

Called by semantic-release via @semantic-release/exec plugin.

Usage:
    python scripts/update_version.py <version>

Example:
    python scripts/update_version.py 1.2.0
"""

import re
import sys
from pathlib import Path


VERSION_FILES = [
    {
        "path": "src/update_service/api/__init__.py",
        "pattern": r'__version__ = "[^"]*"',
        "replacement": '__version__ = "{version}"',
    },
    {
        "path": "src/update_engine/__init__.py",
        "pattern": r'__version__ = "[^"]*"',
        "replacement": '__version__ = "{version}"',
    },
    {
        "path": "src/update_service/main.py",
        "pattern": r'version="[0-9]+\.[0-9]+\.[0-9]+"',
        "replacement": 'version="{version}"',
    },
    {
        "path": "src/update_service/main.py",
        "pattern": r'"version": "[0-9]+\.[0-9]+\.[0-9]+"',
        "replacement": '"version": "{version}"',
    },
]


def update_version(version: str) -> None:
    """Update version in all configured files."""
    root = Path(__file__).parent.parent

    for file_config in VERSION_FILES:
        file_path = root / file_config["path"]

        if not file_path.exists():
            print(f"Warning: {file_path} not found, skipping")
            continue

        content = file_path.read_text()
        replacement = file_config["replacement"].format(version=version)

        new_content, count = re.subn(
            file_config["pattern"],
            replacement,
            content
        )

        if count > 0:
            file_path.write_text(new_content)
            print(f"Updated {file_config['path']} ({count} replacement(s))")
        else:
            print(f"No matches found in {file_config['path']}")


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <version>")
        sys.exit(1)

    version = sys.argv[1]

    # Remove 'v' prefix if present
    if version.startswith("v"):
        version = version[1:]

    print(f"Updating Python files to version: {version}")
    update_version(version)
    print("Done!")


if __name__ == "__main__":
    main()
