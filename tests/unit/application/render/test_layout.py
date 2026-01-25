"""Unit tests for skim.application.render.layout module.

Tests cover layout calculations, positions, and sizing for keyboard rendering.
"""

import pytest

from skim.application.render.layout import (
    Boundary,
    BoundingBox,
    FingerClusterKeyProportions,
    FingerClusterLayout,
    KeyLayout,
    KeymapLayout,
    KeymapLayoutMetrics,
    Position,
    Size,
    ThumbClusterKeyProportions,
    ThumbClusterLayout,
)
from skim.data.config import Border, Layout, Output, SkimConfig, Spacing, Style
from skim.data.keyboard import ThumbCluster
from skim.domain.domain_types import Alignment, KeyboardSide


class TestPosition:
    """Tests for Position dataclass."""

    def test_initialization(self):
        """Position initializes with x and y coordinates."""
        pos = Position(x=10.0, y=20.0)
        assert pos.x == 10.0
        assert pos.y == 20.0

    def test_frozen(self):
        """Position is frozen (immutable)."""
        pos = Position(x=10.0, y=20.0)
        with pytest.raises(AttributeError):
            pos.x = 15.0

    def test_slots_optimization(self):
        """Position uses slots for memory optimization."""
        pos = Position(x=10.0, y=20.0)
        assert not hasattr(pos, "__dict__")


class TestSize:
    """Tests for Size dataclass."""

    def test_initialization(self):
        """Size initializes with width and height."""
        size = Size(width=100.0, height=50.0)
        assert size.width == 100.0
        assert size.height == 50.0

    def test_frozen(self):
        """Size is frozen (immutable)."""
        size = Size(width=100.0, height=50.0)
        with pytest.raises(AttributeError):
            size.width = 200.0

    def test_slots_optimization(self):
        """Size uses slots for memory optimization."""
        size = Size(width=100.0, height=50.0)
        assert not hasattr(size, "__dict__")


class TestBoundary:
    """Tests for Boundary dataclass."""

    def test_initialization(self):
        """Boundary initializes with position and width."""
        boundary = Boundary(pos=Position(x=10.0, y=20.0), width=100.0)
        assert boundary.pos.x == 10.0
        assert boundary.pos.y == 20.0
        assert boundary.width == 100.0

    def test_frozen(self):
        """Boundary is frozen (immutable)."""
        boundary = Boundary(pos=Position(x=10.0, y=20.0), width=100.0)
        with pytest.raises(AttributeError):
            boundary.width = 200.0


class TestBoundingBox:
    """Tests for BoundingBox dataclass."""

    def test_initialization(self):
        """BoundingBox initializes with position and size."""
        bbox = BoundingBox(pos=Position(x=10.0, y=20.0), size=Size(width=100.0, height=50.0))
        assert bbox.pos.x == 10.0
        assert bbox.pos.y == 20.0
        assert bbox.size.width == 100.0
        assert bbox.size.height == 50.0


class TestKeyLayout:
    """Tests for KeyLayout dataclass."""

    def test_basic_initialization(self):
        """KeyLayout initializes with basic boundary parameters."""
        layout = KeyLayout(pos=Position(x=10.0, y=20.0), width=100.0)
        assert layout.pos.x == 10.0
        assert layout.width == 100.0
        assert layout.inset == 0  # Default
        assert layout.label_alignment_h == Alignment.CENTER  # Default
        assert layout.label_alignment_v == Alignment.CENTER  # Default

    def test_with_inset(self):
        """KeyLayout accepts custom inset."""
        layout = KeyLayout(pos=Position(x=10.0, y=20.0), width=100.0, inset=5.0)
        assert layout.inset == 5.0

    def test_with_custom_alignment(self):
        """KeyLayout accepts custom label alignment."""
        layout = KeyLayout(
            pos=Position(x=10.0, y=20.0),
            width=100.0,
            label_alignment_h=Alignment.START,
            label_alignment_v=Alignment.END,
        )
        assert layout.label_alignment_h == Alignment.START
        assert layout.label_alignment_v == Alignment.END


