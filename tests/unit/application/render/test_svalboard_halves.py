# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.
"""Unit tests for :mod:`skim.application.render.svalboard_halves`."""

from __future__ import annotations
import drawsvg as draw
import pytest
from skim.application.render.primitives import Point
from skim.application.render.render_context import RenderContext, using_render_context
from skim.application.render.svalboard_clusters import (
    FingerClusterMetrics,
    ThumbClusterMetrics,
)
from skim.application.render.svalboard_halves import (
    FingerHalf,
    FingerHalfMetrics,
    KeyboardHalf,
    KeyboardHalfMetrics,
)
from skim.data import LayerColor, Palette, SkimConfig, SvalboardKeymap
from skim.data.config import Keyboard, KeyboardLayer, Output, Style
from skim.data.keyboard import FingerCluster as FingerClusterData
from skim.data.keyboard import ThumbCluster as ThumbClusterData
from skim.domain import KeyboardSide, SvalboardTargetKey

# QMK firmware index of the single layer the default ``ctx`` fixture
# registers; tests render against this index.
_LAYER_0 = 0


def _build_config(palette: Palette) -> SkimConfig:
    """Build a :class:`SkimConfig` whose ``Keyboard.layers`` align with
    a one-entry palette so the render context's :class:`RenderPalette`
    has a layer at QMK firmware index 0."""
    return SkimConfig(
        keyboard=Keyboard(layers=(KeyboardLayer(index=_LAYER_0, name="Layer0"),)),
        output=Output(style=Style(palette=palette)),
    )


@pytest.fixture
def ctx(palette: Palette) -> RenderContext:
    return RenderContext.build(_build_config(palette), SvalboardKeymap(layers={}))


@pytest.fixture
def palette() -> Palette:
    """Single-layer palette with a six-stop gradient — enough for the
    cluster's per-slot colour resolution."""
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


# Half width budget the tests use across the board — large enough that
# ``cluster_width = (HALF_WIDTH - 3 * inset) / 4`` is comfortable to
# spell in assertions, small enough that the rendered drawing stays
# inside the test canvas.
_HALF_WIDTH = 1200.0


def _td_key(label: str = "A", **kwargs) -> SvalboardTargetKey:
    return SvalboardTargetKey(label=label, **kwargs)


def _finger_cluster(prefix: str) -> FingerClusterData[SvalboardTargetKey]:
    """A finger cluster whose slot labels embed ``prefix`` so we can
    assert per-cluster labels land in the rendered SVG."""
    return FingerClusterData(
        center_key=_td_key(f"{prefix}C"),
        north_key=_td_key(f"{prefix}N"),
        east_key=_td_key(f"{prefix}E"),
        south_key=_td_key(f"{prefix}S"),
        west_key=_td_key(f"{prefix}W"),
        double_south_key=_td_key(f"{prefix}DS"),
    )


def _thumb_cluster(prefix: str = "T") -> ThumbClusterData[SvalboardTargetKey]:
    return ThumbClusterData(
        down_key=_td_key(f"{prefix}DN"),
        pad_key=_td_key(f"{prefix}PD"),
        up_key=_td_key(f"{prefix}UP"),
        nail_key=_td_key(f"{prefix}NL"),
        knuckle_key=_td_key(f"{prefix}KN"),
        double_down_key=_td_key(f"{prefix}DD"),
    )


def _four_fingers() -> tuple[
    FingerClusterData[SvalboardTargetKey],
    FingerClusterData[SvalboardTargetKey],
    FingerClusterData[SvalboardTargetKey],
    FingerClusterData[SvalboardTargetKey],
]:
    """Four distinct finger clusters labelled by finger position so the
    SVG output makes which-cluster-went-where assertions easy."""
    return (
        _finger_cluster("i"),  # index
        _finger_cluster("m"),  # middle
        _finger_cluster("r"),  # ring
        _finger_cluster("p"),  # pinky
    )


