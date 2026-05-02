# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for :mod:`skim.application.render.layer_indicator`."""

from __future__ import annotations

import drawsvg as draw
import pytest

from skim.application.render.layer_indicator import (
    LayerIndicator,
    LayerIndicatorMetrics,
)
from skim.application.render.primitives import CompassDirection, Point, Size
from skim.application.render.render_context import RenderContext, using_render_context
from skim.data import SkimConfig, SvalboardKeymap


@pytest.fixture
def ctx() -> RenderContext:
    return RenderContext.build(SkimConfig(), SvalboardKeymap(layers={}))


def _draw(component, origin: Point) -> draw.Drawing:
    d = draw.Drawing(400, 400)
    component.draw_at(d, origin)
    return d


def _indicator(
    *,
    target_layer: int = 3,
    anchor: Point = Point(40.0, 0.0),
    direction: CompassDirection = CompassDirection.NORTH,
    circle_diameter: float = 24.0,
    gap: float = 6.0,
    fill_color: str = "#abcdef",
    stroke_color: str = "#012345",
    label_color: str = "white",
):
    return LayerIndicator(
        target_layer=target_layer,
        anchor=anchor,
        direction=direction,
        circle_diameter=circle_diameter,
        gap=gap,
        fill_color=fill_color,
        stroke_color=stroke_color,
        label_color=label_color,
    )


# ---------------------------------------------------------------------------
# Geometry — circle position, routing origin
# ---------------------------------------------------------------------------


class TestGeometry:
    """Anchor + direction → circle / connector / routing geometry."""

    def test_size_is_zero(self, ctx: RenderContext):
        """The indicator is annotation; it doesn't claim layout space."""
        with using_render_context(ctx):
            ind = _indicator()
        assert ind.size == Size(0.0, 0.0)

    def test_metrics_typed_subclass(self, ctx: RenderContext):
        with using_render_context(ctx):
            ind = _indicator()
        assert isinstance(ind.metrics, LayerIndicatorMetrics)

    def test_circle_radius_is_half_diameter(self, ctx: RenderContext):
        with using_render_context(ctx):
            ind = _indicator(circle_diameter=24.0)
        assert ind.metrics.circle_radius == 12.0

    @pytest.mark.parametrize(
        "direction,expected_offset",
        [
            (CompassDirection.NORTH, (0.0, -18.0)),  # gap (6) + radius (12) = 18
            (CompassDirection.EAST, (18.0, 0.0)),
            (CompassDirection.SOUTH, (0.0, 18.0)),
            (CompassDirection.WEST, (-18.0, 0.0)),
        ],
    )
    def test_cardinal_circle_position(
        self,
        ctx: RenderContext,
        direction: CompassDirection,
        expected_offset: tuple[float, float],
    ):
        """Circle sits ``gap + radius`` from the anchor along ``direction``."""
        anchor = Point(40.0, 40.0)
        with using_render_context(ctx):
            ind = _indicator(anchor=anchor, direction=direction, circle_diameter=24.0, gap=6.0)
        assert ind.metrics.circle_center.x == pytest.approx(anchor.x + expected_offset[0])
        assert ind.metrics.circle_center.y == pytest.approx(anchor.y + expected_offset[1])

    def test_diagonal_circle_position_is_radial_distance(self, ctx: RenderContext):
        """SW circle sits ``gap + radius`` away from the anchor as
        a radial distance (Euclidean), not a per-axis distance."""
        anchor = Point(50.0, 50.0)
        circle_diameter = 24.0
        gap = 6.0
        with using_render_context(ctx):
            ind = _indicator(
                anchor=anchor,
                direction=CompassDirection.SOUTH_WEST,
                circle_diameter=circle_diameter,
                gap=gap,
            )
        c = ind.metrics.circle_center
        dx = c.x - anchor.x
        dy = c.y - anchor.y
        # SW: x decreases, y increases.
        assert dx < 0
        assert dy > 0
        # Radial distance equals gap + radius.
        radial = (dx * dx + dy * dy) ** 0.5
        assert radial == pytest.approx(gap + circle_diameter / 2.0)

    @pytest.mark.parametrize(
        "direction",
        [
            CompassDirection.NORTH,
            CompassDirection.EAST,
            CompassDirection.SOUTH,
            CompassDirection.WEST,
            CompassDirection.NORTH_EAST,
            CompassDirection.SOUTH_EAST,
            CompassDirection.SOUTH_WEST,
            CompassDirection.NORTH_WEST,
        ],
    )
    def test_routing_origin_is_opposite_circle_edge(
        self, ctx: RenderContext, direction: CompassDirection
    ):
        """The routing origin sits on the circle's edge OPPOSITE the
        anchor — i.e., one circle diameter past the anchor along
        ``direction``."""
        anchor = Point(40.0, 40.0)
        circle_diameter = 24.0
        gap = 6.0
        with using_render_context(ctx):
            ind = _indicator(
                anchor=anchor,
                direction=direction,
                circle_diameter=circle_diameter,
                gap=gap,
            )
        # Distance from anchor to routing_origin should equal
        # ``gap + diameter`` (gap to the near edge, then across the
        # diameter to the far edge).
        c = ind.metrics.routing_origin
        radial = ((c.x - anchor.x) ** 2 + (c.y - anchor.y) ** 2) ** 0.5
        assert radial == pytest.approx(gap + circle_diameter)

    def test_routing_direction_matches_input_direction(self, ctx: RenderContext):
        """``routing_direction`` is the same compass octant the
        indicator sits in relative to its key — the routing line
        keeps heading outward in that direction."""
        with using_render_context(ctx):
            ind = _indicator(direction=CompassDirection.SOUTH_WEST)
        assert ind.metrics.routing_direction is CompassDirection.SOUTH_WEST


