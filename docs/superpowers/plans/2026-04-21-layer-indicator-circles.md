# Layer Indicator Circles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add colored circle indicators next to layer-switching keys showing the target layer number, with connector lines linking circles to keys.

**Architecture:** A new `indicators.py` module in the render package contains `LayerIndicator` (single circle + connector) and `LayerIndicatorOverlay` (orchestrates all indicators for a cluster). Indicators are drawn as a separate pass after keys in each cluster's `build()` method, controlled by a `show_layer_indicators` config flag.

**Tech Stack:** Python 3.10+, drawsvg, Pydantic v2, pytest

**Spec:** `docs/superpowers/specs/2026-04-21-layer-indicator-circles-design.md`

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `src/skim/data/config.py:590` | Add `show_layer_indicators: bool = True` to `Style` model |
| Modify | `src/skim/application/render/context.py:22-97` | Add `show_layer_indicators` to `RenderContext` and `ClusterRenderContext.from_render_context()` |
| Create | `src/skim/application/render/indicators.py` | `LayerIndicator` and `LayerIndicatorOverlay` classes |
| Modify | `src/skim/application/render/components.py:281-291,437-448` | Call `LayerIndicatorOverlay` from `build()` methods |
| Modify | `src/skim/application/render/__init__.py:41-48` | Pass `show_layer_indicators` when constructing `RenderContext` |
| Create | `tests/unit/application/render/test_indicators.py` | Unit tests for indicator rendering and placement |
| Modify | `tests/unit/application/render/test_context.py` | Tests for the new `show_layer_indicators` field |
| Modify | `tests/unit/data/test_config.py` | Test for `Style.show_layer_indicators` default and parsing |

---

### Task 1: Add `show_layer_indicators` to `Style` config model

**Files:**
- Modify: `src/skim/data/config.py:590`
- Test: `tests/unit/data/test_config.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/data/test_config.py`:

```python
class TestStyleShowLayerIndicators:
    """Tests for Style.show_layer_indicators field."""

    def test_default_is_true(self):
        """show_layer_indicators defaults to True."""
        style = Style()
        assert style.show_layer_indicators is True

    def test_can_be_set_to_false(self):
        """show_layer_indicators can be explicitly set to False."""
        style = Style(show_layer_indicators=False)
        assert style.show_layer_indicators is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/data/test_config.py::TestStyleShowLayerIndicators -v`
Expected: FAIL with `TypeError` — `show_layer_indicators` is not a recognized field.

- [ ] **Step 3: Write minimal implementation**

In `src/skim/data/config.py`, add after line 590 (`use_system_fonts: bool = False`):

```python
    show_layer_indicators: bool = True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/data/test_config.py::TestStyleShowLayerIndicators -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/skim/data/config.py tests/unit/data/test_config.py
git commit -m "feat(config): add show_layer_indicators to Style model"
```

---

### Task 2: Add `show_layer_indicators` to `RenderContext`

**Files:**
- Modify: `src/skim/application/render/context.py:22-97`
- Test: `tests/unit/application/render/test_context.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/application/render/test_context.py`:

```python
class TestRenderContextShowLayerIndicators:
    """Tests for show_layer_indicators in RenderContext."""

    def test_default_is_false(self, sample_palette):
        """show_layer_indicators defaults to False."""
        ctx = RenderContext(
            palette=sample_palette,
            layer_index=0,
            has_double_south=True,
            use_layer_colors_on_keys=True,
            hold_symbol_position=SplitSidePosition.OUTWARD,
        )
        assert ctx.show_layer_indicators is False

    def test_can_be_set_to_true(self, sample_palette):
        """show_layer_indicators can be set to True."""
        ctx = RenderContext(
            palette=sample_palette,
            layer_index=0,
            has_double_south=True,
            use_layer_colors_on_keys=True,
            hold_symbol_position=SplitSidePosition.OUTWARD,
            show_layer_indicators=True,
        )
        assert ctx.show_layer_indicators is True

    def test_cluster_context_propagates(self, sample_palette):
        """ClusterRenderContext.from_render_context propagates show_layer_indicators."""
        base = RenderContext(
            palette=sample_palette,
            layer_index=0,
            has_double_south=True,
            use_layer_colors_on_keys=True,
            hold_symbol_position=SplitSidePosition.OUTWARD,
            show_layer_indicators=True,
        )
        cluster_ctx = ClusterRenderContext.from_render_context(base, KeyboardSide.LEFT)
        assert cluster_ctx.show_layer_indicators is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/application/render/test_context.py::TestRenderContextShowLayerIndicators -v`
Expected: FAIL — `show_layer_indicators` is not a field on `RenderContext`.

- [ ] **Step 3: Write minimal implementation**

In `src/skim/application/render/context.py`, add to `RenderContext` after line 34 (`use_system_fonts: bool = False`):

```python
    show_layer_indicators: bool = False
```

In `ClusterRenderContext.from_render_context()`, add to the `cls()` call at line 89-97:

```python
        return cls(
            palette=render_context.palette,
            layer_index=render_context.layer_index,
            has_double_south=render_context.has_double_south,
            use_layer_colors_on_keys=render_context.use_layer_colors_on_keys,
            hold_symbol_position=render_context.hold_symbol_position,
            use_system_fonts=render_context.use_system_fonts,
            show_layer_indicators=render_context.show_layer_indicators,
            side=side,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/application/render/test_context.py::TestRenderContextShowLayerIndicators -v`
Expected: PASS

- [ ] **Step 5: Wire up in `_draw_layer`**

In `src/skim/application/render/__init__.py`, update the `RenderContext` constructor at lines 41-48:

