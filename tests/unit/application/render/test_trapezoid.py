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


class TestTrapezoidOutset:
    """Tests for Trapezoid.outset() — the Minkowski offset method.

    The outset moves every edge perpendicular to itself by ``amount``
    and grows the corner radius by the same amount. Verified against
    closed-form geometry.
    """

    def test_zero_outset_returns_equivalent_trapezoid(self):
        """outset(0) returns a fresh Trapezoid with identical path."""
        original = Trapezoid(x=10, y=20, width=100, height=80, top_width=70, corners_radius=5)
        outset = original.outset(0)
        assert outset is not original
        assert outset.args["d"] == original.args["d"]

    def test_centered_vertical_top_narrower_dimensions(self):
        """For align_x=CENTER vertical with tw<bw: closed-form match."""
        import math

        original = Trapezoid(
            x=0,
            y=0,
            width=100,
            height=100,
            top_width=80,
            bottom_width=100,
            corners_radius=4,
        )
        n = 10
        outset = original.outset(n)
        delta = (100 - 80) / 2
        slant_len = math.sqrt(100 * 100 + delta * delta)
        expected_top_width = 80 + 2 * n * (slant_len - delta) / 100
        expected_bottom_width = 100 + 2 * n * (slant_len + delta) / 100
        assert outset._construction["top_width"] == pytest.approx(expected_top_width)
        assert outset._construction["bottom_width"] == pytest.approx(expected_bottom_width)
        assert outset._construction["height"] == pytest.approx(120)
        assert outset._construction["corners_radius"] == pytest.approx(14)
        # New bbox width = max(new_tw, new_bw) = new_bw for tw<bw.
        assert outset._construction["width"] == pytest.approx(expected_bottom_width)
        # Centered: new origin = original_x + (W - new_bbox_w)/2.
        assert outset._construction["x"] == pytest.approx((100 - expected_bottom_width) / 2)
        assert outset._construction["y"] == pytest.approx(-10)

    def test_centered_vertical_top_wider_dimensions(self):
        """For align_x=CENTER vertical with tw>bw: top stays wider after outset."""
        import math

        original = Trapezoid(
            x=0,
            y=0,
            width=100,
            height=100,
            top_width=100,
            bottom_width=80,
            corners_radius=4,
        )
        n = 10
        outset = original.outset(n)
        delta = (80 - 100) / 2  # negative
        slant_len = math.sqrt(100 * 100 + delta * delta)
        expected_top_width = 100 + 2 * n * (slant_len - delta) / 100
        expected_bottom_width = 80 + 2 * n * (slant_len + delta) / 100
        assert outset._construction["top_width"] == pytest.approx(expected_top_width)
        assert outset._construction["bottom_width"] == pytest.approx(expected_bottom_width)
        # bbox_w follows the wider face, which is now the top.
        assert outset._construction["width"] == pytest.approx(expected_top_width)

    def test_align_x_start_keeps_left_edge_straight(self):
        """For align_x=START: the left edge stays vertical and shifts left by N."""
        original = Trapezoid(
            x=10,
            y=20,
            width=100,
            height=100,
            top_width=80,
            bottom_width=100,
            align_x=Alignment.START,
            corners_radius=3,
        )
        n = 5
        outset = original.outset(n)
        assert outset._construction["x"] == pytest.approx(10 - n)
        assert outset._construction["y"] == pytest.approx(20 - n)
        assert outset._construction["align_x"] == Alignment.START
        assert outset._construction["height"] == pytest.approx(100 + 2 * n)
        assert outset._construction["corners_radius"] == pytest.approx(3 + n)

    def test_align_x_end_keeps_right_edge_straight(self):
        """For align_x=END: the right edge stays vertical at original_x + W + N."""
        original = Trapezoid(
            x=10,
            y=20,
            width=100,
            height=100,
            top_width=80,
            bottom_width=100,
            align_x=Alignment.END,
            corners_radius=3,
        )
        n = 5
        outset = original.outset(n)
        # Right edge at new_x + new_bbox_w should equal original (x + W) + n.
        right_edge = outset._construction["x"] + outset._construction["width"]
        assert right_edge == pytest.approx(10 + 100 + n)
        assert outset._construction["align_x"] == Alignment.END

    def test_horizontal_align_y_start_dimensions(self):
        """For align_y=START horizontal trapezoid: closed-form match."""
        import math

        original = Trapezoid(
            x=0,
            y=0,
            width=100,
            height=50,
            left_height=40,
            right_height=50,
            align_y=Alignment.START,
            corners_radius=2,
        )
        n = 4
        outset = original.outset(n)
        delta = 50 - 40
        slant_len = math.sqrt(100 * 100 + delta * delta)
        expected_lh = 40 + n * (100 + slant_len - delta) / 100
        expected_rh = 50 + n * (100 + slant_len + delta) / 100
        assert outset._construction["left_height"] == pytest.approx(expected_lh)
        assert outset._construction["right_height"] == pytest.approx(expected_rh)
        assert outset._construction["width"] == pytest.approx(108)
        # bbox height = max(lh, rh) — for lh<rh, that's the right height.
        assert outset._construction["height"] == pytest.approx(expected_rh)
        assert outset._construction["x"] == pytest.approx(-n)
        assert outset._construction["y"] == pytest.approx(-n)
        assert outset._construction["corners_radius"] == pytest.approx(2 + n)

    def test_corner_radius_grows_by_amount(self):
        """Across all supported orientations, corners_radius grows by N."""
        cases = [
            Trapezoid(x=0, y=0, width=80, height=80, top_width=60, corners_radius=3),
            Trapezoid(
                x=0,
                y=0,
                width=80,
                height=80,
                top_width=60,
                align_x=Alignment.START,
                corners_radius=3,
            ),
            Trapezoid(
                x=0,
                y=0,
                width=80,
                height=80,
                top_width=60,
                align_x=Alignment.END,
                corners_radius=3,
            ),
            Trapezoid(
                x=0,
                y=0,
                width=80,
                height=40,
                left_height=40,
                right_height=30,
                align_y=Alignment.START,
                corners_radius=3,
            ),
        ]
        for trap in cases:
            outset = trap.outset(2.5)
            assert outset._construction["corners_radius"] == pytest.approx(5.5), (
                f"corner radius did not grow for {trap._construction!r}"
            )

    def test_unsupported_align_raises(self):
        """Horizontal align_y=CENTER currently raises NotImplementedError."""
        original = Trapezoid(
            x=0,
            y=0,
            width=80,
            height=40,
            left_height=40,
            right_height=30,
            align_y=Alignment.CENTER,
        )
        with pytest.raises(NotImplementedError, match="align_y"):
            original.outset(2)

    def test_perpendicular_distance_is_amount(self):
        """For a CENTER trapezoid, perpendicular distance from the
        original slanted edge to the outset slanted edge should be
        exactly ``amount`` — proving this is a true Minkowski offset
        rather than parameter inflation (which would yield
        ``amount * cos(slant)``)."""
        import math

        # tw=70, bw=100, H=100. Slant angle θ from vertical:
        # tan(θ) = 15/100 = 0.15, cos(θ) ≈ 0.9889. Param inflation
        # would give x_shift_at_top = N (we expect more — N/cos(θ)).
        original = Trapezoid(
            x=0,
            y=0,
            width=100,
            height=100,
            top_width=70,
            bottom_width=100,
        )
        n = 5
        outset = original.outset(n)
        delta = (100 - 70) / 2  # 15
        slant_len = math.sqrt(100 * 100 + delta * delta)
        cos_theta = 100 / slant_len
        # Top corner of slanted side (right slant), original at x = 85.
        # Perpendicular outset by N → x at new top edge level (y=-N) is
        # 85 + N/cos(θ) shifted further by tan(θ)*N (because the new
        # top is at a different y).
        # Closed-form via formula: new_top_width = 70 + 2N*(L-Δ)/H.
        new_top_width = outset._construction["top_width"]
        expected_top_increase = 2 * n * (slant_len - delta) / 100
        assert new_top_width - 70 == pytest.approx(expected_top_increase)
        # Sanity-check that this is GREATER than 2*N*cos(θ) (param inflation
        # would give 2*N for the bbox component, where Minkowski gives
        # something larger by the cos factor):
        param_inflation_top_increase = 2 * n  # what param inflation gave
        assert new_top_width - 70 < param_inflation_top_increase, (
            "for tw<bw, top width grows LESS than 2N because the new top "
            "edge sits at y=-N and the slanted edge has been extended back"
        )
        # The reverse holds for bottom_width: it should grow MORE than 2N.
        new_bottom_width = outset._construction["bottom_width"]
        assert new_bottom_width - 100 > 2 * n
        # And the perpendicular distance check: the diagonal of growth
        # in the horizontal direction at the slant midline should be
        # 2N/cos(θ).
        avg_growth = ((new_top_width - 70) + (new_bottom_width - 100)) / 2
        assert avg_growth == pytest.approx(2 * n / cos_theta)