class TestKeymapLayoutMetrics:
    """Tests for KeymapLayoutMetrics class method and properties."""

    @pytest.fixture
    def default_config(self):
        """Create a default SkimConfig for testing."""
        return SkimConfig()

    @pytest.fixture
    def custom_config(self):
        """Create a custom SkimConfig for testing."""
        return SkimConfig(
            output=Output(
                layout=Layout(width=1200, spacing=Spacing(margin=20, inset=30)),
                style=Style(border=Border(width=5, radius=15)),
            )
        )

    def test_from_config_returns_metrics(self, default_config):
        """from_config creates KeymapLayoutMetrics instance."""
        metrics = KeymapLayoutMetrics.from_config(default_config)
        assert isinstance(metrics, KeymapLayoutMetrics)

    def test_margin_from_config(self, default_config, custom_config):
        """margin is calculated from config."""
        default_metrics = KeymapLayoutMetrics.from_config(default_config)
        custom_metrics = KeymapLayoutMetrics.from_config(custom_config)

        assert default_metrics.margin == 1.0
        assert custom_metrics.margin == 20

    def test_inset_from_config(self, default_config, custom_config):
        """inset is calculated from config."""
        default_metrics = KeymapLayoutMetrics.from_config(default_config)
        custom_metrics = KeymapLayoutMetrics.from_config(custom_config)

        assert default_metrics.inset == 20  # Default inset
        assert custom_metrics.inset == 30  # Custom inset

    def test_canvas_width_from_config(self, default_config, custom_config):
        """width is calculated from config."""
        default_metrics = KeymapLayoutMetrics.from_config(default_config)
        custom_metrics = KeymapLayoutMetrics.from_config(custom_config)

        assert default_metrics.width == 800  # Default width
        assert custom_metrics.width == 1200  # Custom width

    def test_cluster_widths_positive(self, default_config):
        """Cluster widths are positive values."""
        metrics = KeymapLayoutMetrics.from_config(default_config)

        assert metrics.finger_cluster_width > 0
        assert metrics.thumb_cluster_width > 0
        assert metrics.inset > 0

    def test_positions_make_sense(self, default_config):
        """Cluster positions are within canvas bounds."""
        metrics = KeymapLayoutMetrics.from_config(default_config)

        assert metrics.start >= metrics.margin
        assert metrics.end <= metrics.width
        assert metrics.start_right_side > metrics.end_left_side


class TestKeymapLayout:
    """Tests for KeymapLayout class."""

    @pytest.fixture
    def layout(self):
        """Create a KeymapLayout instance."""
        config = SkimConfig()
        return KeymapLayout(config)

    def test_initialization(self):
        """KeymapLayout initializes with config."""
        config = SkimConfig()
        layout = KeymapLayout(config)
        assert layout.metrics is not None

    def test_left_finger_positions(self, layout):
        """left_finger_positions yields 4 positions."""
        positions = list(layout.left_finger_positions())
        assert len(positions) == 4

    def test_right_finger_positions(self, layout):
        """right_finger_positions yields 4 positions."""
        positions = list(layout.right_finger_positions())
        assert len(positions) == 4

    def test_finger_positions_are_positions(self, layout):
        """Finger positions are Position instances."""
        for pos in layout.left_finger_positions():
            assert isinstance(pos, Position)
        for pos in layout.right_finger_positions():
            assert isinstance(pos, Position)

    def test_thumb_positions_returns_tuple(self, layout):
        """thumb_positions returns tuple of two positions."""
        cluster_height = 100.0
        positions = layout.thumb_positions(cluster_height)
        assert isinstance(positions, tuple)
        assert len(positions) == 2

    def test_thumb_positions_are_positions(self, layout):
        """Thumb positions are Position instances."""
        left_pos, right_pos = layout.thumb_positions(100.0)
        assert isinstance(left_pos, Position)
        assert isinstance(right_pos, Position)

    def test_thumb_positions_symmetric(self, layout):
        """Thumb positions are at correct horizontal locations."""
        left_pos, right_pos = layout.thumb_positions(100.0)
        m = layout.metrics
        expected_left_x = m.margin + m.inset * 2 + m.side_width - m.thumb_cluster_width
        expected_right_x = m.width - (m.margin + m.inset * 2) - m.side_width
        assert abs(left_pos.x - expected_left_x) < 0.01
        assert abs(right_pos.x - expected_right_x) < 0.01

    def test_canvas_height(self, layout):
        """canvas_height returns positive value."""
        height = layout.canvas_height(finger_cluster_height=100.0, thumb_cluster_height=80.0)
        assert height > 0
        assert height > 100.0 + 80.0


