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

Connectors are handled in a separate pass once the body has been
positioned — the cluster-level :class:`LayerIndicatorMetrics`
exposes the routing origin / direction the connector router needs.
The document composable that stacks this body inside a header /
footer / legend column lives in :mod:`keymap_document`.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

import drawsvg as draw

from skim.data import SkimConfig, SvalboardKeymap, resolve_spacing
from skim.data.keyboard import (
    FingerCluster as FingerClusterData,
    SplitSide,
    ThumbCluster as ThumbClusterData,
)
from skim.domain import KeyboardSide, SvalboardTargetKey

from .composable import Composable
from .font import Font
from .primitives import (
    Component,
    MetricsComponent,
    Point,
    Size,
)
from .svalboard_clusters import ThumbCluster
from .svalboard_halves import FingerHalf, FingerHalfMetrics

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

# Default proportion (of doc width) for ``layer_badge_inset`` — the
# leading gap between the badge edge and the label text. The trailing
# gap (label end → badge end) is ``2 * layer_badge_inset`` by design:
# a single configurable value governs both, with the trailing side
# weighted heavier so the right edge reads as breathing room rather
# than crowding the next column.
_BADGE_INSET_RATIO = 15 / 1600

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


def _badge_inset(config: SkimConfig) -> float:
    """Leading gap inside a layer badge — badge edge → label text.

    Reads the user's ``Spacing.layer_badge_inset`` override and
    resolves it through :func:`resolve_spacing`, falling back to the
    default proportion when unset. The trailing gap (label end → badge
    edge) is ``2 *`` this value; callers compute it inline via
    ``_badge_inset(config) * 2``.
    """
    return resolve_spacing(
        config.output.layout.spacing.layer_badge_inset,
        base=config.output.layout.width,
        default_proportion=_BADGE_INSET_RATIO,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _BadgeDims:
    width: float
    height: float
    border_radius: float
    index_col_w: float
    """Width of the index column shared across all named badges in this
    overview (PIL-measured against the widest index string). ``0.0``
    when no named badge is present — auto-named badges render with no
    index column."""


@dataclass(frozen=True, slots=True)
class _BadgeLabel:
    """Resolved label parts for a layer badge.

    ``index_text`` is ``None`` when the layer's name is the
    auto-generated ``Layer N`` placeholder — the badge then renders
    just the name with no index column (and the variant label below
    the badge aligns at the leading inset, matching the auto-named
    legacy layout).
    """

    index_text: str | None
    name_text: str


def _badge_label(qmk_idx: int, name: str) -> _BadgeLabel:
    """Compose a layer badge label, deduping the redundant ``Layer N`` case.

    When the layer name is the auto-generated ``Layer N`` placeholder
    matching ``qmk_idx`` (case-insensitive), drop the index column so
    badges don't read ``"0 LAYER 0"``. Named layers carry both: a
    right-aligned index (in a fixed-width column shared across the
    overview) and the upper-cased name.
    """
    upper = name.upper()
    if upper == f"LAYER {qmk_idx}":
        return _BadgeLabel(index_text=None, name_text=upper)
    return _BadgeLabel(index_text=str(qmk_idx), name_text=upper)


def _measure_badge_text_width(text: str, font_size: float) -> float:
    """PIL-measured width of ``text`` rendered at ``font_size``."""
    ref_size = 100
    pil_font = Font.FINGER_KEY.load(ref_size)
    return pil_font.getlength(text) * (font_size / ref_size)


def _compute_badge_dims(
    *,
    config: SkimConfig,
    finger_cluster_width: float,
    badge_labels: list[_BadgeLabel],
) -> _BadgeDims:
    """Compute uniform badge dimensions.

    Height matches the outer-key (E/W key) size of a finger cluster.
    Width is the wider of the two badge layouts:

    - **Named badge**: ``inset + index_col_w + inset + name_w + 2*inset``
      where ``index_col_w`` is the widest index string PIL-measured
      across all named badges, and ``name_w`` is the widest name string.
    - **Auto-named badge**: ``inset + name_w + 2*inset`` (no index
      column).

    The badge column in the overview shares a single width across all
    badges, so the named-case width dominates whenever any layer has a
    custom name.
    """
    height = finger_cluster_width * _OUTER_KEY_PROPORTION
    font_size = height * _BADGE_FONT_SIZE_RATIO
    inset = _badge_inset(config)

    if badge_labels:
        index_widths = [
            _measure_badge_text_width(lbl.index_text, font_size)
            for lbl in badge_labels
            if lbl.index_text is not None
        ]
        name_widths = [_measure_badge_text_width(lbl.name_text, font_size) for lbl in badge_labels]
        index_col_w = max(index_widths) if index_widths else 0.0
        max_name_w = max(name_widths)
    else:
        index_col_w = 0.0
        max_name_w = 50.0

    if index_col_w > 0:
        width = inset + index_col_w + inset + max_name_w + 2 * inset
    else:
        width = inset + max_name_w + 2 * inset

    return _BadgeDims(
        width=width,
        height=height,
        border_radius=height * _BADGE_BORDER_RADIUS_RATIO,
        index_col_w=index_col_w,
    )


@dataclass(frozen=True, slots=True)
class _OverviewLayoutDims:
    """Resolved badge + cluster sizing for the overview body.

    Consumed by :func:`KeymapOverview` at build time. Resolution goes
    through :class:`DocumentMetrics` directly rather than reading off
    ``ctx.document_metrics`` so the helper can run before a context
    has been pushed (kept that way to leave room for any future
    callers that need overview geometry without paying the full
    context-construction cost).
    """

    badge: _BadgeDims
    finger_cluster_width: float
    side_width: float
    col1_width: float
    thumb_cluster_width: float


def _resolve_overview_layout(
    config: SkimConfig,
    keymap: SvalboardKeymap[SvalboardTargetKey],
) -> _OverviewLayoutDims:
    """Solve the overview body's badge column ↔ cluster column split.

    Two-pass fixed-point: seed the cluster width from a generous
    placeholder, derive a badge width by PIL-measuring the badge
    texts at the seeded font size, then re-solve the cluster width
    against the real badge width. Converges in two passes because
    badge height only affects badge width indirectly via its own
    font size.
    """
    # Local import to avoid pulling :mod:`render_context` into modules
    # that only depend on :mod:`layout` value types.
    from .render_context import DocumentMetrics

    metrics = DocumentMetrics.from_config(config)
    column_gap = metrics.column_gap
    badge_to_clusters_gap = 2.0 * column_gap
    center_gap = _CENTER_GAP_INSET_COUNT * column_gap

    content_offset = metrics.margin + metrics.border_width + metrics.inset
    target_content_w = metrics.doc_width - 2 * content_offset

    render_layers: list[tuple[int, int]] = list(
        reversed(
            [
                (pos, layer_cfg.index)
                for pos, layer_cfg in enumerate(config.keyboard.layers)
                if layer_cfg.index in keymap.layers
            ]
        )
    )
    badge_labels: list[_BadgeLabel] = [
        _badge_label(qmk_idx, config.keyboard.layers[pos].name) for pos, qmk_idx in render_layers
    ]
    # The static THUMBS badge has no index — treat it as auto-named so
    # its rendering matches the auto-name path (no index column).
    badge_labels.append(_BadgeLabel(index_text=None, name_text="THUMBS"))

    def _solve(badge_w: float) -> tuple[float, float, float]:
        col1 = badge_w
        clusters_budget = target_content_w - col1 - badge_to_clusters_gap
        side_w = (clusters_budget - center_gap) / 2.0
        fcw = (side_w - 3 * column_gap) / 4.0
        return col1, side_w, fcw

    seed_fcw = (
        target_content_w - center_gap - 6 * column_gap - badge_to_clusters_gap - 200.0
    ) / 8.0
    seed_fcw = max(seed_fcw, 50.0)
    seed_badge = _compute_badge_dims(
        config=config,
        finger_cluster_width=seed_fcw,
        badge_labels=badge_labels,
    )
    _, _, fcw = _solve(seed_badge.width)
    badge = _compute_badge_dims(
        config=config,
        finger_cluster_width=fcw,
        badge_labels=badge_labels,
    )
    col1, side_w, fcw = _solve(badge.width)
    return _OverviewLayoutDims(
        badge=badge,
        finger_cluster_width=fcw,
        side_width=side_w,
        col1_width=col1,
        thumb_cluster_width=side_w * _THUMB_CLUSTER_WIDTH_PROPORTION,
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
    index_text: str | None,
    name_text: str,
    badge_width: float,
    badge_height: float,
    border_radius: float,
    index_col_w: float,
    fill_color: str,
    text_color: str = "white",
    variant: str | None = None,
    variant_color: str | None = None,
):
    """A coloured rectangle + label, with an optional variant label below.

    The label is laid out as up to four columns:

    1. Leading inset (``layer_badge_inset``).
    2. Index column (``index_col_w`` wide; index right-aligned inside).
       Skipped when ``index_text`` is ``None``.
    3. Inter-column inset (``layer_badge_inset``). Skipped with the index.
    4. Name column (``name_text``, left-aligned).
    5. Trailing inset (``2 * layer_badge_inset``) implicit in
       ``badge_width``.

    The variant label below the badge left-aligns with the **name**'s
    starting x: under the name column when the index is present, or
    under the leading-inset edge when the badge is auto-named (where
    the name itself sits flush with the leading inset).

    Reports :class:`MetricsComponent[LayerBadgeMetrics]`.
    """
    badge_font_size = badge_height * _BADGE_FONT_SIZE_RATIO
    use_system_fonts = ctx.config.output.style.use_system_fonts
    family = Font.FINGER_KEY.get_system_font_family() if use_system_fonts else Font.FINGER_KEY.value

    inset = _badge_inset(ctx.config)
    # Auto-named badges (no index column): name + variant align at the
    # leading inset — matches today's single-text behaviour for "LAYER N".
    # Named badges: index right-aligns inside its column; the name
    # starts after an inter-column inset, and the variant aligns under
    # the name.
    name_x_offset = inset if index_text is None else inset + index_col_w + inset

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
        if index_text is not None:
            # Right-aligned index, anchored at the index column's right
            # edge so digits stack across all named badges in the column.
            d.append(
                draw.Text(
                    index_text,
                    font_size=badge_font_size,
                    x=origin.x + inset + index_col_w,
                    y=origin.y + badge_height / 2.0,
                    text_anchor="end",
                    dominant_baseline="central",
                    font_family=family,
                    fill=text_color,
                )
            )
        d.append(
            draw.Text(
                name_text,
                font_size=badge_font_size,
                x=origin.x + name_x_offset,
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
                    x=origin.x + name_x_offset,
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

    def shift_layer_row_and_below(self, row_idx: int, amount: float) -> None:
        # ``row_idx`` here is a QMK layer index per the
        # :class:`RoutingLayout` Protocol contract. Translate via
        # :attr:`_layer_to_row` before delegating to the underlying
        # row list.
        if amount <= 0:
            return
        translated = self._layer_to_row.get(row_idx)
        if translated is None:
            return
        for i in range(translated, len(self._row_y_positions)):
            self._row_y_positions[i] += amount
        self._thumb_y_state[0] += amount

    def shift_below_layer_row(self, row_idx: int, amount: float) -> None:
        # ``row_idx`` is a QMK layer index — see
        # :meth:`shift_layer_row_and_below`.
        if amount <= 0:
            return
        translated = self._layer_to_row.get(row_idx)
        if translated is None:
            return
        for i in range(translated + 1, len(self._row_y_positions)):
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

    # Layers stack top-down with the HIGHEST QMK index on the top row.
    # Reversing the config-order list places layer 15 at the top and
    # layer 0 at the bottom, matching the legacy overview's row order
    # so the most "specialised" / topmost-active layers read first.
    render_layers: list[tuple[int, int]] = list(
        reversed(
            [
                (pos, layer_cfg.index)
                for pos, layer_cfg in enumerate(config.keyboard.layers)
                if layer_cfg.index in keymap.layers
            ]
        )
    )

    if not render_layers:
        # Nothing to render — return a zero-sized noop so the
        # composable's tuple-return contract holds. The document
        # composable also short-circuits, so this is defensive.
        return Size.zero(), lambda _d, _o: None

    # --- Phase 1: derive cluster sizing from the budget. ---
    dims = _resolve_overview_layout(config, keymap)
    badge_dims = dims.badge
    finger_cluster_width = dims.finger_cluster_width
    side_width = dims.side_width
    col1_width = dims.col1_width
    thumb_cluster_width = dims.thumb_cluster_width

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
    finger_halves: list[
        tuple[MetricsComponent[FingerHalfMetrics], MetricsComponent[FingerHalfMetrics]]
    ] = []
    for pos, qmk_idx in render_layers:
        layer_cfg = config.keyboard.layers[pos]
        layer_color = (
            config_palette.layers[pos].base_color
            if pos < len(config_palette.layers)
            else palette.neutral_color
        )
        layer_label = _badge_label(qmk_idx, layer_cfg.name)
        layer_badges.append(
            LayerBadge(
                index_text=layer_label.index_text,
                name_text=layer_label.name_text,
                badge_width=badge_dims.width,
                badge_height=badge_dims.height,
                border_radius=badge_dims.border_radius,
                index_col_w=badge_dims.index_col_w,
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

    # Thumb cluster uses the FIRST CONFIG POSITION layer (typically QMK
    # layer 0), independent of the row-order reversal. ``render_layers``
    # is reversed to render layer-15-on-top, so the bottom row is config
    # position 0 — pick that explicitly.
    base_pos, base_qmk_idx = render_layers[-1]
    del base_pos
    thumb_layer = keymap.layers[base_qmk_idx]
    left_thumb = ThumbCluster(
        side=KeyboardSide.LEFT,
        cluster=thumb_layer.left.thumb,
        layer_qmk_index=base_qmk_idx,
        **common_thumb_kwargs,
    )
    right_thumb = ThumbCluster(
        side=KeyboardSide.RIGHT,
        cluster=thumb_layer.right.thumb,
        layer_qmk_index=base_qmk_idx,
        **common_thumb_kwargs,
    )
    # THUMBS badge: no index column (auto-name path) so the label
    # left-aligns at the leading inset like the legacy single-text
    # rendering did.
    thumbs_badge = LayerBadge(
        index_text=None,
        name_text="THUMBS",
        badge_width=badge_dims.width,
        badge_height=badge_dims.height,
        border_radius=badge_dims.border_radius,
        index_col_w=badge_dims.index_col_w,
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

    # Inward bleeds on the finger halves — the central gap reserves
    # ``center_gap`` of empty space between the two halves' inward
    # indicators (i.e., the row with the worst inward bleed has the
    # documented gap; lower-bleed rows show paint-only intrusion
    # into the otherwise-empty space).
    finger_inward_left = max(_right_bleed(lfh) for lfh, _ in finger_halves)
    finger_inward_right = max(_left_bleed(rfh) for _, rfh in finger_halves)
    # Inward bleeds on the thumb clusters — only used when BOTH
    # sides have inward indicators (typically the knuckle / nail
    # keys). When both are present we may need to widen the
    # central reservation so the visible chrome-to-chrome gap
    # between the two thumbs is at least ``column_gap``.
    thumb_inward_left = _right_bleed(left_thumb)
    thumb_inward_right = _left_bleed(right_thumb)

    # Right outward bleed extends the body's outer right edge so
    # right-side indicators don't paint past the canvas. Left-side
    # outward bleed is intentionally NOT used — the badge-to-cluster
    # gap is pinned at ``2 * column_gap`` and any leftmost-row
    # chrome paints into that gap visually (paint-only, no layout
    # claim), matching how the central gap accommodates inward
    # indicators.
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
    # Top-of-body reservation: enough room for the half's own top
    # overflow (north-key indicators bleeding above the cluster) AND
    # the LAYERS heading, which sits above the first badge by
    # ``layers_heading_height`` and so reaches up to
    # ``placements[0].y + ew_offset - layers_heading_height``. The
    # heading is shorter than ``ew_offset`` in practice, so it fits
    # inside the badge's own row without extra reservation; we still
    # take the max in case future scaling changes that.
    body_top_padding = max(row_top_bleeds[0], layers_heading_height - ew_offset)
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
    # Pin the left half's keys-only edge ``badge_to_clusters_gap``
    # past the badge column so the visible gap between the badge
    # and the keys is exactly ``2 * column_gap`` on every row, not
    # just the row with the worst left-side indicator bleed.
    # Indicators that bleed left of the keys-only edge are paint-only
    # and may visually intrude into the gap on those rows — same
    # accommodation the central gap makes for inward indicators.
    left_half_x = col1_width + badge_to_clusters_gap
    # Central reservation. The finger halves want the visible gap
    # between their inward indicators to equal ``center_gap`` (i.e.,
    # ``2 * column_gap``). When BOTH thumbs additionally have
    # inward-bleed indicators (knuckle / nail keys with a
    # ``layer_switch``), we further require the visible chrome-to-
    # chrome gap between the two thumbs to be at least
    # ``column_gap`` — that means the central column has to be at
    # least ``thumb_inward_left + column_gap + thumb_inward_right``
    # wide. Take the larger of the two requirements; ignore the
    # thumb requirement entirely when only one (or neither) thumb
    # has inward bleed, leaving lower-bleed configs unchanged.
    finger_central_reservation = finger_inward_left + center_gap + finger_inward_right
    if thumb_inward_left > 0 and thumb_inward_right > 0:
        thumb_central_reservation = thumb_inward_left + column_gap + thumb_inward_right
        central_reservation = max(finger_central_reservation, thumb_central_reservation)
    else:
        central_reservation = finger_central_reservation
    right_half_x = left_half_x + side_width + central_reservation
    # Body width still accounts for outer bleeds so the right edge
    # encloses any right-side indicators that paint past the right
    # half's keys-only edge.
    body_width = right_half_x + side_width + max_right_outer_bleed

    # Thumbs: align each thumb's keys-only edge with the matching
    # finger half's keys-only edge — left thumb's right edge with
    # the left half's right edge, right thumb's left edge with the
    # right half's left edge. Inward thumb chrome (knuckle / nail
    # indicators) may paint into the central gap visually; same
    # paint-only accommodation the central gap and badge-to-cluster
    # gap already make.
    left_thumb_x = left_half_x + side_width - left_thumb.size.width
    right_thumb_x = right_half_x

    # --- Phase 6: connector routing. ---
    # Mutable layout state — :func:`route_overview_connectors` shifts
    # rows during pass 1 to make room for inter-row lane banks. After
    # routing the lists below reflect the post-shift positions and we
    # rebuild ``placements`` against them for the draw_at closure.
    mutable_row_ys: list[float] = [p.y for p in placements]
    mutable_thumb_y: list[float] = [thumb_y]
    # Routing-derived constants are needed in Phase 7 (body sizing)
    # whether or not routing actually runs, so compute them up front.
    outer_key_size = finger_cluster_width * _OUTER_KEY_PROPORTION
    keymap_spacing = outer_key_size * _CONNECTOR_SPACING_RATIO
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
        thumb_layer_data = keymap.layers[base_qmk_idx]
        thumb_source = ThumbSource(
            source_layer=base_qmk_idx,
            left=thumb_layer_data.left.thumb,
            right=thumb_layer_data.right.thumb,
        )

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
    cluster_bottom = thumb_y + left_thumb.size.height
    doc_width = config.output.layout.width
    connector_stroke_width = doc_width * _CONNECTOR_PATH_STROKE_WIDTH_RATIO
    indicator_stroke_half = doc_width * _CIRCLE_STROKE_WIDTH_RATIO / 2.0
    connector_stroke_half = connector_stroke_width / 2.0

    # Indicator circles paint past the cluster's keys-only edge by
    # ``bleed`` (centerline) plus ``indicator_stroke_half`` (stroke
    # extent past the centerline). Reserve both so the body fully
    # contains the painted strokes.
    body_width = right_half_x + side_width + max_right_outer_bleed + indicator_stroke_half
    body_height = cluster_bottom + thumb_bottom_bleed + indicator_stroke_half
    if routing is not None and routing.paths:
        # Right-side: routing columns sit past the cluster overflow
        # (the first column is ``cluster_right_edge + 2 * keymap_spacing``)
        # and fully subsume ``max_right_outer_bleed`` once present.
        # The outermost column's vertical segment paints with stroke
        # extending ``connector_stroke_half`` past the centerline.
        body_width = (
            right_half_x
            + side_width
            + max(
                max_right_outer_bleed + indicator_stroke_half,
                routing.extra_right_padding + connector_stroke_half,
            )
        )

        # Bottom-side: actual painted content below ``cluster_bottom``
        # is either (a) indicator circle strokes (``thumb_bottom_bleed
        # + indicator_stroke_half``) or (b) the bottommost DOWN lane
        # (when DOWN lanes exist). The legacy ``extra_bottom_padding``
        # value includes a rect-padding offset (``6 * stroke_width``,
        # for routing geometry only — no paint there) and a ``0.5 *
        # keymap_spacing`` buffer for canvas-edge clearance. Strip
        # both: ``KeymapDocument``'s content_offset provides
        # canvas-edge breathing room and the rect padding is metadata.
        if routing.extra_bottom_padding >= keymap_spacing:
            # DOWN lanes present. The bottommost lane sits at
            # ``cluster_bottom + thumb_overhang_b + n_d * ks``, where
            # ``extra_bottom_padding = (n_d + 0.5) * ks + thumb_overhang_b``.
            # Strip the ``0.5 * ks`` buffer; reserve the connector
            # stroke half below the lane.
            bottom_lane_below_cluster = (
                routing.extra_bottom_padding - 0.5 * keymap_spacing + connector_stroke_half
            )
            body_height = cluster_bottom + max(
                thumb_bottom_bleed + indicator_stroke_half,
                bottom_lane_below_cluster,
            )

    # --- Phase 8: heading position + connector path styling. ---
    layers_heading_baseline_y = (
        placements[0].badge_y - badge_font_size * _VARIANT_LABEL_OFFSET_RATIO_OF_FONT
    )
    layers_heading_x = badge_x + _badge_inset(config)
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


# ===========================================================================
# Connector routing — two-pass router that turns layer-switch indicators into
# the dotted lines threading from each indicator to its destination layer's
# row. Migrated from the standalone ``connectors`` module so all overview
# logic lives in this file.
#
# See ``docs/superpowers/specs/2026-04-26-overview-connector-routing-design.md``
# for the algorithm spec.
# ===========================================================================


class RoutingLayout(Protocol):
    """Minimal layout surface the connector router needs.

    Implemented by :class:`_OverviewRoutingLayout` above (which exposes
    a virtual QMK-indexed view of the overview's mutable row + thumb
    Y positions).
    """

    @property
    def layer_row_y_positions(self) -> list[float]: ...

    @property
    def has_double_south(self) -> bool:
        """Whether the keyboard renders a double-south key per finger cluster.

        When False, ``double_south_key`` slots are not drawn and so cannot
        originate a connector — even if the keymap places a layer-switching
        macro at that position. The router uses this to keep its trigger
        list aligned with what the indicator pass actually rendered.
        """
        ...

    @property
    def row_gap(self) -> float:
        """Default gap between adjacent layer rows when no lanes occupy it.

        Pass 1 replaces this with a lane-sized bank (one ``keymap_spacing``
        of clearance at each end plus the lane width) whenever the upper
        layer has DOWN connectors and/or the lower layer has UP connectors.
        """
        ...

    def layer_row_bounding_box(self, target_layer: int) -> tuple[float, float, float, float]: ...

    def layer_row_target_y(self, target_layer: int) -> float:
        """Return the Y where connectors should land on this layer's row.

        Should be the vertical center of the row's East key (R4 cluster's
        E key center). Different from ``bbox.y + bbox.height / 2`` when the
        row contains a Double-South key — in that case the bbox center
        falls between S and DS, well below the East key.
        """
        ...

    def thumb_cluster_y_bounds(self) -> tuple[float, float]: ...

    def shift_layer_row_and_below(self, row_idx: int, amount: float) -> None:
        """Apply a layer's extra_top_padding."""
        ...

    def shift_below_layer_row(self, row_idx: int, amount: float) -> None:
        """Apply a layer's extra_bottom_padding."""
        ...

    def shift_thumb_down(self, amount: float) -> None: ...


class Direction(Enum):
    """The current heading of a connector path's last segment."""

    UP = "up"
    RIGHT = "right"
    DOWN = "down"
    LEFT = "left"


@dataclass
class ConnectorStep:
    """One in-progress connector path with its current state.

    Attributes:
        key: The source key whose indicator originates this path.
        direction: Current heading of the path's last segment.
        target_point: Where the path must terminate (one per target layer).
        target_layer: The destination layer index.
        col_x: The routing column X coordinate, set during Phase 2 allocation.
        current_point: The path's current end point; updated on each move/line
            so subsequent routing phases can reason about where the pen sits.
        indicator_rect: The source key's layer-indicator bounding rect as
            ``(x, y, width, height)``. Populated by the orchestrator before
            ``set_initial_moveto`` runs; the renderer (not the dataclass)
            owns the rect geometry.
        key_origin_attr: The thumb-cluster attribute name that produced this
            step (e.g. ``"down_key"``, ``"up_key"``). Used by Phase 1 routing
            to identify partner paths (e.g. matching LT_Up to LT_Down).
        source_cluster_attr: The source cluster identifier (e.g. ``"left.index"``,
            ``"right.pinky"``). Empty for thumb steps. Used by
            ``phase1_redirect_right_to_down`` to scope the S+DS partner search
            to the same finger cluster.
        path: Accumulating SVG path; appended to during routing.
    """

    key: SvalboardTargetKey | None
    direction: Direction
    target_point: tuple[float, float]
    target_layer: int
    col_x: float = 0.0
    current_point: tuple[float, float] = (0.0, 0.0)
    indicator_rect: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    key_origin_attr: str = ""
    source_cluster_attr: str = ""
    path: draw.Path = field(default_factory=lambda: draw.Path(fill="none"))


@dataclass
class ConnectorRouting:
    """Output of the routing algorithm.

    Attributes:
        paths: All connector paths in render order, paired with the
            target_layer index of each path. The renderer uses the
            target_layer to pick the per-path stroke color.
        extra_bottom_padding: Caller must extend canvas height by this amount.
            Includes 0.5 * keymap_spacing of buffer between the bottommost DOWN
            lane and the canvas edge when DOWN lanes exist (zero otherwise).
        extra_right_padding: Caller must extend canvas width by this amount.
            Computed as ``(cols_used + 1) * keymap_spacing`` so the canvas
            covers the routing columns plus the keymap_spacing-long LEFT
            segment from the innermost column to ``target_point.x``.
    """

    paths: list[tuple[draw.Path, int]]
    extra_bottom_padding: float
    extra_right_padding: float


@dataclass(frozen=True, slots=True)
class OverviewLayerSource:
    """One layer's finger clusters as a routing source.

    Attributes:
        source_layer: The QMK layer index whose finger keys originate the paths.
        left: Left-side SplitSide containing four finger clusters (and a
            placeholder thumb that the finger router ignores).
        right: Right-side SplitSide containing four finger clusters.
    """

    source_layer: int
    left: SplitSide[SvalboardTargetKey]
    right: SplitSide[SvalboardTargetKey]


@dataclass(frozen=True, slots=True)
class ThumbSource:
    """The thumb cluster as a routing source.

    Attributes:
        source_layer: The QMK layer index the thumb cluster is rendered for.
        left: Left thumb cluster.
        right: Right thumb cluster.
    """

    source_layer: int
    left: ThumbClusterData[SvalboardTargetKey]
    right: ThumbClusterData[SvalboardTargetKey]


def target_point_for(
    layout: RoutingLayout,
    target_layer: int,
    source_layer: int,
    keymap_spacing: float,
) -> tuple[float, float] | None:
    """Compute the target point for a connector, or return ``None`` to skip.

    Returns ``None`` for:
    - Self-referential triggers (source == target).
    - Target layer index out of range for the layout's rendered layer rows.

    The target point's X is one ``keymap_spacing`` to the right of the
    layer row's right edge. Its Y is the row's connector-landing Y
    (``layer_row_target_y``), which corresponds to the East key's vertical
    center — not the row bounding box's center, which can fall between S
    and DS rows when Double-South is present.
    """
    if target_layer == source_layer:
        return None
    if target_layer < 0 or target_layer >= len(layout.layer_row_y_positions):
        return None
    try:
        x, _y, w, _h = layout.layer_row_bounding_box(target_layer)
        target_y = layout.layer_row_target_y(target_layer)
    except KeyError:
        # Unmapped QMK index — target layer isn't rendered. Same as
        # out-of-range: skip.
        return None
    return (x + w + keymap_spacing, target_y)


def set_initial_moveto(step: ConnectorStep) -> None:
    """Place the path's first moveTo on the indicator's bounding rect edge.

    The starting edge depends on the path's initial direction:
    - UP    -> top edge, horizontally centered
    - RIGHT -> right edge, vertically centered
    - DOWN  -> bottom edge, horizontally centered
    - LEFT  -> left edge, vertically centered

    Reads ``step.indicator_rect``; the orchestrator is responsible for
    populating it before this function runs.
    """
    rx, ry, rw, rh = step.indicator_rect
    if step.direction == Direction.UP:
        x, y = rx + rw / 2.0, ry
    elif step.direction == Direction.RIGHT:
        x, y = rx + rw, ry + rh / 2.0
    elif step.direction == Direction.DOWN:
        x, y = rx + rw / 2.0, ry + rh
    else:  # LEFT
        x, y = rx, ry + rh / 2.0
    step.path.M(x, y)
    step.current_point = (x, y)


# Priority for the right-pinky (R4) finger cluster. Most keys exit RIGHT
# directly because R4 sits closest to the routing columns. The E key would
# cross itself going RIGHT so it escapes UP; C is buried in the middle so
# it exits DOWN.
_R4_PRIORITY: list[tuple[str, Direction]] = [
    ("north_key", Direction.RIGHT),
    ("west_key", Direction.RIGHT),
    ("south_key", Direction.RIGHT),
    ("double_south_key", Direction.RIGHT),
    ("east_key", Direction.UP),
    ("center_key", Direction.DOWN),
]

# Priority for every other finger cluster. N/W/E exit UP over the cluster
# top; S/DS/C exit DOWN under it.
_NON_R4_PRIORITY: list[tuple[str, Direction]] = [
    ("west_key", Direction.UP),
    ("north_key", Direction.UP),
    ("east_key", Direction.UP),
    ("south_key", Direction.DOWN),
    ("double_south_key", Direction.DOWN),
    ("center_key", Direction.DOWN),
]


# Priority groups for thumb cluster keys. Each entry is
# (side, attribute_name, default_direction).
_THUMB_PRIORITY: list[tuple[KeyboardSide, str, Direction]] = [
    # Right thumb's outward keys
    (KeyboardSide.RIGHT, "double_down_key", Direction.RIGHT),
    (KeyboardSide.RIGHT, "pad_key", Direction.RIGHT),
    (KeyboardSide.RIGHT, "up_key", Direction.RIGHT),
    (KeyboardSide.RIGHT, "down_key", Direction.RIGHT),
    # Inward-facing UP escapes
    (KeyboardSide.RIGHT, "nail_key", Direction.UP),
    (KeyboardSide.LEFT, "nail_key", Direction.UP),
    (KeyboardSide.LEFT, "double_down_key", Direction.UP),
    (KeyboardSide.LEFT, "pad_key", Direction.UP),
    # Inward-facing DOWN escapes
    (KeyboardSide.RIGHT, "knuckle_key", Direction.DOWN),
    (KeyboardSide.LEFT, "knuckle_key", Direction.DOWN),
    (KeyboardSide.LEFT, "down_key", Direction.DOWN),
]


def build_thumb_path_list(
    left: ThumbClusterData[SvalboardTargetKey],
    right: ThumbClusterData[SvalboardTargetKey],
    layout: RoutingLayout,
    source_layer: int,
    keymap_spacing: float,
) -> list[ConnectorStep]:
    """Build the priority-ordered ConnectorStep list for the thumb cluster.

    Includes the LT_Up special case: if both LT_Down and LT_Up have triggers,
    LT_Up's initial direction is LEFT (to be redirected DOWN in Phase 1);
    otherwise LT_Up takes DOWN directly.
    """
    steps: list[ConnectorStep] = []
    for side, attr, direction in _THUMB_PRIORITY:
        cluster = left if side == KeyboardSide.LEFT else right
        key: SvalboardTargetKey = getattr(cluster, attr)
        if key.layer_switch is None:
            continue
        target = target_point_for(layout, key.layer_switch, source_layer, keymap_spacing)
        if target is None:
            continue
        steps.append(
            ConnectorStep(
                key=key,
                direction=direction,
                target_point=target,
                target_layer=key.layer_switch,
                key_origin_attr=attr,
            )
        )

    # LT_Up special case (added last so its column allocation comes after
    # any LT_Down DOWN-routed path in Phase 2).
    if left.up_key.layer_switch is not None:
        target = target_point_for(layout, left.up_key.layer_switch, source_layer, keymap_spacing)
        if target is not None:
            # Use LEFT direction only if LT_Down actually entered the priority
            # list (i.e., its target survived the skip rules). Without this guard,
            # phase1_redirect_left_to_down would fall back to the wrong DOWN step.
            lt_down_step = next(
                (s for s in steps if s.key_origin_attr == "down_key" and s.key is left.down_key),
                None,
            )
            direction = Direction.LEFT if lt_down_step is not None else Direction.DOWN
            steps.append(
                ConnectorStep(
                    key=left.up_key,
                    direction=direction,
                    target_point=target,
                    target_layer=left.up_key.layer_switch,
                    key_origin_attr="up_key",
                )
            )

    return steps


def build_finger_path_list_for_cluster(
    cluster: FingerClusterData[SvalboardTargetKey],
    is_r4: bool,
    cluster_attr: str,
    source_layer: int,
    layout: RoutingLayout,
    keymap_spacing: float,
) -> list[ConnectorStep]:
    """Build the priority-ordered ConnectorStep list for one finger cluster.

    Applies the R4 vs non-R4 priority table. For non-R4 clusters: when both
    south_key and double_south_key trigger, south's initial direction is
    overridden to RIGHT (the S+DS special case — phase1_redirect_right_to_down
    redirects it to DOWN one keymap_spacing east of DS's drop column).
    Otherwise south takes its table direction (DOWN).

    Args:
        cluster: The finger cluster to scan for layer-switch triggers.
        is_r4: True if this is the right-pinky cluster (uses _R4_PRIORITY).
        cluster_attr: A stable identifier for this cluster, e.g. ``"left.index"``
            or ``"right.pinky"``. Stored on each step's ``source_cluster_attr``
            so phase1_redirect_right_to_down can scope its partner search.
        source_layer: The QMK layer index where the cluster lives (the source
            of the path).
        layout: The routing layout (provides target geometry).
        keymap_spacing: Spacing constant.

    Returns:
        ConnectorSteps in priority order, skipping keys whose target_point is
        None (self-ref or out-of-range).
    """
    priority = _R4_PRIORITY if is_r4 else _NON_R4_PRIORITY
    has_ds = layout.has_double_south
    south_ds_special = (
        not is_r4
        and has_ds
        and cluster.south_key.layer_switch is not None
        and cluster.double_south_key.layer_switch is not None
    )

    steps: list[ConnectorStep] = []
    for attr, direction in priority:
        if attr == "double_south_key" and not has_ds:
            continue
        key = getattr(cluster, attr)
        if key.layer_switch is None:
            continue
        target = target_point_for(layout, key.layer_switch, source_layer, keymap_spacing)
        if target is None:
            continue
        actual_direction = direction
        if south_ds_special and attr == "south_key":
            actual_direction = Direction.RIGHT
        steps.append(
            ConnectorStep(
                key=key,
                direction=actual_direction,
                target_point=target,
                target_layer=key.layer_switch,
                key_origin_attr=attr,
                source_cluster_attr=cluster_attr,
            )
        )

    return steps


# Cluster iteration order for a finger layer:
# L4, L3, L2, L1, R1, R2, R3, R4 — outer-to-inner on the left, then
# inner-to-outer on the right. R4 is the only cluster that uses _R4_PRIORITY.
_FINGER_CLUSTER_ITER_ORDER: list[tuple[str, str, bool]] = [
    # (cluster_attr_for_step, side_attr_on_SplitSide, is_r4)
    ("left.pinky", "pinky", False),
    ("left.ring", "ring", False),
    ("left.middle", "middle", False),
    ("left.index", "index", False),
    ("right.index", "index", False),
    ("right.middle", "middle", False),
    ("right.ring", "ring", False),
    ("right.pinky", "pinky", True),
]


def build_finger_path_list_for_layer(
    left: SplitSide[SvalboardTargetKey],
    right: SplitSide[SvalboardTargetKey],
    source_layer: int,
    layout: RoutingLayout,
    keymap_spacing: float,
) -> list[ConnectorStep]:
    """Build the path list for all 8 finger clusters in one layer.

    Cluster iteration order: L4, L3, L2, L1, R1, R2, R3, R4. Within each
    cluster, keys follow the R4 vs non-R4 priority table.
    """
    steps: list[ConnectorStep] = []
    for cluster_attr, side_attr, is_r4 in _FINGER_CLUSTER_ITER_ORDER:
        side = left if cluster_attr.startswith("left.") else right
        cluster = getattr(side, side_attr)
        steps.extend(
            build_finger_path_list_for_cluster(
                cluster=cluster,
                is_r4=is_r4,
                cluster_attr=cluster_attr,
                source_layer=source_layer,
                layout=layout,
                keymap_spacing=keymap_spacing,
            )
        )
    return steps


def phase1_redirect_left_to_down(
    path_list: list[ConnectorStep],
    keymap_spacing: float,
) -> None:
    """Redirect LEFT-direction paths (LT_Up special case) to DOWN.

    The path is extended west far enough to clear the conflicting DOWN path's
    drop column (LT_Down), then its direction is flipped to DOWN so the regular
    DOWN->RIGHT sub-step picks it up.

    LT_Up's LEFT direction is only assigned by ``build_thumb_path_list`` when
    LT_Down actually entered the priority list (i.e., its target survived the
    skip rules). With that guard upstream, LEFT-direction steps always have an
    annotated ``key_origin_attr=='down_key'`` partner — there is no fallback
    if the partner is missing, matching ``phase1_redirect_right_to_down``'s
    contract.
    """
    left_steps = [s for s in path_list if s.direction == Direction.LEFT]
    if not left_steps:
        return
    # Find the LT_Down partner by its origin attr (set by build_thumb_path_list).
    partner = next(
        (s for s in path_list if s.direction == Direction.DOWN and s.key_origin_attr == "down_key"),
        None,
    )
    if partner is None:
        return  # malformed input; nothing to redirect against

    new_x = partner.current_point[0] - keymap_spacing
    for step in left_steps:
        step.path.L(new_x, step.current_point[1])
        step.current_point = (new_x, step.current_point[1])
        step.direction = Direction.DOWN


def phase1_redirect_right_to_down(
    path_list: list[ConnectorStep],
    keymap_spacing: float,
) -> None:
    """Redirect RIGHT-direction paths (S+DS special case) to DOWN.

    For each RIGHT-direction step (which represents South in the S+DS
    conflict), find its DS partner via ``key_origin_attr ==
    "double_south_key"`` AND same ``source_cluster_attr``. Extend east one
    keymap_spacing past the partner's current X (its drop column), then
    mark direction DOWN so the regular DOWN->RIGHT sub-step picks it up.

    No-op when no RIGHT-direction steps exist. Steps with no DS partner
    (malformed input) are left unchanged.
    """
    right_steps = [s for s in path_list if s.direction == Direction.RIGHT]
    if not right_steps:
        return

    for step in right_steps:
        partner = next(
            (
                s
                for s in path_list
                if s.direction == Direction.DOWN
                and s.key_origin_attr == "double_south_key"
                and s.source_cluster_attr == step.source_cluster_attr
            ),
            None,
        )
        if partner is None:
            continue  # malformed input; nothing to redirect against

        new_x = partner.current_point[0] + keymap_spacing
        step.path.L(new_x, step.current_point[1])
        step.current_point = (new_x, step.current_point[1])
        step.direction = Direction.DOWN


def phase1_up_to_right(
    path_list: list[ConnectorStep],
    cluster_top: float,
    min_y: float,
    keymap_spacing: float,
) -> float:
    """Convert each UP-direction step's path into an east-bound escape lane.

    Each successive UP step takes a lane one ``keymap_spacing`` higher than
    the previous, starting from ``min(cluster_top - spacing, min_y - spacing)``.

    ``cluster_top`` is the cluster's bounding-box top edge; ``min_y`` is the
    running minimum Y across already-routed segments / current path-list entry
    points. Both are needed because the lane must clear whichever sits higher,
    so the clamp picks the smaller (more negative-Y) of the two.

    Returns the vertical extent the lanes occupy above ``cluster_top``. When
    ``min_y >= cluster_top`` (typical: indicators sit inside or below the
    cluster top), this is exactly ``N * keymap_spacing`` — N lanes spaced
    one ``keymap_spacing`` apart starting at ``cluster_top - keymap_spacing``.
    When ``min_y < cluster_top`` (e.g. a north_key indicator overhangs the
    cluster), lanes start higher to clear the indicator and the padding grows
    by ``cluster_top - min_y`` so the topmost lane still fits within the
    reserved space.
    """
    up_steps = [s for s in path_list if s.direction == Direction.UP]
    if not up_steps:
        return 0.0
    new_y = min(cluster_top - keymap_spacing, min_y - keymap_spacing)
    for step in up_steps:
        step.path.L(step.current_point[0], new_y)
        step.current_point = (step.current_point[0], new_y)
        step.direction = Direction.RIGHT
        new_y -= keymap_spacing
    return len(up_steps) * keymap_spacing + max(0.0, cluster_top - min_y)


def phase1_down_to_right(
    path_list: list[ConnectorStep],
    cluster_bottom: float,
    max_y: float,
    keymap_spacing: float,
) -> float:
    """Convert each DOWN-direction step's path into an east-bound escape lane below the cluster.

    Mirror image of ``phase1_up_to_right``. ``cluster_bottom`` is the cluster's
    bounding-box bottom edge; ``max_y`` is the running maximum Y across
    already-routed segments / current path-list entry points. Both are needed
    because the lane must clear whichever sits lower, so the clamp picks the
    larger (more positive-Y) of the two.

    Returns the vertical extent the lanes plus buffer occupy below
    ``cluster_bottom``. When ``max_y <= cluster_bottom`` (typical), this is
    ``(N + 0.5) * keymap_spacing`` — lane 1 at ``cluster_bottom + spacing``,
    lane N at ``cluster_bottom + N * spacing``, plus ``0.5 * spacing`` of
    buffer. When ``max_y > cluster_bottom`` (e.g. an indicator below the
    cluster bottom), lanes start lower to clear it and the padding grows by
    ``max_y - cluster_bottom`` so the bottommost lane still fits within the
    reserved space. The trailing ``0.5 * keymap_spacing`` keeps the
    border/copyright from crowding the bottommost connector.
    """
    down_steps = [s for s in path_list if s.direction == Direction.DOWN]
    if not down_steps:
        return 0.0
    new_y = max(cluster_bottom + keymap_spacing, max_y + keymap_spacing)
    for step in down_steps:
        step.path.L(step.current_point[0], new_y)
        step.current_point = (step.current_point[0], new_y)
        step.direction = Direction.RIGHT
        new_y += keymap_spacing
    return (len(down_steps) + 0.5) * keymap_spacing + max(0.0, max_y - cluster_bottom)


def allocate_columns(
    path_list: list[ConnectorStep],
    first_column_x: float,
    keymap_spacing: float,
) -> int:
    """Assign each step a routing column, sharing columns where Y-spans don't overlap.

    Assigns each step's ``col_x`` in place. Greedy left-most fit: for each
    step, find the leftmost column whose occupied Y-spans don't overlap this
    step's span; if none fits, allocate a new column. Column ``i`` sits at
    ``first_column_x + i * keymap_spacing``, so every assigned ``col_x`` is
    ``>= first_column_x``. Returns the number of columns used.
    """
    columns: list[list[tuple[float, float]]] = []  # per column: list of (y_min, y_max)
    for step in path_list:
        span_low = min(step.current_point[1], step.target_point[1])
        span_high = max(step.current_point[1], step.target_point[1])
        placed = False
        for idx, occupied in enumerate(columns):
            if all(span_high < y_lo or span_low > y_hi for y_lo, y_hi in occupied):
                occupied.append((span_low, span_high))
                step.col_x = first_column_x + idx * keymap_spacing
                placed = True
                break
        if not placed:
            columns.append([(span_low, span_high)])
            step.col_x = first_column_x + (len(columns) - 1) * keymap_spacing
    return len(columns)


def phase2_route_to_targets(path_list: list[ConnectorStep]) -> None:
    """Phase 2 of the routing algorithm.

    For each step:
      1. Extend east to the assigned column (``col_x``).
      2. Drop or rise to the target's Y.
      3. Mark direction LEFT.

    Then for each unique ``target_layer``, the outermost path (largest
    ``col_x``) extends west to ``target_point`` so the final horizontal
    segment is drawn exactly once per target.

    Mutates each step's ``path``, ``current_point``, and ``direction`` in place.
    """
    # Step 1 + 2 — east, drop.
    for step in path_list:
        step.path.L(step.col_x, step.current_point[1])
        step.current_point = (step.col_x, step.current_point[1])
        step.path.L(step.col_x, step.target_point[1])
        step.current_point = (step.col_x, step.target_point[1])
        step.direction = Direction.LEFT

    # Step 3 — multi-target merge: outermost step per target_layer emits the final LEFT segment.
    by_target: dict[int, list[ConnectorStep]] = {}
    for step in path_list:
        by_target.setdefault(step.target_layer, []).append(step)
    for steps in by_target.values():
        outermost = max(steps, key=lambda s: s.col_x)
        outermost.path.L(outermost.target_point[0], outermost.target_point[1])
        outermost.current_point = outermost.target_point


def _layer_cluster_y_bounds(layout: RoutingLayout, source_layer: int) -> tuple[float, float]:
    """Return (top_y, bottom_y) of the finger clusters in a given layer's row."""
    _, row_y, _, row_h = layout.layer_row_bounding_box(source_layer)
    return (row_y, row_y + row_h)


def route_overview_connectors(
    layers: Sequence[OverviewLayerSource],
    thumb: ThumbSource,
    layout: RoutingLayout,
    compute_indicator_rects: Callable[[], Mapping[int, tuple[float, float, float, float]]],
    keymap_spacing: float,
) -> ConnectorRouting:
    """Top-level orchestrator for overview connector routing.

    Two-pass strategy: pass 1 discovers paddings per source and applies
    cascading layout shifts; pass 2 rebuilds paths against the fully-shifted
    layout for final geometry. Phase 2 column allocation runs once globally
    across all sources combined.

    Args:
        layers: Per-layer finger sources.
        thumb: The thumb cluster source.
        layout: The mutable routing layout. Mutated in place via shift_*
            methods during pass 1.
        compute_indicator_rects: Callable invoked twice (once before pass 1,
            once between passes). Each invocation MUST reflect the *current*
            layout state. Keys MUST be ``id(SvalboardTargetKey)`` of the same
            Python instance the router will encounter via ``getattr(cluster,
            attr)`` — value equality is unsafe because layer-switching macros
            (``MO``, ``TO``, ``DF``, ``TG``) with identical layer arguments
            produce equal-valued ``SvalboardTargetKey`` instances across
            layers.
        keymap_spacing: Spacing constant for routing geometry (typically
            ``0.6 * outer_key_size``).

    Returns:
        ConnectorRouting with paths and the residual paddings the caller
        must apply. ``extra_bottom_padding`` is the thumb cluster's bottom
        padding; ``extra_right_padding`` is ``(cols_used + 1) * keymap_spacing``.
        Top padding is consumed via cascading layout shifts during pass 1.
    """
    # --- Pass 1: discover paddings, apply cascading layout shifts. ---
    rects_pass1 = compute_indicator_rects()
    thumb_extra_bottom = _pass1_discover_and_shift(
        layers, thumb, layout, rects_pass1, keymap_spacing
    )

    # --- Pass 2: rebuild paths against the now-shifted layout. ---
    rects_pass2 = compute_indicator_rects()
    all_paths = _pass2_build_paths(layers, thumb, layout, rects_pass2, keymap_spacing)

    if not all_paths:
        return ConnectorRouting(
            paths=[],
            extra_bottom_padding=0.0,
            extra_right_padding=0.0,
        )

    # --- Phase 2: global column allocation + drop to targets. ---
    anchor = layers[0].source_layer if layers else thumb.source_layer
    row_x, _, row_w, _ = layout.layer_row_bounding_box(anchor)
    first_column_x = row_x + row_w + 2 * keymap_spacing
    cols_used = allocate_columns(all_paths, first_column_x, keymap_spacing)
    phase2_route_to_targets(all_paths)

    return ConnectorRouting(
        paths=[(s.path, s.target_layer) for s in all_paths],
        extra_bottom_padding=thumb_extra_bottom,
        extra_right_padding=(cols_used + 1) * keymap_spacing,
    )


def _pass1_discover_and_shift(
    layers: Sequence[OverviewLayerSource],
    thumb: ThumbSource,
    layout: RoutingLayout,
    indicator_rects: Mapping[int, tuple[float, float, float, float]],
    keymap_spacing: float,
) -> float:
    """Pass 1: route each source, discover paddings, apply gap-aware shifts.

    Walks layer sources top-to-bottom in render order, carrying running state
    for the layer immediately above the current one (``prev_n_d``,
    ``prev_overhang_b``, ``prev_qmk``). For each *inter-layer* gap, the
    upper layer's DOWN connectors and the lower layer's UP connectors share
    a single contiguous lane bank: ``(N_d + N_u + 1) * keymap_spacing`` of
    space, plus any indicator overhang from either side, replaces the
    layout's default ``row_gap`` entirely. The same formula applies to the
    bottommost-layer/thumb gap.

    The topmost layer's UP padding (gap above it, abutting the header) and
    the thumb's DOWN padding (gap below it, abutting the canvas edge /
    copyright) are kept on their per-source formulas — neither has a layer
    on the other side of the gap to merge with.

    Initial cluster bounds are snapshotted up front so each layer's
    ``overhang_top``/``overhang_bottom`` stays referenced to its
    pre-shift cluster_top/cluster_bottom (otherwise shifts applied to
    earlier layers would corrupt the overhang of later ones).

    Returns the thumb's extra_bottom_padding (the only padding NOT applied
    via layout shifts; it grows the canvas at the bottom).
    """
    # Snapshot pre-shift cluster bounds. ``layout.layer_row_bounding_box``
    # always returns the *current* row position, so as soon as the first
    # shift fires the bounds for downstream layers move with it. We compute
    # overhangs against the snapshot so each layer's overhang represents
    # "indicator extent beyond the cluster's own edge" — not "indicator
    # extent vs. wherever the cluster has been pushed by another layer".
    initial_layer_bounds: dict[int, tuple[float, float]] = {}
    for layer in layers:
        _, top, _, height = layout.layer_row_bounding_box(layer.source_layer)
        initial_layer_bounds[layer.source_layer] = (top, top + height)
    initial_thumb_top, initial_thumb_bottom = layout.thumb_cluster_y_bounds()
    row_gap = layout.row_gap

    # Iterate in render order: top row first (smallest initial cluster_top).
    sorted_layers = sorted(layers, key=lambda layer: initial_layer_bounds[layer.source_layer][0])

    # State carried from the previous (upper) iteration.
    prev_n_d = 0
    prev_overhang_b = 0.0
    prev_qmk: int | None = None

    for layer in sorted_layers:
        n_u, n_d, overhang_t, overhang_b = _route_finger_layer_phase1(
            layer, layout, indicator_rects, initial_layer_bounds, keymap_spacing
        )

        if prev_qmk is None:
            # Topmost layer: gap above it abuts the header strip.
            top_pad = n_u * keymap_spacing + overhang_t
            if top_pad > 0:
                layout.shift_layer_row_and_below(layer.source_layer, top_pad)
        else:
            _apply_gap_shift(
                layout,
                prev_qmk,
                n_d_upper=prev_n_d,
                n_u_lower=n_u,
                overhang_b_upper=prev_overhang_b,
                overhang_t_lower=overhang_t,
                row_gap=row_gap,
                keymap_spacing=keymap_spacing,
            )

        prev_n_d = n_d
        prev_overhang_b = overhang_b
        prev_qmk = layer.source_layer

    # Thumb cluster: same shape as a finger layer for routing purposes.
    thumb_n_u, thumb_n_d, thumb_overhang_t, thumb_overhang_b = _route_thumb_phase1(
        thumb,
        layout,
        indicator_rects,
        initial_top=initial_thumb_top,
        initial_bottom=initial_thumb_bottom,
        keymap_spacing=keymap_spacing,
    )

    # Bottommost-layer ↔ thumb gap: same lane-bank rule as inter-layer gaps.
    if prev_qmk is not None:
        _apply_gap_shift(
            layout,
            prev_qmk,
            n_d_upper=prev_n_d,
            n_u_lower=thumb_n_u,
            overhang_b_upper=prev_overhang_b,
            overhang_t_lower=thumb_overhang_t,
            row_gap=row_gap,
            keymap_spacing=keymap_spacing,
        )
    elif thumb_n_u > 0 or thumb_overhang_t > 0:
        layout.shift_thumb_down(thumb_n_u * keymap_spacing + thumb_overhang_t)

    if thumb_n_d > 0:
        return (thumb_n_d + 0.5) * keymap_spacing + thumb_overhang_b
    return thumb_overhang_b


def _route_finger_layer_phase1(
    layer: OverviewLayerSource,
    layout: RoutingLayout,
    indicator_rects: Mapping[int, tuple[float, float, float, float]],
    initial_layer_bounds: Mapping[int, tuple[float, float]],
    keymap_spacing: float,
) -> tuple[int, int, float, float]:
    """Build paths for one finger layer and run phase1 redirects.

    Returns ``(n_up, n_down, overhang_top, overhang_bottom)`` — the four
    quantities ``_pass1_discover_and_shift`` needs to size the gaps above
    and below this layer. Empty layers (no triggers) return all zeros.
    """
    paths = build_finger_path_list_for_layer(
        layer.left, layer.right, layer.source_layer, layout, keymap_spacing
    )
    if not paths:
        return 0, 0, 0.0, 0.0
    _attach_rects_and_set_initial_moveto(paths, indicator_rects)
    cluster_top, cluster_bottom = initial_layer_bounds[layer.source_layer]
    min_y = min(s.current_point[1] for s in paths)
    max_y = max(s.current_point[1] for s in paths)
    phase1_redirect_right_to_down(paths, keymap_spacing)
    phase1_redirect_left_to_down(paths, keymap_spacing)
    n_u = sum(1 for s in paths if s.direction == Direction.UP)
    n_d = sum(1 for s in paths if s.direction == Direction.DOWN)
    overhang_t = max(0.0, cluster_top - min_y)
    overhang_b = max(0.0, max_y - cluster_bottom)
    return n_u, n_d, overhang_t, overhang_b


def _route_thumb_phase1(
    thumb: ThumbSource,
    layout: RoutingLayout,
    indicator_rects: Mapping[int, tuple[float, float, float, float]],
    initial_top: float,
    initial_bottom: float,
    keymap_spacing: float,
) -> tuple[int, int, float, float]:
    """Build paths for the thumb cluster and run phase1 redirects."""
    thumb_paths = build_thumb_path_list(
        thumb.left, thumb.right, layout, thumb.source_layer, keymap_spacing
    )
    if not thumb_paths:
        return 0, 0, 0.0, 0.0
    _attach_rects_and_set_initial_moveto(thumb_paths, indicator_rects)
    min_y = min(s.current_point[1] for s in thumb_paths)
    max_y = max(s.current_point[1] for s in thumb_paths)
    phase1_redirect_left_to_down(thumb_paths, keymap_spacing)
    n_u = sum(1 for s in thumb_paths if s.direction == Direction.UP)
    n_d = sum(1 for s in thumb_paths if s.direction == Direction.DOWN)
    overhang_t = max(0.0, initial_top - min_y)
    overhang_b = max(0.0, max_y - initial_bottom)
    return n_u, n_d, overhang_t, overhang_b


def _apply_gap_shift(
    layout: RoutingLayout,
    upper_qmk: int,
    *,
    n_d_upper: int,
    n_u_lower: int,
    overhang_b_upper: float,
    overhang_t_lower: float,
    row_gap: float,
    keymap_spacing: float,
) -> None:
    """Apply the gap-merging shift between an upper layer and the next-down
    cluster (either another layer or the thumb).

    When connectors cross the gap, the lane bank — ``(N_d + N_u + 1)*sp``
    plus combined indicator overhang — replaces the layout's default
    ``row_gap`` entirely. ``shift_below_layer_row(upper_qmk, delta)``
    pushes everything below the upper cluster down by ``gap_target -
    row_gap``, which is always positive because ``2 * keymap_spacing >
    row_gap`` by construction.
    """
    n_lanes = n_d_upper + n_u_lower
    if n_lanes == 0:
        return
    overhang = overhang_b_upper + overhang_t_lower
    gap_target = (n_lanes + 1) * keymap_spacing + overhang
    shift = gap_target - row_gap
    if shift > 0:
        layout.shift_below_layer_row(upper_qmk, shift)


def _pass2_build_paths(
    layers: Sequence[OverviewLayerSource],
    thumb: ThumbSource,
    layout: RoutingLayout,
    indicator_rects: Mapping[int, tuple[float, float, float, float]],
    keymap_spacing: float,
) -> list[ConnectorStep]:
    """Pass 2: rebuild paths against the post-shift layout for final geometry."""
    all_paths: list[ConnectorStep] = []
    for layer in layers:
        paths = build_finger_path_list_for_layer(
            layer.left, layer.right, layer.source_layer, layout, keymap_spacing
        )
        if not paths:
            continue
        _attach_rects_and_set_initial_moveto(paths, indicator_rects)
        cluster_top, cluster_bottom = _layer_cluster_y_bounds(layout, layer.source_layer)
        min_y = min(s.current_point[1] for s in paths)
        max_y = max(s.current_point[1] for s in paths)
        phase1_redirect_right_to_down(paths, keymap_spacing)
        phase1_redirect_left_to_down(paths, keymap_spacing)
        phase1_up_to_right(paths, cluster_top, min_y, keymap_spacing)
        phase1_down_to_right(paths, cluster_bottom, max_y, keymap_spacing)
        all_paths.extend(paths)

    thumb_paths = build_thumb_path_list(
        thumb.left, thumb.right, layout, thumb.source_layer, keymap_spacing
    )
    if thumb_paths:
        _attach_rects_and_set_initial_moveto(thumb_paths, indicator_rects)
        cluster_top, cluster_bottom = layout.thumb_cluster_y_bounds()
        min_y = min(s.current_point[1] for s in thumb_paths)
        max_y = max(s.current_point[1] for s in thumb_paths)
        phase1_redirect_left_to_down(thumb_paths, keymap_spacing)
        phase1_up_to_right(thumb_paths, cluster_top, min_y, keymap_spacing)
        phase1_down_to_right(thumb_paths, cluster_bottom, max_y, keymap_spacing)
        all_paths.extend(thumb_paths)

    return all_paths


def _attach_rects_and_set_initial_moveto(
    paths: list[ConnectorStep],
    indicator_rects: Mapping[int, tuple[float, float, float, float]],
) -> None:
    """Populate each step's indicator_rect from the map and set its initial moveTo.

    Raises ``ValueError`` with a clear message if a step's key is missing
    from the map (programmer error — the caller must populate every key
    whose layer_switch enters the priority list).
    """
    for step in paths:
        if step.key is None:
            continue
        try:
            step.indicator_rect = indicator_rects[id(step.key)]
        except KeyError as e:
            raise ValueError(
                f"indicator_rects missing entry for key "
                f"{step.key_origin_attr!r} in cluster {step.source_cluster_attr!r} "
                f"(target_layer={step.target_layer}); caller must populate every "
                f"key whose layer_switch enters the priority list"
            ) from e
        set_initial_moveto(step)


__all__ = ["KeymapOverview"]