```python
    render_context = RenderContext(
        palette=config.output.style.palette,
        layer_index=layer_idx,
        has_double_south=config.keyboard.features.double_south,
        use_layer_colors_on_keys=config.output.style.use_layer_colors_on_keys,
        hold_symbol_position=config.output.style.hold_symbol_position,
        use_system_fonts=use_system_fonts,
        show_layer_indicators=config.output.style.show_layer_indicators,
    )
```

- [ ] **Step 6: Run full test suite for context**

Run: `uv run pytest tests/unit/application/render/test_context.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/skim/application/render/context.py src/skim/application/render/__init__.py tests/unit/application/render/test_context.py
git commit -m "feat(render): add show_layer_indicators to RenderContext"
```

---

### Task 3: Implement `LayerIndicator` (single circle + connector)

**Files:**
- Create: `src/skim/application/render/indicators.py`
- Create: `tests/unit/application/render/test_indicators.py`

- [ ] **Step 1: Write failing tests for `LayerIndicator`**

Create `tests/unit/application/render/test_indicators.py`:

```python
# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.application.render.indicators module."""

import pytest

from skim.application.render.indicators import ConnectorType, LayerIndicator, OffsetDirection
from skim.data.config import LayerColor, Palette


@pytest.fixture
def sample_palette():
    """Create a sample palette with 3 layers for testing."""
    return Palette(
        layers=(
            LayerColor(
                base_color="#FF0000",
                color_index=2,
                gradient=("#110000", "#220000", "#330000", "#440000", "#550000", "#660000"),
            ),
            LayerColor(
                base_color="#00FF00",
                color_index=2,
                gradient=("#001100", "#002200", "#003300", "#004400", "#005500", "#006600"),
            ),
            LayerColor(
                base_color="#0000FF",
                color_index=2,
                gradient=("#000011", "#000022", "#000033", "#000044", "#000055", "#000066"),
            ),
        ),
        neutral_color="#808080",
        key_label_color="#FFFFFF",
    )


class TestLayerIndicator:
    """Tests for LayerIndicator rendering."""

    def test_creates_svg_group(self, sample_palette):
        """LayerIndicator produces a drawsvg Group."""
        indicator = LayerIndicator(
            key_x=100,
            key_y=30,
            key_width=55,
            key_height=55,
            target_layer=1,
            palette=sample_palette,
            circle_diameter=27.5,
            gap=10,
            offset_direction=OffsetDirection.ABOVE,
            connector_type=ConnectorType.VERTICAL,
        )
        svg = indicator.build()
        svg_str = svg.as_svg()
        # Should contain a circle (the indicator)
        assert "<circle" in svg_str
        # Should contain a line (the connector)
        assert "<line" in svg_str
        # Should contain text (the layer number)
        assert ">1<" in svg_str

    def test_fill_color_uses_target_layer_base_color(self, sample_palette):
        """Circle fill uses the target layer's base_color."""
        indicator = LayerIndicator(
            key_x=100,
            key_y=30,
            key_width=55,
            key_height=55,
            target_layer=1,
            palette=sample_palette,
            circle_diameter=27.5,
            gap=10,
            offset_direction=OffsetDirection.ABOVE,
            connector_type=ConnectorType.VERTICAL,
        )
        svg_str = indicator.build().as_svg()
        # Layer 1 base_color is #00FF00
        assert 'fill="#00FF00"' in svg_str

    def test_stroke_color_uses_gradient_1(self, sample_palette):
        """Circle stroke uses gradient[1] of the target layer."""
        indicator = LayerIndicator(
            key_x=100,
            key_y=30,
            key_width=55,
            key_height=55,
            target_layer=1,
            palette=sample_palette,
            circle_diameter=27.5,
            gap=10,
            offset_direction=OffsetDirection.ABOVE,
            connector_type=ConnectorType.VERTICAL,
        )
        svg_str = indicator.build().as_svg()
        # Layer 1 gradient[1] is #002200
        assert 'stroke="#002200"' in svg_str

    def test_above_offset_places_circle_above_key(self, sample_palette):
        """ABOVE offset places circle center above the key top edge."""
        indicator = LayerIndicator(
            key_x=100,
            key_y=30,
            key_width=55,
            key_height=55,
            target_layer=0,
            palette=sample_palette,
            circle_diameter=28,
            gap=10,
            offset_direction=OffsetDirection.ABOVE,
            connector_type=ConnectorType.VERTICAL,
        )
        # Circle center should be at:
        # x = key_x + key_width/2 = 127.5
        # y = key_y - gap - radius = 30 - 10 - 14 = 6
        assert indicator.circle_center_x == pytest.approx(127.5)
        assert indicator.circle_center_y == pytest.approx(6)

    def test_left_offset_places_circle_left_of_key(self, sample_palette):
        """LEFT offset places circle center to the left of the key."""
        indicator = LayerIndicator(
            key_x=100,
            key_y=155,
            key_width=55,
            key_height=55,
            target_layer=0,
            palette=sample_palette,
            circle_diameter=28,
            gap=10,
            offset_direction=OffsetDirection.LEFT,
            connector_type=ConnectorType.HORIZONTAL,
        )
        # Circle center should be at:
        # x = key_x - gap - radius = 100 - 10 - 14 = 76
        # y = key_y + key_height/2 = 182.5
        assert indicator.circle_center_x == pytest.approx(76)
        assert indicator.circle_center_y == pytest.approx(182.5)

    def test_right_offset_places_circle_right_of_key(self, sample_palette):
        """RIGHT offset places circle center to the right of the key."""
        indicator = LayerIndicator(
            key_x=100,
            key_y=155,
            key_width=55,
            key_height=55,
            target_layer=0,
            palette=sample_palette,
            circle_diameter=28,
            gap=10,
            offset_direction=OffsetDirection.RIGHT,
            connector_type=ConnectorType.HORIZONTAL,
        )
        # x = key_x + key_width + gap + radius = 100 + 55 + 10 + 14 = 179
        # y = key_y + key_height/2 = 182.5
        assert indicator.circle_center_x == pytest.approx(179)
        assert indicator.circle_center_y == pytest.approx(182.5)

    def test_diagonal_right_offset(self, sample_palette):
        """DIAGONAL_RIGHT places circle at 45-deg below-right of key center."""
        indicator = LayerIndicator(
            key_x=99,
            key_y=89,
            key_width=56,
            key_height=56,
            target_layer=0,
            palette=sample_palette,
            circle_diameter=28,
            gap=10,
            offset_direction=OffsetDirection.DIAGONAL_RIGHT,
            connector_type=ConnectorType.DIAGONAL,
        )
        # Key center = (127, 117). Diagonal at 45-deg:
        # The circle is placed along 45-deg from key center, far enough to
        # clear adjacent keys. The exact position depends on implementation.
        # We verify the 45-deg relationship: dx == dy from key center.
        key_cx = 99 + 56 / 2
        key_cy = 89 + 56 / 2
        dx = indicator.circle_center_x - key_cx
        dy = indicator.circle_center_y - key_cy
        assert dx == pytest.approx(dy)
        assert dx > 0  # right and down

    def test_out_of_range_layer_still_renders(self, sample_palette):
        """Indicator for a layer index beyond palette falls back gracefully."""
        indicator = LayerIndicator(
            key_x=100,
            key_y=30,
            key_width=55,
            key_height=55,
            target_layer=99,
            palette=sample_palette,
            circle_diameter=28,
            gap=10,
            offset_direction=OffsetDirection.ABOVE,
            connector_type=ConnectorType.VERTICAL,
        )
        # Should not raise; renders with some fallback color
        svg_str = indicator.build().as_svg()
        assert "<circle" in svg_str
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/application/render/test_indicators.py::TestLayerIndicator -v`
Expected: FAIL — `indicators` module does not exist.

