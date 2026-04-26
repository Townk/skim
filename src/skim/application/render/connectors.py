# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Connector routing for the overview image.

Routes the dotted connector lines that link layer-trigger key indicators to
their target layer's row. See
``docs/superpowers/specs/2026-04-26-overview-connector-routing-design.md``
for the full algorithm.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

import drawsvg as draw

from skim.data.keyboard import FingerCluster, SplitSide, ThumbCluster
from skim.domain import KeyboardSide, SvalboardTargetKey


class RoutingLayout(Protocol):
    """Minimal layout surface the connector router needs.

    Implemented by ``OverviewLayout`` directly. The overview also wraps the
    layout to translate QMK layer indices to row indices before delegating
    to the underlying layout — that wrapper is structurally compatible with
    this protocol.
    """

    @property
    def layer_row_y_positions(self) -> list[float]: ...

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
        extra_top_padding: Caller must shift the thumb cluster (and cluster
            paths already drawn above it) down by this amount before painting
            the routing paths. Applied via the layout's thumb-row offset.
        extra_bottom_padding: Caller must extend canvas height by this amount.
            Includes 0.5 * keymap_spacing of buffer between the bottommost DOWN
            lane and the canvas edge when DOWN lanes exist (zero otherwise).
        extra_right_padding: Caller must extend canvas width by this amount.
            Computed as ``(cols_used + 1) * keymap_spacing`` so the canvas
            covers the routing columns plus the keymap_spacing-long LEFT
            segment from the innermost column to ``target_point.x``.
    """

    paths: list[tuple[draw.Path, int]]
    extra_top_padding: float
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
    left: ThumbCluster[SvalboardTargetKey]
    right: ThumbCluster[SvalboardTargetKey]


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
    x, _y, w, _h = layout.layer_row_bounding_box(target_layer)
    target_y = layout.layer_row_target_y(target_layer)
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
    left: ThumbCluster[SvalboardTargetKey],
    right: ThumbCluster[SvalboardTargetKey],
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
    cluster: FingerCluster[SvalboardTargetKey],
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
    south_ds_special = (
        not is_r4
        and cluster.south_key.layer_switch is not None
        and cluster.double_south_key.layer_switch is not None
    )

    steps: list[ConnectorStep] = []
    for attr, direction in priority:
        key: SvalboardTargetKey = getattr(cluster, attr)
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
        cluster: FingerCluster[SvalboardTargetKey] = getattr(side, side_attr)
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
    """
    left_steps = [s for s in path_list if s.direction == Direction.LEFT]
    if not left_steps:
        return
    # Find the LT_Down partner by its origin attr (set by build_thumb_path_list).
    partner = next(
        (s for s in path_list if s.direction == Direction.DOWN and s.key_origin_attr == "down_key"),
        None,
    )
    # Fallback: use the first DOWN step in path_list if no annotated partner is found.
    if partner is None:
        partner = next((s for s in path_list if s.direction == Direction.DOWN), None)
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

    Returns ``extra_top_padding = N * keymap_spacing`` where ``N`` is the
    number of UP steps processed — exactly the vertical extent the lanes
    occupy above the cluster (lane 1 at ``cluster_top - keymap_spacing``,
    lane N at ``cluster_top - N * keymap_spacing``).
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
    return len(up_steps) * keymap_spacing


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

    Returns ``extra_bottom_padding = (N + 0.5) * keymap_spacing`` where ``N``
    is the number of DOWN steps. The lanes themselves occupy
    ``N * keymap_spacing`` (lane 1 at ``cluster_bottom + keymap_spacing``,
    lane N at ``cluster_bottom + N * keymap_spacing``); the extra
    ``0.5 * keymap_spacing`` buffers the bottommost lane from the canvas
    edge so the border/copyright don't crowd the connector.
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
    # 0.5 * keymap_spacing of buffer between the bottommost lane and the canvas
    # edge so the border/copyright don't crowd the connector.
    return (len(down_steps) + 0.5) * keymap_spacing


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


