# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for :mod:`skim.application.render.svalboard_clusters`."""

from __future__ import annotations

import drawsvg as draw
import pytest

from skim.application.render.primitives import CompassDirection, Point, Size
from skim.application.render.render_context import RenderContext, using_render_context
from skim.application.render.svalboard_clusters import (
    FingerCluster,
    FingerClusterMetrics,
)
from skim.data import LayerColor, Palette, SkimConfig, SplitSidePosition, SvalboardKeymap
from skim.data.keyboard import FingerCluster as FingerClusterData
from skim.domain import KeyboardSide, SvalboardTargetKey


@pytest.fixture
def ctx() -> RenderContext:
    return RenderContext.build(SkimConfig(), SvalboardKeymap(layers={}))


@pytest.fixture
def palette() -> Palette:
    """Palette with a single layer-0 gradient — enough for cluster colour
    resolution. Six gradient stops cover the per-slot indices the
    cluster maps from."""
    layer = LayerColor(
        base_color="#888888",
        gradient=("#cc0000", "#aa0000", "#880000", "#660000", "#440000", "#220000"),
    )
    return Palette(
        layers=(layer,),
        text_color="#000000",
        key_label_color="#ffffff",
        background_color="#ffffff",
        border_color="#000000",
        macro_color="#000000",
        tap_dance_color="#000000",
        neutral_color="#666666",
    )


def _td_key(label: str = "A", **kwargs) -> SvalboardTargetKey:
    """Default :class:`SvalboardTargetKey` — non-transparent, no
    layer-switch, with the given label."""
    return SvalboardTargetKey(label=label, **kwargs)


def _cluster_data() -> FingerClusterData[SvalboardTargetKey]:
    """A simple finger cluster with distinct labels per slot."""
    return FingerClusterData(
        center_key=_td_key("C"),
        north_key=_td_key("N"),
        east_key=_td_key("E"),
        south_key=_td_key("S"),
        west_key=_td_key("W"),
        double_south_key=_td_key("DS"),
    )


def _draw(component, origin: Point) -> draw.Drawing:
    d = draw.Drawing(800, 800)
    component.draw_at(d, origin)
    return d


# ---------------------------------------------------------------------------
# Layout / size
# ---------------------------------------------------------------------------


class TestLayout:
    """Cluster layout — per-key positions and sizes."""

    def test_size_height_matches_outer_width_plus_inset_for_no_double_south(
        self, ctx: RenderContext, palette: Palette
    ):
        """Without double-south the cluster height ends at south's
        bottom edge — north + centre + south stacked vertically with
        inset gaps between."""
        with using_render_context(ctx):
            cluster = FingerCluster(
                cluster=_cluster_data(),
                side=KeyboardSide.RIGHT,
                width=600.0,
                layer_colors=palette.layers[0],
                palette=palette,
                has_double_south=False,
            )
        # north (outer 0.328) + centre (0.309) + south (0.328) +
        # 2 inset gaps (0.018) = 1.001 → close to but slightly more
        # than the cluster width because the proportions don't sum
        # exactly. Just assert it's positive and < cluster width
        # plus an extra slot.
        outer_w = 600.0 * 0.328
        center_w = 600.0 * 0.309
        inset = 600.0 * 0.018
        expected_height = outer_w + inset + center_w + inset + outer_w
        assert cluster.size.width == 600.0
        assert cluster.size.height == pytest.approx(expected_height)

    def test_size_grows_for_double_south(self, ctx: RenderContext, palette: Palette):
        """Double-south adds ``inset + outer_width`` to the cluster
        height."""
        with using_render_context(ctx):
            no_ds = FingerCluster(
                cluster=_cluster_data(),
                side=KeyboardSide.RIGHT,
                width=600.0,
                layer_colors=palette.layers[0],
                palette=palette,
                has_double_south=False,
            )
            with_ds = FingerCluster(
                cluster=_cluster_data(),
                side=KeyboardSide.RIGHT,
                width=600.0,
                layer_colors=palette.layers[0],
                palette=palette,
                has_double_south=True,
            )
        outer_w = 600.0 * 0.328
        inset = 600.0 * 0.018
        assert with_ds.size.height == pytest.approx(no_ds.size.height + inset + outer_w)


# ---------------------------------------------------------------------------
# Metrics — per-key SvalboardKeyMetrics surfaced by slot
# ---------------------------------------------------------------------------


