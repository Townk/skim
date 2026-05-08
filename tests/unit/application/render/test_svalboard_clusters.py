# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for :mod:`skim.application.render.svalboard_clusters`."""

from __future__ import annotations

import drawsvg as draw
import pytest

from skim.application.render.layer_indicator import LayerIndicatorMetrics
from skim.application.render.primitives import CompassDirection, Point
from skim.application.render.render_context import RenderContext, using_render_context
from skim.application.render.svalboard_clusters import (
    _DOWN_CUTOUT_OUTSET_DIVISOR,
    FingerCluster,
    FingerClusterMetrics,
    ThumbCluster,
    ThumbClusterMetrics,
)
from skim.data import LayerColor, Palette, SkimConfig, SvalboardKeymap
from skim.data.config import Keyboard, KeyboardLayer, Output, Style
from skim.data.keyboard import FingerCluster as FingerClusterData, ThumbCluster as ThumbClusterData
from skim.domain import KeyboardSide, SvalboardTargetKey

# QMK firmware index used by every test that doesn't care about the
# specific layer — there's only one configured layer in the default
# fixture, and it's at this index.
_LAYER_0 = 0


def _build_config(palette: Palette, layer_qmk_indices: tuple[int, ...] = (_LAYER_0,)) -> SkimConfig:
    """Build a :class:`SkimConfig` whose ``Keyboard.layers`` align with
    the given palette. Each ``layer_qmk_indices`` entry registers a
    :class:`KeyboardLayer` at that QMK firmware index, paired with the
    next palette entry.

    Tests that exercise layer-switch resolution (where a key's
    ``layer_switch`` looks up a destination palette entry by firmware
    index) use this to wire up multi-layer fixtures.
    """
    return SkimConfig(
        keyboard=Keyboard(
            layers=tuple(KeyboardLayer(index=idx, name=f"Layer{idx}") for idx in layer_qmk_indices),
        ),
        output=Output(style=Style(palette=palette)),
    )


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


@pytest.fixture
def ctx(palette: Palette) -> RenderContext:
    """Render context wired with a one-layer keyboard config (QMK
    index 0) whose palette matches the ``palette`` fixture. Tests
    pass ``layer_qmk_index=_LAYER_0`` to render against this layer's
    colours."""
    config = _build_config(palette)
    return RenderContext.build(config, SvalboardKeymap(layers={}))


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
                layer_qmk_index=_LAYER_0,
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
                layer_qmk_index=_LAYER_0,
                has_double_south=False,
            )
            with_ds = FingerCluster(
                cluster=_cluster_data(),
                side=KeyboardSide.RIGHT,
                width=600.0,
                layer_qmk_index=_LAYER_0,
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
                layer_qmk_index=_LAYER_0,
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
                layer_qmk_index=_LAYER_0,
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
                layer_qmk_index=_LAYER_0,
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
                layer_qmk_index=_LAYER_0,
                has_double_south=True,
            )
            without_ds = FingerCluster(
                cluster=_cluster_data(),
                side=KeyboardSide.RIGHT,
                width=600.0,
                layer_qmk_index=_LAYER_0,
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
                layer_qmk_index=_LAYER_0,
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
                layer_qmk_index=_LAYER_0,
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
                layer_qmk_index=_LAYER_0,
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

    def test_layer_switch_key_uses_destination_layer_color(self):
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
        ctx = RenderContext.build(_build_config(palette, (0, 1)), SvalboardKeymap(layers={}))

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
                layer_qmk_index=0,
                use_layer_colors_on_keys=True,
            )
        svg = str(_draw(cluster, Point(0.0, 0.0)).as_svg())
        # Layer 1's gradient[2] = "#cc00cc" should appear (the north
        # key's fill).
        assert "#cc00cc" in svg.lower()

    def test_layer_switch_disabled_keeps_default_color(self):
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
        ctx = RenderContext.build(_build_config(palette, (0, 1)), SvalboardKeymap(layers={}))

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
                layer_qmk_index=0,
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
                layer_qmk_index=_LAYER_0,
            )
        # Centre key's label colour is computed from its fill — it
        # should NOT be the standard ``#ffffff`` palette label
        # colour. We can't easily assert the exact ghost colour
        # without re-running the calculation, but we can assert the
        # cluster's metrics are still produced (smoke test).
        assert cluster.metrics.center_key is not None