# NOTE: Deprecated by route_overview_connectors. Removed in Task 11
# once overview.py is rewired. Do not call from new code.
def route_thumb_connectors(
    left: ThumbCluster[SvalboardTargetKey],
    right: ThumbCluster[SvalboardTargetKey],
    layout: RoutingLayout,
    source_layer: int,
    keymap_spacing: float,
    indicator_rects: Mapping[SvalboardTargetKey, tuple[float, float, float, float]],
) -> ConnectorRouting:
    """Top-level entry point for thumb cluster connector routing.

    Orchestrates the full algorithm:
      1. Build the priority-ordered ConnectorStep list.
      2. Attach each step's indicator rect.
      3. Set initial moveTo per direction.
      4. Phase 1: LEFT->DOWN redirect, UP->RIGHT escape, DOWN->RIGHT escape.
      5. Phase 2: greedy column allocation, drop to target Y, multi-target merge.

    Args:
        left, right: Thumb clusters for the source layer.
        layout: The overview layout (used for ``layer_row_bounding_box`` and
            ``thumb_cluster_y_bounds``).
        source_layer: The layer whose triggers originate the connectors.
        keymap_spacing: One outer-key width — used for lane spacing.
        indicator_rects: Map of source-key -> indicator ``(x, y, w, h)``. Must
            cover every key in ``left``/``right`` whose ``layer_switch``
            could enter the priority list.

    Returns:
        ``ConnectorRouting`` with the SVG paths and the three padding values
        the caller must apply (see ``ConnectorRouting`` docstring).
    """
    path_list = build_thumb_path_list(left, right, layout, source_layer, keymap_spacing)
    if not path_list:
        return ConnectorRouting(
            paths=[],
            extra_top_padding=0.0,
            extra_bottom_padding=0.0,
            extra_right_padding=0.0,
        )

    # Attach indicator rects to each step (key lookup is O(1)).
    for step in path_list:
        if step.key is None:
            continue
        try:
            step.indicator_rect = indicator_rects[step.key]
        except KeyError as e:
            raise ValueError(
                f"indicator_rects missing entry for thumb key "
                f"{step.key_origin_attr!r} (target_layer={step.target_layer}); "
                f"caller must populate every key whose layer_switch enters "
                f"the priority list"
            ) from e

    # Set initial moveTo per direction.
    for step in path_list:
        set_initial_moveto(step)

    # Track min/max Y across all step start points for Phase 1 lane math.
    min_y = min(s.current_point[1] for s in path_list)
    max_y = max(s.current_point[1] for s in path_list)

    # Phase 1.
    cluster_top, cluster_bottom = layout.thumb_cluster_y_bounds()
    phase1_redirect_left_to_down(path_list, keymap_spacing)
    extra_top = phase1_up_to_right(path_list, cluster_top, min_y, keymap_spacing)
    extra_bottom = phase1_down_to_right(path_list, cluster_bottom, max_y, keymap_spacing)

    # Phase 2.
    # The first column sits one keymap_spacing east of target_point.x so the
    # innermost path has a real (keymap_spacing-long) final LEFT segment to
    # the target. With first_column_x == target_point.x the multi-target merge's
    # final L would be degenerate.
    row_x, _row_y, row_w, _row_h = layout.layer_row_bounding_box(0)
    first_column_x = row_x + row_w + 2 * keymap_spacing
    cols_used = allocate_columns(path_list, first_column_x, keymap_spacing)
    phase2_route_to_targets(path_list)

    return ConnectorRouting(
        paths=[(s.path, s.target_layer) for s in path_list],
        extra_top_padding=extra_top,
        extra_bottom_padding=extra_bottom,
        extra_right_padding=(cols_used + 1) * keymap_spacing,
    )


def _layer_cluster_y_bounds(layout: RoutingLayout, source_layer: int) -> tuple[float, float]:
    """Return (top_y, bottom_y) of the finger clusters in a given layer's row."""
    _, row_y, _, row_h = layout.layer_row_bounding_box(source_layer)
    return (row_y, row_y + row_h)


