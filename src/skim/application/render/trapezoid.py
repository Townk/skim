# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Geometric shapes and aspect ratio utilities for SVG rendering.

This module provides custom SVG shapes (Trapezoid) and aspect ratio handling
for maintaining proportions during keyboard layout rendering.
"""

import math

import drawsvg as draw

from skim.domain import Alignment


class Trapezoid(draw.DrawingBasicElement):
    """
    A trapezoid shape with optional rounded corners.

    Create vertical trapezoids by specifying top_width and/or bottom_width.
    Create horizontal trapezoids by specifying left_height and/or right_height.

    The bounding box (width/height) can be omitted and will be auto-calculated,
    or explicitly provided for precise control.
    """

    TAG_NAME = "path"

    def __init__(
        self,
        x: float = 0,
        y: float = 0,
        width: float | None = None,
        height: float | None = None,
        top_width: float | None = None,
        bottom_width: float | None = None,
        left_height: float | None = None,
        right_height: float | None = None,
        align_x=Alignment.CENTER,
        align_y=Alignment.CENTER,
        corners_radius: float = 0,
        **kwargs,
    ):
        super().__init__(**kwargs)

        # Validate that we have the right combination of parameters
        vertical = top_width is not None or bottom_width is not None
        horizontal = left_height is not None or right_height is not None

        if vertical and horizontal:
            raise ValueError(
                "Cannot specify both vertical (top_width/bottom_width) and "
                "horizontal (left_height/right_height) dimensions. Choose one orientation."
            )

        if not vertical and not horizontal:
            raise ValueError(
                "Must specify either vertical dimensions (top_width/bottom_width) "
                "or horizontal dimensions (left_height/right_height)"
            )

        # Auto-calculate bounding box if not provided
        if vertical:
            if width is None:
                width = max(top_width or 0, bottom_width or 0)
                if width == 0:
                    raise ValueError("At least one of top_width or bottom_width must be > 0")
            if height is None:
                raise ValueError("height is required for vertical trapezoids")

            # Default missing dimensions to full width
            if top_width is None:
                top_width = width
            if bottom_width is None:
                bottom_width = width

        else:  # horizontal
            if height is None:
                height = max(left_height or 0, right_height or 0)
                if height == 0:
                    raise ValueError("At least one of left_height or right_height must be > 0")
            if width is None:
                raise ValueError("width is required for horizontal trapezoids")

            # Default missing dimensions to full height
            if left_height is None:
                left_height = height
            if right_height is None:
                right_height = height

        # Validate dimensions fit within bounding box
        if vertical:
            if top_width is not None and top_width > width:
                raise ValueError(
                    f"top_width ({top_width}) exceeds bounding box width ({width}). "
                    f"Either reduce top_width to ≤{width} or increase width to ≥{top_width}"
                )
            if bottom_width is not None and bottom_width > width:
                raise ValueError(
                    f"bottom_width ({bottom_width}) exceeds bounding box width ({width}). "
                    f"Either reduce bottom_width to ≤{width} or increase width to ≥{bottom_width}"
                )
        else:
            if left_height is not None and left_height > height:
                raise ValueError(
                    f"left_height ({left_height}) exceeds bounding box height ({height}). "
                    f"Either reduce left_height to ≤{height} or increase height to ≥{left_height}"
                )
            if right_height is not None and right_height > height:
                raise ValueError(
                    f"right_height ({right_height}) exceeds bounding box height ({height}). "
                    f"Either reduce right_height to ≤{height} or increase height to ≥{right_height}"
                )

        if vertical:
            assert width is not None and height is not None
            assert top_width is not None and bottom_width is not None
            points = self._calculate_vertical_points(
                width, height, top_width, bottom_width, align_x
            )
        else:
            assert width is not None and height is not None
            assert left_height is not None and right_height is not None
            points = self._calculate_horizontal_points(
                width, height, left_height, right_height, align_y
            )

        # Offset points by x, y position
        points = [(px + x, py + y) for px, py in points]

        # Create path
        if corners_radius > 0:
            path_data = self._create_rounded_path(points, corners_radius)
        else:
            path_data = self._create_sharp_path(points)

        self.args["d"] = path_data

    def _calculate_vertical_points(
        self,
        width: float,
        height: float,
        top_width: float,
        bottom_width: float,
        align_x: Alignment,
    ) -> list[tuple[float, float]]:
        top_offset = self._calculate_offset(width, top_width, align_x)
        bottom_offset = self._calculate_offset(width, bottom_width, align_x)

        return [
            (top_offset, 0),
            (top_offset + top_width, 0),
            (bottom_offset + bottom_width, height),
            (bottom_offset, height),
        ]

    def _calculate_horizontal_points(
        self,
        width: float,
        height: float,
        left_height: float,
        right_height: float,
        align_y: Alignment,
    ) -> list[tuple[float, float]]:
        left_offset = self._calculate_offset(height, left_height, align_y)
        right_offset = self._calculate_offset(height, right_height, align_y)

        return [
            (0, left_offset),
            (width, right_offset),
            (width, right_offset + right_height),
            (0, left_offset + left_height),
        ]

    @staticmethod
    def _calculate_offset(
        long_dimension: float, short_dimension: float, alignment: Alignment
    ) -> float:
        """Calculate offset for aligning a short dimension within a long dimension.

        Args:
            long_dimension: The larger dimension to align within.
            short_dimension: The smaller dimension to align.
            alignment: The alignment strategy (START, CENTER, or END).

        Returns:
            The offset from the start of the long dimension.
        """
        if alignment == Alignment.START:
            return 0
        elif alignment == Alignment.CENTER:
            return (long_dimension - short_dimension) / 2
        elif alignment == Alignment.END:
            return long_dimension - short_dimension
        return 0

    @staticmethod
    def _create_sharp_path(points: list[tuple[float, float]]) -> str:
        """Create SVG path data for a polygon with sharp corners.

        Args:
            points: List of (x, y) coordinate tuples defining the polygon vertices.

        Returns:
            SVG path data string (M/L/Z commands).
        """
        path = f"M {points[0][0]} {points[0][1]}"
        for x, y in points[1:]:
            path += f" L {x} {y}"
        path += " Z"
        return path

    @staticmethod
    def _create_rounded_path(points: list[tuple[float, float]], radius: float) -> str:
        """Create SVG path data for a polygon with rounded corners.

        Uses circular arcs to round each corner of the polygon. The effective
        radius is clamped to not exceed half the length of adjacent edges.

        Args:
            points: List of (x, y) coordinate tuples defining the polygon vertices.
            radius: The desired corner radius in SVG units.

        Returns:
            SVG path data string (M/L/A/Z commands).
        """

        def vector(p1: tuple[float, float], p2: tuple[float, float]) -> tuple[float, float]:
            return p2[0] - p1[0], p2[1] - p1[1]

        def normalize(v: tuple[float, float]) -> tuple[float, float]:
            length = math.sqrt(v[0] ** 2 + v[1] ** 2)
            if length == 0:
                return 0.0, 0.0
            return v[0] / length, v[1] / length

        def distance(p1: tuple[float, float], p2: tuple[float, float]) -> float:
            return math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)

        n = len(points)
        path_parts = []

        for i in range(n):
            curr = points[i]
            prev = points[(i - 1) % n]
            next_point = points[(i + 1) % n]

            # Vectors from current point to neighbors
            v_prev = vector(curr, prev)
            v_next = vector(curr, next_point)

            # Normalize vectors
            v_prev_norm = normalize(v_prev)
            v_next_norm = normalize(v_next)

            # Calculate effective radius (can't be larger than half the edge length)
            edge_len_prev = distance(curr, prev)
            edge_len_next = distance(curr, next_point)
            effective_radius = min(radius, edge_len_prev / 2, edge_len_next / 2)

            # Start point of the arc (offset from corner toward previous point)
            start_x = curr[0] + v_prev_norm[0] * effective_radius
            start_y = curr[1] + v_prev_norm[1] * effective_radius

            # End point of the arc (offset from corner toward next point)
            end_x = curr[0] + v_next_norm[0] * effective_radius
            end_y = curr[1] + v_next_norm[1] * effective_radius

            if i == 0:
                path_parts.append(f"M {start_x} {start_y}")
            else:
                path_parts.append(f"L {start_x} {start_y}")

            # Add arc to the end point
            # Using sweep-flag=1 for consistent clockwise arcs
            path_parts.append(f"A {effective_radius} {effective_radius} 0 0 1 {end_x} {end_y}")

        path_parts.append("Z")
        return " ".join(path_parts)