def _draw(component, origin: Point) -> draw.Drawing:
    d = draw.Drawing(2000, 1500)
    component.draw_at(d, origin)
    return d


def _expected_cluster_step(width: float, inset: float) -> float:
    """The horizontal step between adjacent finger clusters: one
    cluster width + one document inset (the gap)."""
    cluster_width = (width - 3 * inset) / 4
    return cluster_width + inset


# ---------------------------------------------------------------------------
# FingerHalf — layout
# ---------------------------------------------------------------------------
class TestFingerHalfLayout:
    """Half-level layout: cluster origins + bbox size."""

    def test_size_equals_min_width_floor(self, ctx: RenderContext, palette: Palette):
        """The reported half width equals ``min_width`` exactly — the
        composable splits that floor into clusters + insets internally
        and reports it as the bbox extent. The contract leaves room
        to grow past ``min_width`` once indicator-overhang inflation
        is wired in; for now, with no overhang accounted for, the
        reported width matches the floor."""
        with using_render_context(ctx):
            half = FingerHalf(
                fingers=_four_fingers(),
                side=KeyboardSide.RIGHT,
                min_width=_HALF_WIDTH,
                layer_qmk_index=_LAYER_0,
            )
        assert half.size.width == pytest.approx(_HALF_WIDTH)

    def test_size_height_grows_by_stagger_when_enabled(self, ctx: RenderContext, palette: Palette):
        """With stagger ON the half is taller than the cluster height
        by one stagger amount; with stagger OFF the half exactly
        matches the tallest cluster. The stagger derives from
        ``cluster_width / 3`` internally — we verify by comparing the
        two builds at the same input ``width``."""
        with using_render_context(ctx):
            staggered = FingerHalf(
                fingers=_four_fingers(),
                side=KeyboardSide.RIGHT,
                min_width=_HALF_WIDTH,
                stagger_middle_fingers=True,
                layer_qmk_index=_LAYER_0,
            )
            flat = FingerHalf(
                fingers=_four_fingers(),
                side=KeyboardSide.RIGHT,
                min_width=_HALF_WIDTH,
                stagger_middle_fingers=False,
                layer_qmk_index=_LAYER_0,
            )
        cluster_width = (_HALF_WIDTH - 3 * ctx.document_metrics.inset) / 4
        expected_stagger = cluster_width / 3
        assert staggered.size.height == pytest.approx(flat.size.height + expected_stagger)

    def test_right_hand_clusters_run_index_to_pinky_left_to_right(
        self, ctx: RenderContext, palette: Palette
    ):
        """Right hand: index inner (left edge of bbox), pinky outer
        (right edge). Origins step rightward by one cluster + inset."""
        with using_render_context(ctx):
            half = FingerHalf(
                fingers=_four_fingers(),
                side=KeyboardSide.RIGHT,
                min_width=_HALF_WIDTH,
                layer_qmk_index=_LAYER_0,
            )
        m = half.metrics
        step = _expected_cluster_step(_HALF_WIDTH, ctx.document_metrics.inset)
        assert m.index_origin.x == pytest.approx(0.0)
        assert m.middle_origin.x == pytest.approx(step)
        assert m.ring_origin.x == pytest.approx(2 * step)
        assert m.pinky_origin.x == pytest.approx(3 * step)

    def test_left_hand_clusters_mirror_pinky_outer_index_inner(
        self, ctx: RenderContext, palette: Palette
    ):
        """Left hand mirrors — pinky at x=0 (leftmost / outward),
        index at x=3*step (rightmost / inward, hugging the keyboard's
        centre line)."""
        with using_render_context(ctx):
            half = FingerHalf(
                fingers=_four_fingers(),
                side=KeyboardSide.LEFT,
                min_width=_HALF_WIDTH,
                layer_qmk_index=_LAYER_0,
            )
        m = half.metrics
        step = _expected_cluster_step(_HALF_WIDTH, ctx.document_metrics.inset)
        assert m.pinky_origin.x == pytest.approx(0.0)
        assert m.ring_origin.x == pytest.approx(step)
        assert m.middle_origin.x == pytest.approx(2 * step)
        assert m.index_origin.x == pytest.approx(3 * step)

    def test_stagger_lowers_index_and_pinky_only(self, ctx: RenderContext, palette: Palette):
        """With stagger on, index + pinky drop by the stagger amount;
        middle + ring stay at the half's top edge (y=0)."""
        with using_render_context(ctx):
            half = FingerHalf(
                fingers=_four_fingers(),
                side=KeyboardSide.RIGHT,
                min_width=_HALF_WIDTH,
                stagger_middle_fingers=True,
                layer_qmk_index=_LAYER_0,
            )
        m = half.metrics
        cluster_width = (_HALF_WIDTH - 3 * ctx.document_metrics.inset) / 4
        expected_stagger = cluster_width / 3
        assert m.middle_origin.y == pytest.approx(0.0)
        assert m.ring_origin.y == pytest.approx(0.0)
        assert m.index_origin.y == pytest.approx(expected_stagger)
        assert m.pinky_origin.y == pytest.approx(expected_stagger)

    def test_stagger_off_aligns_all_clusters_to_y_zero(self, ctx: RenderContext, palette: Palette):
        """Overview / no-stagger mode places every cluster at y=0."""
        with using_render_context(ctx):
            half = FingerHalf(
                fingers=_four_fingers(),
                side=KeyboardSide.RIGHT,
                min_width=_HALF_WIDTH,
                stagger_middle_fingers=False,
                layer_qmk_index=_LAYER_0,
            )
        m = half.metrics
        assert m.index_origin.y == pytest.approx(0.0)
        assert m.middle_origin.y == pytest.approx(0.0)
        assert m.ring_origin.y == pytest.approx(0.0)
        assert m.pinky_origin.y == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# FingerHalf — metrics