# ---------------------------------------------------------------------------
# Layer indicators — wiring + metrics + drawing
# ---------------------------------------------------------------------------


def _two_layer_palette() -> Palette:
    """Palette with two distinct layer gradients so layer-switch
    indicators have a target colour to resolve to. Layer 1's
    ``base_color`` (#11ee22) and ``gradient[4]`` (#11ee2e) appear in
    indicator SVG; the values are spelled with no overlap with
    layer-0's gradient so colour-presence assertions stay specific."""
    layer0 = LayerColor(
        base_color="#000000",
        gradient=("#100000", "#200000", "#300000", "#400000", "#500000", "#600000"),
    )
    layer1 = LayerColor(
        base_color="#11ee22",
        gradient=("#11ee2a", "#11ee2b", "#11ee2c", "#11ee2d", "#11ee2e", "#11ee2f"),
    )
    return Palette(
        layers=(layer0, layer1),
        text_color="#000000",
        key_label_color="#ffffff",
        background_color="#ffffff",
        border_color="#000000",
        macro_color="#000000",
        tap_dance_color="#000000",
        neutral_color="#666666",
    )


def _two_layer_ctx() -> RenderContext:
    """Render context wired with the two-layer palette (QMK indices
    0 and 1). Tests that exercise layer-switch destination resolution
    use this to make sure ``ctx.theme.palette`` knows about layer 1."""
    return RenderContext.build(
        _build_config(_two_layer_palette(), (0, 1)),
        SvalboardKeymap(layers={}),
    )


