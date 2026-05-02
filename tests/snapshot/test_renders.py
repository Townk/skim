# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Snapshot tests for the SVG render pipeline.

Each case runs the keymap generator end-to-end against a sample
keymap and compares every produced SVG byte-for-byte to a
checked-in fixture under ``tests/snapshot/fixtures/<case>/``.
Regenerate the fixtures via ``pytest tests/snapshot/
--update-snapshots`` whenever an intentional rendering change lands;
the resulting fixture diff is the visible record of what changed.

System fonts are forced (``--use-system-fonts``) for fixtures so the
``@font-face`` base64 blob doesn't bloat the checked-in files —
geometry and structure stay identical, only the font reference
changes (``font-family="Roboto, sans-serif"`` instead of an
embedded font + ``font-family="Finger-Key-Label"``).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from skim.application.keymap_generator import (
    _get_config,
    _get_input_keymap,
    _resolve_keymap,
)
from skim.application.loaders import load_keycode_mappings
from skim.application.render import draw_keymap
from skim.data.cli import InputFiles, KeymapGeneratorTargets

FIXTURES_ROOT = Path(__file__).parent / "fixtures"
SAMPLES_ROOT = Path("samples/keymaps")


@dataclass(frozen=True, slots=True)
class _Case:
    """One snapshot case.

    ``name`` is the on-disk fixture directory name; ``keymap`` is
    the path to the source keymap; ``targets`` returns the
    :class:`KeymapGeneratorTargets` to drive the render. Using a
    factory keeps the parametrize line legible — instances are
    immutable, but a new one is produced per test invocation so
    state never leaks between runs.
    """

    name: str
    keymap: Path
    targets: Callable[[], KeymapGeneratorTargets]


CASES: list[_Case] = [
    _Case(
        name="vial-sample-all",
        keymap=SAMPLES_ROOT / "vial-sample.vil",
        targets=lambda: KeymapGeneratorTargets.from_args(("all",)),
    ),
    _Case(
        name="vial-sample-special-keys",
        keymap=SAMPLES_ROOT / "vial-sample.vil",
        targets=lambda: KeymapGeneratorTargets(special_keys=True),
    ),
    _Case(
        name="colemakdhm-all",
        keymap=SAMPLES_ROOT / "SvalCOLEMAKDHM.vil",
        targets=lambda: KeymapGeneratorTargets.from_args(("all",)),
    ),
]


def _render_case(case: _Case) -> dict[str, str]:
    """Run the case end-to-end and return ``{image_name: svg_text}``."""
    config = _get_config(None, use_system_fonts=True, keymap_for_defaults=case.keymap)
    inputs = InputFiles(keymap=case.keymap)
    raw_keymap = _get_input_keymap(inputs, config)
    keymap = _resolve_keymap(config, raw_keymap)
    keycode_mappings = load_keycode_mappings(config.keycodes)
    drawings = draw_keymap(
        config,
        keymap,
        case.targets(),
        raw_keymap=raw_keymap,
        keycode_mappings=keycode_mappings,
    )
    return {name: str(drawing.as_svg()) for name, drawing in drawings.items()}


def _write_fixture_dir(fixture_dir: Path, rendered: dict[str, str]) -> None:
    """Replace the contents of ``fixture_dir`` with the freshly-rendered SVGs.

    Removes any stale files left from a previous render before
    writing the new set so no orphan fixtures linger after a case
    drops an image (e.g. a layer being removed from a sample
    keymap).
    """
    fixture_dir.mkdir(parents=True, exist_ok=True)
    for stale in fixture_dir.iterdir():
        if stale.is_file() and stale.suffix == ".svg":
            stale.unlink()
    for name, svg in rendered.items():
        (fixture_dir / f"{name}.svg").write_text(svg)


def _compare_fixture_dir(fixture_dir: Path, rendered: dict[str, str]) -> None:
    """Assert the rendered set matches the fixtures under ``fixture_dir``.

    Mismatches are reported per file with a hint pointing at the
    update flag, so the failure message tells the reader exactly
    what to do next.
    """
    assert fixture_dir.is_dir(), (
        f"No fixtures for case at {fixture_dir!s}. Run "
        f"`pytest tests/snapshot/ --update-snapshots` to seed them."
    )
    expected_names = {p.stem for p in fixture_dir.iterdir() if p.suffix == ".svg"}
    actual_names = set(rendered.keys())
    missing = expected_names - actual_names
    extra = actual_names - expected_names
    assert not missing, (
        f"Fixture {fixture_dir.name} expects images that the renderer "
        f"didn't produce: {sorted(missing)}. If this is intentional, "
        f"regenerate with --update-snapshots."
    )
    assert not extra, (
        f"Renderer produced images not in fixture {fixture_dir.name}: "
        f"{sorted(extra)}. If this is intentional, regenerate with "
        f"--update-snapshots."
    )
    for name, svg in rendered.items():
        expected = (fixture_dir / f"{name}.svg").read_text()
        assert svg == expected, (
            f"Snapshot mismatch in {fixture_dir.name}/{name}.svg. "
            f"If this change is intentional, regenerate with "
            f"`pytest tests/snapshot/ --update-snapshots`."
        )


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_render_snapshot(case: _Case, update_snapshots: bool) -> None:
    rendered = _render_case(case)
    fixture_dir = FIXTURES_ROOT / case.name
    if update_snapshots:
        _write_fixture_dir(fixture_dir, rendered)
    else:
        _compare_fixture_dir(fixture_dir, rendered)