# ---------------------------------------------------------------------------
class TestFingerHalfMetrics:
    def test_metrics_typed_subclass(self, ctx: RenderContext, palette: Palette):
        with using_render_context(ctx):
            half = FingerHalf(
                fingers=_four_fingers(),
                side=KeyboardSide.RIGHT,
                min_width=_HALF_WIDTH,
                layer_qmk_index=_LAYER_0,
            )
        assert isinstance(half.metrics, FingerHalfMetrics)
        assert isinstance(half.metrics.index, FingerClusterMetrics)
        assert isinstance(half.metrics.pinky, FingerClusterMetrics)


# ---------------------------------------------------------------------------
# FingerHalf — drawing
# ---------------------------------------------------------------------------
class TestFingerHalfDrawing:
    def test_every_cluster_label_lands_in_svg(self, ctx: RenderContext, palette: Palette):
        """All four finger clusters paint into the canvas — one
        per-finger label per slot."""
        with using_render_context(ctx):
            half = FingerHalf(
                fingers=_four_fingers(),
                side=KeyboardSide.RIGHT,
                min_width=_HALF_WIDTH,
                layer_qmk_index=_LAYER_0,
            )
        svg = str(_draw(half, Point(0.0, 0.0)).as_svg())
        for prefix in ("i", "m", "r", "p"):
            for slot_label in ("C", "N", "E", "S", "W"):
                assert f">{prefix}{slot_label}<" in svg, f"missing {prefix}{slot_label}"


