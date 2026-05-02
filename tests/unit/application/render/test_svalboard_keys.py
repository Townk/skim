# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for :mod:`skim.application.render.svalboard_keys`.

Verifies the composable's public contract — reported size, metrics,
and the SVG elements it emits at ``draw_at``. Cluster-level
end-to-end equivalence vs. the legacy renderer is covered by the
snapshot tests under ``tests/snapshot/`` once these composables are
wired into the cluster code.
"""

from __future__ import annotations

import re

import drawsvg as draw
import pytest

from skim.application.render.primitives import CompassDirection, Point, Size
from skim.application.render.render_context import RenderContext, using_render_context
from skim.application.render.svalboard_keys import (
    CenterKey,
    DirectionalKey,
    DoubleSouthKey,
    SvalboardKeyMetrics,
)
from skim.data import SkimConfig, SvalboardKeymap
from skim.domain import KeyboardSide, KeyDirection


@pytest.fixture
def ctx() -> RenderContext:
    """Default :class:`RenderContext` — empty keymap, default config."""
    return RenderContext.build(SkimConfig(), SvalboardKeymap(layers={}))


def _draw(component, origin: Point) -> draw.Drawing:
    """Run ``component.draw_at`` on a fresh tiny drawing and return it."""
    d = draw.Drawing(200, 200)
    component.draw_at(d, origin)
    return d


# ---------------------------------------------------------------------------
# Test helpers — small constructors that fill in defaults so tests only
# spell the parameters under test. Default ``side`` is RIGHT (the
# reference orientation the composables describe natively); flip to
# ``KeyboardSide.LEFT`` when checking the mirrored metrics.
# ---------------------------------------------------------------------------


def _center_key(
    *,
    side: KeyboardSide = KeyboardSide.RIGHT,
    width: float = 80.0,
    label_text: str = "A",
    fill_color: str = "#abcdef",
    label_color: str = "#012345",
):
    return CenterKey(
        side=side,
        width=width,
        label_text=label_text,
        fill_color=fill_color,
        label_color=label_color,
    )


def _directional_key(
    *,
    direction: KeyDirection,
    side: KeyboardSide = KeyboardSide.RIGHT,
    width: float = 80.0,
    label_text: str = "A",
    fill_color: str = "#abcdef",
    accent_color: str = "#012345",
    label_color: str = "#ffffff",
):
    return DirectionalKey(
        side=side,
        direction=direction,
        width=width,
        label_text=label_text,
        fill_color=fill_color,
        accent_color=accent_color,
        label_color=label_color,
    )


def _double_south_key(
    *,
    side: KeyboardSide = KeyboardSide.RIGHT,
    width: float = 80.0,
    label_text: str = "A",
    fill_color: str = "#abcdef",
    accent_color: str = "#012345",
    label_color: str = "#ffffff",
):
    return DoubleSouthKey(
        side=side,
        width=width,
        label_text=label_text,
        fill_color=fill_color,
        accent_color=accent_color,
        label_color=label_color,
    )


# ---------------------------------------------------------------------------
# CenterKey
# ---------------------------------------------------------------------------


class TestCenterKey:
    """Filled circle + centred label, with diagonal-toward-thumb indicator."""

    def test_reported_size_is_square(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = _center_key()
        assert key.size == Size(80.0, 80.0)

    def test_metrics_typed_subclass(self, ctx: RenderContext):
        """:func:`CenterKey` returns a :class:`MetricsComponent` whose
        ``metrics`` field is the typed :class:`SvalboardKeyMetrics`."""
        with using_render_context(ctx):
            key = _center_key()
        assert isinstance(key.metrics, SvalboardKeyMetrics)

    def test_right_side_indicator_is_south_west(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = _center_key(side=KeyboardSide.RIGHT)
        assert key.metrics.indicator_direction is CompassDirection.SOUTH_WEST

    def test_left_side_indicator_is_south_east(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = _center_key(side=KeyboardSide.LEFT)
        assert key.metrics.indicator_direction is CompassDirection.SOUTH_EAST

    def test_right_side_anchor_lands_on_circle_perimeter_in_sw_quadrant(self, ctx: RenderContext):
        """For a circle ``W`` wide centred at ``(W/2, W/2)`` with radius
        ``W/2``, the SW point is ``(W/2 - r·cos45°, W/2 + r·sin45°)``.
        Verifying the math is on the perimeter (distance from centre
        equals ``W/2``) is a tighter check than asserting the exact
        coordinate floats.
        """
        width = 80.0
        with using_render_context(ctx):
            key = _center_key(side=KeyboardSide.RIGHT, width=width)
        anchor = key.metrics.indicator_anchor
        cx = cy = width / 2.0
        r = width / 2.0
        dx = anchor.x - cx
        dy = anchor.y - cy
        assert abs(dx * dx + dy * dy - r * r) < 1e-6  # on perimeter
        assert dx < 0  # left of centre
        assert dy > 0  # below centre

    def test_left_side_anchor_mirrors_right_side(self, ctx: RenderContext):
        """The left-side anchor is the right-side anchor reflected
        across the key's vertical centre — same y, x flipped around
        ``width / 2``."""
        width = 80.0
        with using_render_context(ctx):
            right = _center_key(side=KeyboardSide.RIGHT, width=width)
            left = _center_key(side=KeyboardSide.LEFT, width=width)
        assert left.metrics.indicator_anchor.y == right.metrics.indicator_anchor.y
        assert left.metrics.indicator_anchor.x == width - right.metrics.indicator_anchor.x

    def test_drawing_is_side_invariant(self, ctx: RenderContext):
        """The circle shape is symmetric about its vertical centre, so
        the painted SVG must be byte-identical regardless of side. Side
        only flips the metrics, not the drawing."""
        with using_render_context(ctx):
            right = _center_key(side=KeyboardSide.RIGHT)
            left = _center_key(side=KeyboardSide.LEFT)
        right_svg = str(_draw(right, Point(50.0, 50.0)).as_svg())
        left_svg = str(_draw(left, Point(50.0, 50.0)).as_svg())
        assert right_svg == left_svg

    def test_draw_emits_circle(self, ctx: RenderContext):
        """The circle paints at the cell centre with the expected fill."""
        with using_render_context(ctx):
            key = _center_key()
        d = _draw(key, Point(50.0, 50.0))
        svg = str(d.as_svg())
        # Centre at (50 + 40, 50 + 40) = (90, 90); radius 40.
        assert 'cx="90.0"' in svg
        assert 'cy="90.0"' in svg
        assert 'r="40.0"' in svg
        assert 'fill="#abcdef"' in svg

    def test_draw_emits_label_text(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = _center_key(label_text="ABC")
        d = _draw(key, Point(0.0, 0.0))
        svg = str(d.as_svg())
        assert "ABC" in svg
        assert 'fill="#012345"' in svg

    def test_long_label_shrinks_via_richtext_relaxation(self, ctx: RenderContext):
        """The ``max_width`` budget passed into RichText is
        ``width * 0.7``, so a label naturally wider than that should
        come out with the painted ``font-size`` smaller than the
        nominal ``width * 0.6`` ceiling.
        """
        with using_render_context(ctx):
            key = _center_key(width=40.0, label_text="MMMMMMMMMM")
        d = _draw(key, Point(0.0, 0.0))
        svg = str(d.as_svg())
        sizes = [float(m) for m in re.findall(r'font-size="([\d.]+)"', svg)]
        # Default ceiling is ``width * 0.6 = 24``; relaxation shrinks
        # below that to fit the budget.
        assert any(0 < s < 24.0 for s in sizes), f"no shrunk font sizes in {sizes!r}"


# ---------------------------------------------------------------------------
# DirectionalKey — N / S / E / W finger-cluster keys (rounded rect + accent bar)
# ---------------------------------------------------------------------------


class TestDirectionalKey:
    """Unified composable for the four directional finger keys."""

    def test_size_is_square(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = _directional_key(direction=KeyDirection.NORTH)
        assert key.size == Size(80.0, 80.0)

    @pytest.mark.parametrize(
        "direction,expected_compass",
        [
            (KeyDirection.NORTH, CompassDirection.NORTH),
            (KeyDirection.EAST, CompassDirection.NORTH),
            (KeyDirection.WEST, CompassDirection.NORTH),
            (KeyDirection.SOUTH, CompassDirection.EAST),
        ],
    )
    def test_right_side_indicator_direction(
        self,
        ctx: RenderContext,
        direction: KeyDirection,
        expected_compass: CompassDirection,
    ):
        """Right-hand reference: N / E / W carry the indicator above; S
        carries it on the outward (east) side."""
        with using_render_context(ctx):
            key = _directional_key(direction=direction, side=KeyboardSide.RIGHT)
        assert key.metrics.indicator_direction is expected_compass

    @pytest.mark.parametrize(
        "direction,expected_compass",
        [
            # N stays N — no horizontal flip on the vertical-axis component.
            (KeyDirection.NORTH, CompassDirection.NORTH),
            (KeyDirection.EAST, CompassDirection.NORTH),
            (KeyDirection.WEST, CompassDirection.NORTH),
            # S flips: outward is now west on the left hand.
            (KeyDirection.SOUTH, CompassDirection.WEST),
        ],
    )
    def test_left_side_indicator_direction_mirrors_right(
        self,
        ctx: RenderContext,
        direction: KeyDirection,
        expected_compass: CompassDirection,
    ):
        with using_render_context(ctx):
            key = _directional_key(direction=direction, side=KeyboardSide.LEFT)
        assert key.metrics.indicator_direction is expected_compass

    @pytest.mark.parametrize(
        "direction,expected_anchor",
        [
            (KeyDirection.NORTH, Point(40.0, 0.0)),
            (KeyDirection.EAST, Point(40.0, 0.0)),
            (KeyDirection.WEST, Point(40.0, 0.0)),
            (KeyDirection.SOUTH, Point(80.0, 40.0)),
        ],
    )
    def test_right_side_indicator_anchor(
        self,
        ctx: RenderContext,
        direction: KeyDirection,
        expected_anchor: Point,
    ):
        """Right-hand reference: N / E / W anchor at the top-edge
        midpoint; S anchors at the right-edge midpoint."""
        with using_render_context(ctx):
            key = _directional_key(direction=direction, side=KeyboardSide.RIGHT)
        assert key.metrics.indicator_anchor == expected_anchor

    @pytest.mark.parametrize(
        "direction",
        [KeyDirection.NORTH, KeyDirection.EAST, KeyDirection.WEST, KeyDirection.SOUTH],
    )
    def test_left_side_anchor_mirrors_right(self, ctx: RenderContext, direction: KeyDirection):
        """Left-side anchor is the right-side anchor reflected across
        the key's vertical centre — same y, x flipped around
        ``width / 2``."""
        width = 80.0
        with using_render_context(ctx):
            right = _directional_key(direction=direction, side=KeyboardSide.RIGHT, width=width)
            left = _directional_key(direction=direction, side=KeyboardSide.LEFT, width=width)
        assert left.metrics.indicator_anchor.y == right.metrics.indicator_anchor.y
        assert left.metrics.indicator_anchor.x == width - right.metrics.indicator_anchor.x

    @pytest.mark.parametrize(
        "direction,expected_bar",
        [
            # NORTH: bar on the south edge (y = top + width - accent_size).
            (KeyDirection.NORTH, ('y="68.0"', 'width="80.0"', 'height="12.0"')),
            # SOUTH: bar on the north edge (y = top).
            (KeyDirection.SOUTH, ('y="0.0"', 'width="80.0"', 'height="12.0"')),
            # EAST: bar on the west edge (x = left).
            (KeyDirection.EAST, ('x="0.0"', 'width="12.0"', 'height="80.0"')),
            # WEST: bar on the east edge (x = left + width - accent_size).
            (KeyDirection.WEST, ('x="68.0"', 'width="12.0"', 'height="80.0"')),
        ],
    )
    def test_accent_bar_on_opposite_edge(
        self,
        ctx: RenderContext,
        direction: KeyDirection,
        expected_bar: tuple[str, str, str],
    ):
        """The accent bar sits on the edge opposite the key's direction.

        Width 80 × accent multiplier 0.15 = bar thickness 12. The
        rendered SVG should contain a rectangle filled with the
        accent colour at the right position. Side-invariant — the
        accent placement is tied to the key's own ``KeyDirection``
        (which is defined relative to the thumb), not the keyboard
        half.
        """
        with using_render_context(ctx):
            key = _directional_key(direction=direction)
        d = _draw(key, Point(0.0, 0.0))
        svg = str(d.as_svg())
        for piece in expected_bar:
            assert piece in svg, f"missing {piece!r} for {direction}"
        assert 'fill="#012345"' in svg

    @pytest.mark.parametrize(
        "direction",
        [KeyDirection.NORTH, KeyDirection.EAST, KeyDirection.WEST, KeyDirection.SOUTH],
    )
    def test_drawing_is_side_invariant(self, ctx: RenderContext, direction: KeyDirection):
        """Shape + accent placement are tied to the key's own direction,
        not the keyboard half. Rendered SVG must be byte-identical
        across sides."""
        with using_render_context(ctx):
            right = _directional_key(direction=direction, side=KeyboardSide.RIGHT)
            left = _directional_key(direction=direction, side=KeyboardSide.LEFT)
        right_svg = str(_draw(right, Point(0.0, 0.0)).as_svg())
        left_svg = str(_draw(left, Point(0.0, 0.0)).as_svg())
        assert right_svg == left_svg


# ---------------------------------------------------------------------------
# DoubleSouthKey — trapezoid + accent bar on top
# ---------------------------------------------------------------------------


class TestDoubleSouthKey:
    """Trapezoid below the south key with an accent bar on top."""

    def test_size_is_square(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = _double_south_key()
        assert key.size == Size(80.0, 80.0)

    def test_right_side_indicator_is_east(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = _double_south_key(side=KeyboardSide.RIGHT)
        assert key.metrics.indicator_direction is CompassDirection.EAST

    def test_left_side_indicator_is_west(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = _double_south_key(side=KeyboardSide.LEFT)
        assert key.metrics.indicator_direction is CompassDirection.WEST

    def test_right_side_anchor_at_right_edge_midpoint(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = _double_south_key(side=KeyboardSide.RIGHT)
        assert key.metrics.indicator_anchor == Point(80.0, 40.0)

    def test_left_side_anchor_at_left_edge_midpoint(self, ctx: RenderContext):
        """Left-side anchor mirrors right-side around the vertical centre."""
        with using_render_context(ctx):
            key = _double_south_key(side=KeyboardSide.LEFT)
        assert key.metrics.indicator_anchor == Point(0.0, 40.0)

    def test_drawing_is_side_invariant(self, ctx: RenderContext):
        """The trapezoid is symmetric about its vertical centre, so the
        painted SVG must be byte-identical regardless of side."""
        with using_render_context(ctx):
            right = _double_south_key(side=KeyboardSide.RIGHT)
            left = _double_south_key(side=KeyboardSide.LEFT)
        right_svg = str(_draw(right, Point(0.0, 0.0)).as_svg())
        left_svg = str(_draw(left, Point(0.0, 0.0)).as_svg())
        assert right_svg == left_svg

    def test_draw_emits_trapezoid_and_accent_bar(self, ctx: RenderContext):
        """The shape SVG should contain a path (the trapezoid) and a
        rectangle filled with the accent colour at the top edge."""
        with using_render_context(ctx):
            key = _double_south_key()
        d = _draw(key, Point(0.0, 0.0))
        svg = str(d.as_svg())
        assert "<path" in svg  # trapezoid
        assert 'fill="#abcdef"' in svg
        # Accent bar — rect at the top edge with the accent colour.
        # ``y="0.0"`` + accent height = ``width * 0.15 = 12``.
        assert 'y="0.0"' in svg
        assert 'height="12.0"' in svg
        assert 'fill="#012345"' in svg

    def test_draw_emits_label_text(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = _double_south_key(label_text="DS")
        d = _draw(key, Point(0.0, 0.0))
        svg = str(d.as_svg())
        assert "DS" in svg
        assert 'fill="#ffffff"' in svg