class TestLayerIndicators:
    """Per-slot layer indicators wired into the cluster."""

    def test_indicator_metrics_none_for_non_layer_switch_slots(
        self, ctx: RenderContext, palette: Palette
    ):
        """Slots whose key has ``layer_switch=None`` expose ``None``
        for that slot's indicator metric — the parent layer composable
        uses presence to decide which slots to route connectors for."""
        with using_render_context(ctx):
            cluster = FingerCluster(
                cluster=_cluster_data(),
                side=KeyboardSide.RIGHT,
                width=600.0,
                layer_qmk_index=_LAYER_0,
            )
        ind = cluster.metrics.indicators
        assert ind.center_key is None
        assert ind.north_key is None
        assert ind.east_key is None
        assert ind.south_key is None
        assert ind.west_key is None
        assert ind.double_south_key is None

    def test_indicator_metrics_present_for_layer_switch_slot(self):
        """A slot with ``layer_switch=1`` exposes a populated
        :class:`LayerIndicatorMetrics` — the parent reads
        ``routing_origin`` / ``routing_direction`` off it without
        reaching back into the per-key composable."""
        ctx = _two_layer_ctx()
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
                layer_qmk_index=_LAYER_0,
            )
        ind = cluster.metrics.indicators.north_key
        assert ind is not None
        assert isinstance(ind, LayerIndicatorMetrics)
        # North-key indicator points NORTH (the key sits at the cluster
        # top edge); routing direction matches indicator direction.
        assert ind.routing_direction is CompassDirection.NORTH

    def test_show_layer_indicators_false_suppresses_metrics_and_paint(self):
        """Disabling indicators removes them from both the metrics
        and the SVG — the cluster paints keys only."""
        ctx = _two_layer_ctx()
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
                layer_qmk_index=_LAYER_0,
                show_layer_indicators=False,
            )
        assert cluster.metrics.indicators.north_key is None
        svg = str(_draw(cluster, Point(0.0, 0.0)).as_svg())
        # Layer 1's ``gradient[4]`` (the indicator stroke) must NOT
        # appear when indicators are disabled.
        assert "#11ee2e" not in svg.lower()

    def test_indicator_fill_uses_destination_layer_base_color(self):
        """The badge fills with the destination layer's
        ``base_color`` — visual cue for "this jumps to layer N"."""
        ctx = _two_layer_ctx()
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
                layer_qmk_index=_LAYER_0,
                use_layer_colors_on_keys=False,
            )
        svg = str(_draw(cluster, Point(0.0, 0.0)).as_svg())
        # Layer 1's base_color is the indicator fill.
        assert "#11ee22" in svg.lower()
        # Layer 1's gradient[4] is the indicator stroke.
        assert "#11ee2e" in svg.lower()

    def test_indicator_label_shows_target_layer_number(self):
        """The badge carries the destination layer's index as its
        text label."""
        ctx = _two_layer_ctx()
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
                layer_qmk_index=_LAYER_0,
            )
        svg = str(_draw(cluster, Point(0.0, 0.0)).as_svg())
        # The ``>1<`` text content is the indicator label.
        assert ">1<" in svg

    def test_indicator_metrics_anchor_to_key_origin(self):
        """The indicator's ``circle_center`` lies in cluster-local
        coordinates: it's the key origin plus the key-local anchor
        plus the gap+radius offset along the indicator direction.
        The cluster paints the indicator at the key's slot origin so
        the indicator metrics' coordinates remain key-local."""
        ctx = _two_layer_ctx()
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
                layer_qmk_index=_LAYER_0,
            )
        north_ind = cluster.metrics.indicators.north_key
        north_key = cluster.metrics.north_key
        assert north_ind is not None
        # The circle's centre is on a vector from the key-local
        # anchor along the indicator direction. For NORTH that's
        # purely upward (negative y), so cx == anchor.x and cy <
        # anchor.y.
        assert north_ind.circle_center.x == pytest.approx(north_key.indicator_anchor.x)
        assert north_ind.circle_center.y < north_key.indicator_anchor.y

    def test_center_key_indicator_uses_larger_gap(self, ctx: RenderContext):
        """The centre key's indicator sits diagonally past the
        surrounding outer keys — a 3× gap multiplier keeps the badge
        clear of the E / W / S edges. Compared to a directional key
        with the same diameter at the same outward direction, the
        centre-key circle's distance from its anchor is larger."""
        cluster_data = FingerClusterData(
            center_key=_td_key("C", layer_switch=1),
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
                layer_qmk_index=_LAYER_0,
            )
        center_ind = cluster.metrics.indicators.center_key
        north_ind = cluster.metrics.indicators.north_key
        assert center_ind is not None and north_ind is not None
        # Same circle radius (proportional to the cluster's outer
        # width), so any difference in (gap+radius) distance must
        # come from the gap. The centre's ``gap+radius`` distance
        # should clearly exceed the north's.
        center_anchor = cluster.metrics.center_key.indicator_anchor
        north_anchor = cluster.metrics.north_key.indicator_anchor
        center_radial = (
            (center_ind.circle_center.x - center_anchor.x) ** 2
            + (center_ind.circle_center.y - center_anchor.y) ** 2
        ) ** 0.5
        north_radial = (
            (north_ind.circle_center.x - north_anchor.x) ** 2
            + (north_ind.circle_center.y - north_anchor.y) ** 2
        ) ** 0.5
        # Same radius on both, so the centre's gap is larger ⇒ the
        # centre's radial distance exceeds the north's.
        assert center_ind.circle_radius == pytest.approx(north_ind.circle_radius)
        assert center_radial > north_radial

    def test_out_of_range_target_layer_falls_back_to_neutral_grey(self, ctx: RenderContext):
        """A ``layer_switch`` index that ``qmk_index_to_position``
        maps outside the palette range paints in neutral fallback
        colours rather than crashing — keeps the indicator visible
        even with a stray layer reference."""
        cluster_data = FingerClusterData(
            center_key=_td_key("C"),
            north_key=_td_key("N", layer_switch=99),  # well past the palette
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
                layer_qmk_index=_LAYER_0,
            )
        svg = str(_draw(cluster, Point(0.0, 0.0)).as_svg())
        # Neutral fallback fill / stroke from the cluster module.
        assert "#808080" in svg.lower()
        assert "#606060" in svg.lower()


