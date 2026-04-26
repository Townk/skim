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

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

import drawsvg as draw

from skim.data.keyboard import ThumbCluster
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
