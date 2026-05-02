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
    SvalboardKeyMetrics,
)
from skim.data import SkimConfig, SvalboardKeymap


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
