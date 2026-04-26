# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

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
from skim.data.config import (
    Border,
    Keyboard,
    KeyboardFeatures,
    Layout,
    Output,
    SkimConfig,
    Spacing,
    Style,
)
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

        assert default_metrics.width == 1600  # Default width
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
        """Thumb cluster inner edges are equidistant from the canvas center."""
        left_pos, right_pos = layout.thumb_positions(100.0)
        m = layout.metrics
        center = m.width / 2
        left_inner_edge = left_pos.x + m.thumb_cluster_width
        right_inner_edge = right_pos.x
        assert center - left_inner_edge == pytest.approx(right_inner_edge - center)

    def test_canvas_height(self, layout):
        """canvas_height returns positive value."""
        height = layout.canvas_height(finger_cluster_height=100.0, thumb_cluster_height=80.0)
        assert height > 0
        assert height > 100.0 + 80.0

    def test_thumb_y_anchors_to_finger_cluster_bottom_regardless_of_double_south(self):
        """thumb_y leaves the same gap from the lowest finger cluster bottom in both DS/NDS.

        The thumb row is anchored to where the finger clusters actually end, so a
        keyboard with or without double_south sees the same vertical spacing between
        the visible bottom of the fingers and the top of the thumbs.
        """
        config_ds = SkimConfig(keyboard=Keyboard(features=KeyboardFeatures(double_south=True)))
        config_no_ds = SkimConfig(keyboard=Keyboard(features=KeyboardFeatures(double_south=False)))

        layout_ds = KeymapLayout(config_ds)
        layout_no_ds = KeymapLayout(config_no_ds)
        cluster_w = layout_ds.metrics.finger_cluster_width
        ds_cluster_height = cluster_w * 4.0 / 3.0
        no_ds_cluster_height = cluster_w

        _, ds_pos = layout_ds.thumb_positions(ds_cluster_height)
        _, no_ds_pos = layout_no_ds.thumb_positions(no_ds_cluster_height)

        ds_lowest_finger_bottom = (
            layout_ds.metrics.margin
            + layout_ds.metrics.inset
            + layout_ds.metrics.finger_key_size
            + ds_cluster_height
        )
        no_ds_lowest_finger_bottom = (
            layout_no_ds.metrics.margin
            + layout_no_ds.metrics.inset
            + layout_no_ds.metrics.finger_key_size
            + no_ds_cluster_height
        )

        assert ds_pos.y - ds_lowest_finger_bottom == pytest.approx(
            no_ds_pos.y - no_ds_lowest_finger_bottom
        )

    def test_thumb_central_gap_matches_finger_central_gap(self):
        """The center gap between thumbs equals the center gap between centermost fingers."""
        layout = KeymapLayout(SkimConfig())
        m = layout.metrics
        left_pos, right_pos = layout.thumb_positions(finger_cluster_height=100.0)

        thumb_center_gap = right_pos.x - (left_pos.x + m.thumb_cluster_width)

        left_index = next(layout.left_finger_positions())  # first yielded = index (innermost)
        right_index = next(layout.right_finger_positions())
        finger_center_gap = right_index.x - (left_index.x + m.finger_cluster_width)

        assert thumb_center_gap == pytest.approx(finger_center_gap)

    def test_vertical_thumb_gap_is_one_inset(self):
        """The gap between the lowest finger cluster bottom and the thumb top is one inset."""
        layout = KeymapLayout(SkimConfig())
        m = layout.metrics
        cluster_height = 100.0
        left_pos, _ = layout.thumb_positions(finger_cluster_height=cluster_height)

        lowest_finger_bottom = m.margin + m.inset + m.finger_key_size + cluster_height
        assert left_pos.y - lowest_finger_bottom == pytest.approx(m.inset)

    def test_canvas_height_leaves_one_inset_below_thumb(self):
        """Canvas extends one inset (plus margin) below the thumb cluster bottom."""
        layout = KeymapLayout(SkimConfig())
        m = layout.metrics
        cluster_height = 100.0
        thumb_height = 80.0
        _, right_pos = layout.thumb_positions(finger_cluster_height=cluster_height)
        thumb_bottom = right_pos.y + thumb_height
        canvas_h = layout.canvas_height(cluster_height, thumb_height)

        assert canvas_h - thumb_bottom == pytest.approx(m.inset + m.margin)

    def test_vertical_indicator_offset_pushes_thumbs_down(self):
        """A vertical_indicator_offset shifts thumb_y down by exactly that amount."""
        layout = KeymapLayout(SkimConfig())
        _, base_pos = layout.thumb_positions(finger_cluster_height=100.0)
        _, shifted_pos = layout.thumb_positions(
            finger_cluster_height=100.0, vertical_indicator_offset=12.5
        )
        assert shifted_pos.y - base_pos.y == pytest.approx(12.5)

    def test_horizontal_indicator_offset_keeps_left_thumb_in_place(self):
        """Left thumb stays at its base x — the canvas grows on the right edge instead."""
        layout = KeymapLayout(SkimConfig())
        base_left, _ = layout.thumb_positions(finger_cluster_height=100.0)
        shifted_left, _ = layout.thumb_positions(
            finger_cluster_height=100.0, horizontal_indicator_offset=7.5
        )
        assert shifted_left.x == pytest.approx(base_left.x)

    def test_horizontal_indicator_offset_shifts_right_thumb_by_double_offset(self):
        """Right thumb shifts by 2x the offset, mirroring the inter-side gap growth."""
        layout = KeymapLayout(SkimConfig())
        _, base_right = layout.thumb_positions(finger_cluster_height=100.0)
        _, shifted_right = layout.thumb_positions(
            finger_cluster_height=100.0, horizontal_indicator_offset=7.5
        )
        assert shifted_right.x - base_right.x == pytest.approx(15.0)

    def test_horizontal_indicator_offset_keeps_left_fingers_in_place(self):
        """Left side fingers stay at their base positions so they stay within the canvas."""
        layout = KeymapLayout(SkimConfig())
        base = list(layout.left_finger_positions())
        shifted = list(layout.left_finger_positions(horizontal_indicator_offset=7.5))
        for b, s in zip(base, shifted, strict=True):
            assert s.x == pytest.approx(b.x)
            assert s.y == pytest.approx(b.y)

    def test_horizontal_indicator_offset_shifts_right_fingers_by_double_offset(self):
        """Right side fingers shift by 2x the offset so they stay aligned with the right thumb."""
        layout = KeymapLayout(SkimConfig())
        base = list(layout.right_finger_positions())
        shifted = list(layout.right_finger_positions(horizontal_indicator_offset=7.5))
        for b, s in zip(base, shifted, strict=True):
            assert s.x - b.x == pytest.approx(15.0)
            assert s.y == pytest.approx(b.y)

    def test_canvas_width_grows_with_horizontal_indicator_offset(self):
        """canvas_width grows by 2x the offset to fit both sides shifting outward."""
        layout = KeymapLayout(SkimConfig())
        base = layout.canvas_width()
        shifted = layout.canvas_width(horizontal_indicator_offset=7.5)
        assert shifted - base == pytest.approx(15.0)

    def test_canvas_height_grows_with_vertical_indicator_offset(self):
        """canvas_height grows by the vertical offset so the thumb cluster fits."""
        layout = KeymapLayout(SkimConfig())
        base = layout.canvas_height(finger_cluster_height=100.0, thumb_cluster_height=80.0)
        shifted = layout.canvas_height(
            finger_cluster_height=100.0,
            thumb_cluster_height=80.0,
            vertical_indicator_offset=12.5,
        )
        assert shifted - base == pytest.approx(12.5)

    def test_top_indicator_offset_shifts_finger_positions_down(self):
        """top_indicator_offset reserves space above the finger clusters by shifting them down."""
        layout = KeymapLayout(SkimConfig())
        base_left = list(layout.left_finger_positions())
        shifted_left = list(layout.left_finger_positions(top_indicator_offset=8.0))
        for b, s in zip(base_left, shifted_left, strict=True):
            assert s.y - b.y == pytest.approx(8.0)
            assert s.x == pytest.approx(b.x)

        base_right = list(layout.right_finger_positions())
        shifted_right = list(layout.right_finger_positions(top_indicator_offset=8.0))
        for b, s in zip(base_right, shifted_right, strict=True):
            assert s.y - b.y == pytest.approx(8.0)
            assert s.x == pytest.approx(b.x)

    def test_top_indicator_offset_shifts_thumb_down(self):
        """top_indicator_offset shifts thumb_y down too — fingers and thumb move together."""
        layout = KeymapLayout(SkimConfig())
        base_left, _ = layout.thumb_positions(finger_cluster_height=100.0)
        shifted_left, _ = layout.thumb_positions(
            finger_cluster_height=100.0, top_indicator_offset=8.0
        )
        assert shifted_left.y - base_left.y == pytest.approx(8.0)

    def test_canvas_height_grows_with_top_indicator_offset(self):
        """canvas_height grows by the top_indicator_offset to fit the shifted content."""
        layout = KeymapLayout(SkimConfig())
        base = layout.canvas_height(finger_cluster_height=100.0, thumb_cluster_height=80.0)
        shifted = layout.canvas_height(
            finger_cluster_height=100.0,
            thumb_cluster_height=80.0,
            top_indicator_offset=8.0,
        )
        assert shifted - base == pytest.approx(8.0)


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