# ===========================================================================
# Thumb cluster
# ===========================================================================


def _thumb_cluster_data() -> ThumbClusterData[SvalboardTargetKey]:
    """A simple thumb cluster with distinct labels per slot."""
    return ThumbClusterData(
        down_key=_td_key("DN"),
        pad_key=_td_key("PD"),
        up_key=_td_key("UP"),
        nail_key=_td_key("NL"),
        knuckle_key=_td_key("KN"),
        double_down_key=_td_key("DD"),
    )


# ---------------------------------------------------------------------------
# Layout / size
# ---------------------------------------------------------------------------


class TestThumbLayout:
    """Cluster layout — bbox shape and per-key positions."""

    def test_size_hugs_deepest_key(self, ctx: RenderContext, palette: Palette):
        """Reported ``Size.height`` matches the deepest painted key's
        bottom edge — the down key, which extends to ``0.25 * width *
        2.6 = 0.65 * width`` from ``y=0``. Internal layout still uses
        the legacy 1.5:1 cluster bbox to anchor up / knuckle slots on
        ``center_y``; only the reported bbox shrinks so callers don't
        reserve empty space below the down key."""
        with using_render_context(ctx):
            cluster = ThumbCluster(
                cluster=_thumb_cluster_data(),
                side=KeyboardSide.RIGHT,
                width=600.0,
                layer_qmk_index=_LAYER_0,
            )
        assert cluster.size.width == 600.0
        # 0.25 (down_w fraction) * 2.6 (down height ratio) = 0.65.
        assert cluster.size.height == pytest.approx(600.0 * 0.65)


# ---------------------------------------------------------------------------
# Metrics — per-key SvalboardKeyMetrics surfaced by slot
# ---------------------------------------------------------------------------


class TestThumbMetrics:
    """Cluster metrics expose per-key indicator metrics by slot."""

    def test_metrics_typed_subclass(self, ctx: RenderContext, palette: Palette):
        with using_render_context(ctx):
            cluster = ThumbCluster(
                cluster=_thumb_cluster_data(),
                side=KeyboardSide.RIGHT,
                width=600.0,
                layer_qmk_index=_LAYER_0,
            )
        assert isinstance(cluster.metrics, ThumbClusterMetrics)

    def test_per_slot_indicator_directions_right_side(self, ctx: RenderContext, palette: Palette):
        """Right-hand reference: down / pad / up indicators outward
        (EAST), nail / knuckle inward (WEST), double-down NORTH."""
        with using_render_context(ctx):
            cluster = ThumbCluster(
                cluster=_thumb_cluster_data(),
                side=KeyboardSide.RIGHT,
                width=600.0,
                layer_qmk_index=_LAYER_0,
            )
        m = cluster.metrics
        assert m.down_key.indicator_direction is CompassDirection.EAST
        assert m.pad_key.indicator_direction is CompassDirection.EAST
        assert m.up_key.indicator_direction is CompassDirection.EAST
        assert m.nail_key.indicator_direction is CompassDirection.WEST
        assert m.knuckle_key.indicator_direction is CompassDirection.WEST
        assert m.double_down_key.indicator_direction is CompassDirection.NORTH

    def test_per_slot_indicator_directions_left_side(self, ctx: RenderContext, palette: Palette):
        """Left-hand reference: directions flip horizontally — outward
        becomes WEST and inward becomes EAST. Double-down's NORTH
        anchor stays NORTH (mirror-invariant)."""
        with using_render_context(ctx):
            cluster = ThumbCluster(
                cluster=_thumb_cluster_data(),
                side=KeyboardSide.LEFT,
                width=600.0,
                layer_qmk_index=_LAYER_0,
            )
        m = cluster.metrics
        assert m.down_key.indicator_direction is CompassDirection.WEST
        assert m.pad_key.indicator_direction is CompassDirection.WEST
        assert m.nail_key.indicator_direction is CompassDirection.EAST
        assert m.double_down_key.indicator_direction is CompassDirection.NORTH


