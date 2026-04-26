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

from skim.domain import SvalboardTargetKey


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
        col_X: The routing column X coordinate, set during Phase 2 allocation.
        path: Accumulating SVG path; appended to during routing.
    """

    key: SvalboardTargetKey | None
    direction: Direction
    target_point: tuple[float, float]
    target_layer: int
    col_X: float = 0.0
    path: draw.Path = field(default_factory=lambda: draw.Path(stroke="black", fill="none"))


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