def route_overview_connectors(
    layers: Sequence[OverviewLayerSource],
    thumb: ThumbSource,
    layout: RoutingLayout,
    compute_indicator_rects: Callable[
        [], Mapping[SvalboardTargetKey, tuple[float, float, float, float]]
    ],
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
            layout state — typically the caller rebuilds cluster components
            on the second invocation, after pass 1's shifts have mutated the
            layout. Passing a memoized closure that returns the same rects
            twice will produce stale path coordinates in pass 2.
        keymap_spacing: Spacing constant for routing geometry (typically
            ``0.6 * outer_key_size``).

    Returns:
        ConnectorRouting with paths and the residual paddings the caller
        must apply. ``extra_top_padding`` is always 0 (consumed via shifts);
        ``extra_bottom_padding`` is the thumb cluster's bottom padding;
        ``extra_right_padding`` is ``(cols_used + 1) * keymap_spacing``.
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
            extra_top_padding=0.0,
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
        extra_top_padding=0.0,
        extra_bottom_padding=thumb_extra_bottom,
        extra_right_padding=(cols_used + 1) * keymap_spacing,
    )


def _pass1_discover_and_shift(
    layers: Sequence[OverviewLayerSource],
    thumb: ThumbSource,
    layout: RoutingLayout,
    indicator_rects: Mapping[SvalboardTargetKey, tuple[float, float, float, float]],
    keymap_spacing: float,
) -> float:
    """Pass 1: route each source, discover paddings, apply cascading shifts.

    Returns the thumb's extra_bottom_padding (the only padding NOT applied
    via layout shifts; it grows the canvas at the bottom).
    """
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
        extra_top = phase1_up_to_right(paths, cluster_top, min_y, keymap_spacing)
        extra_bottom = phase1_down_to_right(paths, cluster_bottom, max_y, keymap_spacing)
        if extra_top > 0:
            layout.shift_layer_row_and_below(layer.source_layer, extra_top)
        if extra_bottom > 0:
            layout.shift_below_layer_row(layer.source_layer, extra_bottom)

    thumb_paths = build_thumb_path_list(
        thumb.left, thumb.right, layout, thumb.source_layer, keymap_spacing
    )
    if not thumb_paths:
        return 0.0
    _attach_rects_and_set_initial_moveto(thumb_paths, indicator_rects)
    cluster_top, cluster_bottom = layout.thumb_cluster_y_bounds()
    min_y = min(s.current_point[1] for s in thumb_paths)
    max_y = max(s.current_point[1] for s in thumb_paths)
    phase1_redirect_left_to_down(thumb_paths, keymap_spacing)
    extra_top = phase1_up_to_right(thumb_paths, cluster_top, min_y, keymap_spacing)
    extra_bottom = phase1_down_to_right(thumb_paths, cluster_bottom, max_y, keymap_spacing)
    if extra_top > 0:
        layout.shift_thumb_down(extra_top)
    return extra_bottom


def _pass2_build_paths(
    layers: Sequence[OverviewLayerSource],
    thumb: ThumbSource,
    layout: RoutingLayout,
    indicator_rects: Mapping[SvalboardTargetKey, tuple[float, float, float, float]],
    keymap_spacing: float,
) -> list[ConnectorStep]:
    """Pass 2: rebuild paths against the post-shift layout for final geometry.

    Padding values are discarded — they were already applied in pass 1.
    """
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
    indicator_rects: Mapping[SvalboardTargetKey, tuple[float, float, float, float]],
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
            step.indicator_rect = indicator_rects[step.key]
        except KeyError as e:
            raise ValueError(
                f"indicator_rects missing entry for key "
                f"{step.key_origin_attr!r} in cluster {step.source_cluster_attr!r} "
                f"(target_layer={step.target_layer}); caller must populate every "
                f"key whose layer_switch enters the priority list"
            ) from e
        set_initial_moveto(step)