- [ ] **Step 3: Implement `LayerIndicator`**

Create `src/skim/application/render/indicators.py`:

```python
# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Layer indicator rendering for keyboard visualization.

This module provides SVG components for rendering colored circle indicators
next to layer-switching keys, showing the target layer number with a
connector line linking the circle to its key.
"""

import math
from enum import Enum

import drawsvg as draw

from skim.data.config import Palette


class OffsetDirection(Enum):
    """Direction to offset the indicator circle from its key."""

    ABOVE = "above"
    LEFT = "left"
    RIGHT = "right"
    DIAGONAL_LEFT = "diagonal_left"
    DIAGONAL_RIGHT = "diagonal_right"


class ConnectorType(Enum):
    """Type of connector line between circle and key."""

    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"
    DIAGONAL = "diagonal"


_CONNECTOR_WIDTH = 2
_CIRCLE_STROKE_WIDTH = 2
_ENDPOINT_RADIUS = 2
_ENDPOINT_INSET = 4
_FALLBACK_FILL = "#808080"
_FALLBACK_STROKE = "#606060"


class LayerIndicator:
    """Renders a single layer indicator circle with connector line.

    The indicator consists of:
    - A filled circle with the target layer's base color
    - A 2px outline using the target layer's gradient[1]
    - A 0-indexed layer number label in white
    - A connector line from the circle edge to the key
    - A 4px endpoint circle drawn 4px inside the key boundary
    """

    def __init__(
        self,
        key_x: float,
        key_y: float,
        key_width: float,
        key_height: float,
        target_layer: int,
        palette: Palette,
        circle_diameter: float,
        gap: float,
        offset_direction: OffsetDirection,
        connector_type: ConnectorType,
    ) -> None:
        self._key_x = key_x
        self._key_y = key_y
        self._key_width = key_width
        self._key_height = key_height
        self._target_layer = target_layer
        self._palette = palette
        self._radius = circle_diameter / 2
        self._gap = gap
        self._offset_direction = offset_direction
        self._connector_type = connector_type

        # Resolve colors
        if 0 <= target_layer < len(palette.layers):
            lc = palette.layers[target_layer]
            self._fill_color = lc.base_color
            self._stroke_color = lc[1]
        else:
            self._fill_color = _FALLBACK_FILL
            self._stroke_color = _FALLBACK_STROKE

        # Compute positions
        self._compute_circle_center()
        self._compute_connector()

    @property
    def circle_center_x(self) -> float:
        return self._cx

    @property
    def circle_center_y(self) -> float:
        return self._cy

    def _compute_circle_center(self) -> None:
        key_cx = self._key_x + self._key_width / 2
        key_cy = self._key_y + self._key_height / 2
        r = self._radius

        match self._offset_direction:
            case OffsetDirection.ABOVE:
                self._cx = key_cx
                self._cy = self._key_y - self._gap - r
            case OffsetDirection.LEFT:
                self._cx = self._key_x - self._gap - r
                self._cy = key_cy
            case OffsetDirection.RIGHT:
                self._cx = self._key_x + self._key_width + self._gap + r
                self._cy = key_cy
            case OffsetDirection.DIAGONAL_RIGHT:
                # 45-deg from key center toward bottom-right
                dist = self._key_width / 2 + self._gap + r
                offset = dist / math.sqrt(2)
                self._cx = key_cx + offset
                self._cy = key_cy + offset
            case OffsetDirection.DIAGONAL_LEFT:
                # 45-deg from key center toward bottom-left
                dist = self._key_width / 2 + self._gap + r
                offset = dist / math.sqrt(2)
                self._cx = key_cx - offset
                self._cy = key_cy + offset

    def _compute_connector(self) -> None:
        """Compute connector line start (circle edge) and end (inside key)."""
        key_cx = self._key_x + self._key_width / 2
        key_cy = self._key_y + self._key_height / 2

        match self._connector_type:
            case ConnectorType.VERTICAL:
                # Line from circle bottom edge to key top edge
                self._line_x1 = self._cx
                self._line_y1 = self._cy + self._radius
                self._line_x2 = self._cx
                self._line_y2 = self._key_y
                # Endpoint inside key
                self._ep_x = self._cx
                self._ep_y = self._key_y + _ENDPOINT_INSET
            case ConnectorType.HORIZONTAL:
                if self._offset_direction == OffsetDirection.LEFT:
                    self._line_x1 = self._cx + self._radius
                    self._line_y1 = self._cy
                    self._line_x2 = self._key_x
                    self._line_y2 = self._cy
                    self._ep_x = self._key_x + _ENDPOINT_INSET
                    self._ep_y = self._cy
                else:  # RIGHT
                    self._line_x1 = self._cx - self._radius
                    self._line_y1 = self._cy
                    self._line_x2 = self._key_x + self._key_width
                    self._line_y2 = self._cy
                    self._ep_x = self._key_x + self._key_width - _ENDPOINT_INSET
                    self._ep_y = self._cy
            case ConnectorType.DIAGONAL:
                # 45-deg line from circle edge to key interior
                cos45 = math.cos(math.pi / 4)
                sin45 = math.sin(math.pi / 4)
                if self._offset_direction == OffsetDirection.DIAGONAL_RIGHT:
                    self._line_x1 = self._cx - self._radius * cos45
                    self._line_y1 = self._cy - self._radius * sin45
                    self._line_x2 = key_cx + _ENDPOINT_INSET * cos45
                    self._line_y2 = key_cy + _ENDPOINT_INSET * sin45
                else:  # DIAGONAL_LEFT
                    self._line_x1 = self._cx + self._radius * cos45
                    self._line_y1 = self._cy - self._radius * sin45
                    self._line_x2 = key_cx - _ENDPOINT_INSET * cos45
                    self._line_y2 = key_cy + _ENDPOINT_INSET * sin45
                self._ep_x = self._line_x2
                self._ep_y = self._line_y2

    def build(self) -> draw.Group:
        """Build the SVG group containing the indicator."""
        g = draw.Group()

        # Connector line
        g.append(draw.Line(
            self._line_x1, self._line_y1,
            self._line_x2, self._line_y2,
            stroke=self._stroke_color,
            stroke_width=_CONNECTOR_WIDTH,
        ))

        # Endpoint circle inside key
        g.append(draw.Circle(
            self._ep_x, self._ep_y,
            _ENDPOINT_RADIUS,
            fill=self._stroke_color,
        ))

        # Indicator circle
        g.append(draw.Circle(
            self._cx, self._cy,
            self._radius,
            fill=self._fill_color,
            stroke=self._stroke_color,
            stroke_width=_CIRCLE_STROKE_WIDTH,
        ))

        # Layer number label
        g.append(draw.Text(
            str(self._target_layer),
            font_size=self._radius * 1.2,
            x=self._cx,
            y=self._cy,
            fill="white",
            text_anchor="middle",
            dominant_baseline="central",
            font_family="Roboto, sans-serif",
            font_weight="bold",
        ))

        return g
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/application/render/test_indicators.py::TestLayerIndicator -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/skim/application/render/indicators.py tests/unit/application/render/test_indicators.py
git commit -m "feat(render): add LayerIndicator component"
```