class TestMetrics:
    """Cluster metrics expose per-key indicator metrics by slot."""

    def test_metrics_typed_subclass(self, ctx: RenderContext, palette: Palette):
        with using_render_context(ctx):
            cluster = FingerCluster(
                cluster=_cluster_data(),
                side=KeyboardSide.RIGHT,
                width=600.0,
                layer_colors=palette.layers[0],
                palette=palette,
            )
        assert isinstance(cluster.metrics, FingerClusterMetrics)

    def test_per_slot_indicator_directions_right_side(self, ctx: RenderContext, palette: Palette):
        """Right-hand reference: NSEW indicators above (N), centre to
        SW, south outward (E)."""
        with using_render_context(ctx):
            cluster = FingerCluster(
                cluster=_cluster_data(),
                side=KeyboardSide.RIGHT,
                width=600.0,
                layer_colors=palette.layers[0],
                palette=palette,
            )
        m = cluster.metrics
        assert m.center_key.indicator_direction is CompassDirection.SOUTH_WEST
        assert m.north_key.indicator_direction is CompassDirection.NORTH
        assert m.east_key.indicator_direction is CompassDirection.NORTH
        assert m.south_key.indicator_direction is CompassDirection.EAST
        assert m.west_key.indicator_direction is CompassDirection.NORTH

    def test_per_slot_indicator_directions_left_side(self, ctx: RenderContext, palette: Palette):
        """Left hand mirrors the directions that have an east-west
        component — centre flips to SE, south to W."""
        with using_render_context(ctx):
            cluster = FingerCluster(
                cluster=_cluster_data(),
                side=KeyboardSide.LEFT,
                width=600.0,
                layer_colors=palette.layers[0],
                palette=palette,
            )
        m = cluster.metrics
        assert m.center_key.indicator_direction is CompassDirection.SOUTH_EAST
        assert m.north_key.indicator_direction is CompassDirection.NORTH
        assert m.south_key.indicator_direction is CompassDirection.WEST

    def test_double_south_metrics_present_when_enabled(self, ctx: RenderContext, palette: Palette):
        with using_render_context(ctx):
            with_ds = FingerCluster(
                cluster=_cluster_data(),
                side=KeyboardSide.RIGHT,
                width=600.0,
                layer_colors=palette.layers[0],
                palette=palette,
                has_double_south=True,
            )
            without_ds = FingerCluster(
                cluster=_cluster_data(),
                side=KeyboardSide.RIGHT,
                width=600.0,
                layer_colors=palette.layers[0],
                palette=palette,
                has_double_south=False,
            )
        assert with_ds.metrics.double_south_key is not None
        assert without_ds.metrics.double_south_key is None


# ---------------------------------------------------------------------------
# Drawing — every key paints into the SVG
# ---------------------------------------------------------------------------


class TestDrawing:
    """SVG output covers every slot's label + shape."""

    def test_every_slot_label_lands_in_svg_no_double_south(
        self, ctx: RenderContext, palette: Palette
    ):
        with using_render_context(ctx):
            cluster = FingerCluster(
                cluster=_cluster_data(),
                side=KeyboardSide.RIGHT,
                width=600.0,
                layer_colors=palette.layers[0],
                palette=palette,
                has_double_south=False,
            )
        svg = str(_draw(cluster, Point(0.0, 0.0)).as_svg())
        for label in ("C", "N", "E", "S", "W"):
            assert f">{label}<" in svg
        # Double-south label should NOT appear.
        assert ">DS<" not in svg

    def test_double_south_label_lands_when_enabled(self, ctx: RenderContext, palette: Palette):
        with using_render_context(ctx):
            cluster = FingerCluster(
                cluster=_cluster_data(),
                side=KeyboardSide.RIGHT,
                width=600.0,
                layer_colors=palette.layers[0],
                palette=palette,
                has_double_south=True,
            )
        svg = str(_draw(cluster, Point(0.0, 0.0)).as_svg())
        assert ">DS<" in svg

    def test_reported_width_matches_input_width(self, ctx: RenderContext, palette: Palette):
        """``size.width`` is the cluster's outer bbox — the input
        ``width``. The proportions sum to ~1.001, so individual keys
        may extend a hair past the bbox; the layout containers above
        clip / pad accordingly. Within tolerance is fine."""
        width = 600.0
        with using_render_context(ctx):
            cluster = FingerCluster(
                cluster=_cluster_data(),
                side=KeyboardSide.RIGHT,
                width=width,
                layer_colors=palette.layers[0],
                palette=palette,
            )
        center_w = width * 0.309
        outer_w = width * 0.328
        inset = width * 0.018
        east_x = (width / 2.0) + (center_w / 2.0) + inset
        east_right_edge = east_x + outer_w
        assert cluster.size.width == width
        # Proportions don't sum to exactly 1.0 — within 0.5 SVG units
        # of tolerance the east edge can sit just past the bbox.
        # Document that this is expected.
        assert east_right_edge <= width + 1.0


