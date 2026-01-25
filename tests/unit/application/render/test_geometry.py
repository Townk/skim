"""Unit tests for skim.application.render.geometry module.

Tests cover Trapezoid shape generation and AspectRatio calculations.
"""

import pytest

from skim.application.render.geometry import (
    AspectRatio,
    Trapezoid,
    dimensions_from_ratio,
)
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


class TestAspectRatioInit:
    """Tests for AspectRatio initialization."""

    def test_basic_ratio_parsing(self):
        """Parse a basic aspect ratio string."""
        ar = AspectRatio("16:9")
        assert ar._width == 16
        assert ar._height == 9

    def test_ratio_with_float_values(self):
        """Parse ratio with float values."""
        ar = AspectRatio("1.5:1")
        assert ar._width == 1.5
        assert ar._height == 1

    def test_square_ratio(self):
        """Parse 1:1 ratio."""
        ar = AspectRatio("1:1")
        assert ar._width == 1
        assert ar._height == 1

    def test_invalid_format_raises(self):
        """Invalid format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid aspect ratio format"):
            AspectRatio("16-9")

    def test_single_value_raises(self):
        """Single value without colon raises ValueError."""
        with pytest.raises(ValueError, match="Invalid aspect ratio format"):
            AspectRatio("16")

    def test_non_numeric_width_raises(self):
        """Non-numeric width raises ValueError."""
        with pytest.raises(ValueError, match="width component"):
            AspectRatio("abc:9")

    def test_non_numeric_height_raises(self):
        """Non-numeric height raises ValueError."""
        with pytest.raises(ValueError, match="height component"):
            AspectRatio("16:xyz")

    def test_zero_width_raises(self):
        """Zero width raises ValueError."""
        with pytest.raises(ValueError, match="width must be positive"):
            AspectRatio("0:9")

    def test_zero_height_raises(self):
        """Zero height raises ValueError."""
        with pytest.raises(ValueError, match="height must be positive"):
            AspectRatio("16:0")

    def test_negative_width_raises(self):
        """Negative width raises ValueError."""
        with pytest.raises(ValueError, match="width must be positive"):
            AspectRatio("-1:9")

    def test_negative_height_raises(self):
        """Negative height raises ValueError."""
        with pytest.raises(ValueError, match="height must be positive"):
            AspectRatio("16:-1")


class TestAspectRatioFromDimensions:
    """Tests for AspectRatio.from_dimensions class method."""

    def test_landscape_dimensions(self):
        """Create ratio from landscape dimensions."""
        ar = AspectRatio.from_dimensions(1920, 1080)
        # Should normalize to something like 1.777...:1
        assert ar._width > ar._height

    def test_portrait_dimensions(self):
        """Create ratio from portrait dimensions."""
        ar = AspectRatio.from_dimensions(1080, 1920)
        # Should normalize to something like 1:1.777...
        assert ar._width < ar._height

    def test_square_dimensions(self):
        """Create ratio from square dimensions."""
        ar = AspectRatio.from_dimensions(100, 100)
        assert str(ar) == "1:1"

    def test_with_precision(self):
        """Apply precision rounding."""
        ar = AspectRatio.from_dimensions(1920, 1080, precision=2)
        assert "1.78" in str(ar) or "1.77" in str(ar)

    def test_zero_width_raises(self):
        """Zero width raises ValueError."""
        with pytest.raises(ValueError, match="width must be positive"):
            AspectRatio.from_dimensions(0, 100)

    def test_zero_height_raises(self):
        """Zero height raises ValueError."""
        with pytest.raises(ValueError, match="height must be positive"):
            AspectRatio.from_dimensions(100, 0)


class TestAspectRatioMethods:
    """Tests for AspectRatio methods."""

    def test_height_from_width(self):
        """Calculate height from width maintaining ratio."""
        ar = AspectRatio("16:9")
        height = ar.height_from_width(160)
        assert height == 90

    def test_width_from_height(self):
        """Calculate width from height maintaining ratio."""
        ar = AspectRatio("16:9")
        width = ar.width_from_height(90)
        assert width == 160

    def test_str_returns_ratio_string(self):
        """__str__ returns the original ratio string."""
        ar = AspectRatio("16:9")
        assert str(ar) == "16:9"

    def test_repr_includes_class_name(self):
        """__repr__ includes class name and ratio."""
        ar = AspectRatio("16:9")
        assert "AspectRatio" in repr(ar)
        assert "16:9" in repr(ar)


class TestAspectRatioEquality:
    """Tests for AspectRatio equality and hashing."""

    def test_equal_ratios(self):
        """Ratios with same mathematical value are equal."""
        ar1 = AspectRatio("16:9")
        ar2 = AspectRatio("32:18")  # Same ratio
        assert ar1 == ar2

    def test_different_ratios_not_equal(self):
        """Different ratios are not equal."""
        ar1 = AspectRatio("16:9")
        ar2 = AspectRatio("4:3")
        assert ar1 != ar2

    def test_equality_with_non_aspect_ratio(self):
        """Comparison with non-AspectRatio returns NotImplemented."""
        ar = AspectRatio("16:9")
        assert ar != "16:9"
        assert ar != 16 / 9

    def test_hash_equality(self):
        """Equal ratios have the same hash."""
        ar1 = AspectRatio("16:9")
        ar2 = AspectRatio("32:18")
        assert hash(ar1) == hash(ar2)

    def test_usable_in_set(self):
        """AspectRatio can be used in sets."""
        ar1 = AspectRatio("16:9")
        ar2 = AspectRatio("32:18")  # Same ratio
        ar3 = AspectRatio("4:3")

        s = {ar1, ar2, ar3}
        # ar1 and ar2 should deduplicate
        assert len(s) == 2


class TestDimensionsFromRatio:
    """Tests for dimensions_from_ratio function."""

    def test_calculate_height_from_width(self):
        """Calculate height when width is provided."""
        ar = AspectRatio("16:9")
        w, h = dimensions_from_ratio(ar, width=160, height=None)
        assert w == 160
        assert h == 90

    def test_calculate_width_from_height(self):
        """Calculate width when height is provided."""
        ar = AspectRatio("16:9")
        w, h = dimensions_from_ratio(ar, width=None, height=90)
        assert w == 160
        assert h == 90

    def test_both_dimensions_returns_fit(self):
        """When both provided, returns dimensions that fit."""
        ar = AspectRatio("16:9")
        w, h = dimensions_from_ratio(ar, width=160, height=100)
        # Should fit within 160x100 maintaining 16:9
        assert w <= 160
        assert h <= 100
        # Check ratio is maintained
        assert abs(w / h - 16 / 9) < 0.01

    def test_both_dimensions_width_constrains(self):
        """When width is the constraint, use it."""
        ar = AspectRatio("16:9")
        w, h = dimensions_from_ratio(ar, width=160, height=200)
        assert w == 160
        assert h == 90

    def test_both_dimensions_height_constrains(self):
        """When height is the constraint, use it."""
        ar = AspectRatio("16:9")
        w, h = dimensions_from_ratio(ar, width=400, height=90)
        assert w == 160
        assert h == 90

    def test_neither_dimension_raises(self):
        """Both None raises ValueError."""
        ar = AspectRatio("16:9")
        with pytest.raises(ValueError, match="At least one"):
            dimensions_from_ratio(ar, width=None, height=None)