---

### Task 4: Implement `LayerIndicatorOverlay` for finger clusters

**Files:**
- Modify: `src/skim/application/render/indicators.py`
- Modify: `tests/unit/application/render/test_indicators.py`

- [ ] **Step 1: Write failing tests for finger cluster overlay**

Add to `tests/unit/application/render/test_indicators.py`:

```python
from skim.application.render.indicators import (
    ConnectorType,
    LayerIndicator,
    LayerIndicatorOverlay,
    OffsetDirection,
)
from skim.application.render.layout import Boundary, Position
from skim.data.keyboard import FingerCluster
from skim.domain.domain_types import KeyboardSide, SvalboardTargetKey


def _make_finger_cluster_keys(layer_switches):
    """Helper: create FingerCluster with given layer_switch values (None = no switch)."""
    names = ["center", "north", "east", "south", "west", "double_south"]
    return FingerCluster(**{
        f"{n}_key": SvalboardTargetKey(label=n.upper(), layer_switch=ls)
        for n, ls in zip(names, layer_switches)
    })


def _make_finger_cluster_metrics():
    """Helper: create a simple FingerCluster of Boundary for layout metrics."""
    return FingerCluster(
        center_key=Boundary(width=50, pos=Position(x=75, y=60)),
        north_key=Boundary(width=55, pos=Position(x=72, y=0)),
        east_key=Boundary(width=55, pos=Position(x=135, y=55)),
        south_key=Boundary(width=55, pos=Position(x=72, y=120)),
        west_key=Boundary(width=55, pos=Position(x=10, y=55)),
        double_south_key=Boundary(width=55, pos=Position(x=72, y=185)),
    )


class TestFingerClusterOverlay:
    """Tests for LayerIndicatorOverlay with finger clusters."""

    def test_skips_keys_without_layer_switch(self, sample_palette):
        """Keys with layer_switch=None produce no indicators."""
        keys = _make_finger_cluster_keys([None, None, None, None, None, None])
        metrics = _make_finger_cluster_metrics()
        overlay = LayerIndicatorOverlay.for_finger_cluster(
            keys=keys,
            metrics=metrics,
            side=KeyboardSide.LEFT,
            palette=sample_palette,
            circle_diameter=28,
            gap=10,
            has_double_south=True,
        )
        indicators = overlay.build()
        assert len(indicators) == 0

    def test_north_key_gets_above_indicator(self, sample_palette):
        """North key with layer_switch produces an ABOVE indicator."""
        keys = _make_finger_cluster_keys([None, 2, None, None, None, None])
        metrics = _make_finger_cluster_metrics()
        overlay = LayerIndicatorOverlay.for_finger_cluster(
            keys=keys,
            metrics=metrics,
            side=KeyboardSide.LEFT,
            palette=sample_palette,
            circle_diameter=28,
            gap=10,
            has_double_south=True,
        )
        indicators = overlay.build()
        assert len(indicators) == 1

    def test_south_left_hand_gets_left_indicator(self, sample_palette):
        """South key on left hand gets LEFT offset."""
        keys = _make_finger_cluster_keys([None, None, None, 1, None, None])
        metrics = _make_finger_cluster_metrics()
        overlay = LayerIndicatorOverlay.for_finger_cluster(
            keys=keys,
            metrics=metrics,
            side=KeyboardSide.LEFT,
            palette=sample_palette,
            circle_diameter=28,
            gap=10,
            has_double_south=True,
        )
        indicators = overlay.build()
        assert len(indicators) == 1

    def test_south_right_hand_gets_right_indicator(self, sample_palette):
        """South key on right hand gets RIGHT offset."""
        keys = _make_finger_cluster_keys([None, None, None, 1, None, None])
        metrics = _make_finger_cluster_metrics()
        overlay = LayerIndicatorOverlay.for_finger_cluster(
            keys=keys,
            metrics=metrics,
            side=KeyboardSide.RIGHT,
            palette=sample_palette,
            circle_diameter=28,
            gap=10,
            has_double_south=True,
        )
        indicators = overlay.build()
        assert len(indicators) == 1

    def test_center_left_hand_gets_diagonal_right(self, sample_palette):
        """Center key on left hand gets DIAGONAL_RIGHT offset."""
        keys = _make_finger_cluster_keys([1, None, None, None, None, None])
        metrics = _make_finger_cluster_metrics()
        overlay = LayerIndicatorOverlay.for_finger_cluster(
            keys=keys,
            metrics=metrics,
            side=KeyboardSide.LEFT,
            palette=sample_palette,
            circle_diameter=28,
            gap=10,
            has_double_south=True,
        )
        indicators = overlay.build()
        assert len(indicators) == 1

    def test_center_right_hand_gets_diagonal_left(self, sample_palette):
        """Center key on right hand gets DIAGONAL_LEFT offset."""
        keys = _make_finger_cluster_keys([1, None, None, None, None, None])
        metrics = _make_finger_cluster_metrics()
        overlay = LayerIndicatorOverlay.for_finger_cluster(
            keys=keys,
            metrics=metrics,
            side=KeyboardSide.RIGHT,
            palette=sample_palette,
            circle_diameter=28,
            gap=10,
            has_double_south=True,
        )
        indicators = overlay.build()
        assert len(indicators) == 1

    def test_double_south_skipped_when_no_double_south(self, sample_palette):
        """Double-south key indicator is skipped when has_double_south is False."""
        keys = _make_finger_cluster_keys([None, None, None, None, None, 2])
        metrics = _make_finger_cluster_metrics()
        overlay = LayerIndicatorOverlay.for_finger_cluster(
            keys=keys,
            metrics=metrics,
            side=KeyboardSide.LEFT,
            palette=sample_palette,
            circle_diameter=28,
            gap=10,
            has_double_south=False,
        )
        indicators = overlay.build()
        assert len(indicators) == 0

    def test_multiple_keys_produce_multiple_indicators(self, sample_palette):
        """Multiple keys with layer_switch produce that many indicators."""
        keys = _make_finger_cluster_keys([1, 2, None, 0, None, None])
        metrics = _make_finger_cluster_metrics()
        overlay = LayerIndicatorOverlay.for_finger_cluster(
            keys=keys,
            metrics=metrics,
            side=KeyboardSide.LEFT,
            palette=sample_palette,
            circle_diameter=28,
            gap=10,
            has_double_south=True,
        )
        indicators = overlay.build()
        assert len(indicators) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/application/render/test_indicators.py::TestFingerClusterOverlay -v`
