"""Mutate the ``version`` field in ``pyproject.toml`` for the release flow.

Used by ``just release`` to flip the dev-suffix on and off.

Usage:
    python scripts/release_version.py strip-dev
        Strip the trailing ``.dev`` from the version. Prints the new
        version on stdout.
        Example: ``0.7.3.dev`` → ``0.7.3``

    python scripts/release_version.py bump-patch
        Bump the patch number and append ``.dev``. Prints the new
        version on stdout.
        Example: ``0.7.3`` → ``0.7.4.dev``
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"

_DEV_VERSION_RE = re.compile(r'^version = "(\d+)\.(\d+)\.(\d+)\.dev"', re.MULTILINE)
_RELEASE_VERSION_RE = re.compile(r'^version = "(\d+)\.(\d+)\.(\d+)"', re.MULTILINE)


def strip_dev() -> str:
    """Remove the trailing ``.dev`` from the version field.

    Returns the new (release) version, e.g. ``"0.7.3"``.
    """
    txt = PYPROJECT.read_text()
    m = _DEV_VERSION_RE.search(txt)
    if m is None:
        sys.exit(
            "Expected pyproject.toml version like X.Y.Z.dev; got something "
            "else. Refusing to mutate."
        )
    new_v = f"{m.group(1)}.{m.group(2)}.{m.group(3)}"
    new_txt = _DEV_VERSION_RE.sub(f'version = "{new_v}"', txt, count=1)
    PYPROJECT.write_text(new_txt)
    return new_v


def bump_patch() -> str:
    """Bump the patch number and append ``.dev``.

    Returns the new dev version, e.g. ``"0.7.4.dev"``.
    """
    txt = PYPROJECT.read_text()
    m = _RELEASE_VERSION_RE.search(txt)
    if m is None:
        sys.exit(
            "Expected pyproject.toml version like X.Y.Z (a released "
            "version); got something else. Run strip-dev first."
        )
    major, minor, patch = m.group(1), m.group(2), int(m.group(3))
    new_v = f"{major}.{minor}.{patch + 1}.dev"
    new_txt = _RELEASE_VERSION_RE.sub(f'version = "{new_v}"', txt, count=1)
    PYPROJECT.write_text(new_txt)
    return new_v


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Usage: release_version.py {strip-dev|bump-patch}")
    cmd = sys.argv[1]
    if cmd == "strip-dev":
        print(strip_dev())
    elif cmd == "bump-patch":
        print(bump_patch())
    else:
        sys.exit(f"Unknown command: {cmd!r}")


if __name__ == "__main__":
    main()
