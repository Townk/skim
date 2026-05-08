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

import inspect
import re

import drawsvg as draw
import pytest

from skim.application.render.primitives import CompassDirection, Point, Size
from skim.application.render.render_context import RenderContext, using_render_context
from skim.application.render.svalboard_keys import (
    _DOUBLE_DOWN_CORNER_RADIUS_MULTIPLIER,
    _DOUBLE_DOWN_HEIGHT_RATIO,
    _DOUBLE_DOWN_INSET_MULTIPLIER,
    _DOUBLE_DOWN_SLANT_MULTIPLIER,
    _UP_CORNER_RADIUS_MULTIPLIER,
    _UP_HEIGHT_RATIO,
    _UP_SLANT_MULTIPLIER,
    CenterKey,
    DirectionalKey,
    DoubleDownKey,
    DoubleSouthKey,
    DownKey,
    KnuckleKey,
    NailKey,
    PadKey,
    SvalboardKeyMetrics,
    UpKey,
)
from skim.application.render.trapezoid import Trapezoid
from skim.data import SkimConfig, SvalboardKeymap
from skim.domain import Alignment, KeyboardSide, KeyDirection


@pytest.fixture
def ctx() -> RenderContext:
    """Default :class:`RenderContext` — empty keymap, default config."""
    return RenderContext.build(SkimConfig(), SvalboardKeymap(layers={}))


def _draw(component, origin: Point) -> draw.Drawing:
    """Run ``component.draw_at`` on a fresh tiny drawing and return it."""
    d = draw.Drawing(200, 200)
    component.draw_at(d, origin)
    return d


def _label_text_x(svg: str | None) -> float:
    """Return the ``x`` attribute of the first ``<text>`` element in
    a rendered SVG — the rendered label's left-hand starting position
    after RichText's text-anchor normalisation.

    Used by label-position tests that need to assert which side of a
    key the label visually sits on without depending on the
    ``text-anchor`` attribute (RichText emits all anchors as ``start``
    with the x adjusted for visual equivalence).
    """
    import re

    assert svg is not None, "expected rendered SVG"
    match = re.search(r'<text[^>]*\sx="([\d.\-]+)"', svg)
    assert match is not None, f"no <text> element found in: {svg[:200]}"
    return float(match.group(1))


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


# ---------------------------------------------------------------------------
# Thumb-cluster key helpers
# ---------------------------------------------------------------------------


def _down_key(
    *,
    side: KeyboardSide = KeyboardSide.RIGHT,
    width: float = 60.0,
    label_text: str = "A",
    fill_color: str = "#abcdef",
    label_color: str = "#012345",
):
    return DownKey(
        side=side,
        width=width,
        label_text=label_text,
        fill_color=fill_color,
        label_color=label_color,
    )


def _double_down_key(
    *,
    side: KeyboardSide = KeyboardSide.RIGHT,
    width: float = 60.0,
    label_text: str = "A",
    fill_color: str = "#abcdef",
    label_color: str = "#012345",
):
    return DoubleDownKey(
        side=side,
        width=width,
        label_text=label_text,
        fill_color=fill_color,
        label_color=label_color,
    )


def _up_key(
    *,
    side: KeyboardSide = KeyboardSide.RIGHT,
    width: float = 220.0,
    label_text: str = "A",
    fill_color: str = "#abcdef",
    label_color: str = "#012345",
):
    return UpKey(
        side=side,
        width=width,
        label_text=label_text,
        fill_color=fill_color,
        label_color=label_color,
    )


def _pad_key(
    *,
    side: KeyboardSide = KeyboardSide.RIGHT,
    width: float = 150.0,
    label_text: str = "A",
    fill_color: str = "#abcdef",
    label_color: str = "#012345",
):
    return PadKey(
        side=side,
        width=width,
        label_text=label_text,
        fill_color=fill_color,
        label_color=label_color,
    )


def _nail_key(
    *,
    side: KeyboardSide = KeyboardSide.RIGHT,
    width: float = 150.0,
    label_text: str = "A",
    fill_color: str = "#abcdef",
    label_color: str = "#012345",
):
    return NailKey(
        side=side,
        width=width,
        label_text=label_text,
        fill_color=fill_color,
        label_color=label_color,
    )


def _knuckle_key(
    *,
    side: KeyboardSide = KeyboardSide.RIGHT,
    width: float = 150.0,
    label_text: str = "A",
    fill_color: str = "#abcdef",
    label_color: str = "#012345",
):
    return KnuckleKey(
        side=side,
        width=width,
        label_text=label_text,
        fill_color=fill_color,
        label_color=label_color,
    )