Expected: FAIL — `LayerIndicatorOverlay` does not exist.

- [ ] **Step 3: Implement `LayerIndicatorOverlay.for_finger_cluster`**

Add to `src/skim/application/render/indicators.py`:

```python
from skim.data.keyboard import FingerCluster, ThumbCluster
from skim.domain.domain_types import KeyboardSide, SvalboardTargetKey

from .layout import Boundary


def _finger_cluster_offset(
    key_name: str, side: KeyboardSide
) -> tuple[OffsetDirection, ConnectorType]:
    """Get the offset direction and connector type for a finger cluster key."""
    match key_name:
        case "north_key" | "east_key" | "west_key":
            return OffsetDirection.ABOVE, ConnectorType.VERTICAL
        case "center_key":
            if side == KeyboardSide.LEFT:
                return OffsetDirection.DIAGONAL_RIGHT, ConnectorType.DIAGONAL
            return OffsetDirection.DIAGONAL_LEFT, ConnectorType.DIAGONAL
        case "south_key" | "double_south_key":
            if side == KeyboardSide.LEFT:
                return OffsetDirection.LEFT, ConnectorType.HORIZONTAL
            return OffsetDirection.RIGHT, ConnectorType.HORIZONTAL
        case _:
            return OffsetDirection.ABOVE, ConnectorType.VERTICAL


_FINGER_KEY_NAMES = [
    "center_key", "north_key", "east_key", "south_key", "west_key", "double_south_key"
]


class LayerIndicatorOverlay:
    """Orchestrates drawing layer indicators for an entire cluster."""

    def __init__(self, indicators: list[LayerIndicator]) -> None:
        self._indicators = indicators

    def build(self) -> list[draw.Group]:
        """Build all indicator SVG groups."""
        return [ind.build() for ind in self._indicators]

    @classmethod
    def for_finger_cluster(
        cls,
        keys: FingerCluster[SvalboardTargetKey],
        metrics: FingerCluster[Boundary],
        side: KeyboardSide,
        palette: Palette,
        circle_diameter: float,
        gap: float,
        has_double_south: bool,
    ) -> "LayerIndicatorOverlay":
        """Create an overlay for a finger cluster."""
        indicators: list[LayerIndicator] = []

        for key_name in _FINGER_KEY_NAMES:
            if key_name == "double_south_key" and not has_double_south:
                continue

            key: SvalboardTargetKey = getattr(keys, key_name)
            if key.layer_switch is None:
                continue

            layout: Boundary = getattr(metrics, key_name)
            offset_dir, conn_type = _finger_cluster_offset(key_name, side)

            indicators.append(LayerIndicator(
                key_x=layout.pos.x,
                key_y=layout.pos.y,
                key_width=layout.width,
                key_height=layout.width,  # finger cluster keys are square
                target_layer=key.layer_switch,
                palette=palette,
                circle_diameter=circle_diameter,
                gap=gap,
                offset_direction=offset_dir,
                connector_type=conn_type,
            ))

        return cls(indicators)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/application/render/test_indicators.py::TestFingerClusterOverlay -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/skim/application/render/indicators.py tests/unit/application/render/test_indicators.py
git commit -m "feat(render): add LayerIndicatorOverlay for finger clusters"
```