# ---------------------------------------------------------------------------
# Drawing — every key paints into the SVG
# ---------------------------------------------------------------------------


class TestThumbDrawing:
    """SVG output covers every slot's label."""

    def test_every_slot_label_lands_in_svg(self, ctx: RenderContext, palette: Palette):
        with using_render_context(ctx):
            cluster = ThumbCluster(
                cluster=_thumb_cluster_data(),
                side=KeyboardSide.RIGHT,
                width=600.0,
                layer_qmk_index=_LAYER_0,
            )
        svg = str(_draw(cluster, Point(0.0, 0.0)).as_svg())
        for label in ("DN", "PD", "UP", "NL", "KN", "DD"):
            assert f">{label}<" in svg

    def test_reported_width_matches_input_width(self, ctx: RenderContext, palette: Palette):
        width = 600.0
        with using_render_context(ctx):
            cluster = ThumbCluster(
                cluster=_thumb_cluster_data(),
                side=KeyboardSide.RIGHT,
                width=width,
                layer_qmk_index=_LAYER_0,
            )
        assert cluster.size.width == width


# ---------------------------------------------------------------------------
# Colour resolution — layer-switch keys, transparent ghost colour, defaults
# ---------------------------------------------------------------------------


class TestThumbColorResolution:
    """Per-slot defaults pull from the right palette / layer source."""

    def test_pad_default_uses_palette_neutral(self):
        """Pad / nail / knuckle paint in ``palette.neutral_color`` by
        default — flat keys that don't carry the layer colour."""
        layer = LayerColor(
            base_color="#aabbcc",
            gradient=("#100000", "#200000", "#300000", "#400000", "#500000", "#600000"),
        )
        palette = Palette(
            layers=(layer,),
            text_color="#000000",
            key_label_color="#ffffff",
            background_color="#ffffff",
            border_color="#000000",
            macro_color="#000000",
            tap_dance_color="#000000",
            neutral_color="#deadbe",  # distinctive — easy to spot in SVG
        )
        ctx = RenderContext.build(_build_config(palette), SvalboardKeymap(layers={}))
        with using_render_context(ctx):
            cluster = ThumbCluster(
                cluster=_thumb_cluster_data(),
                side=KeyboardSide.RIGHT,
                width=600.0,
                layer_qmk_index=_LAYER_0,
            )
        svg = str(_draw(cluster, Point(0.0, 0.0)).as_svg())
        assert "#deadbe" in svg.lower()  # neutral colour landed somewhere

    def test_layer_switch_key_uses_destination_layer_color(self):
        """Same layer-switch behaviour as :class:`FingerCluster`: a
        thumb key with ``layer_switch=1`` paints in layer 1's
        gradient colour when ``use_layer_colors_on_keys=True``."""
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
        ctx = RenderContext.build(_build_config(palette, (0, 1)), SvalboardKeymap(layers={}))
        cluster_data = ThumbClusterData(
            down_key=_td_key("DN"),
            pad_key=_td_key("PD", layer_switch=1),
            up_key=_td_key("UP"),
            nail_key=_td_key("NL"),
            knuckle_key=_td_key("KN"),
            double_down_key=_td_key("DD"),
        )
        with using_render_context(ctx):
            cluster = ThumbCluster(
                cluster=cluster_data,
                side=KeyboardSide.RIGHT,
                width=600.0,
                layer_qmk_index=0,
                use_layer_colors_on_keys=True,
            )
        svg = str(_draw(cluster, Point(0.0, 0.0)).as_svg())
        assert "#cc00cc" in svg.lower()