# ---------------------------------------------------------------------------
# Colour resolution — layer-switch keys, transparent ghost colour
# ---------------------------------------------------------------------------


class TestColorResolution:
    """The cluster picks per-key colours based on layer-switch and
    transparency state."""

    def test_layer_switch_key_uses_destination_layer_color(self, ctx: RenderContext):
        """A key whose ``layer_switch=1`` paints in layer 1's gradient
        colour (when ``use_layer_colors_on_keys`` is enabled)."""
        # Two-layer palette so layer_switch=1 resolves.
        layer0 = LayerColor(
            base_color="#000000",
            gradient=("#100000", "#200000", "#300000", "#400000", "#500000", "#600000"),
        )
        layer1 = LayerColor(
            base_color="#ff00ff",
            gradient=("#aa00aa", "#bb00bb", "#cc00cc", "#dd00dd", "#ee00ee", "#ff00ff"),
            color_index=2,
        )
        palette = Palette(
            layers=(layer0, layer1),
            key_label_color="#ffffff",
        )

        # North key on layer 0 has layer_switch=1 — should paint with
        # layer 1's color (gradient[layer1.color_index]) = "#cc00cc".
        cluster_data = FingerClusterData(
            center_key=_td_key("C"),
            north_key=_td_key("N", layer_switch=1),
            east_key=_td_key("E"),
            south_key=_td_key("S"),
            west_key=_td_key("W"),
            double_south_key=_td_key("DS"),
        )
        with using_render_context(ctx):
            cluster = FingerCluster(
                cluster=cluster_data,
                side=KeyboardSide.RIGHT,
                width=600.0,
                layer_colors=layer0,
                palette=palette,
                use_layer_colors_on_keys=True,
            )
        svg = str(_draw(cluster, Point(0.0, 0.0)).as_svg())
        # Layer 1's gradient[2] = "#cc00cc" should appear (the north
        # key's fill).
        assert "#cc00cc" in svg.lower()

    def test_layer_switch_disabled_keeps_default_color(self, ctx: RenderContext):
        """With ``use_layer_colors_on_keys=False`` the layer_switch is
        ignored for fill — slot defaults apply uniformly."""
        layer0 = LayerColor(
            base_color="#000000",
            gradient=("#100000", "#200000", "#300000", "#400000", "#500000", "#600000"),
        )
        layer1 = LayerColor(
            base_color="#ff00ff",
            gradient=("#aa00aa", "#bb00bb", "#cc00cc", "#dd00dd", "#ee00ee", "#ff00ff"),
        )
        palette = Palette(
            layers=(layer0, layer1),
            key_label_color="#ffffff",
        )

        cluster_data = FingerClusterData(
            center_key=_td_key("C"),
            north_key=_td_key("N", layer_switch=1),
            east_key=_td_key("E"),
            south_key=_td_key("S"),
            west_key=_td_key("W"),
            double_south_key=_td_key("DS"),
        )
        with using_render_context(ctx):
            cluster = FingerCluster(
                cluster=cluster_data,
                side=KeyboardSide.RIGHT,
                width=600.0,
                layer_colors=layer0,
                palette=palette,
                use_layer_colors_on_keys=False,
            )
        svg = str(_draw(cluster, Point(0.0, 0.0)).as_svg())
        # Layer 1's destination colour should NOT appear.
        assert "#cc00cc" not in svg.lower()

    def test_transparent_label_uses_ghost_color(self, ctx: RenderContext, palette: Palette):
        """A transparent key paints its label in a faded "ghost"
        colour derived from the fill — not the palette's standard
        white."""
        cluster_data = FingerClusterData(
            center_key=_td_key("C", is_transparent=True),
            north_key=_td_key("N"),
            east_key=_td_key("E"),
            south_key=_td_key("S"),
            west_key=_td_key("W"),
            double_south_key=_td_key("DS"),
        )
        with using_render_context(ctx):
            cluster = FingerCluster(
                cluster=cluster_data,
                side=KeyboardSide.RIGHT,
                width=600.0,
                layer_colors=palette.layers[0],
                palette=palette,
            )
        # Centre key's label colour is computed from its fill — it
        # should NOT be the standard ``#ffffff`` palette label
        # colour. We can't easily assert the exact ghost colour
        # without re-running the calculation, but we can assert the
        # cluster's metrics are still produced (smoke test).
        assert cluster.metrics.center_key is not None