---

### Task 5: Implement `LayerIndicatorOverlay` for thumb clusters

**Files:**
- Modify: `src/skim/application/render/indicators.py`
- Modify: `tests/unit/application/render/test_indicators.py`

- [ ] **Step 1: Write failing tests for thumb cluster overlay**

Add to `tests/unit/application/render/test_indicators.py`:

```python
def _make_thumb_cluster_keys(layer_switches):
    """Helper: create ThumbCluster with given layer_switch values."""
    names = ["down", "pad", "up", "nail", "knuckle", "double_down"]
    return ThumbCluster(**{
        f"{n}_key": SvalboardTargetKey(label=n.upper(), layer_switch=ls)
        for n, ls in zip(names, layer_switches)
    })


def _make_thumb_cluster_metrics():
    """Helper: create ThumbCluster of Boundary for layout metrics."""
    return ThumbCluster(
        down_key=Boundary(width=40, pos=Position(x=130, y=0)),
        pad_key=Boundary(width=110, pos=Position(x=10, y=10)),
        up_key=Boundary(width=100, pos=Position(x=30, y=80)),
        nail_key=Boundary(width=110, pos=Position(x=180, y=10)),
        knuckle_key=Boundary(width=100, pos=Position(x=180, y=80)),
        double_down_key=Boundary(width=34, pos=Position(x=133, y=20)),
    )


class TestThumbClusterOverlay:
    """Tests for LayerIndicatorOverlay with thumb clusters."""

    def test_skips_keys_without_layer_switch(self, sample_palette):
        """Keys with layer_switch=None produce no indicators."""
        keys = _make_thumb_cluster_keys([None, None, None, None, None, None])
        metrics = _make_thumb_cluster_metrics()
        overlay = LayerIndicatorOverlay.for_thumb_cluster(
            keys=keys,
            metrics=metrics,
            down_key_metrics=metrics.down_key,
            side=KeyboardSide.LEFT,
            palette=sample_palette,
            circle_diameter=28,
            gap=10,
        )
        indicators = overlay.build()
        assert len(indicators) == 0

    def test_pad_left_hand_gets_left_indicator(self, sample_palette):
        """Pad key on left hand gets LEFT offset (outward)."""
        keys = _make_thumb_cluster_keys([None, 1, None, None, None, None])
        metrics = _make_thumb_cluster_metrics()
        overlay = LayerIndicatorOverlay.for_thumb_cluster(
            keys=keys,
            metrics=metrics,
            down_key_metrics=metrics.down_key,
            side=KeyboardSide.LEFT,
            palette=sample_palette,
            circle_diameter=28,
            gap=10,
        )
        indicators = overlay.build()
        assert len(indicators) == 1

    def test_pad_right_hand_gets_right_indicator(self, sample_palette):
        """Pad key on right hand gets RIGHT offset (outward)."""
        keys = _make_thumb_cluster_keys([None, 1, None, None, None, None])
        metrics = _make_thumb_cluster_metrics()
        overlay = LayerIndicatorOverlay.for_thumb_cluster(
            keys=keys,
            metrics=metrics,
            down_key_metrics=metrics.down_key,
            side=KeyboardSide.RIGHT,
            palette=sample_palette,
            circle_diameter=28,
            gap=10,
        )
        indicators = overlay.build()
        assert len(indicators) == 1

    def test_double_down_gets_above_indicator(self, sample_palette):
        """Double-down key always gets ABOVE offset (gap measured to Down key)."""
        keys = _make_thumb_cluster_keys([None, None, None, None, None, 2])
        metrics = _make_thumb_cluster_metrics()
        overlay = LayerIndicatorOverlay.for_thumb_cluster(
            keys=keys,
            metrics=metrics,
            down_key_metrics=metrics.down_key,
            side=KeyboardSide.LEFT,
            palette=sample_palette,
            circle_diameter=28,
            gap=10,
        )
        indicators = overlay.build()
        assert len(indicators) == 1

    def test_multiple_thumb_keys(self, sample_palette):
        """Multiple thumb keys with layer_switch produce that many indicators."""
        keys = _make_thumb_cluster_keys([1, 2, 0, None, None, None])
        metrics = _make_thumb_cluster_metrics()
        overlay = LayerIndicatorOverlay.for_thumb_cluster(
            keys=keys,
            metrics=metrics,
            down_key_metrics=metrics.down_key,
            side=KeyboardSide.LEFT,
            palette=sample_palette,
            circle_diameter=28,
            gap=10,
        )
        indicators = overlay.build()
        assert len(indicators) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/application/render/test_indicators.py::TestThumbClusterOverlay -v`