# ---------------------------------------------------------------------------
# SVG output — chrome that should appear in the rendered drawing
# ---------------------------------------------------------------------------


class TestSvgOutput:
    """The painted SVG carries circle + connector + endpoint + label."""

    def test_emits_indicator_circle(self, ctx: RenderContext):
        with using_render_context(ctx):
            ind = _indicator(circle_diameter=24.0, fill_color="#aabbcc")
        svg = str(_draw(ind, Point(0.0, 0.0)).as_svg())
        # Indicator circle uses the fill colour and the radius.
        assert 'fill="#aabbcc"' in svg
        assert 'r="12.0"' in svg

    def test_emits_endpoint_marker(self, ctx: RenderContext):
        """A small filled circle sits just inside the key edge so the
        connector visually anchors to the key boundary."""
        with using_render_context(ctx):
            ind = _indicator(stroke_color="#dd0000")
        svg = str(_draw(ind, Point(0.0, 0.0)).as_svg())
        # Endpoint uses the stroke colour and a small radius
        # (doc_width * 2/1600 = 1600 * 2/1600 = 2.0 by default).
        assert 'fill="#dd0000"' in svg
        assert svg.count("<circle") >= 2  # endpoint + indicator

    def test_emits_connector_line(self, ctx: RenderContext):
        """A line connects the indicator circle to the key edge.

        ``drawsvg.Line`` serialises as ``<path d="M.. L..">`` rather
        than ``<line>``, so assert on the path's stroke + the
        ``M``/``L`` move-line shape.
        """
        with using_render_context(ctx):
            ind = _indicator(stroke_color="#dd0000")
        svg = str(_draw(ind, Point(0.0, 0.0)).as_svg())
        assert 'stroke="#dd0000"' in svg
        # A connector path of the shape ``M x,y L x,y`` (single move +
        # line) — the indicator's connector is the only such path.
        import re

        assert re.search(r'<path d="M[\d.\-, ]+L[\d.\-, ]+"', svg) is not None

    def test_emits_layer_number_label(self, ctx: RenderContext):
        with using_render_context(ctx):
            ind = _indicator(target_layer=7)
        svg = str(_draw(ind, Point(0.0, 0.0)).as_svg())
        assert ">7<" in svg  # text content in the SVG

    def test_label_color_lands_in_svg(self, ctx: RenderContext):
        with using_render_context(ctx):
            ind = _indicator(label_color="#ff00ff")
        svg = str(_draw(ind, Point(0.0, 0.0)).as_svg())
        assert 'fill="#ff00ff"' in svg

    def test_origin_offsets_all_geometry(self, ctx: RenderContext):
        """Calling ``draw_at`` with a non-zero origin shifts every
        painted element by that origin — the indicator is positioned
        relative to its caller's origin (== the key origin)."""
        anchor = Point(40.0, 0.0)
        circle_diameter = 24.0
        gap = 6.0
        with using_render_context(ctx):
            ind = _indicator(
                anchor=anchor,
                direction=CompassDirection.NORTH,
                circle_diameter=circle_diameter,
                gap=gap,
            )
        # Paint at (100, 200). The circle should land at
        # (100 + 40, 200 + 0 - 18) = (140, 182).
        svg = str(_draw(ind, Point(100.0, 200.0)).as_svg())
        # Look for the indicator circle's centre.
        assert 'cx="140.0"' in svg
        assert 'cy="182.0"' in svg