class TestFingerClusterLayout:
    """Tests for FingerClusterLayout class."""

    @pytest.fixture
    def cluster_boundary(self):
        """Create a boundary for testing."""
        return Boundary(pos=Position(x=100.0, y=50.0), width=200.0)

    @pytest.fixture
    def proportions(self):
        """Create proportions for testing."""
        return FingerClusterKeyProportions(
            center_key_width_proportion=0.4,
            outer_key_width_proportion=0.25,
            inset_width_proportion=0.05,
        )

    def test_initialization(self, cluster_boundary, proportions):
        """FingerClusterLayout initializes correctly."""
        layout = FingerClusterLayout(cluster_boundary, proportions)
        assert layout.metrics is not None

    def test_metrics_has_all_keys(self, cluster_boundary, proportions):
        """Layout metrics contains all finger cluster keys."""
        layout = FingerClusterLayout(cluster_boundary, proportions)

        # Check all keys are present
        assert layout.metrics.center_key is not None
        assert layout.metrics.north_key is not None
        assert layout.metrics.east_key is not None
        assert layout.metrics.south_key is not None
        assert layout.metrics.west_key is not None
        assert layout.metrics.double_south_key is not None

    def test_metrics_are_boundaries(self, cluster_boundary, proportions):
        """All metrics values are Boundary instances."""
        layout = FingerClusterLayout(cluster_boundary, proportions)

        for key_boundary in layout.metrics:
            assert isinstance(key_boundary, Boundary)


class TestThumbClusterLayout:
    """Tests for ThumbClusterLayout class."""

    @pytest.fixture
    def cluster_boundary(self):
        """Create a bounding box for testing."""
        return BoundingBox(pos=Position(x=100.0, y=50.0), size=Size(width=200.0, height=150.0))

    @pytest.fixture
    def proportions(self):
        """Create proportions for testing."""
        return ThumbClusterKeyProportions(
            keys_width_proportion=ThumbCluster(
                down_key=0.2,
                pad_key=0.15,
                up_key=0.15,
                nail_key=0.15,
                knuckle_key=0.15,
                double_down_key=0.2,
            ),
            inset_width_proportion=0.05,
        )

    def test_initialization_left(self, cluster_boundary, proportions):
        """ThumbClusterLayout initializes for left side."""
        layout = ThumbClusterLayout(KeyboardSide.LEFT, cluster_boundary, proportions)
        assert layout.metrics is not None

    def test_initialization_right(self, cluster_boundary, proportions):
        """ThumbClusterLayout initializes for right side."""
        layout = ThumbClusterLayout(KeyboardSide.RIGHT, cluster_boundary, proportions)
        assert layout.metrics is not None

    def test_metrics_has_all_keys(self, cluster_boundary, proportions):
        """Layout metrics contains all thumb cluster keys."""
        layout = ThumbClusterLayout(KeyboardSide.LEFT, cluster_boundary, proportions)

        assert layout.metrics.down_key is not None
        assert layout.metrics.pad_key is not None
        assert layout.metrics.up_key is not None
        assert layout.metrics.nail_key is not None
        assert layout.metrics.knuckle_key is not None
        assert layout.metrics.double_down_key is not None

    def test_metrics_are_boundaries(self, cluster_boundary, proportions):
        """All metrics values are Boundary instances."""
        layout = ThumbClusterLayout(KeyboardSide.LEFT, cluster_boundary, proportions)

        for key_boundary in layout.metrics:
            assert isinstance(key_boundary, Boundary)

    def test_left_right_layouts_differ(self, cluster_boundary, proportions):
        """Left and right side layouts have different key positions."""
        left_layout = ThumbClusterLayout(KeyboardSide.LEFT, cluster_boundary, proportions)
        right_layout = ThumbClusterLayout(KeyboardSide.RIGHT, cluster_boundary, proportions)

        # Pad and nail keys should be on opposite sides
        # This is a sanity check that side affects layout
        left_pad_x = left_layout.metrics.pad_key.pos.x
        right_pad_x = right_layout.metrics.pad_key.pos.x

        # They should be different (mirrored)
        assert (
            left_pad_x != right_pad_x
            or left_layout.metrics.pad_key.width != right_layout.metrics.pad_key.width
        )