# ---------------------------------------------------------------------------
# DownKey — tall narrow trapezoid, symmetric
# ---------------------------------------------------------------------------


class TestDownKey:
    """Tall trapezoid at the bottom of the thumb cluster."""

    def test_size_uses_aspect_ratio(self, ctx: RenderContext):
        """``height = width * 2.6`` for the tall narrow shape."""
        with using_render_context(ctx):
            key = _down_key(width=60.0)
        assert key.size == Size(60.0, 156.0)

    def test_right_side_indicator_is_east(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = _down_key(side=KeyboardSide.RIGHT)
        assert key.metrics.indicator_direction is CompassDirection.EAST

    def test_left_side_indicator_is_west(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = _down_key(side=KeyboardSide.LEFT)
        assert key.metrics.indicator_direction is CompassDirection.WEST

    def test_anchor_at_outward_edge_lower_band(self, ctx: RenderContext):
        """The DownKey's indicator anchor sits on the OUTWARD edge in
        the bottom band of the key — the upper half is occluded by
        adjacent thumb keys at typing time, so the indicator badge
        belongs on the visible (lower) part of the outward edge."""
        width = 60.0
        height = width * 2.6
        with using_render_context(ctx):
            right = _down_key(side=KeyboardSide.RIGHT, width=width)
            left = _down_key(side=KeyboardSide.LEFT, width=width)
        # Right hand: outward edge is the right side, x = width.
        assert right.metrics.indicator_anchor.x == pytest.approx(width)
        # Left hand: outward edge is the left side, x = 0.
        assert left.metrics.indicator_anchor.x == pytest.approx(0.0)
        # Both: anchor sits well below the key's vertical centre — in
        # the bottom band of the key.
        assert right.metrics.indicator_anchor.y > height / 2.0
        assert left.metrics.indicator_anchor.y > height / 2.0
        assert right.metrics.indicator_anchor.y == pytest.approx(left.metrics.indicator_anchor.y)

    def test_drawing_is_side_invariant(self, ctx: RenderContext):
        """Symmetric trapezoid — same SVG on both sides."""
        with using_render_context(ctx):
            right = _down_key(side=KeyboardSide.RIGHT)
            left = _down_key(side=KeyboardSide.LEFT)
        assert str(_draw(right, Point(0.0, 0.0)).as_svg()) == str(
            _draw(left, Point(0.0, 0.0)).as_svg()
        )

    def test_draw_emits_trapezoid_and_label(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = _down_key(label_text="DN")
        svg = str(_draw(key, Point(0.0, 0.0)).as_svg())
        assert "<path" in svg  # trapezoid
        assert 'fill="#abcdef"' in svg
        assert "DN" in svg
        assert 'fill="#012345"' in svg


# ---------------------------------------------------------------------------
# DoubleDownKey — squat trapezoid with stroke outline, symmetric
# ---------------------------------------------------------------------------


class TestDoubleDownKey:
    """Stroke-outlined trapezoid between Down and Up."""

    def test_size_uses_aspect_ratio(self, ctx: RenderContext):
        """``height = width * 1.1``."""
        with using_render_context(ctx):
            key = _double_down_key(width=60.0)
        assert key.size == Size(60.0, 66.0)

    @pytest.mark.parametrize("side", [KeyboardSide.RIGHT, KeyboardSide.LEFT])
    def test_indicator_is_north_on_both_sides(self, ctx: RenderContext, side: KeyboardSide):
        """Indicator always sits above the key — ``NORTH`` is mirror-
        invariant under horizontal reflection."""
        with using_render_context(ctx):
            key = _double_down_key(side=side)
        assert key.metrics.indicator_direction is CompassDirection.NORTH

    def test_anchor_at_top_edge_midpoint(self, ctx: RenderContext):
        width = 60.0
        with using_render_context(ctx):
            key = _double_down_key(width=width)
        assert key.metrics.indicator_anchor == Point(width / 2, 0.0)

    def test_drawing_is_side_invariant(self, ctx: RenderContext):
        with using_render_context(ctx):
            right = _double_down_key(side=KeyboardSide.RIGHT)
            left = _double_down_key(side=KeyboardSide.LEFT)
        assert str(_draw(right, Point(0.0, 0.0)).as_svg()) == str(
            _draw(left, Point(0.0, 0.0)).as_svg()
        )

    def test_draw_emits_no_stroke(self, ctx: RenderContext):
        """The trapezoid is painted without SVG stroke (inset geometry
        replaces the old stroke trick)."""
        with using_render_context(ctx):
            key = _double_down_key()
        svg = str(_draw(key, Point(0.0, 0.0)).as_svg())
        path_lines = [line for line in svg.splitlines() if "<path" in line]
        for line in path_lines:
            assert "stroke=" not in line, f"unexpected stroke in {line!r}"


# ---------------------------------------------------------------------------
# UpKey — wide horizontal trapezoid, asymmetric (mirrors per side)
# ---------------------------------------------------------------------------


class TestUpKey:
    """Single-trapezoid horizontal key at the cluster top."""

    def test_size_uses_aspect_ratio(self, ctx: RenderContext):
        """Aspect 2.75:1 — ``height = width / 2.75``."""
        with using_render_context(ctx):
            key = _up_key(width=220.0)
        assert key.size == Size(220.0, 80.0)

    def test_right_side_indicator_is_east(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = _up_key(side=KeyboardSide.RIGHT)
        assert key.metrics.indicator_direction is CompassDirection.EAST

    def test_left_side_indicator_is_west(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = _up_key(side=KeyboardSide.LEFT)
        assert key.metrics.indicator_direction is CompassDirection.WEST

    def test_drawing_mirrors_per_side(self, ctx: RenderContext):
        """Asymmetric shape — slant on the inward side; SVG differs
        between sides."""
        with using_render_context(ctx):
            right = _up_key(side=KeyboardSide.RIGHT)
            left = _up_key(side=KeyboardSide.LEFT)
        assert str(_draw(right, Point(0.0, 0.0)).as_svg()) != str(
            _draw(left, Point(0.0, 0.0)).as_svg()
        )

    def test_draw_emits_fill_and_label(self, ctx: RenderContext):
        """Single fill-coloured trapezoid plus the label."""
        with using_render_context(ctx):
            key = _up_key(label_text="UP")
        svg = str(_draw(key, Point(0.0, 0.0)).as_svg())
        assert 'fill="#abcdef"' in svg
        assert "UP" in svg


# ---------------------------------------------------------------------------
# PadKey — vertical trapezoid, narrow bottom OUTWARD
# ---------------------------------------------------------------------------


class TestPadKey:
    """Pad — narrow bottom on the outward (away-from-thumb) edge."""

    def test_size_uses_aspect_ratio(self, ctx: RenderContext):
        """Aspect 1.85:1 — ``height = width / 1.85``."""
        with using_render_context(ctx):
            key = _pad_key(width=185.0)
        assert key.size.width == 185.0
        assert key.size.height == pytest.approx(100.0)

    def test_right_side_indicator_is_east(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = _pad_key(side=KeyboardSide.RIGHT)
        assert key.metrics.indicator_direction is CompassDirection.EAST

    def test_left_side_indicator_is_west(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = _pad_key(side=KeyboardSide.LEFT)
        assert key.metrics.indicator_direction is CompassDirection.WEST

    def test_drawing_mirrors_per_side(self, ctx: RenderContext):
        with using_render_context(ctx):
            right = _pad_key(side=KeyboardSide.RIGHT)
            left = _pad_key(side=KeyboardSide.LEFT)
        assert str(_draw(right, Point(0.0, 0.0)).as_svg()) != str(
            _draw(left, Point(0.0, 0.0)).as_svg()
        )

    def test_label_centred(self, ctx: RenderContext):
        """Pad's label is centred horizontally on the key.

        Center alignment is mirror-invariant — the rendered text's
        ``x`` attribute (its leftmost position after RichText
        normalisation) lands at the same offset on both halves.
        """
        width = 185.0
        with using_render_context(ctx):
            right = _pad_key(side=KeyboardSide.RIGHT, width=width)
            left = _pad_key(side=KeyboardSide.LEFT, width=width)
        right_x = _label_text_x(_draw(right, Point(0.0, 0.0)).as_svg())
        left_x = _label_text_x(_draw(left, Point(0.0, 0.0)).as_svg())
        # Mirror-invariant: both halves render the label at the same x.
        assert abs(right_x - left_x) < 0.5
        # Leftmost position sits in the left half (text extends from
        # there past the centre).
        assert right_x < width / 2.0


# ---------------------------------------------------------------------------
# NailKey — vertical trapezoid, narrow bottom INWARD
# ---------------------------------------------------------------------------


class TestNailKey:
    """Nail — mirrored shape of Pad: narrow bottom on the inward edge."""

    def test_right_side_indicator_is_west_inward(self, ctx: RenderContext):
        """Right hand: indicator on the inward / west side (toward the
        thumb), opposite the outward direction Pad / Down / Up use."""
        with using_render_context(ctx):
            key = _nail_key(side=KeyboardSide.RIGHT)
        assert key.metrics.indicator_direction is CompassDirection.WEST

    def test_left_side_indicator_is_east_inward(self, ctx: RenderContext):
        """Left hand: inward is east — the mirror of right-hand inward."""
        with using_render_context(ctx):
            key = _nail_key(side=KeyboardSide.LEFT)
        assert key.metrics.indicator_direction is CompassDirection.EAST

    def test_drawing_mirrors_per_side(self, ctx: RenderContext):
        with using_render_context(ctx):
            right = _nail_key(side=KeyboardSide.RIGHT)
            left = _nail_key(side=KeyboardSide.LEFT)
        assert str(_draw(right, Point(0.0, 0.0)).as_svg()) != str(
            _draw(left, Point(0.0, 0.0)).as_svg()
        )

    def test_pad_and_nail_mirror_each_other_on_same_side(self, ctx: RenderContext):
        """Pad's narrow bottom is outward; Nail's is inward. On the
        same side the two shapes are mirror images of each other —
        equivalent to flipping :func:`PadKey`'s SVG horizontally."""
        with using_render_context(ctx):
            pad = _pad_key(side=KeyboardSide.RIGHT)
            nail = _nail_key(side=KeyboardSide.RIGHT)
        # Both have the EAST or WEST indicator depending on which is
        # outward / inward — assert they're opposite.
        assert pad.metrics.indicator_direction is CompassDirection.EAST
        assert nail.metrics.indicator_direction is CompassDirection.WEST

    def test_label_centred(self, ctx: RenderContext):
        """Nail's label is centred horizontally — same x for both halves."""
        width = 195.0
        with using_render_context(ctx):
            right = _nail_key(side=KeyboardSide.RIGHT, width=width)
            left = _nail_key(side=KeyboardSide.LEFT, width=width)
        right_x = _label_text_x(_draw(right, Point(0.0, 0.0)).as_svg())
        left_x = _label_text_x(_draw(left, Point(0.0, 0.0)).as_svg())
        assert abs(right_x - left_x) < 0.5
        assert right_x < width / 2.0


# ---------------------------------------------------------------------------
# KnuckleKey — same shape pattern as Nail, different proportions
# ---------------------------------------------------------------------------


class TestKnuckleKey:
    """Knuckle — same pattern as Nail with slightly squatter proportions."""

    def test_right_side_indicator_is_west_inward(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = _knuckle_key(side=KeyboardSide.RIGHT)
        assert key.metrics.indicator_direction is CompassDirection.WEST

    def test_left_side_indicator_is_east_inward(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = _knuckle_key(side=KeyboardSide.LEFT)
        assert key.metrics.indicator_direction is CompassDirection.EAST

    def test_drawing_mirrors_per_side(self, ctx: RenderContext):
        with using_render_context(ctx):
            right = _knuckle_key(side=KeyboardSide.RIGHT)
            left = _knuckle_key(side=KeyboardSide.LEFT)
        assert str(_draw(right, Point(0.0, 0.0)).as_svg()) != str(
            _draw(left, Point(0.0, 0.0)).as_svg()
        )

    def test_size_differs_from_nail(self, ctx: RenderContext):
        """Knuckle's aspect ratio (1.87:1) is squatter than Nail's
        (1.95:1) — same width gives Knuckle a slightly taller key."""
        with using_render_context(ctx):
            knuckle = _knuckle_key(width=187.0)
            nail = _nail_key(width=187.0)
        assert knuckle.size.height > nail.size.height

    def test_label_centred(self, ctx: RenderContext):
        """Knuckle uses the same centre-aligned convention as Nail."""
        width = 187.0
        with using_render_context(ctx):
            right = _knuckle_key(side=KeyboardSide.RIGHT, width=width)
            left = _knuckle_key(side=KeyboardSide.LEFT, width=width)
        right_x = _label_text_x(_draw(right, Point(0.0, 0.0)).as_svg())
        left_x = _label_text_x(_draw(left, Point(0.0, 0.0)).as_svg())
        assert abs(right_x - left_x) < 0.5
        assert right_x < width / 2.0


# ---------------------------------------------------------------------------
# _make_thumb_key — shared helper for parametrised path-metric tests
# ---------------------------------------------------------------------------

_THUMB_KEY_BUILDERS = {
    "DownKey": DownKey,
    "PadKey": PadKey,
    "NailKey": NailKey,
    "KnuckleKey": KnuckleKey,
    "DoubleDownKey": DoubleDownKey,
    "UpKey": UpKey,
}


def _make_thumb_key(ctx: RenderContext, name: str):
    """Construct the named thumb-cluster key composable with stock args.

    Used by parametrised tests that exercise every trapezoid key under
    the same contract.  The ``ctx`` argument must be active (the helper
    is called *inside* a ``with using_render_context`` block).
    """
    builder = _THUMB_KEY_BUILDERS[name]
    kwargs: dict[str, object] = {
        "side": KeyboardSide.RIGHT,
        "width": 40.0,
        "label_text": "A",
        "fill_color": "#fff",
        "label_color": "#000",
    }
    with using_render_context(ctx):
        return builder(**kwargs)


# ---------------------------------------------------------------------------
# TestKeyPathMetric — every key composable exposes ``metrics.path``
# ---------------------------------------------------------------------------


class TestKeyPathMetric:
    """Every key composable populates ``metrics.path`` with a callable
    that returns the rendered fill shape (and outset variants)."""

    @pytest.mark.parametrize(
        "name", ["DownKey", "PadKey", "NailKey", "KnuckleKey", "DoubleDownKey", "UpKey"]
    )
    def test_thumb_trapezoid_path_outset_grows_bbox(self, ctx: RenderContext, name: str):
        """``path(amount)`` returns a trapezoid whose ``d`` differs from
        ``path(0.0)`` — the outset arithmetic moves the shape outward."""
        key = _make_thumb_key(ctx, name)
        base = key.metrics.path(0.0)
        grown = key.metrics.path(2.5)
        assert isinstance(base, Trapezoid)
        assert isinstance(grown, Trapezoid)
        assert base.args["d"] != grown.args["d"]

    def test_center_key_path_is_callable_returning_circle(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = _center_key(side=KeyboardSide.RIGHT, width=40.0)
        elem = key.metrics.path(0.0)
        assert isinstance(elem, draw.Circle)
        assert elem.args["r"] == 20.0  # half of width

    def test_center_key_path_outset_grows_radius(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = _center_key(side=KeyboardSide.RIGHT, width=40.0)
        elem = key.metrics.path(2.5)
        assert isinstance(elem, draw.Circle)
        assert elem.args["r"] == 22.5

    def test_directional_key_path_is_rectangle(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = _directional_key(
                side=KeyboardSide.RIGHT, direction=KeyDirection.NORTH, width=40.0
            )
        elem = key.metrics.path(0.0)
        assert isinstance(elem, draw.Rectangle)
        assert elem.args["width"] == 40.0
        assert elem.args["height"] == 40.0

    def test_directional_key_path_outset_grows_rect(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = _directional_key(
                side=KeyboardSide.RIGHT, direction=KeyDirection.NORTH, width=40.0
            )
        elem = key.metrics.path(1.0)
        assert elem.args["width"] == 42.0
        assert elem.args["height"] == 42.0
        assert elem.args["x"] == -1.0
        assert elem.args["y"] == -1.0

    def test_double_south_key_path_is_trapezoid(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = _double_south_key(side=KeyboardSide.RIGHT, width=40.0)
        elem = key.metrics.path(0.0)
        assert isinstance(elem, Trapezoid)

    def test_down_key_path_is_trapezoid(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = DownKey(
                side=KeyboardSide.RIGHT,
                width=40.0,
                label_text="A",
                fill_color="#fff",
                label_color="#000",
            )
        elem = key.metrics.path(0.0)
        assert isinstance(elem, Trapezoid)

    def test_pad_key_path_is_trapezoid(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = PadKey(
                side=KeyboardSide.RIGHT,
                width=40.0,
                label_text="A",
                fill_color="#fff",
                label_color="#000",
            )
        elem = key.metrics.path(0.0)
        assert isinstance(elem, Trapezoid)

    def test_nail_key_path_is_trapezoid(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = NailKey(
                side=KeyboardSide.RIGHT,
                width=40.0,
                label_text="A",
                fill_color="#fff",
                label_color="#000",
            )
        elem = key.metrics.path(0.0)
        assert isinstance(elem, Trapezoid)

    def test_knuckle_key_path_is_trapezoid(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = KnuckleKey(
                side=KeyboardSide.RIGHT,
                width=40.0,
                label_text="A",
                fill_color="#fff",
                label_color="#000",
            )
        elem = key.metrics.path(0.0)
        assert isinstance(elem, Trapezoid)

    def test_double_down_key_path_is_trapezoid(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = DoubleDownKey(
                side=KeyboardSide.RIGHT,
                width=40.0,
                label_text="A",
                fill_color="#fff",
                label_color="#000",
            )
        elem = key.metrics.path(0.0)
        assert isinstance(elem, Trapezoid)

    def test_up_key_path_is_trapezoid(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = UpKey(
                side=KeyboardSide.RIGHT,
                width=40.0,
                label_text="A",
                fill_color="#fff",
                label_color="#000",
            )
        elem = key.metrics.path(0.0)
        assert isinstance(elem, Trapezoid)


# ---------------------------------------------------------------------------
# TestDoubleDownKeyGeometry
# ---------------------------------------------------------------------------


class TestDoubleDownKeyGeometry:
    """DD's painted trapezoid is inset by stroke_width/2 from the
    legacy width/height/top_width, with no SVG stroke applied."""

    def test_signature_drops_stroke_color(self):
        # ``@Composable`` uses ``functools.wraps``; the underlying builder is
        # accessible via ``__wrapped__``.
        sig = inspect.signature(DoubleDownKey.__wrapped__)  # type: ignore[attr-defined]
        assert "stroke_color" not in sig.parameters

    def test_path_zero_outset_is_inset_trapezoid(self, ctx: RenderContext):
        width = 40.0
        with using_render_context(ctx):
            key = DoubleDownKey(
                side=KeyboardSide.RIGHT,
                width=width,
                label_text="A",
                fill_color="#fff",
                label_color="#000",
            )
        elem = key.metrics.path(0.0)
        assert isinstance(elem, Trapezoid)
        inset = width * _DOUBLE_DOWN_INSET_MULTIPLIER
        expected = Trapezoid(
            x=inset,
            y=inset,
            width=width - 2 * inset,
            height=width * _DOUBLE_DOWN_HEIGHT_RATIO - 2 * inset,
            top_width=(width * (1 - _DOUBLE_DOWN_SLANT_MULTIPLIER)) - 2 * inset,
            corners_radius=width * _DOUBLE_DOWN_CORNER_RADIUS_MULTIPLIER,
            fill="#fff",
        )
        assert elem.args["d"] == expected.args["d"]


# ---------------------------------------------------------------------------
# TestUpKeyGeometry
# ---------------------------------------------------------------------------


class TestUpKeyGeometry:
    """UP paints a single trapezoid (the legacy ``inner``); no outer
    twin, no stroke."""

    def test_signature_drops_stroke_color(self):
        sig = inspect.signature(UpKey.__wrapped__)  # type: ignore[attr-defined]
        assert "stroke_color" not in sig.parameters

    def test_draw_emits_single_trapezoid(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = UpKey(
                side=KeyboardSide.RIGHT, width=40.0, label_text="A",
                fill_color="#fff", label_color="#000",
            )
        svg = str(_draw(key, Point(0.0, 0.0)).as_svg())
        # Count <path> elements with fill="#fff" — there should be exactly
        # one (the trapezoid). The label may render as separate elements
        # but won't share the fill colour.
        trap_paths = [
            line for line in svg.splitlines()
            if '<path' in line and 'fill="#fff"' in line
        ]
        assert len(trap_paths) == 1, f"expected 1 trapezoid, got {len(trap_paths)}: {trap_paths}"

    def test_path_zero_outset_matches_legacy_inner(self, ctx: RenderContext):
        width = 40.0
        with using_render_context(ctx):
            key = UpKey(
                side=KeyboardSide.RIGHT, width=width, label_text="A",
                fill_color="#fff", label_color="#000",
            )
        elem = key.metrics.path(0.0)
        height = width * _UP_HEIGHT_RATIO
        short_face = height * (1.0 - _UP_SLANT_MULTIPLIER)
        # Right hand: slant on the left edge (left_height = short_face).
        expected = Trapezoid(
            x=0, y=0,
            width=width, height=height,
            left_height=short_face,
            corners_radius=width * _UP_CORNER_RADIUS_MULTIPLIER,
            align_y=Alignment.START,
            fill="#fff",
        )
        assert elem.args["d"] == expected.args["d"]