# ---------------------------------------------------------------------------
# Layer indicators — wiring + metrics
# ---------------------------------------------------------------------------


class TestThumbLayerIndicators:
    """Per-slot layer indicators wired into the thumb cluster."""

    def test_indicator_metrics_none_for_non_layer_switch_slots(
        self, ctx: RenderContext, palette: Palette
    ):
        with using_render_context(ctx):
            cluster = ThumbCluster(
                cluster=_thumb_cluster_data(),
                side=KeyboardSide.RIGHT,
                width=600.0,
                layer_qmk_index=_LAYER_0,
            )
        ind = cluster.metrics.indicators
        assert ind.down_key is None
        assert ind.pad_key is None
        assert ind.up_key is None
        assert ind.nail_key is None
        assert ind.knuckle_key is None
        assert ind.double_down_key is None

    def test_indicator_metrics_present_for_layer_switch_slot(self):
        """A slot with ``layer_switch`` exposes a populated
        :class:`LayerIndicatorMetrics` with the routing direction
        matching the slot's outward / inward orientation."""
        layer0 = LayerColor(
            base_color="#000000",
            gradient=("#100000", "#200000", "#300000", "#400000", "#500000", "#600000"),
        )
        layer1 = LayerColor(
            base_color="#11ee22",
            gradient=("#11ee2a", "#11ee2b", "#11ee2c", "#11ee2d", "#11ee2e", "#11ee2f"),
        )
        palette = Palette(layers=(layer0, layer1), key_label_color="#ffffff")
        ctx = RenderContext.build(_build_config(palette, (0, 1)), SvalboardKeymap(layers={}))
        cluster_data = ThumbClusterData(
            down_key=_td_key("DN"),
            pad_key=_td_key("PD"),
            up_key=_td_key("UP"),
            nail_key=_td_key("NL"),
            knuckle_key=_td_key("KN"),
            double_down_key=_td_key("DD", layer_switch=1),
        )
        with using_render_context(ctx):
            cluster = ThumbCluster(
                cluster=cluster_data,
                side=KeyboardSide.RIGHT,
                width=600.0,
                layer_qmk_index=0,
            )
        ind = cluster.metrics.indicators.double_down_key
        assert ind is not None
        assert isinstance(ind, LayerIndicatorMetrics)
        assert ind.routing_direction is CompassDirection.NORTH

    def test_show_layer_indicators_false_suppresses_metrics(self):
        layer0 = LayerColor(
            base_color="#000000",
            gradient=("#100000", "#200000", "#300000", "#400000", "#500000", "#600000"),
        )
        layer1 = LayerColor(
            base_color="#11ee22",
            gradient=("#11ee2a", "#11ee2b", "#11ee2c", "#11ee2d", "#11ee2e", "#11ee2f"),
        )
        palette = Palette(layers=(layer0, layer1), key_label_color="#ffffff")
        ctx = RenderContext.build(_build_config(palette, (0, 1)), SvalboardKeymap(layers={}))
        cluster_data = ThumbClusterData(
            down_key=_td_key("DN", layer_switch=1),
            pad_key=_td_key("PD"),
            up_key=_td_key("UP"),
            nail_key=_td_key("NL"),
            knuckle_key=_td_key("KN"),
            double_down_key=_td_key("DD"),
        )
        with using_render_context(ctx):
            cluster = ThumbCluster(
                cluster=cluster_data,
                side=KeyboardSide.RIGHT,
                width=600.0,
                layer_qmk_index=0,
                show_layer_indicators=False,
            )
        assert cluster.metrics.indicators.down_key is None

    def test_dd_indicator_clears_down_top(self):
        """The double-down indicator's circle should sit clear of the
        DOWN key's top edge — not just the DD key's top edge. Down
        starts at ``y=0``; DD starts at ``y=2*inset``, so DD's
        indicator needs ``gap + 2*inset`` of vertical clearance to
        keep the badge ``gap`` away from the cluster's outermost top
        edge."""
        layer0 = LayerColor(
            base_color="#000000",
            gradient=("#100000", "#200000", "#300000", "#400000", "#500000", "#600000"),
        )
        layer1 = LayerColor(
            base_color="#11ee22",
            gradient=("#11ee2a", "#11ee2b", "#11ee2c", "#11ee2d", "#11ee2e", "#11ee2f"),
        )
        palette = Palette(layers=(layer0, layer1), key_label_color="#ffffff")
        ctx = RenderContext.build(_build_config(palette, (0, 1)), SvalboardKeymap(layers={}))
        cluster_data = ThumbClusterData(
            down_key=_td_key("DN"),
            pad_key=_td_key("PD"),
            up_key=_td_key("UP"),
            nail_key=_td_key("NL"),
            knuckle_key=_td_key("KN"),
            double_down_key=_td_key("DD", layer_switch=1),
        )
        cluster_width = 600.0
        with using_render_context(ctx):
            cluster = ThumbCluster(
                cluster=cluster_data,
                side=KeyboardSide.RIGHT,
                width=cluster_width,
                layer_qmk_index=0,
            )
        dd_ind = cluster.metrics.indicators.double_down_key
        dd_metrics = cluster.metrics.double_down_key
        assert dd_ind is not None
        # ``LayerIndicatorMetrics`` are in DD-LOCAL coords (the
        # indicator paints at DD's origin). DD's anchor is at y=0
        # in DD-local coords (the NORTH edge); the circle centre sits
        # ``gap + 2*inset + radius`` ABOVE the anchor in NORTH (i.e.,
        # at y = -(gap + 2*inset + radius)).
        inset = cluster_width * 0.038
        radius = dd_ind.circle_radius
        # Layer-indicator gap is now doc-width-relative (the legacy
        # ``down_width * 0.18`` was per-cluster; the unified default
        # is ``doc_width * 12/1600``). Default config doc_width = 1600.
        gap = 1600.0 * 12.0 / 1600.0
        expected_circle_cy = -(gap + 2 * inset + radius)
        assert dd_ind.circle_center.y == pytest.approx(expected_circle_cy)
        # Translated to cluster-relative coords (DD origin + DD-local
        # circle bottom), the circle's bottom edge sits ``gap`` above
        # the cluster top (y=0).
        dd_origin_y = 2 * inset
        circle_bottom_cluster = dd_origin_y + dd_ind.circle_center.y + radius
        assert circle_bottom_cluster == pytest.approx(-gap)
        # Sanity: anchor unchanged + direction stays NORTH.
        assert dd_ind.routing_direction is CompassDirection.NORTH
        assert dd_metrics.indicator_anchor.y == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# _ThumbKeyColors dataclass shape
