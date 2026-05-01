# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Integration: overview rendering with connectors uses the new algorithm."""

import re
from pathlib import Path

from skim.application.keymap_generator import (
    _get_config,
    _get_input_keymap,
    _resolve_keymap,
)
from skim.application.render import draw_keymap
from skim.data.cli import InputFiles, KeymapGeneratorTargets


# Existing thin sanity test - keep for the public sample.
def test_overview_renders_with_connectors_for_layer_trigger_keymap(tmp_path):
    """Sanity: rendering an overview with show_layer_indicators ON produces SVG with paths."""
    sample = Path("samples/keymaps/vial-sample.vil")
    config = _get_config(None, keymap_for_defaults=sample)
    new_style = config.output.style.model_copy(update={"show_layer_indicators": True})
    new_output = config.output.model_copy(update={"style": new_style})
    cfg = config.model_copy(update={"output": new_output})

    inputs = InputFiles(keymap=sample)
    keymap = _resolve_keymap(cfg, _get_input_keymap(inputs, cfg))
    drawings = draw_keymap(cfg, keymap, KeymapGeneratorTargets(overview=True))

    overview = drawings["keymap-overview"]
    out = tmp_path / "overview.svg"
    overview.save_svg(str(out))
    content = out.read_text()
    # Expect at least one connector path (dotted SVG path).
    assert re.search(r"<path[^>]+stroke-dasharray", content) is not None


# --- Phase 2 structured-assertion tests against the synthetic fixture ---

FIXTURE_PATH = Path("tests/integration/fixtures/connector-routing-coverage.vil")

# Connector dashed-stroke pattern. The dot length is fixed at 0.1 SVG
# units; the gap length is doc-width-proportional (currently
# ``12.25 / 1600 * doc_width``). Match the dot literally and allow any
# numeric gap so the regex doesn't depend on the exact ratio.
_CONNECTOR_DASH_PATTERN = r"stroke-dasharray=\"0\.1 [\d.]+\""


def _render_fixture(tmp_path: Path) -> str:
    """Render the synthetic coverage fixture and return the SVG text."""
    config = _get_config(None, keymap_for_defaults=FIXTURE_PATH)
    new_style = config.output.style.model_copy(
        update={"show_layer_indicators": True, "show_layer_connectors": True}
    )
    new_output = config.output.model_copy(update={"style": new_style})
    cfg = config.model_copy(update={"output": new_output})

    inputs = InputFiles(keymap=FIXTURE_PATH)
    keymap = _resolve_keymap(cfg, _get_input_keymap(inputs, cfg))
    drawings = draw_keymap(cfg, keymap, KeymapGeneratorTargets(overview=True))

    overview = drawings["keymap-overview"]
    out = tmp_path / "overview.svg"
    overview.save_svg(str(out))
    return out.read_text()


def test_path_count_matches_baseline(tmp_path):
    """The fixture produces a known number of dashed connector paths.

    Rendering ``connector-routing-coverage.vil`` produces 7 dashed paths.
    The fixture declares 11 layer-switch triggers, but the working-tree
    config only renders 3 layers and has ``double_south=False``, so
    triggers targeting out-of-range layers and triggers parked at the
    non-rendered double-south slot are filtered by the orchestrator.
    This locks the path count against accidental routing changes that
    drop or add paths.
    """
    content = _render_fixture(tmp_path)
    paths = re.findall(rf"<path[^>]+{_CONNECTOR_DASH_PATTERN}", content)
    EXPECTED_PATH_COUNT = 7
    assert len(paths) == EXPECTED_PATH_COUNT


def test_each_path_has_a_real_target_color(tmp_path):
    """Connector strokes should match a real layer color, not the fallback gray."""
    content = _render_fixture(tmp_path)
    # Capture the stroke="..." attr for each path that has stroke-dasharray.
    pattern = rf"<path[^>]+stroke=\"([^\"]+)\"[^>]+{_CONNECTOR_DASH_PATTERN}"
    colors = re.findall(pattern, content)
    assert len(colors) > 0
    for color in colors:
        # Hex codes; never the gray fallback (which would mean the
        # qmk_index_to_position chain failed for that target_layer).
        assert color.startswith("#"), f"Stroke color {color!r} is not a hex code"
        assert color != "#808080", (
            "Connector fell back to default gray; check qmk_index_to_position"
        )


