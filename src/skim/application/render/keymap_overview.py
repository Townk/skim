# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Composable building blocks for the multi-layer overview image.

Mirrors the per-layer document pattern from :mod:`keymap_layer` —
identical spacing rules so the overview reads at the same visual
rhythm as the per-layer images. The spacing convention is uniform
across every image:

* ``inset`` is reserved for vertical spacing between elements stacked
  in a Column (and as the outer chrome's border-to-content gap).
* ``column_gap`` is the canonical horizontal spacing for any visual
  column arrangement.

Concrete sizes used by this composable:

* Inter-cluster horizontal gap inside a half = ``column_gap``
  (default :func:`FingerHalf` behaviour).
* Central gap between the two keyboard halves = ``2 * column_gap``.
* Badge column → cluster column gap = ``2 * column_gap`` — a primary
  visual divider, the same width as the central gap.
* Inter-row vertical gap = ``inset``.

Pieces:

* :func:`LayerBadge` — the small filled rectangle on the left of each
  row (layer name on layer rows, ``THUMBS`` on the thumb row).
* :func:`KeymapOverview` — the keyboard area, built from one
  :func:`LayerBadge` + two :func:`FingerHalf` (one per side) per
  layer, plus a thumb row carrying two :func:`ThumbCluster` (only
  the first layer's thumb cluster is shown). Each piece is
  positioned by an explicit overflow-aware placement algorithm so
  the body's bbox absorbs all chrome — :func:`KeymapOverview`
  exposes ``size`` only.
* :func:`KeymapOverviewDocument` — the full overview image. Stacks
  :func:`Header`, :func:`KeymapOverview`, the optional macro / TD
  legend, the optional symbol legend, and an optional :func:`Footer`
  in a :class:`Column`, then wraps the whole thing in
  :func:`KeymapDocument` for the rounded background border + content
  offset chrome.

Connectors are handled in a separate pass once the body has been
positioned — the cluster-level :class:`LayerIndicatorMetrics`
exposes the routing origin / direction the connector router needs.
"""

from __future__ import annotations

from dataclasses import dataclass

import drawsvg as draw

from skim.data import KeycodeMappings, SkimConfig, SvalboardKeymap
from skim.domain import KeyboardSide, SvalboardTargetKey

from .composable import Composable
from .connectors import (
    ConnectorRouting,
    OverviewLayerSource,
    ThumbSource,
    route_overview_connectors,
)
from .footer import Footer
from .header import Header
from .keymap_document import KeymapDocument
from .legend import all_macros, all_tap_dances
from .macros import MacroSection
from .primitives import (
    Column,
    Component,
    MetricsComponent,
    Point,
    Row,
    Size,
    Spacer,
)
from .render_context import RenderContext, using_render_context
from .svalboard_clusters import ThumbCluster
from .svalboard_halves import FingerHalf
from .symbol_legend import collect_used_descriptions
from .symbols import FlowDirection, SymbolSection
from .tap_dance import TapDanceSection
from .text import Font

# ---------------------------------------------------------------------------
# Sizing constants
# ---------------------------------------------------------------------------

# Central gap between the two keyboard halves, in units of
# ``DocumentMetrics.inset`` — matches the per-layer image's
# :data:`keymap_layer._CENTER_GAP_INSET_COUNT` so the overview's halves
# breathe the same way as the per-layer image's halves.
_CENTER_GAP_INSET_COUNT = 2.0

# Thumb cluster width as a proportion of one keyboard side's width —
# matches :data:`keymap_layer._THUMB_CLUSTER_WIDTH_PROPORTION`.
_THUMB_CLUSTER_WIDTH_PROPORTION = 0.42

# Outer-key-width proportion inside one finger cluster — matches
# :data:`svalboard_clusters._OUTER_KEY_WIDTH_PROPORTION`. Used to
# derive the layer-badge height (one outer-key tall) without reaching
# into another module's privates.
_OUTER_KEY_PROPORTION = 0.328

# Badge font size as a fraction of badge height.
_BADGE_FONT_SIZE_RATIO = 0.45

# Badge corner radius as a fraction of badge height.
_BADGE_BORDER_RADIUS_RATIO = 0.2

# Variant label vertical offset above/below the badge, expressed as a
# fraction of the badge font size. Also used as the gap between the
# LAYERS heading text's after-edge baseline and the first badge's top.
_VARIANT_LABEL_OFFSET_RATIO_OF_FONT = 0.2

# Internal badge text padding, expressed as fractions of the document
# width — kept on the legacy ratios so badge typography stays
# unchanged across the migration.
_BADGE_PADDING_LEFT_RATIO = 15 / 1600
_BADGE_PADDING_RIGHT_RATIO = 30 / 1600

# Connector routing constants — mirrored from the legacy overview so
# the new path produces identical-rhythm dotted lines. ``keymap_spacing``
# (the routing-lane / column spacing) is ``0.6`` of an outer-key width;
# the indicator-rect offset is ``6 *`` the indicator circle's stroke
# width so paths land well clear of the circle's outer edge.
_CONNECTOR_SPACING_RATIO = 0.6
_CIRCLE_STROKE_WIDTH_RATIO = 2.0 / 1600.0
_INDICATOR_RECT_PADDING_MULTIPLIER = 6.0

# Connector path stroke styling — the dotted cadence stays legible
# across canvas sizes because both stroke width and dash gap track
# ``doc_width``.
_CONNECTOR_PATH_STROKE_WIDTH_RATIO = 4.375 / 1600
_CONNECTOR_PATH_DASH_DOT_RATIO = 0.1 / 1600
_CONNECTOR_PATH_DASH_GAP_RATIO = 12.25 / 1600
_CONNECTOR_PATH_OPACITY = 0.7
_CONNECTOR_PATH_FALLBACK_COLOR = "#808080"


def _badge_padding_left(doc_width: float) -> float:
    return doc_width * _BADGE_PADDING_LEFT_RATIO


def _badge_padding_right(doc_width: float) -> float:
    return doc_width * _BADGE_PADDING_RIGHT_RATIO


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _BadgeDims:
    width: float
    height: float
    border_radius: float


def _badge_text(qmk_idx: int, name: str) -> str:
    """Compose a layer badge label, deduping the redundant ``Layer N`` case.

    When the layer name is the auto-generated ``Layer N`` placeholder
    matching ``qmk_idx`` (case-insensitive), drop the leading number to
    avoid badges that read ``"0 LAYER 0"``. Named layers keep the index
    prefix (e.g. ``"0 LETTERS"``).
    """
    upper = name.upper()
    if upper == f"LAYER {qmk_idx}":
        return upper
    return f"{qmk_idx} {upper}"


def _measure_badge_text_width(text: str, font_size: float) -> float:
    """PIL-measured width of ``text`` rendered at ``font_size``."""
    ref_size = 100
    pil_font = Font.FINGER_KEY.load(ref_size)
    return pil_font.getlength(text) * (font_size / ref_size)


def _compute_badge_dims(
    *,
    doc_width: float,
    finger_cluster_width: float,
    badge_texts: list[str],
) -> _BadgeDims:
    """Compute uniform badge dimensions.

    Height matches the outer-key (E/W key) size of a finger cluster.
    Width = ``badge_pad_left + widest_text + badge_pad_right``.
    """
    height = finger_cluster_width * _OUTER_KEY_PROPORTION
    font_size = height * _BADGE_FONT_SIZE_RATIO
    if badge_texts:
        max_text_width = max(_measure_badge_text_width(t, font_size) for t in badge_texts)
    else:
        max_text_width = 50.0
    width = _badge_padding_left(doc_width) + max_text_width + _badge_padding_right(doc_width)
    return _BadgeDims(
        width=width,
        height=height,
        border_radius=height * _BADGE_BORDER_RADIUS_RATIO,
    )


# ---------------------------------------------------------------------------
# LayerBadge — the colored rectangle + text on the left of each row.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class LayerBadgeMetrics:
    """Metrics surfaced by a built :func:`LayerBadge`.

    Attributes
    ----------
    badge_size : Size
        The filled rectangle's width × height. Reported separately
        from the composable's :attr:`Size` because the composable's
        size also includes any variant label rendered below the badge.
    font_size : float
        The badge text's font size, used by callers (typically the
        ``LAYERS`` heading) that need to align baseline-relative.
    variant_offset : float
        Distance from the badge's bottom edge to the variant label's
        top. ``0`` when no variant is present.
    """

    badge_size: Size
    font_size: float
    variant_offset: float


@Composable(use_context=True)
def LayerBadge(
    ctx,
    *,
    text: str,
    badge_width: float,
    badge_height: float,
    border_radius: float,
    fill_color: str,
    text_color: str = "white",
    variant: str | None = None,
    variant_color: str | None = None,
):
    """A coloured rectangle + label, with an optional variant label below.

    Reports :class:`MetricsComponent[LayerBadgeMetrics]`. The
    composable's :attr:`Size` is the full bounding box including the
    variant label (when present); the badge rectangle itself is
    ``badge_size`` on the metrics. ``draw_at(d, origin)`` paints the
    badge starting at ``origin`` (top-left of the rectangle).
    """
    badge_font_size = badge_height * _BADGE_FONT_SIZE_RATIO
    use_system_fonts = ctx.config.output.style.use_system_fonts
    family = Font.FINGER_KEY.get_system_font_family() if use_system_fonts else Font.FINGER_KEY.value

    badge_pad_left = _badge_padding_left(ctx.config.output.layout.width)

    variant_offset = badge_font_size * _VARIANT_LABEL_OFFSET_RATIO_OF_FONT
    total_height = badge_height + (variant_offset + badge_font_size if variant else 0.0)
    size = Size(badge_width, total_height)
    badge_size = Size(badge_width, badge_height)

    def draw_at(d, origin):
        d.append(
            draw.Rectangle(
                x=origin.x,
                y=origin.y,
                width=badge_width,
                height=badge_height,
                rx=border_radius,
                ry=border_radius,
                fill=fill_color,
            )
        )
        d.append(
            draw.Text(
                text,
                font_size=badge_font_size,
                x=origin.x + badge_pad_left,
                y=origin.y + badge_height / 2.0,
                text_anchor="start",
                dominant_baseline="central",
                font_family=family,
                fill=text_color,
            )
        )
        if variant:
            d.append(
                draw.Text(
                    variant,
                    font_size=badge_font_size,
                    x=origin.x + badge_pad_left,
                    y=origin.y + badge_height + variant_offset,
                    text_anchor="start",
                    dominant_baseline="text-before-edge",
                    font_family=family,
                    fill=variant_color or fill_color,
                )
            )

    return MetricsComponent(
        size=size,
        draw_fn=draw_at,
        metrics=LayerBadgeMetrics(
            badge_size=badge_size,
            font_size=badge_font_size,
            variant_offset=variant_offset,
        ),
    )


# ---------------------------------------------------------------------------
# Connector routing — adapter + indicator-rect helper
# ---------------------------------------------------------------------------


# Cluster slot order matching :class:`FingerClusterData` (used to walk
# every finger slot when computing indicator rects).
_FINGER_SLOTS: tuple[str, ...] = (
    "center_key",
    "north_key",
    "east_key",
    "south_key",
    "west_key",
    "double_south_key",
)
_THUMB_SLOTS: tuple[str, ...] = (
    "down_key",
    "double_down_key",
    "pad_key",
    "up_key",
    "nail_key",
    "knuckle_key",
)


class _OverviewRoutingLayout:
    """``RoutingLayout`` adapter for :func:`KeymapOverview`.

    Holds mutable layer-row Y positions (and the thumb row's Y) so
    :func:`route_overview_connectors`'s pass-1 shifts can push rows
    down to clear lane banks. After routing, :func:`KeymapOverview`
    reads the final positions from the lists captured here. The
    adapter satisfies the ``RoutingLayout`` Protocol from
    :mod:`connectors`.
    """

    def __init__(
        self,
        *,
        layer_to_row: dict[int, int],
        row_y_positions: list[float],
        thumb_y_state: list[float],
        row_height: float,
        thumb_height: float,
        cluster_x: float,
        cluster_w: float,
        ew_offset: float,
        outer_key_size: float,
        row_gap_value: float,
        has_double_south: bool,
    ) -> None:
        self._layer_to_row = layer_to_row
        self._row_y_positions = row_y_positions
        self._thumb_y_state = thumb_y_state  # single-element mutable list
        self._row_height = row_height
        self._thumb_height = thumb_height
        self._cluster_x = cluster_x
        self._cluster_w = cluster_w
        self._ew_offset = ew_offset
        self._outer_key_size = outer_key_size
        self._row_gap_value = row_gap_value
        self._has_double_south = has_double_south

    @property
    def layer_row_y_positions(self) -> list[float]:
        """Virtual list keyed by QMK index, padded to ``max(qmk) + 1``.

        :func:`route_overview_connectors`'s ``target_point_for`` uses
        ``len(layer_row_y_positions)`` to bounds-check QMK indices —
        so the list must be long enough that every valid QMK index
        passes the check, not just the first ``N`` rendered rows.
        Unpopulated slots get ``0.0``; the actual y values come from
        :meth:`layer_row_bounding_box` / :meth:`layer_row_target_y`,
        which read the underlying row list via ``_layer_to_row``.
        """
        if not self._layer_to_row:
            return []
        size = max(self._layer_to_row.keys()) + 1
        out = [0.0] * size
        for qmk_idx, row_idx in self._layer_to_row.items():
            if 0 <= row_idx < len(self._row_y_positions):
                out[qmk_idx] = self._row_y_positions[row_idx]
        return out

    @property
    def row_gap(self) -> float:
        return self._row_gap_value

    @property
    def has_double_south(self) -> bool:
        return self._has_double_south

    def layer_row_bounding_box(self, target_layer: int) -> tuple[float, float, float, float]:
        row_idx = self._layer_to_row.get(target_layer)
        if row_idx is None:
            raise KeyError(f"target_layer={target_layer} is not a rendered QMK layer")
        return (
            self._cluster_x,
            self._row_y_positions[row_idx],
            self._cluster_w,
            self._row_height,
        )

    def layer_row_target_y(self, target_layer: int) -> float:
        row_idx = self._layer_to_row.get(target_layer)
        if row_idx is None:
            raise KeyError(f"target_layer={target_layer} is not a rendered QMK layer")
        return self._row_y_positions[row_idx] + self._ew_offset + self._outer_key_size / 2.0

    def thumb_cluster_y_bounds(self) -> tuple[float, float]:
        return (self._thumb_y_state[0], self._thumb_y_state[0] + self._thumb_height)

    def shift_layer_row_and_below(self, target_layer: int, amount: float) -> None:
        if amount <= 0:
            return
        row_idx = self._layer_to_row.get(target_layer)
        if row_idx is None:
            return
        for i in range(row_idx, len(self._row_y_positions)):
            self._row_y_positions[i] += amount
        self._thumb_y_state[0] += amount

    def shift_below_layer_row(self, target_layer: int, amount: float) -> None:
        if amount <= 0:
            return
        row_idx = self._layer_to_row.get(target_layer)
        if row_idx is None:
            return
        for i in range(row_idx + 1, len(self._row_y_positions)):
            self._row_y_positions[i] += amount
        self._thumb_y_state[0] += amount

    def shift_thumb_down(self, amount: float) -> None:
        if amount <= 0:
            return
        self._thumb_y_state[0] += amount


def _indicator_rect(
    abs_cx: float, abs_cy: float, radius: float, offset: float
) -> tuple[float, float, float, float]:
    """Compute one indicator's bounding rect with a clearance offset.

    The legacy router expects ``(x, y, w, h)`` rects padded outward by
    ``offset`` on every side so connector paths land clear of the
    circle's outer stroke. ``offset`` defaults to ``6 *
    circle_stroke_width`` per the legacy convention.
    """
    return (
        abs_cx - radius - offset,
        abs_cy - radius - offset,
        2.0 * radius + 2.0 * offset,
        2.0 * radius + 2.0 * offset,
    )


# ---------------------------------------------------------------------------
# KeymapOverview — the body of the overview image.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _RowPlacement:
    """Resolved position of one layer row inside the overview body.

    ``y`` is the keys-only top edge (the FingerHalf's ``draw_at``
    origin Y). ``badge_y`` is the badge's top-left Y; the badge
    aligns with the W key's top, which sits at
    ``y + ew_key_y_offset`` in the half's local frame.
    """

    y: float
    badge_y: float


@Composable(use_context=True)
def KeymapOverview(
    ctx,
    *,
    keymap: SvalboardKeymap[SvalboardTargetKey],
    target_content_w: float,
):
    """Multi-layer compact view + thumb cluster row.

    Builds:

    * One :func:`LayerBadge` per rendered layer, plus a ``THUMBS``
      :func:`LayerBadge` on the bottom row.
    * One left :func:`FingerHalf` and one right :func:`FingerHalf`
      per rendered layer, both with ``stagger_middle_fingers=False``
      so the rows pack onto a single baseline.
    * One left :func:`ThumbCluster` and one right
      :func:`ThumbCluster`, populated from the first rendered layer's
      thumb data.

    Layout uses the same uniform inset rules as the per-layer image:
    inter-cluster gap = ``inset``; central gap between halves =
    ``2 * inset``; inter-row gap = ``inset``; column gap (badge column
    → cluster column) = ``column_gap``.

    Connectors are intentionally deferred — they will be added in a
    follow-up step that consumes each :func:`FingerHalf` /
    :func:`ThumbCluster`'s indicator routing geometry.

    The composable's :attr:`Size` covers the body's natural width and
    height (everything below the LAYERS heading down to the thumb
    cluster's bottom edge). All overflow lands inside the bbox; the
    parent column reads ``size`` and reserves no extra chrome.
    """
    config = ctx.config
    metrics = ctx.document_metrics
    palette = ctx.theme.palette
    config_palette = config.output.style.palette
    # Spacing convention: ``inset`` is vertical-only (between rows /
    # inside a Column); ``column_gap`` is the canonical horizontal
    # spacing. The badge column → cluster column gap and the central
    # gap between the two halves both use ``2 * column_gap`` to read
    # as primary visual dividers; inter-cluster horizontal gaps within
    # a half default to ``column_gap`` (see :func:`FingerHalf`).
    inset = metrics.inset
    column_gap = metrics.column_gap
    badge_to_clusters_gap = 2.0 * column_gap
    center_gap = _CENTER_GAP_INSET_COUNT * column_gap

    render_layers: list[tuple[int, int]] = [
        (pos, layer_cfg.index)
        for pos, layer_cfg in enumerate(config.keyboard.layers)
        if layer_cfg.index in keymap.layers
    ]

    if not render_layers:
        # Nothing to render — return an empty body. The document
        # composable also short-circuits, so this is defensive.
        return Spacer()

    # --- Phase 1: derive cluster sizing from the budget. ---
    # Initial pass with badge_dims set from a placeholder cluster width;
    # we refine once we know the real cluster width. The fixed-point
    # iteration converges in two passes because ``badge_height`` only
    # affects ``badge_dims.width`` indirectly via its own font size.
    def _solve_layout(badge_w: float):
        col1 = badge_w
        clusters_budget = target_content_w - col1 - badge_to_clusters_gap
        side_w = (clusters_budget - center_gap) / 2.0
        fcw = (side_w - 3 * column_gap) / 4.0
        return col1, side_w, fcw

    # Seed: badge width approximated from a guess at cluster width.
    seed_finger_cluster_width = (
        target_content_w - center_gap - 6 * column_gap - badge_to_clusters_gap - 200.0
    ) / 8.0
    seed_finger_cluster_width = max(seed_finger_cluster_width, 50.0)
    badge_texts: list[str] = [
        _badge_text(qmk_idx, config.keyboard.layers[pos].name) for pos, qmk_idx in render_layers
    ]
    badge_texts.append("THUMBS")
    seed_badge = _compute_badge_dims(
        doc_width=config.output.layout.width,
        finger_cluster_width=seed_finger_cluster_width,
        badge_texts=badge_texts,
    )
    _, _, finger_cluster_width = _solve_layout(seed_badge.width)
    badge_dims = _compute_badge_dims(
        doc_width=config.output.layout.width,
        finger_cluster_width=finger_cluster_width,
        badge_texts=badge_texts,
    )
    col1_width, side_width, finger_cluster_width = _solve_layout(badge_dims.width)
    thumb_cluster_width = side_width * _THUMB_CLUSTER_WIDTH_PROPORTION

    # --- Phase 2: build composables. ---
    common_finger_kwargs = {
        "min_width": side_width,
        "stagger_middle_fingers": False,
        "has_double_south": config.keyboard.features.double_south,
        "use_layer_colors_on_keys": config.output.style.use_layer_colors_on_keys,
        "show_layer_indicators": config.output.style.show_layer_indicators,
        "hold_symbol_position": config.output.style.hold_symbol_position,
        # FingerHalf defaults to ``ctx.document_metrics.column_gap`` —
        # left implicit so the per-layer image and the overview share
        # the same canonical horizontal spacing.
    }
    common_thumb_kwargs = {
        "width": thumb_cluster_width,
        "use_layer_colors_on_keys": config.output.style.use_layer_colors_on_keys,
        "show_layer_indicators": config.output.style.show_layer_indicators,
        "hold_symbol_position": config.output.style.hold_symbol_position,
    }

    layer_badges: list[Component] = []
    finger_halves: list[tuple[Component, Component]] = []
    for pos, qmk_idx in render_layers:
        layer_cfg = config.keyboard.layers[pos]
        layer_color = (
            config_palette.layers[pos].base_color
            if pos < len(config_palette.layers)
            else palette.neutral_color
        )
        layer_badges.append(
            LayerBadge(
                text=_badge_text(qmk_idx, layer_cfg.name),
                badge_width=badge_dims.width,
                badge_height=badge_dims.height,
                border_radius=badge_dims.border_radius,
                fill_color=layer_color,
                variant=layer_cfg.variant or None,
                variant_color=layer_color,
            )
        )
        layer_data = keymap.layers[qmk_idx]
        left_half = FingerHalf(
            side=KeyboardSide.LEFT,
            fingers=layer_data.left.fingers,
            layer_qmk_index=qmk_idx,
            **common_finger_kwargs,
        )
        right_half = FingerHalf(
            side=KeyboardSide.RIGHT,
            fingers=layer_data.right.fingers,
            layer_qmk_index=qmk_idx,
            **common_finger_kwargs,
        )
        finger_halves.append((left_half, right_half))

    first_pos, first_qmk_idx = render_layers[0]
    thumb_layer = keymap.layers[first_qmk_idx]
    left_thumb = ThumbCluster(
        side=KeyboardSide.LEFT,
        cluster=thumb_layer.left.thumb,
        layer_qmk_index=first_qmk_idx,
        **common_thumb_kwargs,
    )
    right_thumb = ThumbCluster(
        side=KeyboardSide.RIGHT,
        cluster=thumb_layer.right.thumb,
        layer_qmk_index=first_qmk_idx,
        **common_thumb_kwargs,
    )
    thumbs_badge = LayerBadge(
        text="THUMBS",
        badge_width=badge_dims.width,
        badge_height=badge_dims.height,
        border_radius=badge_dims.border_radius,
        fill_color=palette.text_color,
    )

    # --- Phase 3: per-row overflow accounting. ---
    def _top_bleed(half) -> float:
        return max(0.0, -half.metrics.overflow_offset.y)

    def _bottom_bleed(half) -> float:
        return max(
            0.0,
            half.metrics.overflow_size.height - half.size.height + half.metrics.overflow_offset.y,
        )

    def _left_bleed(half) -> float:
        return max(0.0, -half.metrics.overflow_offset.x)

    def _right_bleed(half) -> float:
        return max(
            0.0,
            half.metrics.overflow_size.width - half.size.width + half.metrics.overflow_offset.x,
        )

    row_top_bleeds = [max(_top_bleed(lfh), _top_bleed(rfh)) for lfh, rfh in finger_halves]
    row_bottom_bleeds = [max(_bottom_bleed(lfh), _bottom_bleed(rfh)) for lfh, rfh in finger_halves]
    thumb_top_bleed = max(_top_bleed(left_thumb), _top_bleed(right_thumb))
    thumb_bottom_bleed = max(_bottom_bleed(left_thumb), _bottom_bleed(right_thumb))

    # Inward bleeds — kept per-piece so the visible gap between the
    # left/right pair's inward indicators always equals ``center_gap``,
    # regardless of which row's indicators dominate. Finger halves and
    # thumbs have different geometries (thumb's knuckle/nail bleeds are
    # smaller than a finger's centre-key indicator's diagonal bleed),
    # so they get independent x-positioning anchored on a shared
    # horizontal centre axis.
    finger_inward_left = max(_right_bleed(lfh) for lfh, _ in finger_halves)
    finger_inward_right = max(_left_bleed(rfh) for _, rfh in finger_halves)
    thumb_inward_left = _right_bleed(left_thumb)
    thumb_inward_right = _left_bleed(right_thumb)

    # Outward bleeds extend the body's outer width; finger halves are
    # wider than thumb clusters so finger outer bleeds typically
    # dominate. Take the max across pieces for safety.
    max_left_outer_bleed = max(
        max(_left_bleed(lfh) for lfh, _ in finger_halves),
        _left_bleed(left_thumb),
    )
    max_right_outer_bleed = max(
        max(_right_bleed(rfh) for _, rfh in finger_halves),
        _right_bleed(right_thumb),
    )

    # --- Phase 4: row Y positions. ---
    # ``row_y`` is the keys-only top edge of the half on that row.
    # The first row's row_y must be at least its top bleed so chrome
    # doesn't escape the body. The LAYERS heading sits above the
    # first badge in the negative-y space — but since it's a single
    # text label that only paints upward of its anchor, it adds an
    # extra ``badge_font_size + variant_offset`` of headroom.
    badge_font_size = badge_dims.height * _BADGE_FONT_SIZE_RATIO
    layers_heading_height = badge_font_size + badge_font_size * _VARIANT_LABEL_OFFSET_RATIO_OF_FONT

    placements: list[_RowPlacement] = []
    half_height = finger_halves[0][0].size.height
    # ew_offset = where the W/E key's top sits in the half's local frame
    # (= one outer key down from the half's top edge). Same as the
    # cluster's ``north_key`` width since outer keys are square.
    ew_offset = finger_cluster_width * _OUTER_KEY_PROPORTION
    # Reserve top-of-body space: heading above the first badge, which
    # itself sits at row_y + ew_offset (so the badge's top is below
    # the half's top by ``ew_offset``).
    body_top_padding = max(layers_heading_height, row_top_bleeds[0])
    y_cursor = body_top_padding
    for i, bot_b in enumerate(row_bottom_bleeds):
        placements.append(_RowPlacement(y=y_cursor, badge_y=y_cursor + ew_offset))
        # Move past this row.
        y_cursor += half_height
        # Inter-row separation: this row's bottom bleed + inset + next
        # row's top bleed (or the thumb row's top bleed for the last
        # transition).
        if i + 1 < len(finger_halves):
            y_cursor += bot_b + inset + row_top_bleeds[i + 1]
        else:
            y_cursor += bot_b + inset + thumb_top_bleed

    thumb_y = y_cursor
    # Thumb pad-key offset matches the per-cluster's pad_key origin's
    # local-y, which sits at one thumb-inset below the down key (which
    # is at cluster top). Read off the thumb cluster's metrics.
    thumb_pad_offset = left_thumb.metrics.pad_key.indicator_anchor.y
    # ``indicator_anchor`` is the indicator's anchor point, not the pad
    # key's top. Use a more direct measure: the thumb cluster's height
    # divided into the legacy pad-key offset proportion. Mirrors
    # :data:`overview_layout._THUMB_KEY_INSET_PROPORTION` (0.038).
    _THUMB_KEY_INSET_PROPORTION = 0.038
    thumb_pad_offset = thumb_cluster_width * _THUMB_KEY_INSET_PROPORTION
    thumbs_badge_y = thumb_y + thumb_pad_offset
    body_height = thumb_y + left_thumb.size.height + thumb_bottom_bleed

    # --- Phase 5: X positions. ---
    badge_x = 0.0
    # Finger halves: position so the visible gap between inward
    # indicators (left half's right-edge indicators ↔ right half's
    # left-edge indicators) equals exactly ``center_gap``. Width
    # contributed by inward bleeds on each side is added to the
    # central reservation.
    left_half_x = col1_width + badge_to_clusters_gap + max_left_outer_bleed
    right_half_x = left_half_x + side_width + finger_inward_left + center_gap + finger_inward_right
    body_width = right_half_x + side_width + max_right_outer_bleed

    # Body horizontal centre axis — midpoint between the finger
    # halves' inward indicator outer edges. Both pairs (finger halves
    # and thumbs) sit symmetrically around it so each pair's visible
    # gap equals ``center_gap``.
    body_center_x = left_half_x + side_width + finger_inward_left + center_gap / 2.0

    # Thumbs: anchored on the same centre axis using their own
    # inward bleeds so the visible gap between the knuckle indicators
    # is also exactly ``center_gap``.
    left_thumb_x = body_center_x - center_gap / 2.0 - thumb_inward_left - left_thumb.size.width
    right_thumb_x = body_center_x + center_gap / 2.0 + thumb_inward_right

    # --- Phase 6: connector routing. ---
    # Mutable layout state — :func:`route_overview_connectors` shifts
    # rows during pass 1 to make room for inter-row lane banks. After
    # routing the lists below reflect the post-shift positions and we
    # rebuild ``placements`` against them for the draw_at closure.
    mutable_row_ys: list[float] = [p.y for p in placements]
    mutable_thumb_y: list[float] = [thumb_y]
    routing: ConnectorRouting | None = None
    if (
        config.output.style.show_layer_indicators
        and config.output.style.show_layer_connectors
        and len(render_layers) > 1
    ):
        layer_to_row = {qmk_idx: ri for ri, (_pos, qmk_idx) in enumerate(render_layers)}
        layer_sources = [
            OverviewLayerSource(
                source_layer=qmk_idx,
                left=keymap.layers[qmk_idx].left,
                right=keymap.layers[qmk_idx].right,
            )
            for _pos, qmk_idx in render_layers
        ]
        thumb_layer_data = keymap.layers[first_qmk_idx]
        thumb_source = ThumbSource(
            source_layer=first_qmk_idx,
            left=thumb_layer_data.left.thumb,
            right=thumb_layer_data.right.thumb,
        )

        outer_key_size = finger_cluster_width * _OUTER_KEY_PROPORTION
        keymap_spacing = outer_key_size * _CONNECTOR_SPACING_RATIO
        rect_offset = (
            _INDICATOR_RECT_PADDING_MULTIPLIER
            * config.output.layout.width
            * _CIRCLE_STROKE_WIDTH_RATIO
        )

        routing_layout = _OverviewRoutingLayout(
            layer_to_row=layer_to_row,
            row_y_positions=mutable_row_ys,
            thumb_y_state=mutable_thumb_y,
            row_height=half_height,
            thumb_height=left_thumb.size.height,
            cluster_x=left_half_x,
            cluster_w=right_half_x + side_width - left_half_x,
            ew_offset=ew_offset,
            outer_key_size=outer_key_size,
            row_gap_value=inset,
            has_double_south=config.keyboard.features.double_south,
        )

        def _compute_rects() -> dict[int, tuple[float, float, float, float]]:
            """Walk every cluster's indicators, project their circles to
            canvas-absolute coords, and return ``id(key) -> rect``.

            Called twice by :func:`route_overview_connectors` (pass 1
            and pass 2). Both invocations read from the mutable
            ``mutable_row_ys`` / ``mutable_thumb_y`` lists so the
            second call automatically reflects the post-shift state
            after pass 1's row shifts.
            """
            rects: dict[int, tuple[float, float, float, float]] = {}
            # Per-layer finger cluster indicators.
            for row_idx, (_pos, qmk_idx) in enumerate(render_layers):
                row_y = mutable_row_ys[row_idx]
                lfh, rfh = finger_halves[row_idx]
                layer_data = keymap.layers[qmk_idx]
                # Match cluster names between FingerHalfMetrics
                # (``index_origin``, ``middle_origin``, …) and
                # FingerClusterMetrics + FingerClusterData
                # (``index``, ``middle``, …).
                for half_x, half, side_data in (
                    (left_half_x, lfh, layer_data.left),
                    (right_half_x, rfh, layer_data.right),
                ):
                    finger_idx_to_attr = (
                        ("index", "index_origin"),
                        ("middle", "middle_origin"),
                        ("ring", "ring_origin"),
                        ("pinky", "pinky_origin"),
                    )
                    for finger_idx, (cluster_attr, origin_attr) in enumerate(finger_idx_to_attr):
                        cluster_metrics = getattr(half.metrics, cluster_attr)
                        cluster_origin = getattr(half.metrics, origin_attr)
                        cluster_data = side_data.fingers[finger_idx]
                        for slot in _FINGER_SLOTS:
                            indicator = getattr(cluster_metrics.indicators, slot)
                            if indicator is None:
                                continue
                            key_origin = getattr(cluster_metrics.key_origins, slot)
                            abs_cx = (
                                half_x + cluster_origin.x + key_origin.x + indicator.circle_center.x
                            )
                            abs_cy = (
                                row_y + cluster_origin.y + key_origin.y + indicator.circle_center.y
                            )
                            key = getattr(cluster_data, slot)
                            rects[id(key)] = _indicator_rect(
                                abs_cx, abs_cy, indicator.circle_radius, rect_offset
                            )
            # Thumb cluster indicators — first layer only, matching
            # what the body actually paints.
            current_thumb_y = mutable_thumb_y[0]
            for thumb_x, thumb, side_data in (
                (left_thumb_x, left_thumb, thumb_layer_data.left.thumb),
                (right_thumb_x, right_thumb, thumb_layer_data.right.thumb),
            ):
                for slot in _THUMB_SLOTS:
                    indicator = getattr(thumb.metrics.indicators, slot)
                    if indicator is None:
                        continue
                    key_origin = getattr(thumb.metrics.key_origins, slot)
                    abs_cx = thumb_x + key_origin.x + indicator.circle_center.x
                    abs_cy = current_thumb_y + key_origin.y + indicator.circle_center.y
                    key = getattr(side_data, slot)
                    rects[id(key)] = _indicator_rect(
                        abs_cx, abs_cy, indicator.circle_radius, rect_offset
                    )
            return rects

        routing = route_overview_connectors(
            layers=layer_sources,
            thumb=thumb_source,
            layout=routing_layout,
            compute_indicator_rects=_compute_rects,
            keymap_spacing=keymap_spacing,
        )

    # --- Phase 7: rebuild placements from post-routing layout state. ---
    placements = [_RowPlacement(y=y, badge_y=y + ew_offset) for y in mutable_row_ys]
    thumb_y = mutable_thumb_y[0]
    thumbs_badge_y = thumb_y + thumb_pad_offset
    body_height = thumb_y + left_thumb.size.height + thumb_bottom_bleed
    if routing is not None:
        body_width += routing.extra_right_padding
        body_height += routing.extra_bottom_padding

    # --- Phase 8: heading position + connector path styling. ---
    layers_heading_baseline_y = (
        placements[0].badge_y - badge_font_size * _VARIANT_LABEL_OFFSET_RATIO_OF_FONT
    )
    layers_heading_x = badge_x + _badge_padding_left(config.output.layout.width)
    use_system_fonts = config.output.style.use_system_fonts
    label_font = (
        Font.FINGER_KEY.get_system_font_family() if use_system_fonts else Font.FINGER_KEY.value
    )

    # Layer-color lookup for connector path stroke (each path takes the
    # destination layer's gradient stop).
    palette_layers = config_palette.layers
    qmk_to_pos: dict[int, int] = {
        layer_cfg.index: pos for pos, layer_cfg in enumerate(config.keyboard.layers)
    }

    doc_width = config.output.layout.width
    connector_stroke_width = doc_width * _CONNECTOR_PATH_STROKE_WIDTH_RATIO
    dot = doc_width * _CONNECTOR_PATH_DASH_DOT_RATIO
    dash_gap = doc_width * _CONNECTOR_PATH_DASH_GAP_RATIO

    size = Size(body_width, body_height)

    def draw_at(d, origin):
        # LAYERS heading.
        d.append(
            draw.Text(
                "LAYERS",
                font_size=badge_font_size,
                x=origin.x + layers_heading_x,
                y=origin.y + layers_heading_baseline_y,
                text_anchor="start",
                dominant_baseline="text-after-edge",
                font_family=label_font,
                fill=palette.neutral_color,
            )
        )

        # Layer rows: badge + left + right finger half.
        for placement, badge, halves in zip(placements, layer_badges, finger_halves, strict=True):
            badge.draw_at(d, Point(origin.x + badge_x, origin.y + placement.badge_y))
            left_half, right_half = halves
            left_half.draw_at(d, Point(origin.x + left_half_x, origin.y + placement.y))
            right_half.draw_at(d, Point(origin.x + right_half_x, origin.y + placement.y))

        # Thumb row.
        thumbs_badge.draw_at(d, Point(origin.x + badge_x, origin.y + thumbs_badge_y))
        left_thumb.draw_at(d, Point(origin.x + left_thumb_x, origin.y + thumb_y))
        right_thumb.draw_at(d, Point(origin.x + right_thumb_x, origin.y + thumb_y))

        # Connector paths sit on top of the clusters. Each path takes
        # its destination layer's accent colour; an unmapped layer
        # falls back to neutral grey rather than crashing. Paths are
        # pre-routed in body-local coords, so wrap them in a Group
        # with a translate transform to land them in the document
        # frame.
        if routing is not None and routing.paths:
            g = draw.Group(transform=f"translate({origin.x}, {origin.y})")
            for path, target_layer in routing.paths:
                pos = qmk_to_pos.get(target_layer)
                if pos is not None and 0 <= pos < len(palette_layers):
                    stroke_color = palette_layers[pos][4]
                else:
                    stroke_color = _CONNECTOR_PATH_FALLBACK_COLOR
                path.args["stroke"] = stroke_color
                path.args["stroke-width"] = connector_stroke_width
                path.args["stroke-dasharray"] = f"{dot} {dash_gap}"
                path.args["stroke-linecap"] = "round"
                path.args["opacity"] = _CONNECTOR_PATH_OPACITY
                g.append(path)
            d.append(g)

    return size, draw_at


# ---------------------------------------------------------------------------
# KeymapOverviewDocument — the full overview image.
# ---------------------------------------------------------------------------


@Composable(use_context=True)
def KeymapOverviewDocument(
    ctx,
    *,
    keymap: SvalboardKeymap[SvalboardTargetKey],
    title: str,
    copyright: str | None = None,
    raw_keymap: SvalboardKeymap[str] | None = None,
    keycode_mappings: KeycodeMappings | None = None,
):
    """The full overview image as a single composable.

    Stacks :func:`Header`, :func:`KeymapOverview`, the optional macro
    / TD legend, the optional symbol legend, and an optional
    :func:`Footer` in a :class:`Column`, then wraps in
    :func:`KeymapDocument` for the rounded background border +
    content_offset chrome.
    """
    config = ctx.config
    metrics = ctx.document_metrics
    content_offset = metrics.margin + metrics.border_width + metrics.inset
    doc_content_w = metrics.doc_width - 2 * content_offset

    if not keymap.layers:
        return Spacer()

    body = KeymapOverview(keymap=keymap, target_content_w=doc_content_w)
    content_w = max(body.size.width, doc_content_w)

    # Macro / TD legend — the overview shows ALL macros and tap-dances,
    # not just those used on a specific layer.
    macro_entries: list = []
    td_entries: list = []
    if config.output.style.show_special_keys_legend:
        macro_entries = all_macros(keymap.macros)
        td_entries = all_tap_dances(keymap.tap_dances)

    col_gap = metrics.column_gap
    col_w = (content_w - col_gap) / 2 if macro_entries and td_entries else content_w
    macro_section = (
        MacroSection(macros=macro_entries, content_width=col_w) if macro_entries else None
    )
    td_section = TapDanceSection(tap_dances=td_entries, max_width=col_w) if td_entries else None

    # Symbol legend — union across all rendered layers.
    symbol_section = None
    if (
        config.output.style.show_symbol_legend
        and raw_keymap is not None
        and keycode_mappings is not None
    ):
        all_raw_keycodes: list[str] = []
        for layer_cfg in config.keyboard.layers:
            qmk_idx = layer_cfg.index
            if qmk_idx in raw_keymap.layers and qmk_idx in keymap.layers:
                all_raw_keycodes.extend(k for k in raw_keymap.layers[qmk_idx] if k is not None)
        symbol_entries = collect_used_descriptions(
            all_raw_keycodes,
            raw_keymap,
            keycode_mappings,
            include_transparent=not config.output.style.show_transparent_fallthrough,
        )
        if symbol_entries:
            flow_value = config.output.style.symbol_legend_flow.value
            typed_flow: FlowDirection = "row" if flow_value == "row" else "column"
            symbol_section = SymbolSection(
                entries=symbol_entries,
                max_width=content_w,
                column_count=config.output.style.symbol_legend_columns,
                flow=typed_flow,
            )

    with Column(gap=metrics.inset, align="start") as content:
        Header(
            title=title,
            min_gap=2 * metrics.inset,
            max_width=content_w,
        )
        content.add(body)
        # Macro and tap-dance sections share a Row when both are
        # present, mirroring :func:`KeymapLayerDocument` /
        # :func:`KeymapSpecialKeysDocument`. ``col_gap`` is
        # ``metrics.column_gap`` — the canonical horizontal spacing.
        if macro_section is not None and td_section is not None:
            Row([macro_section, td_section], gap=col_gap, align="top")
        elif macro_section is not None:
            content.add(macro_section)
        elif td_section is not None:
            content.add(td_section)
        if symbol_section is not None:
            content.add(symbol_section)
        if copyright:
            Footer(text=copyright, max_width=content_w)

    return KeymapDocument(content=content)


# ---------------------------------------------------------------------------
# Entry point — parallel ``draw_overview_v2`` for visual comparison
# against the legacy imperative path. Will replace the legacy
# ``draw_overview`` once visual parity is confirmed and connectors are
# in place.
# ---------------------------------------------------------------------------


def _resolve_overview_title(config: SkimConfig) -> str:
    """Replicate :func:`overview.draw_overview`'s title resolution."""
    if config.output.keymap_title:
        return config.output.keymap_title
    if config.keyboard.layers:
        first_layer = config.keyboard.layers[0]
        return f"{(first_layer.variant or first_layer.name)} Layers Layout"
    return "Keymap Layout"


def draw_overview_v2(
    config: SkimConfig,
    keymap: SvalboardKeymap[SvalboardTargetKey],
    raw_keymap: SvalboardKeymap[str] | None = None,
    keycode_mappings: KeycodeMappings | None = None,
) -> draw.Drawing:
    """Generate the overview SVG via the composable framework.

    Mirrors the per-layer image's :func:`_draw_layer` shape: build a
    :class:`RenderContext`, construct :func:`KeymapOverviewDocument`
    inside it, then paint into a drawsvg :class:`Drawing` with the
    user-requested display width.

    Connectors are not yet emitted — those land in a follow-up step.
    The output is structurally identical to the legacy overview
    minus the dotted connector lines.
    """
    title = _resolve_overview_title(config)
    copyright_text = config.output.copyright or ""

    ctx = RenderContext.build(config, keymap)
    with using_render_context(ctx):
        doc = KeymapOverviewDocument(
            keymap=keymap,
            title=title,
            copyright=copyright_text,
            raw_keymap=raw_keymap,
            keycode_mappings=keycode_mappings,
        )

    canvas_width = doc.size.width
    canvas_height = doc.size.height
    display_w = config.output.layout.width
    display_h = canvas_height * (display_w / canvas_width) if canvas_width else canvas_height
    d = draw.Drawing(display_w, display_h, viewBox=f"0 0 {canvas_width} {canvas_height}")

    if not config.output.style.use_system_fonts:
        for font in Font:
            d.append_css(font.css_style)

    doc.draw_at(d, Point(0.0, 0.0))
    return d


__all__ = [
    "KeymapOverview",
    "KeymapOverviewDocument",
    "LayerBadge",
    "LayerBadgeMetrics",
    "draw_overview_v2",
]
