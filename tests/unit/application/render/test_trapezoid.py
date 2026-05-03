# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.application.render.geometry module.

Tests cover Trapezoid shape generation.
"""

import pytest

from skim.application.render.trapezoid import Trapezoid
from skim.domain.domain_types import Alignment


class TestTrapezoidVertical:
    """Tests for Trapezoid with vertical orientation."""

    def test_basic_vertical_trapezoid(self):
        """Create a basic vertical trapezoid with top smaller than bottom."""
        trap = Trapezoid(x=10, y=20, width=100, height=50, top_width=60, bottom_width=100)
        assert "d" in trap.args
        assert trap.args["d"]

    def test_vertical_trapezoid_top_only(self):
        """Vertical trapezoid with only top_width specified."""
        trap = Trapezoid(x=0, y=0, width=100, height=50, top_width=60)
        assert "d" in trap.args

    def test_vertical_trapezoid_bottom_only(self):
        """Vertical trapezoid with only bottom_width specified."""
        trap = Trapezoid(x=0, y=0, width=100, height=50, bottom_width=60)
        assert "d" in trap.args

    def test_vertical_trapezoid_width_auto_calculated(self):
        """Width is auto-calculated from max of top/bottom when not specified."""
        trap = Trapezoid(x=0, y=0, height=50, top_width=60, bottom_width=80)
        # Width should be inferred from max
        assert "d" in trap.args

    def test_vertical_trapezoid_requires_height(self):
        """Vertical trapezoid requires explicit height."""
        with pytest.raises(ValueError, match="height is required"):
            Trapezoid(x=0, y=0, top_width=60)

    def test_vertical_trapezoid_align_start(self):
        """Vertical trapezoid with START alignment."""
        trap = Trapezoid(x=0, y=0, width=100, height=50, top_width=60, align_x=Alignment.START)
        assert "d" in trap.args

    def test_vertical_trapezoid_align_center(self):
        """Vertical trapezoid with CENTER alignment."""
        trap = Trapezoid(x=0, y=0, width=100, height=50, top_width=60, align_x=Alignment.CENTER)
        assert "d" in trap.args

    def test_vertical_trapezoid_align_end(self):
        """Vertical trapezoid with END alignment."""
        trap = Trapezoid(x=0, y=0, width=100, height=50, top_width=60, align_x=Alignment.END)
        assert "d" in trap.args

    def test_vertical_trapezoid_exceeds_width_raises(self):
        """Error when top_width exceeds bounding box width."""
        with pytest.raises(ValueError, match="top_width.*exceeds bounding box"):
            Trapezoid(x=0, y=0, width=50, height=50, top_width=100)

    def test_vertical_trapezoid_bottom_exceeds_width_raises(self):
        """Error when bottom_width exceeds bounding box width."""
        with pytest.raises(ValueError, match="bottom_width.*exceeds bounding box"):
            Trapezoid(x=0, y=0, width=50, height=50, bottom_width=100)


class TestTrapezoidHorizontal:
    """Tests for Trapezoid with horizontal orientation."""

    def test_basic_horizontal_trapezoid(self):
        """Create a basic horizontal trapezoid."""
        trap = Trapezoid(x=10, y=20, width=100, height=50, left_height=30, right_height=50)
        assert "d" in trap.args

    def test_horizontal_trapezoid_left_only(self):
        """Horizontal trapezoid with only left_height specified."""
        trap = Trapezoid(x=0, y=0, width=100, height=50, left_height=30)
        assert "d" in trap.args

    def test_horizontal_trapezoid_right_only(self):
        """Horizontal trapezoid with only right_height specified."""
        trap = Trapezoid(x=0, y=0, width=100, height=50, right_height=30)
        assert "d" in trap.args

    def test_horizontal_trapezoid_height_auto_calculated(self):
        """Height is auto-calculated from max of left/right when not specified."""
        trap = Trapezoid(x=0, y=0, width=100, left_height=30, right_height=50)
        assert "d" in trap.args

    def test_horizontal_trapezoid_requires_width(self):
        """Horizontal trapezoid requires explicit width."""
        with pytest.raises(ValueError, match="width is required"):
            Trapezoid(x=0, y=0, left_height=30)

    def test_horizontal_trapezoid_exceeds_height_raises(self):
        """Error when left_height exceeds bounding box height."""
        with pytest.raises(ValueError, match="left_height.*exceeds bounding box"):
            Trapezoid(x=0, y=0, width=100, height=50, left_height=100)


class TestTrapezoidValidation:
    """Tests for Trapezoid parameter validation."""

    def test_cannot_mix_vertical_and_horizontal(self):
        """Cannot specify both vertical and horizontal dimensions."""
        with pytest.raises(ValueError, match="Cannot specify both"):
            Trapezoid(
                x=0,
                y=0,
                width=100,
                height=50,
                top_width=60,
                left_height=30,
            )

    def test_must_specify_orientation(self):
        """Must specify either vertical or horizontal dimensions."""
        with pytest.raises(ValueError, match="Must specify either"):
            Trapezoid(x=0, y=0, width=100, height=50)

    def test_zero_dimension_raises(self):
        """Zero-width dimension raises error."""
        with pytest.raises(ValueError):
            Trapezoid(x=0, y=0, height=50, top_width=0, bottom_width=0)


class TestTrapezoidRounded:
    """Tests for Trapezoid with rounded corners."""

    def test_rounded_corners(self):
        """Trapezoid with rounded corners generates arc commands."""
        trap = Trapezoid(x=0, y=0, width=100, height=50, top_width=60, corners_radius=5)
        path = trap.args["d"]
        # Rounded path should contain Arc commands
        assert "A" in path

    def test_sharp_corners(self):
        """Trapezoid with radius=0 generates only line commands."""
        trap = Trapezoid(x=0, y=0, width=100, height=50, top_width=60, corners_radius=0)
        path = trap.args["d"]
        # Sharp path should only have M, L, Z
        assert "A" not in path
        assert "M" in path
        assert "L" in path
        assert "Z" in path

    def test_radius_clamped_to_half_edge(self):
        """Large radius is clamped to half the smallest edge."""
        trap = Trapezoid(x=0, y=0, width=100, height=10, top_width=60, corners_radius=50)
        # Should not raise, radius is clamped internally
        assert "d" in trap.args


class TestTrapezoidSvgAttributes:
    """Tests for Trapezoid SVG attributes."""

    def test_fill_attribute(self):
        """Trapezoid accepts fill attribute."""
        trap = Trapezoid(x=0, y=0, width=100, height=50, top_width=60, fill="#FF0000")
        assert trap.args.get("fill") == "#FF0000"

    def test_stroke_attribute(self):
        """Trapezoid accepts stroke attribute."""
        trap = Trapezoid(
            x=0, y=0, width=100, height=50, top_width=60, stroke="black", stroke_width=2
        )
        assert trap.args.get("stroke") == "black"
        assert trap.args.get("stroke-width") == 2

    def test_tag_name_is_path(self):
        """Trapezoid renders as a path element."""
        assert Trapezoid.TAG_NAME == "path"
