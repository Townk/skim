# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Pytest configuration for the rendering snapshot tests.

Adds ``--update-snapshots`` so the SVG fixtures under
``tests/snapshot/fixtures/`` can be regenerated in one shot when
something changes intentionally::

    uv run pytest tests/snapshot/ --update-snapshots

Without the flag the tests compare each rendered SVG byte-for-byte
to its checked-in fixture, locking the legacy / migrated rendering
behaviour against silent drift.
"""

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-snapshots",
        action="store_true",
        default=False,
        help="Regenerate snapshot fixtures instead of comparing against them.",
    )


@pytest.fixture
def update_snapshots(request: pytest.FixtureRequest) -> bool:
    """Whether to overwrite the on-disk fixtures rather than compare to them."""
    return bool(request.config.getoption("--update-snapshots"))