# ---------------------------------------------------------------------------


class TestThumbKeyColorsShape:
    """``_ThumbKeyColors`` no longer carries a stroke field — DD and
    UP have stopped consuming it."""

    def test_dataclass_has_no_stroke_field(self):
        import dataclasses

        from skim.application.render.svalboard_clusters import _ThumbKeyColors

        field_names = {f.name for f in dataclasses.fields(_ThumbKeyColors)}
        assert field_names == {"fill", "label"}


class TestCutoutOutsetDivisor:
    """The DD/UP cutouts in Down are sized as ``thumb_key_gap /
    _DOWN_CUTOUT_OUTSET_DIVISOR`` — i.e. the rim band scales with the
    side gap between Down and the surrounding keys, not with the
    cutout's own width."""

    def test_divisor_value(self):
        assert _DOWN_CUTOUT_OUTSET_DIVISOR == 3.0


class TestDownCutouts:
    """ThumbCluster computes Down's rendered ``<path>`` as a true
    Boolean subtraction (Down minus DD minus UP) via Skia PathOps.
    The holes are real edges of Down's geometry — a stroke or any
    other outline-aware effect traces both the outer outline and
    the rims of the holes — and no spillover sits outside Down's
    outline (XOR / fill-rule="evenodd" would produce that)."""

    def test_no_clippath_emitted(self, ctx: RenderContext, palette: Palette):
        """No ``<clipPath>`` — cutouts are baked into Down's path."""
        cluster_data = ThumbClusterData(
            down_key=_td_key(label="DOWN"),
            pad_key=_td_key(label="PAD"),
            up_key=_td_key(label="UP"),
            nail_key=_td_key(label="NAIL"),
            knuckle_key=_td_key(label="KNUCKLE"),
            double_down_key=_td_key(label="DD"),
        )
        with using_render_context(ctx):
            cluster = ThumbCluster(
                cluster=cluster_data,
                side=KeyboardSide.RIGHT,
                width=200.0,
                layer_qmk_index=_LAYER_0,
            )
        svg = str(_draw(cluster, Point(0, 0)).as_svg())
        assert "<clipPath" not in svg
        assert "clip-path=" not in svg

    def test_down_path_uses_real_subtraction_not_evenodd(
        self, ctx: RenderContext, palette: Palette
    ):
        """No ``fill-rule="evenodd"`` anywhere — the subtraction is real.
        Down's rendered path is the geometric difference Down minus DD
        minus UP. Because UP overlaps Down's outer edge, Skia turns UP
        into a notch in the outline (not a separate hole); DD, fully
        inside Down, becomes an inner hole. So the resulting path has
        between 1 and 3 ``M``-subpaths depending on overlap geometry —
        the invariant we pin is "no spillover": the path's bounding
        box must not exceed Down's original bounding box."""
        import re

        cluster_data = ThumbClusterData(
            down_key=_td_key(label="DOWN"),
            pad_key=_td_key(label="PAD"),
            up_key=_td_key(label="UP"),
            nail_key=_td_key(label="NAIL"),
            knuckle_key=_td_key(label="KNUCKLE"),
            double_down_key=_td_key(label="DD"),
        )
        with using_render_context(ctx):
            cluster = ThumbCluster(
                cluster=cluster_data,
                side=KeyboardSide.RIGHT,
                width=200.0,
                layer_qmk_index=_LAYER_0,
            )
        svg = str(_draw(cluster, Point(0, 0)).as_svg())
        assert 'fill-rule="evenodd"' not in svg

        # Find Down's path: it's the largest path (longest d-string)
        # that uses cubic ``C`` commands (Skia's output for the
        # rounded corners). Other thumb keys still use ``A`` arcs.
        down_d = ""
        for m in re.finditer(r'<path d="([^"]*)"', svg):
            d_str = m.group(1)
            if "C" in d_str and len(d_str) > len(down_d):
                down_d = d_str
        assert down_d, f"no skia-emitted path found in {svg!r}"

        # Extract every coordinate in the d-string and assert the bbox
        # never exceeds Down's bounding box plus a sub-pixel tolerance.
        # cluster ``width=200`` → Down's slot sits at right side; check
        # that no X coordinate exceeds the cluster width.
        coords = [float(n) for n in re.findall(r"-?\d+\.?\d*", down_d)]
        max_x_in_down = max(coords[::2])  # x coords (every other)
        assert max_x_in_down <= 200.0 + 1e-3, (
            f"Down's path extends past x=200: max x = {max_x_in_down}"
        )
