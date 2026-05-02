# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Composable building blocks for Svalboard key clusters.

Hosts cluster-level composables that lay out the per-key composables
from :mod:`svalboard_keys` in their cluster shape — finger cluster
(centre + 4 directional + optional double-south) for now; thumb
cluster follows.

The cluster does four jobs the per-key composables don't:

* **Layout.** Each key's position inside the cluster bbox falls out
  of the cluster proportions — outer (NSEW) keys at outer edges,
  centre key in the middle, double-south below south. The cluster
  composable owns this geometry.
* **Colour resolution.** Per-key fill / accent / label colours
  derive from the layer's palette plus the key's own state
  (transparent → ghost label colour, layer-switch keys → switched-
  to-layer's colour when ``use_layer_colors_on_keys`` is on). The
  per-key composables stay pure; the cluster does the resolution.
* **Hold-symbol nudging.** East / west keys' labels embed a
  hold/tap symbol whose side flips based on
  :attr:`Style.hold_symbol_position` and the keyboard half. The
  cluster adjusts the label string before it reaches the per-key
  composable.
* **Layer indicators.** Slots whose key carries a ``layer_switch``
  get a :func:`LayerIndicator` painted at the key's origin, using
  the key's :class:`SvalboardKeyMetrics` for the anchor and
  direction. The cluster owns the badge sizing + colour resolution
  so the per-key composables stay free of palette knowledge.
"""

from __future__ import annotations

import colorsys
from dataclasses import dataclass

from skim.data import LayerColor, SplitSidePosition
from skim.data.keyboard import FingerCluster as FingerClusterData, ThumbCluster as ThumbClusterData
from skim.domain import KeyboardSide, KeyDirection, SvalboardTargetKey

from .composable import Composable
from .layer_indicator import LayerIndicator, LayerIndicatorMetrics
from .primitives import MetricsComponent, Point, Size
from .render_context import RenderPalette
from .styling import lighten, str_to_rgb
from .svalboard_keys import (
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

# Magnitude of the HSL lightness shift applied to a transparent key's
# fill colour to produce its faded "ghost" label colour. Mirrors the
# legacy :data:`context.GHOST_LABEL_LIGHTNESS_DELTA`; pulled in here
# so cluster-level colour resolution doesn't reach into the legacy
# render-context module.
_GHOST_LABEL_LIGHTNESS_DELTA = 0.12

# Per-key proportional widths inside the cluster bbox. Centre key is
# slightly wider than the outer keys; the inset is the gap between
# the centre key and the four outer keys. Sum of (centre + 2×outer
# + 2×inset) gives the cluster bbox width — by construction, both
# axes match because the outer keys are square and the layout is
# cross-shaped (north + centre + south stacks vertically).
_CENTER_KEY_WIDTH_PROPORTION = 0.309
_OUTER_KEY_WIDTH_PROPORTION = 0.328
_INSET_WIDTH_PROPORTION = 0.018

# Layer-indicator chrome — sized as proportions of an outer key's
# width so the badge stays visually balanced with the cluster
# regardless of canvas size. Mirrors the legacy
# :class:`FingerClusterComponent.build` constants.
_INDICATOR_DIAMETER_PROPORTION = 0.55
_INDICATOR_GAP_PROPORTION = 0.18
# The centre key's indicator runs diagonally past the surrounding
# E / W / S keys; the larger gap multiplier keeps the badge clear of
# their edges. Matches legacy ``key_gap = gap * 3`` for the centre
# slot in :func:`indicators._finger_cluster_offset`.
_CENTER_KEY_GAP_MULTIPLIER = 3.0

# Fallback indicator colours used when ``qmk_index_to_position`` maps
# the target layer outside the palette's range. Matches legacy
# :data:`indicators._FALLBACK_FILL` / ``_FALLBACK_STROKE`` so the
# rendered indicator stays neutral grey rather than crashing on a
# stray ``layer_switch`` index.
_INDICATOR_FALLBACK_FILL = "#808080"
_INDICATOR_FALLBACK_STROKE = "#606060"


# ---------------------------------------------------------------------------
# Cluster metrics
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class FingerClusterMetrics:
    """Metrics surfaced by a built finger cluster.

    Per-key :class:`SvalboardKeyMetrics` are exposed by slot so the
    parent (a future per-layer composable) can read indicator
    anchors / directions for any key without re-instantiating the
    per-key composables. ``indicators`` carries per-slot
    :class:`LayerIndicatorMetrics` for slots whose key has a
    ``layer_switch`` set — the parent's connector router consumes
    these to start its routing paths from the indicator's outward
    edge instead of recomputing the geometry.
    """

    center_key: SvalboardKeyMetrics
    north_key: SvalboardKeyMetrics
    east_key: SvalboardKeyMetrics
    south_key: SvalboardKeyMetrics
    west_key: SvalboardKeyMetrics
    double_south_key: SvalboardKeyMetrics | None
    indicators: FingerClusterData[LayerIndicatorMetrics | None]


# ---------------------------------------------------------------------------
# Per-key colour resolution
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class _FingerKeyColors:
    """Resolved fill / accent / label colours for one finger-cluster slot.

    The cluster builds one of these per slot, then passes the
    resolved values to the per-key composable. Keeps the per-key
    composables pure and the cluster as the single home for
    colour-resolution logic.
    """

    fill: str
    accent: str
    label: str


def _resolve_fill(
    *,
    key: SvalboardTargetKey,
    default: str,
    use_accent: bool,
    palette: RenderPalette,
    use_layer_colors_on_keys: bool,
) -> str:
    """Pick the fill colour for a key.

    Layer-switch keys with ``use_layer_colors_on_keys`` enabled
    paint in the destination layer's colour so the visual cue
    "this jumps to layer N" lands without a separate badge.
    Otherwise the slot's default colour applies.
    """
    if not use_layer_colors_on_keys:
        return default
    if key.layer_switch is None:
        return default
    lc = palette.layers.get(key.layer_switch)
    if lc is None:
        return default
    return lc[lc.color_index - (1 if use_accent else 0)]


def _resolve_label_color(
    *,
    key: SvalboardTargetKey,
    fill_color: str,
    palette: RenderPalette,
    layer_base_color: str,
) -> str:
    """Pick the label text colour.

    Transparent keys with a non-empty (substituted) label render in
    a faded "ghost" colour derived from the key's fill, so the
    fall-through label reads as a hint rather than as the layer's
    primary content. Solid keys use the palette's standard label
    colour.
    """
    if key.is_transparent and key.label:
        fill_lightness = colorsys.rgb_to_hls(*str_to_rgb(fill_color))[1]
        base_lightness = colorsys.rgb_to_hls(*str_to_rgb(layer_base_color))[1]
        delta = (
            _GHOST_LABEL_LIGHTNESS_DELTA
            if fill_lightness <= base_lightness
            else -_GHOST_LABEL_LIGHTNESS_DELTA
        )
        return lighten(fill_color, delta)
    return palette.key_label_color


def _resolve_key_colors(
    *,
    key: SvalboardTargetKey,
    default_primary: str,
    default_accent: str,
    palette: RenderPalette,
    layer_base_color: str,
    use_layer_colors_on_keys: bool,
) -> _FingerKeyColors:
    """Resolve fill + accent + label colours for one slot."""
    fill = _resolve_fill(
        key=key,
        default=default_primary,
        use_accent=False,
        palette=palette,
        use_layer_colors_on_keys=use_layer_colors_on_keys,
    )
    accent = _resolve_fill(
        key=key,
        default=default_accent,
        use_accent=True,
        palette=palette,
        use_layer_colors_on_keys=use_layer_colors_on_keys,
    )
    label = _resolve_label_color(
        key=key,
        fill_color=fill,
        palette=palette,
        layer_base_color=layer_base_color,
    )
    return _FingerKeyColors(fill=fill, accent=accent, label=label)


@dataclass(frozen=True, slots=True, kw_only=True)
class _FingerSlotColors:
    """Per-slot ``(primary, accent)`` defaults pulled from the layer
    colour gradient.

    The legacy :class:`FingerClusterKeyColors` carries the same
    pair; pulling it into a private dataclass here keeps the cluster
    composable from threading two strings per slot through the
    resolve step.
    """

    primary: str
    accent: str


def _slot_defaults(
    *, layer_colors: LayerColor, side: KeyboardSide, has_double_south: bool
) -> FingerClusterData[_FingerSlotColors]:
    """Pick the gradient indices for each cluster slot.

    Mirrors the legacy ``FingerClusterComponent._get_key_colors``
    mapping. ``has_double_south`` shifts the centre / south slot
    pairs by one gradient step because the extra key takes the
    bottom-most colour. ``side`` swaps east / west so the warmer
    gradient steps land on the inward edge of each cluster.
    """
    c = layer_colors
    north = _FingerSlotColors(primary=c[4], accent=c[3])
    double_south = _FingerSlotColors(primary=c[2], accent=c[1])
    if has_double_south:
        center = _FingerSlotColors(primary=c[0], accent=c[0])
        south = _FingerSlotColors(primary=c[1], accent=c[0])
    else:
        center = _FingerSlotColors(primary=c[1], accent=c[1])
        south = _FingerSlotColors(primary=c[2], accent=c[1])

    if side is KeyboardSide.LEFT:
        east = _FingerSlotColors(primary=c[3], accent=c[2])
        west = _FingerSlotColors(primary=c[5], accent=c[4])
    else:
        east = _FingerSlotColors(primary=c[5], accent=c[4])
        west = _FingerSlotColors(primary=c[3], accent=c[2])

    return FingerClusterData(
        center_key=center,
        north_key=north,
        east_key=east,
        south_key=south,
        west_key=west,
        double_south_key=double_south,
    )


# ---------------------------------------------------------------------------
# Indicator colour resolution
# ---------------------------------------------------------------------------


def _resolve_indicator_colors(
    *,
    target_layer: int,
    palette: RenderPalette,
) -> tuple[str, str]:
    """Pick an indicator's ``(fill, stroke)`` for ``target_layer``.

    ``target_layer`` is the QMK firmware index stored on a key's
    ``layer_switch`` field. The indicator paints in the destination
    layer's palette so the badge visually identifies the layer it
    jumps to: fill is the layer's :attr:`LayerColor.base_color`;
    stroke is the gradient's fifth stop (``lc[4]``) — both mirror
    legacy :class:`indicators.LayerIndicator`. Unregistered firmware
    indices fall back to neutral grey rather than raising, since a
    stray ``layer_switch`` index shouldn't crash rendering.
    """
    lc = palette.layers.get(target_layer)
    if lc is None:
        return _INDICATOR_FALLBACK_FILL, _INDICATOR_FALLBACK_STROKE
    return lc.base_color, lc[4]


# ---------------------------------------------------------------------------
# Hold-symbol nudging
# ---------------------------------------------------------------------------


def _adjust_hold_symbol_label(
    *, position: SplitSidePosition, side: KeyboardSide, label: str
) -> str:
    """Rewrite a label so any hold/tap modifier symbol sits on the
    requested side.

    Keymap labels for east / west keys with hold-modifier behaviour
    embed a separator-prefixed or -suffixed glyph; the user's
    ``hold_symbol_position`` config setting decides whether the
    glyph reads on the inward or outward side. This nudge happens
    at the cluster level because only the cluster knows the keyboard
    half, which the side mapping depends on.
    """
    if position is SplitSidePosition.QMK_DEFINED or not label:
        return label
    sep = "|"
    if sep not in label:
        return label
    prefix, suffix = label.split(sep, 1)
    is_outward = (position is SplitSidePosition.OUTWARD and side is KeyboardSide.LEFT) or (
        position is SplitSidePosition.INWARD and side is KeyboardSide.RIGHT
    )
    if is_outward:
        return f"{suffix}{sep}{prefix}"
    return f"{prefix}{sep}{suffix}"


def _adjust_cluster_hold_symbols(
    *,
    cluster: FingerClusterData[SvalboardTargetKey],
    side: KeyboardSide,
    position: SplitSidePosition,
) -> FingerClusterData[SvalboardTargetKey]:
    """Apply :func:`_adjust_hold_symbol_label` to the east / west
    keys of a finger cluster, leaving the rest untouched."""
    if position is SplitSidePosition.QMK_DEFINED:
        return cluster

    east_label = _adjust_hold_symbol_label(
        position=position, side=KeyboardSide.LEFT, label=cluster.east_key.label
    )
    west_label = _adjust_hold_symbol_label(
        position=position, side=KeyboardSide.RIGHT, label=cluster.west_key.label
    )
    return FingerClusterData(
        center_key=cluster.center_key,
        north_key=cluster.north_key,
        east_key=SvalboardTargetKey(
            label=east_label,
            layer_switch=cluster.east_key.layer_switch,
            is_transparent=cluster.east_key.is_transparent,
            macro_id=cluster.east_key.macro_id,
            tap_dance_id=cluster.east_key.tap_dance_id,
        ),
        south_key=cluster.south_key,
        west_key=SvalboardTargetKey(
            label=west_label,
            layer_switch=cluster.west_key.layer_switch,
            is_transparent=cluster.west_key.is_transparent,
            macro_id=cluster.west_key.macro_id,
            tap_dance_id=cluster.west_key.tap_dance_id,
        ),
        double_south_key=cluster.double_south_key,
    )


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class _FingerClusterSlots:
    """Per-key ``(origin, width)`` boundaries inside a finger cluster.

    Computed once per cluster build from the cluster's outer width;
    each slot reports the absolute origin (relative to the cluster
    origin) and the per-key cell width. Heights match width for the
    rounded-square outer keys; the centre is square at its own
    width.
    """

    center_origin: Point
    center_width: float
    north_origin: Point
    east_origin: Point
    south_origin: Point
    west_origin: Point
    double_south_origin: Point
    outer_width: float
    cluster_height: float


def _compute_slots(*, cluster_width: float, has_double_south: bool) -> _FingerClusterSlots:
    """Resolve per-key boundaries from the cluster's outer width.

    Layout matches the legacy ``FingerClusterLayout``: outer keys
    centred on the cluster's vertical / horizontal midline; centre
    key inset from the inner edges of the outer keys by
    ``inset_width``; double-south sits below south by
    ``inset_width`` when present.
    """
    center_width = cluster_width * _CENTER_KEY_WIDTH_PROPORTION
    outer_width = cluster_width * _OUTER_KEY_WIDTH_PROPORTION
    inset = cluster_width * _INSET_WIDTH_PROPORTION

    cx = cluster_width / 2.0  # cluster's horizontal centre

    # North sits at the top, horizontally centred.
    north_origin = Point(cx - outer_width / 2.0, 0.0)
    # Centre sits below north by the outer key's height + inset gap.
    center_origin = Point(
        cx - center_width / 2.0,
        north_origin.y + outer_width + inset,
    )
    # South sits below the centre by its height + inset gap.
    south_origin = Point(
        cx - outer_width / 2.0,
        center_origin.y + center_width + inset,
    )
    # East sits right of the centre, vertically aligned with the
    # centre's row top.
    east_origin = Point(
        center_origin.x + center_width + inset,
        north_origin.y + outer_width,
    )
    # West sits left of the centre, mirrored.
    west_origin = Point(
        center_origin.x - (outer_width + inset),
        north_origin.y + outer_width,
    )
    # Double-south sits below south, when present.
    double_south_origin = Point(
        cx - outer_width / 2.0,
        south_origin.y + outer_width + inset,
    )

    last_y = (
        double_south_origin.y + outer_width if has_double_south else south_origin.y + outer_width
    )
    return _FingerClusterSlots(
        center_origin=center_origin,
        center_width=center_width,
        north_origin=north_origin,
        east_origin=east_origin,
        south_origin=south_origin,
        west_origin=west_origin,
        double_south_origin=double_south_origin,
        outer_width=outer_width,
        cluster_height=last_y,
    )


# ---------------------------------------------------------------------------
# FingerCluster composable
# ---------------------------------------------------------------------------


@Composable(use_context=True)
def FingerCluster(
    ctx,
    *,
    cluster: FingerClusterData[SvalboardTargetKey],
    side: KeyboardSide,
    width: float,
    layer_qmk_index: int,
    has_double_south: bool = False,
    use_layer_colors_on_keys: bool = True,
    show_layer_indicators: bool = True,
    hold_symbol_position: SplitSidePosition = SplitSidePosition.OUTWARD,
):
    """A finger cluster — five (or six) keys laid out in cross shape.

    Owns the cluster-level concerns: per-key layout from the
    cluster proportions, colour resolution from the layer palette,
    hold-symbol nudging on east / west keys, and (when
    ``show_layer_indicators`` is on) layer-indicator badges painted
    next to layer-switch keys. Each per-key composable receives
    resolved inputs and stays pure.

    ``layer_qmk_index`` identifies the layer this cluster paints —
    the QMK firmware index, the same int that ends up on
    layer-switch keys' ``layer_switch`` field. The cluster reads
    :class:`RenderPalette` off ``ctx.theme.palette`` and looks up
    the layer's colours directly via ``palette.layers[layer_qmk_index]``;
    layer-switch destinations look up the same way. Symbolic layer
    ids (``"_NAV"``) are a config-time concept — by the time the
    keymap data reaches us they're already firmware ints.

    Reports :class:`MetricsComponent[FingerClusterMetrics]` exposing
    each key's :class:`SvalboardKeyMetrics` plus per-slot
    :class:`LayerIndicatorMetrics` (or ``None`` for slots without a
    layer-switch / when indicators are off). ``Size`` covers only
    the keys' bbox; indicators are annotation that sits on top and
    may protrude past the bbox — the parent layer composable shifts
    its layout to make room based on the indicator metrics.

    ``has_double_south`` controls whether a sixth key (the double-
    south trapezoid below the south key) renders. ``Size.height``
    grows accordingly.
    """
    palette = ctx.theme.palette
    layer_colors = palette.layers.get(layer_qmk_index)
    if layer_colors is None:
        # Unknown firmware index — fall back to a synthetic LayerColor
        # that uses the palette's neutral chrome colour everywhere.
        # The cluster still renders; nothing crashes on a stray label.
        layer_colors = LayerColor(base_color=palette.neutral_color)

    # Apply hold-symbol nudging before colour resolution — the
    # ``label`` field is what the per-key composable paints.
    nudged_cluster = _adjust_cluster_hold_symbols(
        cluster=cluster, side=side, position=hold_symbol_position
    )

    # Per-slot default colours, then resolve fill / accent / label
    # for each slot.
    slot_defaults = _slot_defaults(
        layer_colors=layer_colors, side=side, has_double_south=has_double_south
    )

    def _colors(slot_key: SvalboardTargetKey, defaults: _FingerSlotColors) -> _FingerKeyColors:
        return _resolve_key_colors(
            key=slot_key,
            default_primary=defaults.primary,
            default_accent=defaults.accent,
            palette=palette,
            layer_base_color=layer_colors.base_color,
            use_layer_colors_on_keys=use_layer_colors_on_keys,
        )

    center_colors = _colors(nudged_cluster.center_key, slot_defaults.center_key)
    north_colors = _colors(nudged_cluster.north_key, slot_defaults.north_key)
    east_colors = _colors(nudged_cluster.east_key, slot_defaults.east_key)
    south_colors = _colors(nudged_cluster.south_key, slot_defaults.south_key)
    west_colors = _colors(nudged_cluster.west_key, slot_defaults.west_key)
    double_south_colors = _colors(nudged_cluster.double_south_key, slot_defaults.double_south_key)

    # Layout — per-key origins + widths inside the cluster bbox.
    slots = _compute_slots(cluster_width=width, has_double_south=has_double_south)

    # Per-key composables.
    center = CenterKey(
        side=side,
        width=slots.center_width,
        label_text=nudged_cluster.center_key.label,
        fill_color=center_colors.fill,
        label_color=center_colors.label,
    )
    north = DirectionalKey(
        side=side,
        direction=KeyDirection.NORTH,
        width=slots.outer_width,
        label_text=nudged_cluster.north_key.label,
        fill_color=north_colors.fill,
        accent_color=north_colors.accent,
        label_color=north_colors.label,
    )
    east = DirectionalKey(
        side=side,
        direction=KeyDirection.EAST,
        width=slots.outer_width,
        label_text=nudged_cluster.east_key.label,
        fill_color=east_colors.fill,
        accent_color=east_colors.accent,
        label_color=east_colors.label,
    )
    south = DirectionalKey(
        side=side,
        direction=KeyDirection.SOUTH,
        width=slots.outer_width,
        label_text=nudged_cluster.south_key.label,
        fill_color=south_colors.fill,
        accent_color=south_colors.accent,
        label_color=south_colors.label,
    )
    west = DirectionalKey(
        side=side,
        direction=KeyDirection.WEST,
        width=slots.outer_width,
        label_text=nudged_cluster.west_key.label,
        fill_color=west_colors.fill,
        accent_color=west_colors.accent,
        label_color=west_colors.label,
    )
    double_south = (
        DoubleSouthKey(
            side=side,
            width=slots.outer_width,
            label_text=nudged_cluster.double_south_key.label,
            fill_color=double_south_colors.fill,
            accent_color=double_south_colors.accent,
            label_color=double_south_colors.label,
        )
        if has_double_south
        else None
    )

    # Layer indicators — one per slot whose key has a layer_switch
    # set, sized as proportions of the outer key width so badges stay
    # visually balanced with the cluster. ``None`` for slots without
    # a layer-switch or when indicators are disabled.
    indicator_diameter = slots.outer_width * _INDICATOR_DIAMETER_PROPORTION
    indicator_gap = slots.outer_width * _INDICATOR_GAP_PROPORTION

    def _maybe_indicator(
        slot_key: SvalboardTargetKey,
        key_metrics: SvalboardKeyMetrics,
        *,
        gap_multiplier: float = 1.0,
    ):
        if not show_layer_indicators or slot_key.layer_switch is None:
            return None
        fill, stroke = _resolve_indicator_colors(
            target_layer=slot_key.layer_switch,
            palette=palette,
        )
        return LayerIndicator(
            target_layer=slot_key.layer_switch,
            anchor=key_metrics.indicator_anchor,
            direction=key_metrics.indicator_direction,
            circle_diameter=indicator_diameter,
            gap=indicator_gap * gap_multiplier,
            fill_color=fill,
            stroke_color=stroke,
        )

    center_indicator = _maybe_indicator(
        nudged_cluster.center_key,
        center.metrics,
        gap_multiplier=_CENTER_KEY_GAP_MULTIPLIER,
    )
    north_indicator = _maybe_indicator(nudged_cluster.north_key, north.metrics)
    east_indicator = _maybe_indicator(nudged_cluster.east_key, east.metrics)
    south_indicator = _maybe_indicator(nudged_cluster.south_key, south.metrics)
    west_indicator = _maybe_indicator(nudged_cluster.west_key, west.metrics)
    double_south_indicator = (
        _maybe_indicator(nudged_cluster.double_south_key, double_south.metrics)
        if double_south is not None
        else None
    )

    size = Size(width, slots.cluster_height)

    def draw_at(d, origin):
        center_origin = Point(origin.x + slots.center_origin.x, origin.y + slots.center_origin.y)
        north_origin = Point(origin.x + slots.north_origin.x, origin.y + slots.north_origin.y)
        east_origin = Point(origin.x + slots.east_origin.x, origin.y + slots.east_origin.y)
        south_origin = Point(origin.x + slots.south_origin.x, origin.y + slots.south_origin.y)
        west_origin = Point(origin.x + slots.west_origin.x, origin.y + slots.west_origin.y)
        double_south_origin = Point(
            origin.x + slots.double_south_origin.x,
            origin.y + slots.double_south_origin.y,
        )

        center.draw_at(d, center_origin)
        north.draw_at(d, north_origin)
        east.draw_at(d, east_origin)
        south.draw_at(d, south_origin)
        west.draw_at(d, west_origin)
        if double_south is not None:
            double_south.draw_at(d, double_south_origin)

        # Indicators paint after the keys so the badge sits over any
        # adjacent key edge it overlaps. Each indicator paints at the
        # SAME origin as its key — its anchor is in key-local
        # coordinates so the cluster origin offset is enough.
        if center_indicator is not None:
            center_indicator.draw_at(d, center_origin)
        if north_indicator is not None:
            north_indicator.draw_at(d, north_origin)
        if east_indicator is not None:
            east_indicator.draw_at(d, east_origin)
        if south_indicator is not None:
            south_indicator.draw_at(d, south_origin)
        if west_indicator is not None:
            west_indicator.draw_at(d, west_origin)
        if double_south_indicator is not None:
            double_south_indicator.draw_at(d, double_south_origin)

    indicators_metrics: FingerClusterData[LayerIndicatorMetrics | None] = FingerClusterData(
        center_key=center_indicator.metrics if center_indicator is not None else None,
        north_key=north_indicator.metrics if north_indicator is not None else None,
        east_key=east_indicator.metrics if east_indicator is not None else None,
        south_key=south_indicator.metrics if south_indicator is not None else None,
        west_key=west_indicator.metrics if west_indicator is not None else None,
        double_south_key=(
            double_south_indicator.metrics if double_south_indicator is not None else None
        ),
    )

    return MetricsComponent(
        size=size,
        draw_fn=draw_at,
        metrics=FingerClusterMetrics(
            center_key=center.metrics,
            north_key=north.metrics,
            east_key=east.metrics,
            south_key=south.metrics,
            west_key=west.metrics,
            double_south_key=double_south.metrics if double_south is not None else None,
            indicators=indicators_metrics,
        ),
    )


# ---------------------------------------------------------------------------
# Thumb cluster — proportions + layout + metrics + composable
# ---------------------------------------------------------------------------


# Per-key proportional widths inside the thumb-cluster bbox. Pulled
# from the legacy ``ThumbClusterComponent._CLUSTER_WIDTH_PROPORTIONS``
# verbatim so the rendered cluster stays pixel-equivalent.
_DOWN_KEY_PROPORTION = 0.25
_PAD_KEY_PROPORTION = 0.38
_UP_KEY_PROPORTION = 0.372
_NAIL_KEY_PROPORTION = 0.4
_KNUCKLE_KEY_PROPORTION = 0.385
_DOUBLE_DOWN_KEY_PROPORTION = 0.13
_THUMB_INSET_PROPORTION = 0.038

# Cluster bbox aspect — the legacy ``ThumbClusterComponent._ASPECT_RATIO``
# is "1.5:1" (width / height). Used to compute the cluster height
# from its width.
_THUMB_CLUSTER_HEIGHT_RATIO = 1.0 / 1.5

# Layer-indicator chrome on the thumb cluster — sized as proportions
# of the down key's width (matches legacy
# ``LayerIndicatorOverlay.for_thumb_cluster`` invocation in
# :class:`ThumbClusterComponent`).
_THUMB_INDICATOR_DIAMETER_PROPORTION = 0.4
_THUMB_INDICATOR_GAP_PROPORTION = 0.18


# ---------------------------------------------------------------------------
# Thumb cluster metrics
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class ThumbClusterMetrics:
    """Metrics surfaced by a built thumb cluster.

    Mirrors :class:`FingerClusterMetrics`: per-slot
    :class:`SvalboardKeyMetrics` so the parent layer composable can
    read each key's indicator anchor / direction without re-running
    the per-key composables, plus :class:`LayerIndicatorMetrics` for
    slots whose key has a ``layer_switch`` set (or ``None`` for
    slots without one).

    ``top_overhang`` reports how far any present indicator extends
    ABOVE the cluster's top edge (y=0 in cluster-local coords),
    measured as a positive magnitude. Zero when no indicator is
    above-extending. The double-down key's NORTH indicator dominates
    in practice — it sits on top of the down key whose top edge IS
    the cluster top, so its full ``gap + diameter`` overhang shows
    up here. The parent :func:`KeyboardHalf` reads this to inflate
    the gap between the finger half and the thumb cluster.
    """

    down_key: SvalboardKeyMetrics
    pad_key: SvalboardKeyMetrics
    up_key: SvalboardKeyMetrics
    nail_key: SvalboardKeyMetrics
    knuckle_key: SvalboardKeyMetrics
    double_down_key: SvalboardKeyMetrics
    indicators: ThumbClusterData[LayerIndicatorMetrics | None]
    top_overhang: float


# ---------------------------------------------------------------------------
# Per-slot colour resolution for thumb keys
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class _ThumbKeyColors:
    """Resolved fill / label / stroke colours for one thumb-cluster slot.

    Some thumb keys (down / pad / nail / knuckle) don't draw a
    stroke — for those slots the resolved ``stroke`` is unused and
    the cluster passes only ``fill`` and ``label`` to the per-key
    composable. ``stroke`` carries the palette's outline colour so
    the up / double-down keys (which DO stroke) can use it.
    """

    fill: str
    label: str
    stroke: str


def _resolve_thumb_key_colors(
    *,
    key: SvalboardTargetKey,
    default_fill: str,
    palette: RenderPalette,
    layer_base_color: str,
    use_layer_colors_on_keys: bool,
) -> _ThumbKeyColors:
    """Resolve fill + label + stroke for one thumb slot.

    Reuses the finger-cluster's :func:`_resolve_fill` (without an
    accent variant, since thumb keys don't carry the accent bar
    that finger directional keys do) and
    :func:`_resolve_label_color` (ghost-label logic for transparent
    keys). Stroke always lands on the palette's
    ``key_label_color`` — the legacy thumb keys use that as the
    outline colour for keys that stroke.
    """
    fill = _resolve_fill(
        key=key,
        default=default_fill,
        use_accent=False,
        palette=palette,
        use_layer_colors_on_keys=use_layer_colors_on_keys,
    )
    label = _resolve_label_color(
        key=key,
        fill_color=fill,
        palette=palette,
        layer_base_color=layer_base_color,
    )
    return _ThumbKeyColors(fill=fill, label=label, stroke=palette.key_label_color)


# ---------------------------------------------------------------------------
# Thumb hold-symbol nudging
# ---------------------------------------------------------------------------


def _adjust_thumb_cluster_hold_symbols(
    *,
    cluster: ThumbClusterData[SvalboardTargetKey],
    side: KeyboardSide,
    position: SplitSidePosition,
) -> ThumbClusterData[SvalboardTargetKey]:
    """Apply :func:`_adjust_hold_symbol_label` to the pad / up / nail /
    knuckle keys of a thumb cluster.

    Down + double-down don't carry hold/tap separators in practice
    (they're typed alone, not as modifier-tap chords) and the legacy
    code preserves them untouched, so the new composable does the
    same. Pad and up nudge by the cluster's own side; nail and
    knuckle nudge by the OPPOSITE side because their visual
    orientation flips relative to pad / up — the slant on a
    right-hand nail key sits on the LEFT, which reads as the
    "outward" side from the keyboard's user-facing perspective even
    though that's the inward side of the cluster bbox.
    """
    if position is SplitSidePosition.QMK_DEFINED:
        return cluster

    same_side = side
    flipped_side = KeyboardSide.RIGHT if side is KeyboardSide.LEFT else KeyboardSide.LEFT

    def _swap(key: SvalboardTargetKey, key_side: KeyboardSide) -> SvalboardTargetKey:
        return SvalboardTargetKey(
            label=_adjust_hold_symbol_label(position=position, side=key_side, label=key.label),
            layer_switch=key.layer_switch,
            is_transparent=key.is_transparent,
            macro_id=key.macro_id,
            tap_dance_id=key.tap_dance_id,
        )

    return ThumbClusterData(
        down_key=cluster.down_key,
        pad_key=_swap(cluster.pad_key, same_side),
        up_key=_swap(cluster.up_key, same_side),
        nail_key=_swap(cluster.nail_key, flipped_side),
        knuckle_key=_swap(cluster.knuckle_key, flipped_side),
        double_down_key=cluster.double_down_key,
    )


# ---------------------------------------------------------------------------
# Thumb cluster layout
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class _ThumbClusterSlots:
    """Per-key ``(origin, width)`` boundaries inside a thumb cluster.

    Mirrors :class:`_FingerClusterSlots`. Each ``*_origin`` is in
    cluster-local coordinates (relative to the cluster origin); the
    cluster composable adds the caller's draw origin during paint.
    """

    down_origin: Point
    down_width: float
    pad_origin: Point
    pad_width: float
    up_origin: Point
    up_width: float
    nail_origin: Point
    nail_width: float
    knuckle_origin: Point
    knuckle_width: float
    double_down_origin: Point
    double_down_width: float
    cluster_height: float


def _compute_thumb_slots(*, cluster_width: float, side: KeyboardSide) -> _ThumbClusterSlots:
    """Resolve per-key thumb-cluster boundaries from the bbox width.

    Layout matches the legacy ``ThumbClusterLayout._compute_layout``
    verbatim. ``side`` controls which way pad / nail / up /
    knuckle's outward edges point; the down + double-down keys are
    horizontally centred on the cluster's vertical midline and
    don't depend on side.
    """
    cluster_height = cluster_width * _THUMB_CLUSTER_HEIGHT_RATIO
    center_x = cluster_width / 2.0
    center_y = cluster_height / 2.0

    down_w = cluster_width * _DOWN_KEY_PROPORTION
    pad_w = cluster_width * _PAD_KEY_PROPORTION
    up_w = cluster_width * _UP_KEY_PROPORTION
    nail_w = cluster_width * _NAIL_KEY_PROPORTION
    knuckle_w = cluster_width * _KNUCKLE_KEY_PROPORTION
    double_down_w = cluster_width * _DOUBLE_DOWN_KEY_PROPORTION
    inset = cluster_width * _THUMB_INSET_PROPORTION

    is_left = side is KeyboardSide.LEFT
    down_origin = Point(center_x - down_w / 2.0, 0.0)
    double_down_origin = Point(center_x - double_down_w / 2.0, inset * 2.0)

    # Pad / nail sit either side of the down key, with the slant /
    # taper running away from the down key.
    top_left_x = center_x - down_w / 2.0 - pad_w + inset / 2.0
    top_right_x = center_x + down_w / 2.0 - inset / 2.0
    pad_origin = Point(top_left_x if is_left else top_right_x, inset)

    nail_top_left_x = center_x - down_w / 2.0 - nail_w + inset / 2.0
    nail_origin = Point(top_right_x if is_left else nail_top_left_x, inset)

    # Up / knuckle sit at mid-cluster, mirroring nail / pad's side
    # placement. Up's own outward-side slant lives in :func:`UpKey`;
    # the cluster just positions it.
    up_left_x = center_x - up_w - inset / 2.0
    up_right_x = center_x + inset / 2.0
    up_origin = Point(up_left_x if is_left else up_right_x, center_y - inset * 1.5)

    knuckle_left_x = nail_origin.x + nail_w - knuckle_w
    knuckle_right_x = nail_origin.x
    knuckle_origin = Point(knuckle_left_x if is_left else knuckle_right_x, up_origin.y)

    return _ThumbClusterSlots(
        down_origin=down_origin,
        down_width=down_w,
        pad_origin=pad_origin,
        pad_width=pad_w,
        up_origin=up_origin,
        up_width=up_w,
        nail_origin=nail_origin,
        nail_width=nail_w,
        knuckle_origin=knuckle_origin,
        knuckle_width=knuckle_w,
        double_down_origin=double_down_origin,
        double_down_width=double_down_w,
        cluster_height=cluster_height,
    )


# ---------------------------------------------------------------------------
# ThumbCluster composable
# ---------------------------------------------------------------------------


@Composable(use_context=True)
def ThumbCluster(
    ctx,
    *,
    cluster: ThumbClusterData[SvalboardTargetKey],
    side: KeyboardSide,
    width: float,
    layer_qmk_index: int,
    use_layer_colors_on_keys: bool = True,
    show_layer_indicators: bool = True,
    hold_symbol_position: SplitSidePosition = SplitSidePosition.OUTWARD,
):
    """A thumb cluster — six keys laid out in the thumb's reach pattern.

    Mirrors :func:`FingerCluster` for the thumb half of the
    keyboard: the six per-key composables (down, pad, up, nail,
    knuckle, double-down) are positioned inside the cluster bbox,
    coloured from the layer + palette, hold-symbol-nudged on the
    appropriate slots, and (optionally) decorated with layer
    indicators on slots whose key has a ``layer_switch`` set.

    ``layer_qmk_index`` is the QMK firmware index of the layer this
    cluster paints. The cluster reads :class:`RenderPalette` off
    ``ctx.theme.palette`` and looks up the layer's colours directly
    via ``palette.layers[layer_qmk_index]``.

    Reports :class:`MetricsComponent[ThumbClusterMetrics]` so the
    parent layer composable can read per-slot indicator anchors /
    routing geometry without re-instantiating the per-key
    composables.

    The cluster ``size`` is ``Size(width, width / 1.5)`` — the
    legacy ``ThumbClusterComponent`` aspect-ratio-derived bbox.
    Individual keys may extend slightly past the bbox (e.g. up /
    knuckle protrude above the midline by their own height/2) — the
    legacy renderer dealt with this by translating the SVG group's
    transform; the composable's caller can do the same with the
    drawn output, or read the per-slot metrics to compute the actual
    extent.
    """
    palette = ctx.theme.palette
    layer_colors = palette.layers.get(layer_qmk_index)
    if layer_colors is None:
        layer_colors = LayerColor(base_color=palette.neutral_color)

    nudged_cluster = _adjust_thumb_cluster_hold_symbols(
        cluster=cluster, side=side, position=hold_symbol_position
    )

    # Per-slot default fills come from the legacy thumb-key constructors:
    # down → layer base; double-down + up → layer dark accent; pad /
    # nail / knuckle → palette neutral.
    layer_base = layer_colors.base_color
    layer_dark_accent = layer_colors.dark_accent_color
    neutral = palette.neutral_color

    def _colors(slot_key: SvalboardTargetKey, default_fill: str) -> _ThumbKeyColors:
        return _resolve_thumb_key_colors(
            key=slot_key,
            default_fill=default_fill,
            palette=palette,
            layer_base_color=layer_base,
            use_layer_colors_on_keys=use_layer_colors_on_keys,
        )

    down_colors = _colors(nudged_cluster.down_key, layer_base)
    pad_colors = _colors(nudged_cluster.pad_key, neutral)
    up_colors = _colors(nudged_cluster.up_key, layer_dark_accent)
    nail_colors = _colors(nudged_cluster.nail_key, neutral)
    knuckle_colors = _colors(nudged_cluster.knuckle_key, neutral)
    double_down_colors = _colors(nudged_cluster.double_down_key, layer_dark_accent)

    slots = _compute_thumb_slots(cluster_width=width, side=side)

    # Per-key composables.
    down = DownKey(
        side=side,
        width=slots.down_width,
        label_text=nudged_cluster.down_key.label,
        fill_color=down_colors.fill,
        label_color=down_colors.label,
    )
    pad = PadKey(
        side=side,
        width=slots.pad_width,
        label_text=nudged_cluster.pad_key.label,
        fill_color=pad_colors.fill,
        label_color=pad_colors.label,
    )
    up = UpKey(
        side=side,
        width=slots.up_width,
        label_text=nudged_cluster.up_key.label,
        fill_color=up_colors.fill,
        label_color=up_colors.label,
        stroke_color=up_colors.stroke,
    )
    nail = NailKey(
        side=side,
        width=slots.nail_width,
        label_text=nudged_cluster.nail_key.label,
        fill_color=nail_colors.fill,
        label_color=nail_colors.label,
    )
    knuckle = KnuckleKey(
        side=side,
        width=slots.knuckle_width,
        label_text=nudged_cluster.knuckle_key.label,
        fill_color=knuckle_colors.fill,
        label_color=knuckle_colors.label,
    )
    double_down = DoubleDownKey(
        side=side,
        width=slots.double_down_width,
        label_text=nudged_cluster.double_down_key.label,
        fill_color=double_down_colors.fill,
        label_color=double_down_colors.label,
        stroke_color=double_down_colors.stroke,
    )

    # Layer indicators — sized as proportions of the down key's
    # width (legacy convention). Each indicator anchors to its own
    # key via :class:`SvalboardKeyMetrics`.
    indicator_diameter = slots.down_width * _THUMB_INDICATOR_DIAMETER_PROPORTION
    indicator_gap = slots.down_width * _THUMB_INDICATOR_GAP_PROPORTION

    # The double-down indicator points NORTH but the cluster's
    # outermost top edge isn't DD's top — it's the down key, which
    # extends ``2 * inset`` ABOVE DD. The indicator should sit
    # ``indicator_gap`` away from THAT outermost edge, not from DD's
    # own top — otherwise it ends up uncomfortably close to (or
    # overlapping) the down key's upper portion. Pad / up / nail /
    # knuckle indicators don't need this adjustment because nothing
    # in the cluster sits above their outward edges.
    dd_extra_gap = slots.double_down_origin.y - slots.down_origin.y

    def _maybe_indicator(
        slot_key: SvalboardTargetKey,
        key_metrics: SvalboardKeyMetrics,
        *,
        gap: float | None = None,
    ):
        if not show_layer_indicators or slot_key.layer_switch is None:
            return None
        fill, stroke = _resolve_indicator_colors(
            target_layer=slot_key.layer_switch,
            palette=palette,
        )
        return LayerIndicator(
            target_layer=slot_key.layer_switch,
            anchor=key_metrics.indicator_anchor,
            direction=key_metrics.indicator_direction,
            circle_diameter=indicator_diameter,
            gap=indicator_gap if gap is None else gap,
            fill_color=fill,
            stroke_color=stroke,
        )

    down_indicator = _maybe_indicator(nudged_cluster.down_key, down.metrics)
    pad_indicator = _maybe_indicator(nudged_cluster.pad_key, pad.metrics)
    up_indicator = _maybe_indicator(nudged_cluster.up_key, up.metrics)
    nail_indicator = _maybe_indicator(nudged_cluster.nail_key, nail.metrics)
    knuckle_indicator = _maybe_indicator(nudged_cluster.knuckle_key, knuckle.metrics)
    double_down_indicator = _maybe_indicator(
        nudged_cluster.double_down_key,
        double_down.metrics,
        gap=indicator_gap + dd_extra_gap,
    )

    size = Size(width, slots.cluster_height)

    def draw_at(d, origin):
        # Compute each key's absolute paint origin once — both the
        # key and (optionally) its indicator paint at the same one.
        down_o = Point(origin.x + slots.down_origin.x, origin.y + slots.down_origin.y)
        pad_o = Point(origin.x + slots.pad_origin.x, origin.y + slots.pad_origin.y)
        up_o = Point(origin.x + slots.up_origin.x, origin.y + slots.up_origin.y)
        nail_o = Point(origin.x + slots.nail_origin.x, origin.y + slots.nail_origin.y)
        knuckle_o = Point(origin.x + slots.knuckle_origin.x, origin.y + slots.knuckle_origin.y)
        double_down_o = Point(
            origin.x + slots.double_down_origin.x,
            origin.y + slots.double_down_origin.y,
        )

        # Paint order matches the legacy ``for key in self._cluster``
        # iteration over :class:`ThumbClusterData` field order:
        # down → pad → up → nail → knuckle → double-down. The
        # double-down sits ON TOP of the down key's upper edge, so
        # painting it last keeps its outline visible.
        down.draw_at(d, down_o)
        pad.draw_at(d, pad_o)
        up.draw_at(d, up_o)
        nail.draw_at(d, nail_o)
        knuckle.draw_at(d, knuckle_o)
        double_down.draw_at(d, double_down_o)

        # Indicators paint above the keys.
        if down_indicator is not None:
            down_indicator.draw_at(d, down_o)
        if pad_indicator is not None:
            pad_indicator.draw_at(d, pad_o)
        if up_indicator is not None:
            up_indicator.draw_at(d, up_o)
        if nail_indicator is not None:
            nail_indicator.draw_at(d, nail_o)
        if knuckle_indicator is not None:
            knuckle_indicator.draw_at(d, knuckle_o)
        if double_down_indicator is not None:
            double_down_indicator.draw_at(d, double_down_o)

    indicators_metrics: ThumbClusterData[LayerIndicatorMetrics | None] = ThumbClusterData(
        down_key=down_indicator.metrics if down_indicator is not None else None,
        pad_key=pad_indicator.metrics if pad_indicator is not None else None,
        up_key=up_indicator.metrics if up_indicator is not None else None,
        nail_key=nail_indicator.metrics if nail_indicator is not None else None,
        knuckle_key=knuckle_indicator.metrics if knuckle_indicator is not None else None,
        double_down_key=(
            double_down_indicator.metrics if double_down_indicator is not None else None
        ),
    )

    # Top overhang — how far any present indicator extends above the
    # cluster's top edge (y=0). Each indicator's ``circle_center`` is
    # in key-local coords; add the key's slot origin to get its
    # cluster-local top edge, then take the most negative across all
    # present indicators. Zero when none extend above the cluster.
    indicator_slots = (
        (slots.down_origin, down_indicator),
        (slots.pad_origin, pad_indicator),
        (slots.up_origin, up_indicator),
        (slots.nail_origin, nail_indicator),
        (slots.knuckle_origin, knuckle_indicator),
        (slots.double_down_origin, double_down_indicator),
    )
    top_overhang = max(
        (
            -(slot_origin.y + ind.metrics.circle_center.y - ind.metrics.circle_radius)
            for slot_origin, ind in indicator_slots
            if ind is not None
        ),
        default=0.0,
    )
    top_overhang = max(0.0, top_overhang)

    return MetricsComponent(
        size=size,
        draw_fn=draw_at,
        metrics=ThumbClusterMetrics(
            down_key=down.metrics,
            pad_key=pad.metrics,
            up_key=up.metrics,
            nail_key=nail.metrics,
            knuckle_key=knuckle.metrics,
            double_down_key=double_down.metrics,
            indicators=indicators_metrics,
            top_overhang=top_overhang,
        ),
    )


__all__ = [
    "FingerCluster",
    "FingerClusterMetrics",
    "ThumbCluster",
    "ThumbClusterMetrics",
]
