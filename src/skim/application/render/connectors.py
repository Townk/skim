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

from dataclasses import dataclass, field
from enum import Enum

import drawsvg as draw

from skim.application.render.overview_layout import OverviewLayout
from skim.data.keyboard import ThumbCluster
from skim.domain import KeyboardSide, SvalboardTargetKey


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
        key_origin_attr: The thumb-cluster attribute name that produced this
            step (e.g. ``"down_key"``, ``"up_key"``). Used by Phase 1 routing
            to identify partner paths (e.g. matching LT_Up to LT_Down).
        path: Accumulating SVG path; appended to during routing.
    """

    key: SvalboardTargetKey | None
    direction: Direction
    target_point: tuple[float, float]
    target_layer: int
    col_x: float = 0.0
    current_point: tuple[float, float] = (0.0, 0.0)
    key_origin_attr: str = ""
    path: draw.Path = field(default_factory=lambda: draw.Path(fill="none"))


@dataclass
class ConnectorRouting:
    """Output of the routing algorithm.

    Attributes:
        paths: All connector paths in render order.
        extra_bottom_padding: Caller must extend canvas height by this amount.
        extra_right_padding: Caller must extend canvas width by this amount.
    """

    paths: list[draw.Path]
    extra_bottom_padding: float
    extra_right_padding: float


def target_point_for(
    layout: OverviewLayout,
    target_layer: int,
    source_layer: int,
    keymap_spacing: float,
) -> tuple[float, float] | None:
    """Compute the target point for a connector, or return ``None`` to skip.

    Returns ``None`` for:
    - Self-referential triggers (source == target).
    - Target layer index out of range for the layout's rendered layer rows.

    The target point is one ``keymap_spacing`` to the right of the layer row's
    right edge, vertically centered on the row.
    """
    if target_layer == source_layer:
        return None
    if target_layer < 0 or target_layer >= len(layout.layer_row_y_positions):
        return None
    x, y, w, h = layout.layer_row_bounding_box(target_layer)
    return (x + w + keymap_spacing, y + h / 2.0)


def set_initial_moveto(step: ConnectorStep) -> None:
    """Place the path's first moveTo on the indicator's bounding rect edge.

    The starting edge depends on the path's initial direction:
    - UP    -> top edge, horizontally centered
    - RIGHT -> right edge, vertically centered
    - DOWN  -> bottom edge, horizontally centered
    - LEFT  -> left edge, vertically centered

    The step's key is expected to carry a ``layer_indicator`` attribute with a
    ``bounding_rect`` of the form ``(x, y, width, height)``. This attribute is
    attached to the key by the renderer (see Task 9 in the connector-routing
    foundation plan); it is not part of ``SvalboardTargetKey``'s static schema.
    """
    rx, ry, rw, rh = step.key.layer_indicator.bounding_rect  # pyright: ignore[reportAttributeAccessIssue, reportOptionalMemberAccess]
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
    layout: OverviewLayout,
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
            direction = Direction.LEFT if left.down_key.layer_switch is not None else Direction.DOWN
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