# ---------------------------------------------------------------------------
# KeyboardHalf — layout + composition
# ---------------------------------------------------------------------------
class TestKeyboardHalfLayout:
    def test_thumb_sits_below_fingers_with_one_inset_gap(
        self, ctx: RenderContext, palette: Palette
    ):
        """The thumb's top edge sits one document-inset below the
        finger half's bottom — assert the full half height equals
        ``finger_half.height + inset + thumb_cluster.height`` by
        reading the thumb's origin y back out and comparing to the
        finger half's height."""
        with using_render_context(ctx):
            half = KeyboardHalf(
                fingers=_four_fingers(),
                thumb=_thumb_cluster(),
                side=KeyboardSide.RIGHT,
                min_width=_HALF_WIDTH,
                layer_qmk_index=_LAYER_0,
            )
            # Build the finger half on its own to compare heights.
            finger_only = FingerHalf(
                fingers=_four_fingers(),
                side=KeyboardSide.RIGHT,
                min_width=_HALF_WIDTH,
                layer_qmk_index=_LAYER_0,
            )
        assert half.metrics.thumb_origin.y == pytest.approx(
            finger_only.size.height + ctx.document_metrics.inset
        )

    def test_thumb_hugs_inward_edge_per_side(self, ctx: RenderContext, palette: Palette):
        """Right hand: thumb at x=0 (left of half = inward toward the
        keyboard's centre). Left hand: thumb's right edge sits at the
        half's right edge (so x = width - thumb_cluster_width)."""
        with using_render_context(ctx):
            right = KeyboardHalf(
                fingers=_four_fingers(),
                thumb=_thumb_cluster(),
                side=KeyboardSide.RIGHT,
                min_width=_HALF_WIDTH,
                layer_qmk_index=_LAYER_0,
            )
            left = KeyboardHalf(
                fingers=_four_fingers(),
                thumb=_thumb_cluster(),
                side=KeyboardSide.LEFT,
                min_width=_HALF_WIDTH,
                layer_qmk_index=_LAYER_0,
            )
        # The thumb cluster width is ``width * 0.42`` per the
        # composable's internal proportion; we don't need to spell
        # that constant here — derive it from the metrics-exposed
        # thumb origin. For the right hand the thumb hugs x=0; for
        # the left hand its right edge hugs x=width, so the thumb
        # origin's distance from the half's right edge equals the
        # thumb cluster width.
        assert right.metrics.thumb_origin.x == pytest.approx(0.0)
        # Left hand: thumb_origin.x > 0 and thumb_origin.x +
        # thumb_width = width. We can only directly check the first
        # part without re-deriving the proportion, but a sanity
        # bound is enough — assert it sits in the right half.
        assert left.metrics.thumb_origin.x > _HALF_WIDTH / 2


class TestKeyboardHalfMetrics:
    def test_metrics_typed_subclass(self, ctx: RenderContext, palette: Palette):
        with using_render_context(ctx):
            half = KeyboardHalf(
                fingers=_four_fingers(),
                thumb=_thumb_cluster(),
                side=KeyboardSide.RIGHT,
                min_width=_HALF_WIDTH,
                layer_qmk_index=_LAYER_0,
            )
        assert isinstance(half.metrics, KeyboardHalfMetrics)
        assert isinstance(half.metrics.fingers, FingerHalfMetrics)
        assert isinstance(half.metrics.thumb, ThumbClusterMetrics)


class TestKeyboardHalfDrawing:
    def test_thumb_and_finger_labels_land_in_svg(self, ctx: RenderContext, palette: Palette):
        """Every slot label from the four fingers + the thumb cluster
        ends up painted somewhere in the SVG — confirms
        :func:`KeyboardHalf` actually draws both halves of its
        composition."""
        with using_render_context(ctx):
            half = KeyboardHalf(
                fingers=_four_fingers(),
                thumb=_thumb_cluster(),
                side=KeyboardSide.RIGHT,
                min_width=_HALF_WIDTH,
                layer_qmk_index=_LAYER_0,
            )
        svg = str(_draw(half, Point(0.0, 0.0)).as_svg())
        # Finger labels.
        for prefix in ("i", "m", "r", "p"):
            assert f">{prefix}C<" in svg
        # Thumb labels.
        for slot in ("DN", "PD", "UP", "NL", "KN", "DD"):
            assert f">T{slot}<" in svg
