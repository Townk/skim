# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Composable building blocks for Svalboard key clusters.

Hosts cluster-level composables that lay out the per-key composables
from :mod:`svalboard_keys` in their cluster shape — finger cluster
(centre + 4 directional + optional double-south) for now; thumb
cluster follows.

The cluster does three jobs the per-key composables don't:

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

Layer indicators are not wired in yet — the cluster composable
returns Size + drawing for the keys themselves; the indicator pass
follows in a subsequent commit. This keeps the cluster commit
reviewable in isolation.
"""

from __future__ import annotations

import colorsys
from collections.abc import Callable
from dataclasses import dataclass

from skim.data import LayerColor, Palette, SplitSidePosition
from skim.data.keyboard import FingerCluster as FingerClusterData
from skim.domain import KeyboardSide, KeyDirection, SvalboardTargetKey

from .composable import Composable
from .primitives import MetricsComponent, Point, Size
from .styling import lighten, str_to_rgb
from .svalboard_keys import (
    CenterKey,
    DirectionalKey,
    DoubleSouthKey,
    SvalboardKeyMetrics,
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


# ---------------------------------------------------------------------------
# Cluster metrics
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class FingerClusterMetrics:
    """Metrics surfaced by a built finger cluster.

    Per-key :class:`SvalboardKeyMetrics` are exposed by slot so the
    parent (a future per-layer composable) can read indicator
    anchors / directions for any key without re-instantiating the
    per-key composables.
    """

    center_key: SvalboardKeyMetrics
    north_key: SvalboardKeyMetrics
    east_key: SvalboardKeyMetrics
    south_key: SvalboardKeyMetrics
    west_key: SvalboardKeyMetrics
    double_south_key: SvalboardKeyMetrics | None


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
    palette: Palette,
    use_layer_colors_on_keys: bool,
    qmk_index_to_position: Callable[[int], int | None],
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
    position = qmk_index_to_position(key.layer_switch)
    if position is not None and 0 <= position < len(palette.layers):
        lc = palette.layers[position]
        return lc[lc.color_index - (1 if use_accent else 0)]
    return default


def _resolve_label_color(
    *,
    key: SvalboardTargetKey,
    fill_color: str,
    palette: Palette,
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
    palette: Palette,
    layer_base_color: str,
    use_layer_colors_on_keys: bool,
    qmk_index_to_position: Callable[[int], int | None],
) -> _FingerKeyColors:
    """Resolve fill + accent + label colours for one slot."""
    fill = _resolve_fill(
        key=key,
        default=default_primary,
        use_accent=False,
        palette=palette,
        use_layer_colors_on_keys=use_layer_colors_on_keys,
        qmk_index_to_position=qmk_index_to_position,
    )
    accent = _resolve_fill(
        key=key,
        default=default_accent,
        use_accent=True,
        palette=palette,
        use_layer_colors_on_keys=use_layer_colors_on_keys,
        qmk_index_to_position=qmk_index_to_position,
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
    layer_colors: LayerColor,
    palette: Palette,
    has_double_south: bool = False,
    use_layer_colors_on_keys: bool = True,
    hold_symbol_position: SplitSidePosition = SplitSidePosition.OUTWARD,
    qmk_index_to_position: Callable[[int], int | None] = lambda idx: idx,
):
    """A finger cluster — five (or six) keys laid out in cross shape.

    Owns the cluster-level concerns: per-key layout from the
    cluster proportions, colour resolution from the layer palette,
    hold-symbol nudging on east / west keys. Each per-key composable
    receives resolved inputs and stays pure.

    Reports :class:`MetricsComponent[FingerClusterMetrics]` exposing
    each key's :class:`SvalboardKeyMetrics` by slot — a future
    per-layer composable will read these to build layer indicators
    around the cluster without re-instantiating the keys.

    ``has_double_south`` controls whether a sixth key (the double-
    south trapezoid below the south key) renders. ``Size.height``
    grows accordingly.
    """
    del ctx  # Per-key composables read ``ctx`` themselves.

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
            qmk_index_to_position=qmk_index_to_position,
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

    size = Size(width, slots.cluster_height)

    def draw_at(d, origin):
        center.draw_at(d, Point(origin.x + slots.center_origin.x, origin.y + slots.center_origin.y))
        north.draw_at(d, Point(origin.x + slots.north_origin.x, origin.y + slots.north_origin.y))
        east.draw_at(d, Point(origin.x + slots.east_origin.x, origin.y + slots.east_origin.y))
        south.draw_at(d, Point(origin.x + slots.south_origin.x, origin.y + slots.south_origin.y))
        west.draw_at(d, Point(origin.x + slots.west_origin.x, origin.y + slots.west_origin.y))
        if double_south is not None:
            double_south.draw_at(
                d,
                Point(
                    origin.x + slots.double_south_origin.x,
                    origin.y + slots.double_south_origin.y,
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
        ),
    )


__all__ = [
    "FingerCluster",
    "FingerClusterMetrics",
]
