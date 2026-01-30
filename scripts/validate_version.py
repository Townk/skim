#!/usr/bin/env python3
# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Validate version format in pyproject.toml.

This script ensures the version in pyproject.toml follows the expected format:
- Development: X.Y.Z.dev (e.g., 0.4.2.dev)
- Release: X.Y.Z (e.g., 0.4.2)

Used as a pre-commit hook to catch version format errors before committing.
"""

import re
import sys
from pathlib import Path


def validate_version() -> int:
    """Validate the version string in pyproject.toml.

    Returns:
        0 if valid, 1 if invalid or error occurred.
    """
    pyproject_path = Path("pyproject.toml")

    if not pyproject_path.exists():
        print("Error: pyproject.toml not found")
        return 1

    content = pyproject_path.read_text()

    # Match version line: version = "X.Y.Z" or version = "X.Y.Z.dev"
    version_match = re.search(r'version\s*=\s*"([^"]+)"', content)

    if not version_match:
        print("Error: Could not find version in pyproject.toml")
        return 1

    version = version_match.group(1)

    # Valid patterns:
    # - Release: X.Y.Z (e.g., 0.4.2, 1.0.0)
    # - Development: X.Y.Z.dev (e.g., 0.4.2.dev)
    # - CI-generated dev: X.Y.Z.devN (e.g., 0.4.2.dev5) - allowed for CI builds
    valid_pattern = re.compile(r"^\d+\.\d+\.\d+(\.dev\d*)?$")

    if not valid_pattern.match(version):
        print(f"Error: Invalid version format: {version}")
        print("Expected format: X.Y.Z or X.Y.Z.dev")
        print("Examples: 0.4.2, 1.0.0, 0.4.2.dev")
        return 1

    # Additional check: .dev versions should not have a number in committed code
    # (CI adds the commit count dynamically)
    dev_with_number = re.compile(r"^\d+\.\d+\.\d+\.dev\d+$")
    if dev_with_number.match(version):
        print(f"Warning: Version '{version}' has a dev number.")
        print("Development versions in source should be 'X.Y.Z.dev' without a number.")
        print("The CI workflow adds the commit count automatically.")
        # This is a warning, not an error - CI may have generated this
        # For strict enforcement, change return 0 to return 1

    print(f"Version format valid: {version}")
    return 0


if __name__ == "__main__":
    sys.exit(validate_version())