def test_no_path_coordinate_escapes_canvas_bounds(tmp_path):
    """Every connector path's coordinates should sit within the canvas."""
    content = _render_fixture(tmp_path)
    # The natural canvas is the SVG ``viewBox`` (the displayed
    # ``width``/``height`` attributes carry the request-time render
    # size, which can scale the natural coordinates down).
    vb_match = re.search(r"<svg[^>]+viewBox=\"0 0 ([\d.]+) ([\d.]+)\"", content)
    assert vb_match, "Could not parse SVG viewBox"
    canvas_w = float(vb_match.group(1))
    canvas_h = float(vb_match.group(2))

    path_ds = re.findall(
        rf"<path[^>]+d=\"([^\"]+)\"[^>]+{_CONNECTOR_DASH_PATTERN}",
        content,
    )
    for d in path_ds:
        coords = re.findall(r"(-?\d+\.?\d*)", d)
        for x_str, y_str in zip(coords[0::2], coords[1::2], strict=False):
            x, y = float(x_str), float(y_str)
            assert 0 <= x <= canvas_w, f"Path X={x} escapes canvas width {canvas_w}"
            assert 0 <= y <= canvas_h, f"Path Y={y} escapes canvas height {canvas_h}"


def test_s_plus_ds_path_has_right_down_right_geometry(tmp_path):
    """The S+DS double-trigger in the fixture must produce a path with at
    least four line segments (M + 4+ Ls), reflecting RIGHT-DOWN-RIGHT-LEFT
    geometry.

    A normal escape path has 3 line segments (M start, L east, L east2,
    L drop); the S+DS path has at least one extra L from the
    RIGHT->DOWN->RIGHT->LEFT redirect that brings the dotted line into
    the indicator's left edge.
    """
    content = _render_fixture(tmp_path)
    path_ds = re.findall(
        rf"<path[^>]+d=\"([^\"]+)\"[^>]+{_CONNECTOR_DASH_PATTERN}",
        content,
    )

    # Count coord pairs per path: an "M x,y L x,y L x,y..." path has
    # one pair per command. A normal path has 4 pairs (M + 3 Ls); the
    # S+DS path has 5+ pairs (M + 4+ Ls).
    def num_segments(d: str) -> int:
        return len(re.findall(r"-?\d+\.?\d*", d)) // 2 - 1

    s_ds_paths = [d for d in path_ds if num_segments(d) >= 4]
    assert len(s_ds_paths) >= 1, (
        "No path matched the S+DS RIGHT-DOWN-RIGHT geometry signature "
        "(expected at least one path with 4+ line segments)"
    )


def test_extra_right_padding_grows_canvas_meaningfully(tmp_path):
    """Canvas width must be wide enough to accommodate the routing columns
    plus the keymap-spacing-long final LEFT segment.

    Lower bound: more than the bare cluster-area width (caught the Phase 1
    over-allocation regression). The exact value depends on cols_used and
    keymap_spacing; we just check the routing area is meaningful.
    """
    content = _render_fixture(tmp_path)
    # Read the natural canvas from the ``viewBox`` — the displayed
    # ``width`` attribute carries the request-time render size and is
    # capped at ``config.output.layout.width``, which would defeat the
    # check.
    vb_match = re.search(r"<svg[^>]+viewBox=\"0 0 ([\d.]+) ", content)
    assert vb_match
    canvas_w = float(vb_match.group(1))
    # Calibrated from real render: canvas_w ~ 1829.67 at implementation.
    # Use a value just below to alarm if the routing area shrinks
    # unexpectedly while still tolerating minor layout drift.
    MIN_CANVAS_WIDTH = 1700.0
    assert canvas_w >= MIN_CANVAS_WIDTH, (
        f"Canvas width {canvas_w} is below the expected minimum {MIN_CANVAS_WIDTH} - "
        f"routing area may have been over-shrunk."
    )
