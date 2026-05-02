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
from skim.domain import KeyDirection


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
# CenterKey
# ---------------------------------------------------------------------------


class TestCenterKey:
    """Filled circle + centred label, with SW indicator metrics."""

    def test_reported_size_is_square(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = CenterKey(
                width=80.0,
                label_text="A",
                fill_color="#abcdef",
                label_color="#012345",
            )
        assert key.size == Size(80.0, 80.0)

    def test_metrics_indicator_direction_is_south_west(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = CenterKey(
                width=80.0,
                label_text="A",
                fill_color="#abcdef",
                label_color="#012345",
            )
        assert key.metrics.indicator_direction is CompassDirection.SOUTH_WEST

    def test_metrics_indicator_anchor_lands_on_circle_perimeter(self, ctx: RenderContext):
        """SW anchor sits on the circle's perimeter at 225° from centre.

        For a circle of width ``W`` centred at ``(W/2, W/2)`` with
        radius ``W/2``, the SW point is ``(W/2 - r·cos45°, W/2 + r·sin45°)``.
        Verifying the math is on the perimeter (distance from centre
        equals ``W/2``) is a tighter check than asserting the exact
        coordinate floats.
        """
        width = 80.0
        with using_render_context(ctx):
            key = CenterKey(
                width=width,
                label_text="A",
                fill_color="#abcdef",
                label_color="#012345",
            )
        anchor = key.metrics.indicator_anchor
        cx = cy = width / 2.0
        r = width / 2.0
        dx = anchor.x - cx
        dy = anchor.y - cy
        # On the perimeter — distance from centre equals radius.
        assert abs(dx * dx + dy * dy - r * r) < 1e-6
        # In the SW quadrant — left of centre, below centre.
        assert dx < 0
        assert dy > 0

    def test_metrics_typed_subclass(self, ctx: RenderContext):
        """:func:`CenterKey` returns a :class:`MetricsComponent` whose
        ``metrics`` field is the typed :class:`SvalboardKeyMetrics`."""
        with using_render_context(ctx):
            key = CenterKey(
                width=80.0,
                label_text="A",
                fill_color="#abcdef",
                label_color="#012345",
            )
        assert isinstance(key.metrics, SvalboardKeyMetrics)

    def test_draw_emits_circle(self, ctx: RenderContext):
        """The circle paints at the cell centre with the expected fill."""
        width = 80.0
        with using_render_context(ctx):
            key = CenterKey(
                width=width,
                label_text="A",
                fill_color="#abcdef",
                label_color="#012345",
            )
        d = _draw(key, Point(50.0, 50.0))
        svg = str(d.as_svg())
        # Centre at (50 + 40, 50 + 40) = (90, 90); radius 40.
        assert 'cx="90.0"' in svg
        assert 'cy="90.0"' in svg
        assert 'r="40.0"' in svg
        assert 'fill="#abcdef"' in svg

    def test_draw_emits_label_text(self, ctx: RenderContext):
        """The label content lands in the SVG text content."""
        with using_render_context(ctx):
            key = CenterKey(
                width=80.0,
                label_text="ABC",
                fill_color="#abcdef",
                label_color="#012345",
            )
        d = _draw(key, Point(0.0, 0.0))
        svg = str(d.as_svg())
        # The painted text — and the label-colour fill — should land
        # in the SVG output.
        assert "ABC" in svg
        assert 'fill="#012345"' in svg

    def test_long_label_shrinks_via_richtext_relaxation(self, ctx: RenderContext):
        """A long label triggers RichText's shrink-to-fit relaxation.

        The ``max_width`` budget passed into RichText is
        ``width * 0.7``, so a label naturally wider than that should
        come out with the painted ``font-size`` smaller than the
        nominal ``width * 0.6`` ceiling.
        """
        width = 40.0
        with using_render_context(ctx):
            key = CenterKey(
                width=width,
                label_text="MMMMMMMMMM",
                fill_color="#abcdef",
                label_color="#012345",
            )
        d = _draw(key, Point(0.0, 0.0))
        svg = str(d.as_svg())
        # Default ceiling is ``width * 0.6 = 24``; relaxation shrinks
        # below that to fit. Spot-check by asserting at least one
        # ``font-size`` in the rendered SVG that's < 24.
        import re

        sizes = [float(m) for m in re.findall(r'font-size="([\d.]+)"', svg)]
        assert any(0 < s < 24.0 for s in sizes), f"no shrunk font sizes in {sizes!r}"


# ---------------------------------------------------------------------------
# DirectionalKey — N / S / E / W finger-cluster keys (rounded rect + accent bar)
# ---------------------------------------------------------------------------


class TestDirectionalKey:
    """Unified composable for the four directional finger keys."""

    @pytest.mark.parametrize(
        "direction,expected_compass",
        [
            (KeyDirection.NORTH, CompassDirection.NORTH),
            (KeyDirection.EAST, CompassDirection.NORTH),
            (KeyDirection.WEST, CompassDirection.NORTH),
            (KeyDirection.SOUTH, CompassDirection.EAST),
        ],
    )
    def test_indicator_direction(
        self,
        ctx: RenderContext,
        direction: KeyDirection,
        expected_compass: CompassDirection,
    ):
        """N / E / W carry the indicator above; S carries it on the
        outward (east) side in the right-hand reference orientation.
        """
        with using_render_context(ctx):
            key = DirectionalKey(
                direction=direction,
                width=80.0,
                label_text="A",
                fill_color="#abcdef",
                accent_color="#012345",
                label_color="#ffffff",
            )
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
    def test_indicator_anchor(
        self,
        ctx: RenderContext,
        direction: KeyDirection,
        expected_anchor: Point,
    ):
        """N / E / W anchor at the top-edge midpoint; S anchors at the
        right-edge midpoint (right-hand reference)."""
        with using_render_context(ctx):
            key = DirectionalKey(
                direction=direction,
                width=80.0,
                label_text="A",
                fill_color="#abcdef",
                accent_color="#012345",
                label_color="#ffffff",
            )
        assert key.metrics.indicator_anchor == expected_anchor

    def test_size_is_square(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = DirectionalKey(
                direction=KeyDirection.NORTH,
                width=80.0,
                label_text="A",
                fill_color="#abcdef",
                accent_color="#012345",
                label_color="#ffffff",
            )
        assert key.size == Size(80.0, 80.0)

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
        accent colour at the right position.
        """
        with using_render_context(ctx):
            key = DirectionalKey(
                direction=direction,
                width=80.0,
                label_text="A",
                fill_color="#abcdef",
                accent_color="#012345",
                label_color="#ffffff",
            )
        d = _draw(key, Point(0.0, 0.0))
        svg = str(d.as_svg())
        for piece in expected_bar:
            assert piece in svg, f"missing {piece!r} for {direction}"
        # The accent rectangle must use the accent colour.
        assert 'fill="#012345"' in svg


# ---------------------------------------------------------------------------
# DoubleSouthKey — trapezoid + accent bar on top
# ---------------------------------------------------------------------------


class TestDoubleSouthKey:
    """Trapezoid below the south key with an accent bar on top."""

    def test_size_is_square(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = DoubleSouthKey(
                width=80.0,
                label_text="A",
                fill_color="#abcdef",
                accent_color="#012345",
                label_color="#ffffff",
            )
        assert key.size == Size(80.0, 80.0)

    def test_metrics_indicator_direction_is_east(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = DoubleSouthKey(
                width=80.0,
                label_text="A",
                fill_color="#abcdef",
                accent_color="#012345",
                label_color="#ffffff",
            )
        assert key.metrics.indicator_direction is CompassDirection.EAST

    def test_metrics_indicator_anchor_at_right_edge_midpoint(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = DoubleSouthKey(
                width=80.0,
                label_text="A",
                fill_color="#abcdef",
                accent_color="#012345",
                label_color="#ffffff",
            )
        assert key.metrics.indicator_anchor == Point(80.0, 40.0)

    def test_draw_emits_trapezoid_and_accent_bar(self, ctx: RenderContext):
        """The shape SVG should contain a path (the trapezoid) and a
        rectangle filled with the accent colour at the top edge."""
        with using_render_context(ctx):
            key = DoubleSouthKey(
                width=80.0,
                label_text="A",
                fill_color="#abcdef",
                accent_color="#012345",
                label_color="#ffffff",
            )
        d = _draw(key, Point(0.0, 0.0))
        svg = str(d.as_svg())
        # Trapezoid renders as a <path>.
        assert "<path" in svg
        assert 'fill="#abcdef"' in svg
        # Accent bar — rect at the top edge with the accent colour.
        # ``y="0.0"`` + accent height = ``width * 0.15 = 12``.
        assert 'y="0.0"' in svg
        assert 'height="12.0"' in svg
        assert 'fill="#012345"' in svg

    def test_draw_emits_label_text(self, ctx: RenderContext):
        with using_render_context(ctx):
            key = DoubleSouthKey(
                width=80.0,
                label_text="DS",
                fill_color="#abcdef",
                accent_color="#012345",
                label_color="#ffffff",
            )
        d = _draw(key, Point(0.0, 0.0))
        svg = str(d.as_svg())
        assert "DS" in svg
        assert 'fill="#ffffff"' in svg