Expected: FAIL — `for_thumb_cluster` does not exist.

- [ ] **Step 3: Implement `LayerIndicatorOverlay.for_thumb_cluster`**

Add to `src/skim/application/render/indicators.py`:

```python
def _thumb_cluster_offset(
    key_name: str, side: KeyboardSide
) -> tuple[OffsetDirection, ConnectorType]:
    """Get the offset direction and connector type for a thumb cluster key."""
    is_left = side == KeyboardSide.LEFT
    outward = OffsetDirection.LEFT if is_left else OffsetDirection.RIGHT
    inward = OffsetDirection.RIGHT if is_left else OffsetDirection.LEFT

    match key_name:
        case "pad_key" | "up_key" | "down_key":
            return outward, ConnectorType.HORIZONTAL
        case "nail_key" | "knuckle_key":
            return inward, ConnectorType.HORIZONTAL
        case "double_down_key":
            return OffsetDirection.ABOVE, ConnectorType.VERTICAL
        case _:
            return outward, ConnectorType.HORIZONTAL


_THUMB_KEY_NAMES = [
    "down_key", "pad_key", "up_key", "nail_key", "knuckle_key", "double_down_key"
]
```

And add to the `LayerIndicatorOverlay` class:

```python
    @classmethod
    def for_thumb_cluster(
        cls,
        keys: ThumbCluster[SvalboardTargetKey],
        metrics: ThumbCluster[Boundary],
        down_key_metrics: Boundary,
        side: KeyboardSide,
        palette: Palette,
        circle_diameter: float,
        gap: float,
    ) -> "LayerIndicatorOverlay":
        """Create an overlay for a thumb cluster.

        Args:
            down_key_metrics: The Down key boundary, used for DD gap calculation.
        """
        indicators: list[LayerIndicator] = []

        for key_name in _THUMB_KEY_NAMES:
            key: SvalboardTargetKey = getattr(keys, key_name)
            if key.layer_switch is None:
                continue

            layout: Boundary = getattr(metrics, key_name)
            offset_dir, conn_type = _thumb_cluster_offset(key_name, side)

            # DD: gap is measured from the Down key's top edge, not DD's own edge.
            # We pass the Down key boundary so the ABOVE circle clears the Down key.
            if key_name == "double_down_key":
                ref_y = down_key_metrics.pos.y
                ref_height = down_key_metrics.pos.y - layout.pos.y + layout.width
            else:
                ref_y = layout.pos.y
                ref_height = layout.width  # thumb keys use width for aspect ratio calc

            indicators.append(LayerIndicator(
                key_x=layout.pos.x,
                key_y=ref_y,
                key_width=layout.width,
                key_height=ref_height,
                target_layer=key.layer_switch,
                palette=palette,
                circle_diameter=circle_diameter,
                gap=gap,
                offset_direction=offset_dir,
                connector_type=conn_type,
            ))

        return cls(indicators)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/application/render/test_indicators.py::TestThumbClusterOverlay -v`
Expected: All PASS

- [ ] **Step 5: Run all indicator tests**

Run: `uv run pytest tests/unit/application/render/test_indicators.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/skim/application/render/indicators.py tests/unit/application/render/test_indicators.py
git commit -m "feat(render): add LayerIndicatorOverlay for thumb clusters"
```

---

### Task 6: Integrate indicators into cluster `build()` methods

**Files:**
- Modify: `src/skim/application/render/components.py:281-291,437-448`
- Modify: `tests/unit/application/render/test_components.py`

- [ ] **Step 1: Write failing integration tests**

Add to `tests/unit/application/render/test_components.py`:

```python
class TestFingerClusterIndicators:
    """Tests for layer indicator integration in FingerClusterComponent."""

    def test_indicators_rendered_when_enabled(self, sample_palette):
        """Indicators appear in SVG when show_layer_indicators is True."""
        keys = FingerCluster(
            center_key=SvalboardTargetKey(label="C", layer_switch=1),
            north_key=SvalboardTargetKey(label="N", layer_switch=None),
            east_key=SvalboardTargetKey(label="E", layer_switch=None),
            south_key=SvalboardTargetKey(label="S", layer_switch=None),
            west_key=SvalboardTargetKey(label="W", layer_switch=None),
            double_south_key=SvalboardTargetKey(label="DS", layer_switch=None),
        )
        ctx = RenderContext(
            palette=sample_palette,
            layer_index=0,
            has_double_south=True,
            use_layer_colors_on_keys=True,
            hold_symbol_position=SplitSidePosition.OUTWARD,
            show_layer_indicators=True,
        )
        component = FingerClusterComponent(
            keymap_cluster=keys,
            side=KeyboardSide.LEFT,
            layout=Boundary(width=165, pos=Position(x=0, y=0)),
            render_context=ctx,
        )
        svg = component.build()
        svg_str = svg.as_svg()
        # Should contain indicator elements (layer number "1")
        assert ">1<" in svg_str

    def test_indicators_not_rendered_when_disabled(self, sample_palette):
        """No indicators in SVG when show_layer_indicators is False."""
        keys = FingerCluster(
            center_key=SvalboardTargetKey(label="C", layer_switch=1),
            north_key=SvalboardTargetKey(label="N", layer_switch=None),
            east_key=SvalboardTargetKey(label="E", layer_switch=None),
            south_key=SvalboardTargetKey(label="S", layer_switch=None),
            west_key=SvalboardTargetKey(label="W", layer_switch=None),
            double_south_key=SvalboardTargetKey(label="DS", layer_switch=None),
        )
        ctx = RenderContext(
            palette=sample_palette,
            layer_index=0,
            has_double_south=True,
            use_layer_colors_on_keys=True,
            hold_symbol_position=SplitSidePosition.OUTWARD,
            show_layer_indicators=False,
        )
        component = FingerClusterComponent(
            keymap_cluster=keys,
            side=KeyboardSide.LEFT,
            layout=Boundary(width=165, pos=Position(x=0, y=0)),
            render_context=ctx,
        )
        svg = component.build()
        svg_str = svg.as_svg()
        # Layer number "1" should NOT appear as indicator text
        # (it might appear in key labels though, so check for indicator-specific elements)
        # The indicator circle uses the target layer's base_color as fill
        assert f'fill="{sample_palette.layers[1].base_color}"' not in svg_str
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/application/render/test_components.py::TestFingerClusterIndicators -v`
Expected: FAIL — indicators are not rendered yet.

- [ ] **Step 3: Integrate into `FingerClusterComponent.build()`**

In `src/skim/application/render/components.py`, add import at the top:

```python
from .indicators import LayerIndicatorOverlay
```

Replace `FingerClusterComponent.build()` (lines 437-448):

```python
    @override
    def build(self) -> DrawingElement:
        """Build the SVG element for this finger cluster."""
        for key in self._cluster:
            if key:
                self.append(key)

        if self._render_context.show_layer_indicators:
            overlay = LayerIndicatorOverlay.for_finger_cluster(
                keys=self._keymap_cluster,
                metrics=self._layout.metrics,
                side=self._side,
                palette=self._render_context.palette,
                circle_diameter=self._layout.metrics.north_key.width / 2,
                gap=self._layout.metrics.north_key.width * 0.18,
                has_double_south=self._render_context.has_double_south,
            )
            for indicator_group in overlay.build():
                self.append(indicator_group)

        return self
```

- [ ] **Step 4: Integrate into `ThumbClusterComponent.build()`**

Replace `ThumbClusterComponent.build()` (lines 281-291):

```python
    @override
    def build(self) -> DrawingElement:
        """Build the SVG element for this thumb cluster."""
        for key in self._cluster:
            self.append(key)

        if self._render_context.show_layer_indicators:
            overlay = LayerIndicatorOverlay.for_thumb_cluster(
                keys=self._keymap_cluster,
                metrics=self._layout.metrics,
                down_key_metrics=self._layout.metrics.down_key,
                side=self._side,
                palette=self._render_context.palette,
                circle_diameter=self._layout.metrics.down_key.width / 2,
                gap=self._layout.metrics.down_key.width * 0.18,
            )
            for indicator_group in overlay.build():
                self.append(indicator_group)

        return self
```

- [ ] **Step 5: Run integration tests**

Run: `uv run pytest tests/unit/application/render/test_components.py::TestFingerClusterIndicators -v`
Expected: All PASS

- [ ] **Step 6: Run full test suite**

Run: `uv run pytest tests/unit/application/render/ -v`
Expected: All PASS (existing tests should not break)

- [ ] **Step 7: Commit**

```bash
git add src/skim/application/render/components.py tests/unit/application/render/test_components.py
git commit -m "feat(render): integrate layer indicators into cluster build()"
```

---

### Task 7: Visual verification

**Files:** None (manual testing)

- [ ] **Step 1: Generate a test SVG with indicators**

```bash
uv run skim gen -c samples/config/skim-config.yaml -k samples/keymaps/c2json-sample.json -f svg --force -l 0 -S
```

- [ ] **Step 2: Open and inspect the generated SVG**

Open `keymap-layer-0.svg` in a browser. Verify:
- Layer-switching keys have colored circles with layer numbers
- Circles are positioned correctly per the placement rules
- Connector lines are horizontal/vertical (diagonal for center key)
- Connector endpoints are visible inside keys
- Non-layer-switching keys have no indicators

- [ ] **Step 3: Test with indicators disabled**

Temporarily set `show_layer_indicators: false` in `samples/config/skim-config.yaml` under `output.style`, regenerate, and verify no indicators appear. Then revert the config change.

- [ ] **Step 4: Commit any adjustments**

If visual inspection reveals positioning issues, adjust gap/size constants and commit:

```bash
git add -u
git commit -m "fix(render): tune layer indicator positioning"
```
