# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.application.render.layout module.

Tests cover the small geometry value types (``Position``, ``Size``,
``Boundary``, ``BoundingBox``) and the ``KeymapLayoutMetrics`` bundle
that derives canvas-relative dimensions from a :class:`SkimConfig`.
"""

import pytest

from skim.application.render.layout import (
    Boundary,
    BoundingBox,
    KeymapLayoutMetrics,
    Position,
    Size,
)
from skim.data.config import (
    Border,
    Layout,
    Output,
    SkimConfig,
    Spacing,
    Style,
)


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

        # Default config leaves ``Spacing.inset`` unset, so the
        # canonical resolution falls back to the width-proportional
        # default ``doc_width * 40 / 1600`` — i.e. 40 at width 1600.
        assert default_metrics.inset == 40
        assert custom_metrics.inset == 30

    def test_canvas_width_from_config(self, default_config, custom_config):
        """width is calculated from config."""
        default_metrics = KeymapLayoutMetrics.from_config(default_config)
        custom_metrics = KeymapLayoutMetrics.from_config(custom_config)

        assert default_metrics.width == 1600
        assert custom_metrics.width == 1200

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
