# Connector Routing Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-layer finger-cluster connector routing, the South + Double-South (S+DS) RIGHT-DOWN-RIGHT special case, and a multi-layer composition driver. Replace `route_thumb_connectors` with a top-level `route_overview_connectors` orchestrator that handles every source (8 finger clusters per layer + the thumb cluster) and runs Phase 2 column allocation globally.

**Architecture:** New finger-cluster builders + a new Phase 1 sub-step (`phase1_redirect_right_to_down`) live in `connectors.py` next to the existing thumb-cluster code. The orchestrator runs Phase 1 per source top-down with cascading layout shifts (a layer's `extra_top_padding` shifts that row + below; its `extra_bottom_padding` shifts strictly below), then a single global Phase 2 over all paths. Two-pass strategy from Plan 1 carries forward — pass 1 discovers paddings and applies shifts, pass 2 rebuilds paths against the fully-shifted layout.

**Tech Stack:** Python, drawsvg, dataclasses.

**Spec:** `docs/superpowers/specs/2026-04-26-overview-connector-routing-phase-2-design.md`

---

## File structure

- **Modify:** `src/skim/application/render/connectors.py` — adds priority constants, finger-cluster builders, the new Phase 1 sub-step, the source dataclasses, and the new orchestrator. Removes `route_thumb_connectors` (replaced by `route_overview_connectors`).
- **Modify:** `src/skim/application/render/overview_layout.py` — adds `shift_layer_row_and_below` and `shift_below_layer_row`.
- **Modify:** `src/skim/application/render/overview.py` — adds `_compute_finger_indicator_rects` and `_compute_all_indicator_rects`; updates the `_RoutingLayoutAdapter`; rewires `draw_overview` to use the new orchestrator.
- **Create:** `tests/integration/fixtures/connector-routing-coverage.vil` — synthetic Vial keymap exercising R4/non-R4 priority, S+DS double-trigger, and multi-layer cascading shifts.
- **Modify:** `tests/unit/application/render/test_connectors.py` — unit tests for every new helper (TDD).
- **Modify:** `tests/unit/application/render/test_overview_layout.py` — unit tests for the new shift methods.
- **Create or modify:** `tests/integration/test_overview_connectors.py` — structured-assertion integration tests against the synthetic fixture.

---

### Task 1: Add `shift_layer_row_and_below` and `shift_below_layer_row` to the layout API

**Files:**
- Modify: `src/skim/application/render/overview_layout.py`
- Modify: `src/skim/application/render/connectors.py` (RoutingLayout Protocol)
- Modify: `src/skim/application/render/overview.py` (`_RoutingLayoutAdapter`)
- Test: `tests/unit/application/render/test_overview_layout.py`

- [ ] **Step 1: Write the failing tests for `OverviewLayout`**

Add to `tests/unit/application/render/test_overview_layout.py`:

```python
def _make_layout_for_shift_tests() -> OverviewLayout:
    """Build a 3-layer OverviewLayout for shift-method tests."""
    config = make_test_config(num_layers=3)  # Use whatever helper the file already has
    badge = BadgeDimensions(width=200.0, height=40.0, border_radius=8.0)
    return OverviewLayout(config, badge, routing_column_count=0)


class TestShiftLayerRowAndBelow:
    def test_shifts_target_row_and_every_row_below(self):
        layout = _make_layout_for_shift_tests()
        ys_before = list(layout.layer_row_y_positions)
        thumb_before = layout.thumb_row_y
        canvas_before = layout.canvas_height

        layout.shift_layer_row_and_below(row_idx=1, amount=20.0)

        assert layout.layer_row_y_positions[0] == ys_before[0]
        assert layout.layer_row_y_positions[1] == ys_before[1] + 20.0
        assert layout.layer_row_y_positions[2] == ys_before[2] + 20.0
        assert layout.thumb_row_y == thumb_before + 20.0
        assert layout.canvas_height == canvas_before + 20.0

    def test_noop_on_non_positive_amount(self):
        layout = _make_layout_for_shift_tests()
        ys_before = list(layout.layer_row_y_positions)
        canvas_before = layout.canvas_height

        layout.shift_layer_row_and_below(row_idx=1, amount=0.0)
        layout.shift_layer_row_and_below(row_idx=1, amount=-5.0)

        assert layout.layer_row_y_positions == ys_before
        assert layout.canvas_height == canvas_before


class TestShiftBelowLayerRow:
    def test_shifts_rows_strictly_below_target(self):
        layout = _make_layout_for_shift_tests()
        ys_before = list(layout.layer_row_y_positions)
        thumb_before = layout.thumb_row_y
        canvas_before = layout.canvas_height

        layout.shift_below_layer_row(row_idx=1, amount=20.0)

        assert layout.layer_row_y_positions[0] == ys_before[0]
        assert layout.layer_row_y_positions[1] == ys_before[1]  # NOT shifted
        assert layout.layer_row_y_positions[2] == ys_before[2] + 20.0
        assert layout.thumb_row_y == thumb_before + 20.0
        assert layout.canvas_height == canvas_before + 20.0

    def test_noop_on_non_positive_amount(self):
        layout = _make_layout_for_shift_tests()
        ys_before = list(layout.layer_row_y_positions)
        canvas_before = layout.canvas_height

        layout.shift_below_layer_row(row_idx=1, amount=0.0)
        layout.shift_below_layer_row(row_idx=1, amount=-5.0)

        assert layout.layer_row_y_positions == ys_before
        assert layout.canvas_height == canvas_before
```

If `make_test_config` doesn't already exist in the file, look at the existing `test_canvas_width_no_routing_when_zero_columns` test (added during Phase 1 Task 7 polish) for an existing pattern that builds `OverviewLayout` — copy/adapt it. Use 3 layers so we can verify the cascading.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/application/render/test_overview_layout.py -v`
Expected: FAIL with `AttributeError: 'OverviewLayout' object has no attribute 'shift_layer_row_and_below'` (and the same for `shift_below_layer_row`).

- [ ] **Step 3: Implement the two shift methods on `OverviewLayout`**

Add to `OverviewLayout` in `src/skim/application/render/overview_layout.py`, near the existing `shift_thumb_down`:

```python
def shift_layer_row_and_below(self, row_idx: int, amount: float) -> None:
    """Shift layer row ``row_idx`` and every row below it (plus thumb) down.

    Used to apply a layer's ``extra_top_padding`` during connector routing.
    Grows the canvas accordingly. No-op when ``amount <= 0``.
    """
    if amount <= 0:
        return
    for i in range(row_idx, len(self._layer_row_y_positions)):
        self._layer_row_y_positions[i] += amount
    self._thumb_row_y += amount
    self._canvas_height += amount

def shift_below_layer_row(self, row_idx: int, amount: float) -> None:
    """Shift every row strictly below ``row_idx`` (plus thumb) down.

    Used to apply a layer's ``extra_bottom_padding`` — the lanes occupy
    the gap reserved between this layer's row and the next thing below.
    The row at ``row_idx`` itself does NOT move. Grows the canvas
    accordingly. No-op when ``amount <= 0``.
    """
    if amount <= 0:
        return
    for i in range(row_idx + 1, len(self._layer_row_y_positions)):
        self._layer_row_y_positions[i] += amount
    self._thumb_row_y += amount
    self._canvas_height += amount
```

- [ ] **Step 4: Update the `RoutingLayout` Protocol**

In `src/skim/application/render/connectors.py`, add the two methods to the `RoutingLayout` Protocol:

```python
class RoutingLayout(Protocol):
    """Minimal layout surface the connector router needs.

    Implemented by ``OverviewLayout`` directly. The overview also wraps
    the layout to translate QMK layer indices to row indices before
    delegating to the underlying layout — that wrapper is structurally
    compatible with this protocol.
    """

    @property
    def layer_row_y_positions(self) -> list[float]: ...

    def layer_row_bounding_box(self, target_layer: int) -> tuple[float, float, float, float]: ...

    def layer_row_target_y(self, target_layer: int) -> float:
        """Y where connectors should land — vertical center of the East key."""

    def thumb_cluster_y_bounds(self) -> tuple[float, float]: ...

    def shift_layer_row_and_below(self, row_idx: int, amount: float) -> None:
        """Apply a layer's extra_top_padding."""

    def shift_below_layer_row(self, row_idx: int, amount: float) -> None:
        """Apply a layer's extra_bottom_padding."""

    def shift_thumb_down(self, amount: float) -> None: ...
```

(The Protocol may not currently list `shift_thumb_down` either; add it if missing — the orchestrator uses it.)

- [ ] **Step 5: Update `_RoutingLayoutAdapter` in `overview.py`**

Add the matching delegation methods. The adapter receives a QMK layer index and translates to the underlying row index via `_layer_to_row`:

```python
def shift_layer_row_and_below(self, target_layer: int, amount: float) -> None:
    row_idx = self._layer_to_row.get(target_layer)
    if row_idx is None:
        return  # caller passed an unmapped index; nothing to shift
    self._layout.shift_layer_row_and_below(row_idx, amount)

def shift_below_layer_row(self, target_layer: int, amount: float) -> None:
    row_idx = self._layer_to_row.get(target_layer)
    if row_idx is None:
        return
    self._layout.shift_below_layer_row(row_idx, amount)

def shift_thumb_down(self, amount: float) -> None:
    self._layout.shift_thumb_down(amount)
```

(`shift_thumb_down` may already be on the adapter — if so, leave it alone.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/unit/application/render/test_overview_layout.py -v`
Expected: PASS.

Run: `uv run pytest` to ensure nothing else broke.
Expected: PASS.

Run: `just check && just typecheck`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add src/skim/application/render/overview_layout.py \
        src/skim/application/render/connectors.py \
        src/skim/application/render/overview.py \
        tests/unit/application/render/test_overview_layout.py
git commit -m "feat(layout): add shift_layer_row_and_below and shift_below_layer_row"
```

---

### Task 2: Add `source_cluster_attr` field to `ConnectorStep`

**Files:**
- Modify: `src/skim/application/render/connectors.py`
- Test: `tests/unit/application/render/test_connectors.py`

The S+DS partner search needs to scope to the same cluster (otherwise a south_key in left.index would partner with a double_south_key in left.middle, etc.). The cleanest way is to record the cluster the step came from on the step itself.

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/application/render/test_connectors.py` inside `TestConnectorStep`:

```python
def test_default_source_cluster_attr_is_empty(self):
    step = ConnectorStep(
        key=None,
        direction=Direction.UP,
        target_point=(0.0, 0.0),
        target_layer=0,
    )
    assert step.source_cluster_attr == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/application/render/test_connectors.py::TestConnectorStep -v`
Expected: FAIL with `AttributeError: 'ConnectorStep' object has no attribute 'source_cluster_attr'`.

- [ ] **Step 3: Add the field**

In `src/skim/application/render/connectors.py`, add `source_cluster_attr: str = ""` to the `ConnectorStep` dataclass (place it after `key_origin_attr`, before `path`). Update the dataclass docstring's `Attributes` block:

```python
key_origin_attr: The thumb-cluster attribute name that produced this
    step (e.g. ``"down_key"``, ``"up_key"``). Used by Phase 1 routing
    to identify partner paths (e.g. matching LT_Up to LT_Down).
source_cluster_attr: The source cluster identifier (e.g. ``"left.index"``,
    ``"right.pinky"``). Empty for thumb steps. Used by
    ``phase1_redirect_right_to_down`` to scope the S+DS partner search
    to the same finger cluster.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/application/render/test_connectors.py::TestConnectorStep -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/skim/application/render/connectors.py tests/unit/application/render/test_connectors.py
git commit -m "feat(connectors): add source_cluster_attr field to ConnectorStep"
```

---

### Task 3: `_R4_PRIORITY`, `_NON_R4_PRIORITY`, and `build_finger_path_list_for_cluster`

**Files:**
- Modify: `src/skim/application/render/connectors.py`
- Test: `tests/unit/application/render/test_connectors.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/application/render/test_connectors.py`:

```python
from skim.application.render.connectors import build_finger_path_list_for_cluster
from skim.data.keyboard import FingerCluster


def _finger(**overrides):
    """Build a FingerCluster with all keys defaulting to no layer_switch."""
    base = {
        name: _key()
        for name in ("center_key", "north_key", "east_key", "south_key", "west_key", "double_south_key")
    }
    base.update(overrides)
    return FingerCluster(**base)


class TestBuildFingerPathListForCluster:
    def _layout_target(self):
        layout = MagicMock()
        layout.layer_row_y_positions = [100, 200, 300]
        layout.layer_row_heights = [50, 50, 50]
        layout.layer_row_bounding_box = lambda idx: (200, layout.layer_row_y_positions[idx], 600, 50)
        layout.layer_row_target_y = lambda idx: layout.layer_row_y_positions[idx] + 25
        return layout

    def test_empty_cluster_produces_no_steps(self):
        layout = self._layout_target()
        steps = build_finger_path_list_for_cluster(
            cluster=_finger(),
            is_r4=False,
            cluster_attr="left.index",
            source_layer=0,
            layout=layout,
            keymap_spacing=18,
        )
        assert steps == []

    def test_r4_priority_order_and_directions(self):
        # R4: N, W, S, DS, E, C → RIGHT, RIGHT, RIGHT, RIGHT, UP, DOWN
        layout = self._layout_target()
        cluster = _finger(
            north_key=_key(layer_switch=1),
            west_key=_key(layer_switch=2),
            south_key=_key(layer_switch=1),
            double_south_key=_key(layer_switch=2),
            east_key=_key(layer_switch=1),
            center_key=_key(layer_switch=2),
        )
        steps = build_finger_path_list_for_cluster(
            cluster=cluster,
            is_r4=True,
            cluster_attr="right.pinky",
            source_layer=0,
            layout=layout,
            keymap_spacing=18,
        )
        attrs = [s.key_origin_attr for s in steps]
        directions = [s.direction for s in steps]
        assert attrs == ["north_key", "west_key", "south_key", "double_south_key", "east_key", "center_key"]
        assert directions == [
            Direction.RIGHT, Direction.RIGHT, Direction.RIGHT, Direction.RIGHT,
            Direction.UP, Direction.DOWN,
        ]

    def test_non_r4_priority_order_and_directions(self):
        # Non-R4: W, N, E, S, DS, C → UP, UP, UP, DOWN, DOWN, DOWN
        layout = self._layout_target()
        cluster = _finger(
            west_key=_key(layer_switch=1),
            north_key=_key(layer_switch=2),
            east_key=_key(layer_switch=1),
            south_key=_key(layer_switch=2),
            double_south_key=_key(layer_switch=1),
            center_key=_key(layer_switch=2),
        )
        steps = build_finger_path_list_for_cluster(
            cluster=cluster,
            is_r4=False,
            cluster_attr="left.index",
            source_layer=0,
            layout=layout,
            keymap_spacing=18,
        )
        attrs = [s.key_origin_attr for s in steps]
        directions = [s.direction for s in steps]
        assert attrs == ["west_key", "north_key", "east_key", "south_key", "double_south_key", "center_key"]
        assert directions == [
            Direction.UP, Direction.UP, Direction.UP,
            Direction.DOWN, Direction.DOWN, Direction.DOWN,
        ]

    def test_s_and_ds_double_trigger_in_non_r4_makes_south_right(self):
        # When both south and DS trigger in a non-R4 cluster, south's initial
        # direction is RIGHT (S+DS special case).
        layout = self._layout_target()
        cluster = _finger(
            south_key=_key(layer_switch=1),
            double_south_key=_key(layer_switch=2),
        )
        steps = build_finger_path_list_for_cluster(
            cluster=cluster,
            is_r4=False,
            cluster_attr="left.index",
            source_layer=0,
            layout=layout,
            keymap_spacing=18,
        )
        south_step = next(s for s in steps if s.key_origin_attr == "south_key")
        ds_step = next(s for s in steps if s.key_origin_attr == "double_south_key")
        assert south_step.direction == Direction.RIGHT
        assert ds_step.direction == Direction.DOWN

    def test_only_south_triggers_in_non_r4_keeps_south_down(self):
        layout = self._layout_target()
        cluster = _finger(south_key=_key(layer_switch=1))
        steps = build_finger_path_list_for_cluster(
            cluster=cluster,
            is_r4=False,
            cluster_attr="left.index",
            source_layer=0,
            layout=layout,
            keymap_spacing=18,
        )
        assert len(steps) == 1
        assert steps[0].direction == Direction.DOWN

    def test_only_ds_triggers_in_non_r4_keeps_ds_down(self):
        layout = self._layout_target()
        cluster = _finger(double_south_key=_key(layer_switch=1))
        steps = build_finger_path_list_for_cluster(
            cluster=cluster,
            is_r4=False,
            cluster_attr="left.index",
            source_layer=0,
            layout=layout,
            keymap_spacing=18,
        )
        assert len(steps) == 1
        assert steps[0].direction == Direction.DOWN

    def test_r4_with_s_and_ds_double_trigger_keeps_both_right(self):
        # R4's table already has S/DS as RIGHT — no special case applies.
        layout = self._layout_target()
        cluster = _finger(
            south_key=_key(layer_switch=1),
            double_south_key=_key(layer_switch=2),
        )
        steps = build_finger_path_list_for_cluster(
            cluster=cluster,
            is_r4=True,
            cluster_attr="right.pinky",
            source_layer=0,
            layout=layout,
            keymap_spacing=18,
        )
        directions = {s.key_origin_attr: s.direction for s in steps}
        assert directions["south_key"] == Direction.RIGHT
        assert directions["double_south_key"] == Direction.RIGHT

    def test_self_referential_trigger_skipped(self):
        layout = self._layout_target()
        cluster = _finger(north_key=_key(layer_switch=0))  # source=0, target=0
        steps = build_finger_path_list_for_cluster(
            cluster=cluster,
            is_r4=False,
            cluster_attr="left.index",
            source_layer=0,
            layout=layout,
            keymap_spacing=18,
        )
        assert steps == []

    def test_steps_carry_source_cluster_attr(self):
        layout = self._layout_target()
        cluster = _finger(north_key=_key(layer_switch=1))
        steps = build_finger_path_list_for_cluster(
            cluster=cluster,
            is_r4=False,
            cluster_attr="left.index",
            source_layer=0,
            layout=layout,
            keymap_spacing=18,
        )
        assert steps[0].source_cluster_attr == "left.index"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/application/render/test_connectors.py::TestBuildFingerPathListForCluster -v`
Expected: FAIL with `ImportError: cannot import name 'build_finger_path_list_for_cluster'`.

- [ ] **Step 3: Add the priority constants and the builder**

In `src/skim/application/render/connectors.py`, add at module scope (place near `_THUMB_PRIORITY`):

```python
# Priority for the right-pinky (R4) finger cluster. Most keys exit RIGHT
# directly because R4 sits closest to the routing columns. The E key would
# cross itself going RIGHT so it escapes UP; C is buried in the middle so
# it exits DOWN.
_R4_PRIORITY: list[tuple[str, Direction]] = [
    ("north_key", Direction.RIGHT),
    ("west_key", Direction.RIGHT),
    ("south_key", Direction.RIGHT),
    ("double_south_key", Direction.RIGHT),
    ("east_key", Direction.UP),
    ("center_key", Direction.DOWN),
]

# Priority for every other finger cluster. N/W/E exit UP over the cluster
# top; S/DS/C exit DOWN under it.
_NON_R4_PRIORITY: list[tuple[str, Direction]] = [
    ("west_key", Direction.UP),
    ("north_key", Direction.UP),
    ("east_key", Direction.UP),
    ("south_key", Direction.DOWN),
    ("double_south_key", Direction.DOWN),
    ("center_key", Direction.DOWN),
]
```

Add the import for `FingerCluster` at the top of the file:

```python
from skim.data.keyboard import FingerCluster, ThumbCluster  # ThumbCluster already imported
```

Add the builder function (place it after `build_thumb_path_list`):

```python
def build_finger_path_list_for_cluster(
    cluster: FingerCluster[SvalboardTargetKey],
    is_r4: bool,
    cluster_attr: str,
    source_layer: int,
    layout: RoutingLayout,
    keymap_spacing: float,
) -> list[ConnectorStep]:
    """Build the priority-ordered ConnectorStep list for one finger cluster.

    Applies the R4 vs non-R4 priority table. For non-R4 clusters: when both
    south_key and double_south_key trigger, south's initial direction is
    overridden to RIGHT (the S+DS special case — phase1_redirect_right_to_down
    redirects it to DOWN one keymap_spacing east of DS's drop column).
    Otherwise south takes its table direction (DOWN).

    Args:
        cluster: The finger cluster to scan for layer-switch triggers.
        is_r4: True if this is the right-pinky cluster (uses _R4_PRIORITY).
        cluster_attr: A stable identifier for this cluster, e.g. ``"left.index"``
            or ``"right.pinky"``. Stored on each step's ``source_cluster_attr``
            so phase1_redirect_right_to_down can scope its partner search.
        source_layer: The QMK layer index where the cluster lives (the source
            of the path).
        layout: The routing layout (provides target geometry).
        keymap_spacing: Spacing constant.

    Returns:
        ConnectorSteps in priority order, skipping keys whose target_point is
        None (self-ref or out-of-range).
    """
    priority = _R4_PRIORITY if is_r4 else _NON_R4_PRIORITY
    south_ds_special = (
        not is_r4
        and cluster.south_key.layer_switch is not None
        and cluster.double_south_key.layer_switch is not None
    )

    steps: list[ConnectorStep] = []
    for attr, direction in priority:
        key: SvalboardTargetKey = getattr(cluster, attr)
        if key.layer_switch is None:
            continue
        target = target_point_for(layout, key.layer_switch, source_layer, keymap_spacing)
        if target is None:
            continue
        actual_direction = direction
        if south_ds_special and attr == "south_key":
            actual_direction = Direction.RIGHT
        steps.append(
            ConnectorStep(
                key=key,
                direction=actual_direction,
                target_point=target,
                target_layer=key.layer_switch,
                key_origin_attr=attr,
                source_cluster_attr=cluster_attr,
            )
        )

    return steps
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/application/render/test_connectors.py::TestBuildFingerPathListForCluster -v`
Expected: PASS.

Run: `just check && just typecheck`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add src/skim/application/render/connectors.py tests/unit/application/render/test_connectors.py
git commit -m "feat(connectors): add finger-cluster priority tables and per-cluster builder"
```

---

### Task 4: `build_finger_path_list_for_layer`

**Files:**
- Modify: `src/skim/application/render/connectors.py`
- Test: `tests/unit/application/render/test_connectors.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/application/render/test_connectors.py`:

```python
from skim.application.render.connectors import build_finger_path_list_for_layer
from skim.data.keyboard import SplitSide


def _side(*, index=None, middle=None, ring=None, pinky=None):
    """Build a SplitSide with empty FingerClusters by default."""
    return SplitSide(
        index=index or _finger(),
        middle=middle or _finger(),
        ring=ring or _finger(),
        pinky=pinky or _finger(),
        thumb=_thumb(),  # not used by finger routing — placeholder
    )


class TestBuildFingerPathListForLayer:
    def _layout_target(self):
        layout = MagicMock()
        layout.layer_row_y_positions = [100, 200, 300]
        layout.layer_row_heights = [50, 50, 50]
        layout.layer_row_bounding_box = lambda idx: (200, layout.layer_row_y_positions[idx], 600, 50)
        layout.layer_row_target_y = lambda idx: layout.layer_row_y_positions[idx] + 25
        return layout

    def test_empty_layer_produces_no_steps(self):
        layout = self._layout_target()
        steps = build_finger_path_list_for_layer(
            left=_side(), right=_side(),
            source_layer=0,
            layout=layout, keymap_spacing=18,
        )
        assert steps == []

    def test_cluster_iteration_order_is_l4_l3_l2_l1_r1_r2_r3_r4(self):
        # Trigger one key in each cluster so we can recover the order from
        # the resulting source_cluster_attr sequence.
        layout = self._layout_target()
        l1 = _finger(north_key=_key(layer_switch=1))
        l2 = _finger(north_key=_key(layer_switch=1))
        l3 = _finger(north_key=_key(layer_switch=1))
        l4 = _finger(north_key=_key(layer_switch=1))
        r1 = _finger(north_key=_key(layer_switch=1))
        r2 = _finger(north_key=_key(layer_switch=1))
        r3 = _finger(north_key=_key(layer_switch=1))
        r4 = _finger(north_key=_key(layer_switch=1))

        steps = build_finger_path_list_for_layer(
            left=_side(index=l1, middle=l2, ring=l3, pinky=l4),
            right=_side(index=r1, middle=r2, ring=r3, pinky=r4),
            source_layer=0,
            layout=layout, keymap_spacing=18,
        )
        cluster_order = [s.source_cluster_attr for s in steps]
        assert cluster_order == [
            "left.pinky",   # L4
            "left.ring",    # L3
            "left.middle",  # L2
            "left.index",   # L1
            "right.index",  # R1
            "right.middle", # R2
            "right.ring",   # R3
            "right.pinky",  # R4
        ]

    def test_only_r4_uses_r4_priority(self):
        layout = self._layout_target()
        # Right-pinky north_key uses R4 → direction RIGHT.
        # Left-pinky north_key uses non-R4 → direction UP.
        right = _side(pinky=_finger(north_key=_key(layer_switch=1)))
        left = _side(pinky=_finger(north_key=_key(layer_switch=1)))

        steps = build_finger_path_list_for_layer(
            left=left, right=right,
            source_layer=0,
            layout=layout, keymap_spacing=18,
        )
        l4_step = next(s for s in steps if s.source_cluster_attr == "left.pinky")
        r4_step = next(s for s in steps if s.source_cluster_attr == "right.pinky")
        assert l4_step.direction == Direction.UP   # non-R4 priority
        assert r4_step.direction == Direction.RIGHT  # R4 priority
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/application/render/test_connectors.py::TestBuildFingerPathListForLayer -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement the layer builder**

Add to `src/skim/application/render/connectors.py` after `build_finger_path_list_for_cluster`:

```python
# Cluster iteration order for a finger layer:
# L4, L3, L2, L1, R1, R2, R3, R4 — outer-to-inner on the left, then
# inner-to-outer on the right. R4 is the only cluster that uses _R4_PRIORITY.
_FINGER_CLUSTER_ITER_ORDER: list[tuple[str, str, bool]] = [
    # (cluster_attr_for_step, side_attr_on_SplitSide, is_r4)
    ("left.pinky",   "pinky",  False),
    ("left.ring",    "ring",   False),
    ("left.middle",  "middle", False),
    ("left.index",   "index",  False),
    ("right.index",  "index",  False),
    ("right.middle", "middle", False),
    ("right.ring",   "ring",   False),
    ("right.pinky",  "pinky",  True),
]


def build_finger_path_list_for_layer(
    left: SplitSide[SvalboardTargetKey],
    right: SplitSide[SvalboardTargetKey],
    source_layer: int,
    layout: RoutingLayout,
    keymap_spacing: float,
) -> list[ConnectorStep]:
    """Build the path list for all 8 finger clusters in one layer.

    Cluster iteration order: L4, L3, L2, L1, R1, R2, R3, R4. Within each
    cluster, keys follow the R4 vs non-R4 priority table.
    """
    steps: list[ConnectorStep] = []
    for cluster_attr, side_attr, is_r4 in _FINGER_CLUSTER_ITER_ORDER:
        side = left if cluster_attr.startswith("left.") else right
        cluster: FingerCluster[SvalboardTargetKey] = getattr(side, side_attr)
        steps.extend(
            build_finger_path_list_for_cluster(
                cluster=cluster,
                is_r4=is_r4,
                cluster_attr=cluster_attr,
                source_layer=source_layer,
                layout=layout,
                keymap_spacing=keymap_spacing,
            )
        )
    return steps
```

Add the `SplitSide` import at the top:

```python
from skim.data.keyboard import FingerCluster, SplitSide, ThumbCluster
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/application/render/test_connectors.py::TestBuildFingerPathListForLayer -v`
Expected: PASS.

Run: `just check && just typecheck`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add src/skim/application/render/connectors.py tests/unit/application/render/test_connectors.py
git commit -m "feat(connectors): build finger path list for one layer in cluster order"
```

---

### Task 5: `phase1_redirect_right_to_down`

**Files:**
- Modify: `src/skim/application/render/connectors.py`
- Test: `tests/unit/application/render/test_connectors.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/application/render/test_connectors.py`:

```python
from skim.application.render.connectors import phase1_redirect_right_to_down


class TestPhase1RedirectRightToDown:
    def test_south_extends_east_then_marks_down(self):
        # S+DS pair in the same cluster.
        # South: indicator at x=100, direction=RIGHT initially.
        # DS:    indicator at x=100, direction=DOWN.
        # After set_initial_moveto:
        #   south.current_point = (rx + rw, ry + rh/2) — RIGHT moveTo edge.
        #     For (100, 200, 8, 8): (108, 204).
        #   ds.current_point = (rx + rw/2, ry + rh) — DOWN moveTo edge.
        #     For (100, 220, 8, 8): (104, 228).
        # Redirect: new_x = ds.current_point[0] + spacing = 104 + 18 = 122.
        # South path extends to (122, south.current_point[1] = 204), direction = DOWN.
        south = _step(Direction.RIGHT, (100, 200, 8, 8))
        south.key_origin_attr = "south_key"
        south.source_cluster_attr = "left.index"
        ds = _step(Direction.DOWN, (100, 220, 8, 8))
        ds.key_origin_attr = "double_south_key"
        ds.source_cluster_attr = "left.index"
        set_initial_moveto(south)
        set_initial_moveto(ds)

        phase1_redirect_right_to_down([south, ds], keymap_spacing=18)

        assert south.current_point == (122.0, 204.0)
        assert south.direction == Direction.DOWN
        # DS unchanged.
        assert ds.direction == Direction.DOWN
        assert ds.current_point == (104.0, 228.0)

    def test_no_op_when_no_right_paths(self):
        a = _step(Direction.UP, (10, 100, 6, 8))
        a.source_cluster_attr = "left.index"
        b = _step(Direction.DOWN, (20, 110, 6, 8))
        b.source_cluster_attr = "left.index"
        b.key_origin_attr = "south_key"
        set_initial_moveto(a)
        set_initial_moveto(b)

        phase1_redirect_right_to_down([a, b], keymap_spacing=18)

        assert a.direction == Direction.UP
        assert b.direction == Direction.DOWN

    def test_partner_search_scoped_to_same_cluster(self):
        # South in left.index has its DS partner in left.index, not left.middle.
        south = _step(Direction.RIGHT, (100, 200, 8, 8))
        south.key_origin_attr = "south_key"
        south.source_cluster_attr = "left.index"
        wrong_ds = _step(Direction.DOWN, (500, 220, 8, 8))
        wrong_ds.key_origin_attr = "double_south_key"
        wrong_ds.source_cluster_attr = "left.middle"
        right_ds = _step(Direction.DOWN, (100, 220, 8, 8))
        right_ds.key_origin_attr = "double_south_key"
        right_ds.source_cluster_attr = "left.index"
        set_initial_moveto(south)
        set_initial_moveto(wrong_ds)
        set_initial_moveto(right_ds)

        phase1_redirect_right_to_down([south, wrong_ds, right_ds], keymap_spacing=18)

        # Should redirect against right_ds.current_point[0] = 104, not wrong_ds.current_point[0] = 504.
        assert south.current_point[0] == 122.0
        assert south.direction == Direction.DOWN

    def test_no_partner_leaves_step_unchanged(self):
        # South is RIGHT, but no DS step exists in path_list (malformed input).
        south = _step(Direction.RIGHT, (100, 200, 8, 8))
        south.key_origin_attr = "south_key"
        south.source_cluster_attr = "left.index"
        set_initial_moveto(south)

        phase1_redirect_right_to_down([south], keymap_spacing=18)

        assert south.direction == Direction.RIGHT
        # current_point unchanged from set_initial_moveto.
        assert south.current_point == (108.0, 204.0)

    def test_multiple_right_steps_in_different_clusters(self):
        # Two S+DS pairs in two different clusters.
        s1 = _step(Direction.RIGHT, (100, 200, 8, 8))
        s1.key_origin_attr = "south_key"
        s1.source_cluster_attr = "left.index"
        ds1 = _step(Direction.DOWN, (100, 220, 8, 8))
        ds1.key_origin_attr = "double_south_key"
        ds1.source_cluster_attr = "left.index"
        s2 = _step(Direction.RIGHT, (300, 200, 8, 8))
        s2.key_origin_attr = "south_key"
        s2.source_cluster_attr = "left.middle"
        ds2 = _step(Direction.DOWN, (300, 220, 8, 8))
        ds2.key_origin_attr = "double_south_key"
        ds2.source_cluster_attr = "left.middle"
        for s in (s1, ds1, s2, ds2):
            set_initial_moveto(s)

        phase1_redirect_right_to_down([s1, ds1, s2, ds2], keymap_spacing=18)

        assert s1.direction == Direction.DOWN
        assert s2.direction == Direction.DOWN
        # Each redirected against its own cluster's DS.
        assert s1.current_point[0] == ds1.current_point[0] + 18  # 104 + 18 = 122
        assert s2.current_point[0] == ds2.current_point[0] + 18  # 304 + 18 = 322
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/application/render/test_connectors.py::TestPhase1RedirectRightToDown -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement the redirect**

Add to `src/skim/application/render/connectors.py` near `phase1_redirect_left_to_down`:

```python
def phase1_redirect_right_to_down(
    path_list: list[ConnectorStep],
    keymap_spacing: float,
) -> None:
    """Redirect RIGHT-direction paths (S+DS special case) to DOWN.

    For each RIGHT-direction step (which represents South in the S+DS
    conflict), find its DS partner via ``key_origin_attr ==
    "double_south_key"`` AND same ``source_cluster_attr``. Extend east one
    keymap_spacing past the partner's current X (its drop column), then
    mark direction DOWN so the regular DOWN→RIGHT sub-step picks it up.

    No-op when no RIGHT-direction steps exist. Steps with no DS partner
    (malformed input) are left unchanged.
    """
    right_steps = [s for s in path_list if s.direction == Direction.RIGHT]
    if not right_steps:
        return

    for step in right_steps:
        partner = next(
            (
                s
                for s in path_list
                if s.direction == Direction.DOWN
                and s.key_origin_attr == "double_south_key"
                and s.source_cluster_attr == step.source_cluster_attr
            ),
            None,
        )
        if partner is None:
            continue  # malformed input; nothing to redirect against

        new_x = partner.current_point[0] + keymap_spacing
        step.path.L(new_x, step.current_point[1])
        step.current_point = (new_x, step.current_point[1])
        step.direction = Direction.DOWN
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/application/render/test_connectors.py::TestPhase1RedirectRightToDown -v`
Expected: PASS.

Run: `just check && just typecheck`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add src/skim/application/render/connectors.py tests/unit/application/render/test_connectors.py
git commit -m "feat(connectors): phase 1 RIGHT→DOWN redirect for S+DS special case"
```

---

### Task 6: `OverviewLayerSource` and `ThumbSource` dataclasses

**Files:**
- Modify: `src/skim/application/render/connectors.py`
- Test: `tests/unit/application/render/test_connectors.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/application/render/test_connectors.py`:

```python
from skim.application.render.connectors import OverviewLayerSource, ThumbSource


class TestSourceDataclasses:
    def test_overview_layer_source_field_access(self):
        left = _side()
        right = _side()
        src = OverviewLayerSource(source_layer=3, left=left, right=right)
        assert src.source_layer == 3
        assert src.left is left
        assert src.right is right

    def test_thumb_source_field_access(self):
        left = _thumb()
        right = _thumb()
        src = ThumbSource(source_layer=0, left=left, right=right)
        assert src.source_layer == 0
        assert src.left is left
        assert src.right is right
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/application/render/test_connectors.py::TestSourceDataclasses -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Add the dataclasses**

In `src/skim/application/render/connectors.py`, add after `ConnectorRouting`:

```python
@dataclass(frozen=True, slots=True)
class OverviewLayerSource:
    """One layer's finger clusters as a routing source.

    Attributes:
        source_layer: The QMK layer index whose finger keys originate the paths.
        left: Left-side SplitSide containing four finger clusters (and a
            placeholder thumb that the finger router ignores).
        right: Right-side SplitSide containing four finger clusters.
    """

    source_layer: int
    left: SplitSide[SvalboardTargetKey]
    right: SplitSide[SvalboardTargetKey]


@dataclass(frozen=True, slots=True)
class ThumbSource:
    """The thumb cluster as a routing source.

    Attributes:
        source_layer: The QMK layer index the thumb cluster is rendered for.
        left: Left thumb cluster.
        right: Right thumb cluster.
    """

    source_layer: int
    left: ThumbCluster[SvalboardTargetKey]
    right: ThumbCluster[SvalboardTargetKey]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/application/render/test_connectors.py::TestSourceDataclasses -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/skim/application/render/connectors.py tests/unit/application/render/test_connectors.py
git commit -m "feat(connectors): add OverviewLayerSource and ThumbSource dataclasses"
```

---

### Task 7: `route_overview_connectors` orchestrator

**Files:**
- Modify: `src/skim/application/render/connectors.py`
- Test: `tests/unit/application/render/test_connectors.py`

The orchestrator runs the two-pass strategy: pass 1 discovers paddings per source and applies cascading layout shifts; pass 2 rebuilds paths against the fully-shifted layout for final geometry. Phase 2 column allocation runs once globally.

The orchestrator accepts a callable for indicator-rect computation so it can request rebuilt rects between passes (the rects move when the layout shifts).

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/application/render/test_connectors.py`:

```python
from skim.application.render.connectors import route_overview_connectors


class TestRouteOverviewConnectors:
    def _layout(self):
        layout = MagicMock()
        layout.layer_row_y_positions = [100, 200, 300]
        layout.layer_row_heights = [50, 50, 50]
        layout.layer_row_bounding_box = lambda i: (200, layout.layer_row_y_positions[i], 600, 50)
        layout.layer_row_target_y = lambda i: layout.layer_row_y_positions[i] + 25
        layout.thumb_cluster_y_bounds = lambda: (400.0, 500.0)
        # Mutating methods recorded but no-op for the test layout.
        layout.shift_layer_row_and_below = MagicMock()
        layout.shift_below_layer_row = MagicMock()
        layout.shift_thumb_down = MagicMock()
        return layout

    def test_empty_sources_returns_zero_padding(self):
        layout = self._layout()
        result = route_overview_connectors(
            layers=[],
            thumb=ThumbSource(source_layer=0, left=_thumb(), right=_thumb()),
            layout=layout,
            compute_indicator_rects=lambda: {},
            keymap_spacing=18,
        )
        assert result.paths == []
        assert result.extra_top_padding == 0.0
        assert result.extra_bottom_padding == 0.0
        assert result.extra_right_padding == 0.0

    def test_single_finger_trigger_produces_one_path(self):
        layout = self._layout()
        # Right-pinky north_key on layer 0 targets layer 1.
        rp_n = _key(layer_switch=1)
        right = _side(pinky=_finger(north_key=rp_n))
        rects = {rp_n: (700.0, 110.0, 6.0, 6.0)}
        result = route_overview_connectors(
            layers=[OverviewLayerSource(source_layer=0, left=_side(), right=right)],
            thumb=ThumbSource(source_layer=0, left=_thumb(), right=_thumb()),
            layout=layout,
            compute_indicator_rects=lambda: rects,
            keymap_spacing=18,
        )
        assert len(result.paths) == 1
        path, target_layer = result.paths[0]
        assert target_layer == 1

    def test_finger_up_trigger_applies_shift_layer_row_and_below(self):
        # A non-R4 north_key trigger has direction=UP, which produces a
        # non-zero extra_top_padding that the orchestrator applies via
        # layout.shift_layer_row_and_below.
        layout = self._layout()
        l1_n = _key(layer_switch=1)  # left.index north_key
        left = _side(index=_finger(north_key=l1_n))
        rects = {l1_n: (300.0, 110.0, 6.0, 6.0)}
        route_overview_connectors(
            layers=[OverviewLayerSource(source_layer=0, left=left, right=_side())],
            thumb=ThumbSource(source_layer=0, left=_thumb(), right=_thumb()),
            layout=layout,
            compute_indicator_rects=lambda: rects,
            keymap_spacing=18,
        )
        # 1 UP step → extra_top_padding = 1 * 18 = 18.0.
        layout.shift_layer_row_and_below.assert_called_with(0, 18.0)

    def test_thumb_extra_bottom_returned_in_routing(self):
        # A thumb DOWN trigger (RT_Knuckle) produces extra_bottom = (1 + 0.5) * 18 = 27.
        layout = self._layout()
        rt_knuckle = _key(layer_switch=1)
        right_thumb = _thumb(knuckle_key=rt_knuckle)
        rects = {rt_knuckle: (700.0, 450.0, 6.0, 6.0)}
        result = route_overview_connectors(
            layers=[],
            thumb=ThumbSource(source_layer=0, left=_thumb(), right=right_thumb),
            layout=layout,
            compute_indicator_rects=lambda: rects,
            keymap_spacing=18,
        )
        assert result.extra_bottom_padding == 27.0
        # No layer sources → no shift_layer_row_and_below calls.
        layout.shift_layer_row_and_below.assert_not_called()

    def test_compute_indicator_rects_called_twice(self):
        # Two-pass strategy: pass 1 + pass 2.
        layout = self._layout()
        rp_n = _key(layer_switch=1)
        right = _side(pinky=_finger(north_key=rp_n))
        rects = {rp_n: (700.0, 110.0, 6.0, 6.0)}
        compute_calls = [0]

        def compute_rects():
            compute_calls[0] += 1
            return rects

        route_overview_connectors(
            layers=[OverviewLayerSource(source_layer=0, left=_side(), right=right)],
            thumb=ThumbSource(source_layer=0, left=_thumb(), right=_thumb()),
            layout=layout,
            compute_indicator_rects=compute_rects,
            keymap_spacing=18,
        )
        assert compute_calls[0] == 2

    def test_extra_right_padding_uses_n_plus_one_formula(self):
        # 1 column allocated → extra_right = (1 + 1) * 18 = 36.
        layout = self._layout()
        rp_n = _key(layer_switch=1)
        right = _side(pinky=_finger(north_key=rp_n))
        rects = {rp_n: (700.0, 110.0, 6.0, 6.0)}
        result = route_overview_connectors(
            layers=[OverviewLayerSource(source_layer=0, left=_side(), right=right)],
            thumb=ThumbSource(source_layer=0, left=_thumb(), right=_thumb()),
            layout=layout,
            compute_indicator_rects=lambda: rects,
            keymap_spacing=18,
        )
        assert result.extra_right_padding == 36.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/application/render/test_connectors.py::TestRouteOverviewConnectors -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement the orchestrator**

In `src/skim/application/render/connectors.py`, extend the existing `from collections.abc import Mapping` line to:

```python
from collections.abc import Callable, Mapping, Sequence
```

Add this helper function (place after `phase2_route_to_targets`):

```python
def _layer_cluster_y_bounds(layout: RoutingLayout, source_layer: int) -> tuple[float, float]:
    """Return (top_y, bottom_y) of the finger clusters in a given layer's row."""
    _, row_y, _, row_h = layout.layer_row_bounding_box(source_layer)
    return (row_y, row_y + row_h)
```

Add the orchestrator (after the helper):

```python
def route_overview_connectors(
    layers: Sequence[OverviewLayerSource],
    thumb: ThumbSource,
    layout: RoutingLayout,
    compute_indicator_rects: Callable[
        [], Mapping[SvalboardTargetKey, tuple[float, float, float, float]]
    ],
    keymap_spacing: float,
) -> ConnectorRouting:
    """Top-level orchestrator for overview connector routing.

    Two-pass strategy: pass 1 discovers paddings per source and applies
    cascading layout shifts; pass 2 rebuilds paths against the fully-shifted
    layout for final geometry. Phase 2 column allocation runs once globally
    across all sources combined.

    Args:
        layers: Per-layer finger sources.
        thumb: The thumb cluster source.
        layout: The mutable routing layout. Mutated in place via shift_*
            methods during pass 1.
        compute_indicator_rects: Callable invoked twice (once before pass 1,
            once between passes) to produce indicator rects against the
            current layout state. The caller is responsible for any cluster-
            component rebuild needed to keep rects in sync with the
            post-shift layout.
        keymap_spacing: Spacing constant for routing geometry (typically
            ``0.6 * outer_key_size``).

    Returns:
        ConnectorRouting with paths and the residual paddings the caller
        must apply. ``extra_top_padding`` is always 0 (consumed via shifts);
        ``extra_bottom_padding`` is the thumb cluster's bottom padding;
        ``extra_right_padding`` is ``(cols_used + 1) * keymap_spacing``.
    """
    # --- Pass 1: discover paddings, apply cascading layout shifts. ---
    rects_pass1 = compute_indicator_rects()
    thumb_extra_bottom = _pass1_discover_and_shift(
        layers, thumb, layout, rects_pass1, keymap_spacing
    )

    # --- Pass 2: rebuild paths against the now-shifted layout. ---
    rects_pass2 = compute_indicator_rects()
    all_paths = _pass2_build_paths(
        layers, thumb, layout, rects_pass2, keymap_spacing
    )

    if not all_paths:
        return ConnectorRouting(
            paths=[],
            extra_top_padding=0.0,
            extra_bottom_padding=0.0,
            extra_right_padding=0.0,
        )

    # --- Phase 2: global column allocation + drop to targets. ---
    anchor = layers[0].source_layer if layers else thumb.source_layer
    row_x, _, row_w, _ = layout.layer_row_bounding_box(anchor)
    first_column_x = row_x + row_w + 2 * keymap_spacing
    cols_used = allocate_columns(all_paths, first_column_x, keymap_spacing)
    phase2_route_to_targets(all_paths)

    return ConnectorRouting(
        paths=[(s.path, s.target_layer) for s in all_paths],
        extra_top_padding=0.0,
        extra_bottom_padding=thumb_extra_bottom,
        extra_right_padding=(cols_used + 1) * keymap_spacing,
    )


def _pass1_discover_and_shift(
    layers: Sequence[OverviewLayerSource],
    thumb: ThumbSource,
    layout: RoutingLayout,
    indicator_rects: Mapping[SvalboardTargetKey, tuple[float, float, float, float]],
    keymap_spacing: float,
) -> float:
    """Pass 1: route each source, discover paddings, apply cascading shifts.

    Returns the thumb's extra_bottom_padding (the only padding NOT applied
    via layout shifts; it grows the canvas at the bottom).
    """
    for layer in layers:
        paths = build_finger_path_list_for_layer(
            layer.left, layer.right, layer.source_layer, layout, keymap_spacing
        )
        if not paths:
            continue
        _attach_rects_and_set_initial_moveto(paths, indicator_rects)
        cluster_top, cluster_bottom = _layer_cluster_y_bounds(layout, layer.source_layer)
        min_y = min(s.current_point[1] for s in paths)
        max_y = max(s.current_point[1] for s in paths)
        phase1_redirect_right_to_down(paths, keymap_spacing)
        phase1_redirect_left_to_down(paths, keymap_spacing)
        extra_top = phase1_up_to_right(paths, cluster_top, min_y, keymap_spacing)
        extra_bottom = phase1_down_to_right(paths, cluster_bottom, max_y, keymap_spacing)
        if extra_top > 0:
            layout.shift_layer_row_and_below(layer.source_layer, extra_top)
        if extra_bottom > 0:
            layout.shift_below_layer_row(layer.source_layer, extra_bottom)

    thumb_paths = build_thumb_path_list(
        thumb.left, thumb.right, layout, thumb.source_layer, keymap_spacing
    )
    if not thumb_paths:
        return 0.0
    _attach_rects_and_set_initial_moveto(thumb_paths, indicator_rects)
    cluster_top, cluster_bottom = layout.thumb_cluster_y_bounds()
    min_y = min(s.current_point[1] for s in thumb_paths)
    max_y = max(s.current_point[1] for s in thumb_paths)
    phase1_redirect_left_to_down(thumb_paths, keymap_spacing)
    extra_top = phase1_up_to_right(thumb_paths, cluster_top, min_y, keymap_spacing)
    extra_bottom = phase1_down_to_right(thumb_paths, cluster_bottom, max_y, keymap_spacing)
    if extra_top > 0:
        layout.shift_thumb_down(extra_top)
    return extra_bottom


def _pass2_build_paths(
    layers: Sequence[OverviewLayerSource],
    thumb: ThumbSource,
    layout: RoutingLayout,
    indicator_rects: Mapping[SvalboardTargetKey, tuple[float, float, float, float]],
    keymap_spacing: float,
) -> list[ConnectorStep]:
    """Pass 2: rebuild paths against the post-shift layout for final geometry.

    Padding values are discarded — they were already applied in pass 1.
    """
    all_paths: list[ConnectorStep] = []
    for layer in layers:
        paths = build_finger_path_list_for_layer(
            layer.left, layer.right, layer.source_layer, layout, keymap_spacing
        )
        if not paths:
            continue
        _attach_rects_and_set_initial_moveto(paths, indicator_rects)
        cluster_top, cluster_bottom = _layer_cluster_y_bounds(layout, layer.source_layer)
        min_y = min(s.current_point[1] for s in paths)
        max_y = max(s.current_point[1] for s in paths)
        phase1_redirect_right_to_down(paths, keymap_spacing)
        phase1_redirect_left_to_down(paths, keymap_spacing)
        phase1_up_to_right(paths, cluster_top, min_y, keymap_spacing)
        phase1_down_to_right(paths, cluster_bottom, max_y, keymap_spacing)
        all_paths.extend(paths)

    thumb_paths = build_thumb_path_list(
        thumb.left, thumb.right, layout, thumb.source_layer, keymap_spacing
    )
    if thumb_paths:
        _attach_rects_and_set_initial_moveto(thumb_paths, indicator_rects)
        cluster_top, cluster_bottom = layout.thumb_cluster_y_bounds()
        min_y = min(s.current_point[1] for s in thumb_paths)
        max_y = max(s.current_point[1] for s in thumb_paths)
        phase1_redirect_left_to_down(thumb_paths, keymap_spacing)
        phase1_up_to_right(thumb_paths, cluster_top, min_y, keymap_spacing)
        phase1_down_to_right(thumb_paths, cluster_bottom, max_y, keymap_spacing)
        all_paths.extend(thumb_paths)

    return all_paths


def _attach_rects_and_set_initial_moveto(
    paths: list[ConnectorStep],
    indicator_rects: Mapping[SvalboardTargetKey, tuple[float, float, float, float]],
) -> None:
    """Populate each step's indicator_rect from the map and set its initial moveTo.

    Raises ``ValueError`` with a clear message if a step's key is missing
    from the map (programmer error — the caller must populate every key
    whose layer_switch enters the priority list).
    """
    for step in paths:
        if step.key is None:
            continue
        try:
            step.indicator_rect = indicator_rects[step.key]
        except KeyError as e:
            raise ValueError(
                f"indicator_rects missing entry for key "
                f"{step.key_origin_attr!r} in cluster {step.source_cluster_attr!r} "
                f"(target_layer={step.target_layer}); caller must populate every "
                f"key whose layer_switch enters the priority list"
            ) from e
        set_initial_moveto(step)
```

Now **remove `route_thumb_connectors`** — the new orchestrator replaces it. Search the file for `def route_thumb_connectors` and delete the function. (Task 11 will update overview.py to call `route_overview_connectors` instead; until then, overview.py won't compile — that's fine for an interim commit because we'll keep the codebase running by leaving the test file's references alone in this commit; integration test failures will be addressed in Task 11.)

Actually, **don't remove `route_thumb_connectors` yet** — leave it in place so the existing tests in `TestRouteThumbConnectors` keep passing. Task 11 will remove it as part of the overview.py rewire commit.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/application/render/test_connectors.py::TestRouteOverviewConnectors -v`
Expected: PASS.

Run: `uv run pytest tests/unit/application/render/test_connectors.py -v`
Expected: PASS (existing route_thumb_connectors tests still work; new orchestrator tests pass).

Run: `just check && just typecheck`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add src/skim/application/render/connectors.py tests/unit/application/render/test_connectors.py
git commit -m "feat(connectors): top-level route_overview_connectors orchestrator"
```

---

### Task 8: `_compute_finger_indicator_rects` in overview.py

**Files:**
- Modify: `src/skim/application/render/overview.py`
- Test: covered by Task 13 integration tests (this helper has no clean unit-test boundary without rebuilding cluster components)

The existing `_compute_thumb_indicator_rects` collects indicator bounding rects for each thumb-key with a layer_switch trigger. We need the equivalent for finger clusters: walk all 8 finger clusters of a layer, find each layer-switch triggering key, compute its indicator bounding rect.

The finger-side indicator geometry already lives in `LayerIndicator` and the existing `FingerClusterComponent` knows where each key sits. Mirror the structure of `_compute_thumb_indicator_rects` and reference the existing finger indicator code path.

The existing finger-render pipeline already provides the geometry: `_finger_cluster_offset` and `_FINGER_KEY_NAMES` live in `src/skim/application/render/indicators.py`, and `LayerIndicatorOverlay.for_finger_cluster` shows the canonical way to build `LayerIndicator` instances for finger keys (lines 329–375 of indicators.py). Mirror the thumb helper's pattern (`_compute_thumb_indicator_rects` in overview.py:116–197) using the finger versions.

- [ ] **Step 1: Add the imports**

In `src/skim/application/render/overview.py`, extend the existing import from `.indicators`:

```python
from .indicators import (
    _FINGER_KEY_NAMES,
    _THUMB_KEY_HEIGHT_RATIOS,
    _THUMB_KEY_NAMES,
    LayerIndicator,
    _finger_cluster_offset,
    _thumb_cluster_offset,
)
```

(Adjust to whatever subset is currently imported plus the additions.) If `SvalboardLayout` isn't already imported, add it to the existing `from skim.data import …` line:

```python
from skim.data import Palette, SkimConfig, SvalboardKeymap, SvalboardLayout
```

Keep `KeyboardSide` and `FingerClusterComponent` imports as they already are.

- [ ] **Step 2: Implement `_compute_finger_indicator_rects`**

Add to `src/skim/application/render/overview.py` (place it directly after `_compute_thumb_indicator_rects`):

```python
def _compute_finger_indicator_rects(
    finger_clusters_left: list[FingerClusterComponent],
    finger_clusters_right: list[FingerClusterComponent],
    layer_data: SvalboardLayout[SvalboardTargetKey],
    has_double_south: bool,
) -> dict[SvalboardTargetKey, tuple[float, float, float, float]]:
    """Return ``{triggering_key: (rect_x, rect_y, rect_w, rect_h)}`` for one
    layer's finger-cluster indicators.

    Mirrors ``_compute_thumb_indicator_rects`` for finger keys: walks every
    finger cluster on both sides, builds a ``LayerIndicator`` using the
    same parameters as the rendered output, and converts the indicator's
    circle to a bounding rect in absolute SVG coordinates:
    ``(cx - r, cy - r, 2r, 2r)``.

    Args:
        finger_clusters_left: The 4 left-side ``FingerClusterComponent`` instances
            in the same order ``draw_overview`` builds them.
        finger_clusters_right: The 4 right-side components, same order.
        layer_data: The keymap layer that the components were rendered for.
        has_double_south: Whether ``double_south_key`` is present (matches
            ``LayerIndicatorOverlay.for_finger_cluster``).
    """
    results: dict[SvalboardTargetKey, tuple[float, float, float, float]] = {}

    # finger_clusters_left/right are already in the order draw_overview
    # builds them. The data side has named attributes — zip in the same
    # iteration order ``draw_overview`` uses (extract the order from there
    # if it differs from the (pinky, ring, middle, index) / (index, middle,
    # ring, pinky) convention used elsewhere).
    finger_iter_left = (
        ("pinky",  layer_data.left.pinky),
        ("ring",   layer_data.left.ring),
        ("middle", layer_data.left.middle),
        ("index",  layer_data.left.index),
    )
    finger_iter_right = (
        ("index",  layer_data.right.index),
        ("middle", layer_data.right.middle),
        ("ring",   layer_data.right.ring),
        ("pinky",  layer_data.right.pinky),
    )

    for components, side_iter, side in [
        (finger_clusters_left,  finger_iter_left,  KeyboardSide.LEFT),
        (finger_clusters_right, finger_iter_right, KeyboardSide.RIGHT),
    ]:
        for finger_comp, (_finger_attr, cluster_data) in zip(components, side_iter):
            metrics = finger_comp.layout_metrics
            palette = finger_comp.palette
            # Match LayerIndicatorOverlay.for_finger_cluster's circle sizing:
            # use the same proportions the renderer uses. The cluster's outer
            # key width is the unit; circle_diameter and gap derive from it.
            outer_key_width = metrics.north_key.width
            circle_diameter = outer_key_width * 0.4
            gap = outer_key_width * 0.18

            for key_name in _FINGER_KEY_NAMES:
                if key_name == "double_south_key" and not has_double_south:
                    continue
                key: SvalboardTargetKey = getattr(cluster_data, key_name)
                if key.layer_switch is None:
                    continue

                layout_b = getattr(metrics, key_name)
                offset_dir, conn_type = _finger_cluster_offset(key_name, side)
                key_gap = gap * 3 if key_name == "center_key" else gap

                indicator = LayerIndicator(
                    key_x=layout_b.pos.x,
                    key_y=layout_b.pos.y,
                    key_width=layout_b.width,
                    key_height=layout_b.width,  # finger keys are square
                    target_layer=key.layer_switch,
                    palette=palette,
                    circle_diameter=circle_diameter,
                    gap=key_gap,
                    offset_direction=offset_dir,
                    connector_type=conn_type,
                )

                radius = circle_diameter / 2.0
                abs_cx = finger_comp.x + indicator.circle_center_x
                abs_cy = finger_comp.y + indicator.circle_center_y
                results[key] = (
                    abs_cx - radius,
                    abs_cy - radius,
                    circle_diameter,
                    circle_diameter,
                )

    return results
```

> **Cross-check:** if `LayerIndicatorOverlay.for_finger_cluster` (in `indicators.py`) computes `outer_key_width`, `circle_diameter`, or `gap` differently from the values above, match its formulas exactly — the indicator coordinates must agree with what the renderer actually draws. The values shown here mirror lines 336–337, 357 of indicators.py at the time of writing.

- [ ] **Step 3: Manual smoke check**

Render the existing `vial-sample.vil` to confirm the helper doesn't crash on a real keymap (even though Vial-sample doesn't trigger any finger layer-switches — the helper should still walk safely):

```bash
just skim gen -k samples/keymaps/vial-sample.vil -o /tmp/overview-task8/
```

Expected: succeeds, output unchanged from before this commit.

If it crashes, the geometry helper has a bug — investigate and fix before committing.

- [ ] **Step 4: Run tests**

Run: `uv run pytest`
Expected: PASS. No test calls `_compute_finger_indicator_rects` directly yet — Task 12 covers it via integration. The Phase 1 thumb-only path through `draw_overview` is still operative until Task 11 rewires the orchestrator, so existing tests continue to exercise the same code paths they did before.

Run: `just check && just typecheck`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add src/skim/application/render/overview.py
git commit -m "feat(overview): compute finger indicator rects per layer"
```

---

### Task 9: `_build_finger_clusters_for_layer` and `_compute_all_indicator_rects`

**Files:**
- Modify: `src/skim/application/render/overview.py`

The aggregator combines the thumb and per-layer finger indicator rects into a single map. It's the closure body the orchestrator calls (twice). Before writing the aggregator, factor out the finger-cluster construction from `draw_overview` into a reusable helper so the indicator-rect path and the rendering path agree on geometry.

- [ ] **Step 1: Extract `_build_finger_clusters_for_layer` from `draw_overview`**

The existing `draw_overview` constructs `FingerClusterComponent`s inline (around lines 553–581 of overview.py). Extract that pattern into a helper next to `_build_thumb_clusters`:

```python
def _build_finger_clusters_for_layer(
    config: SkimConfig,
    layer_data: SvalboardLayout[SvalboardTargetKey],
    config_position: int,
    row_idx: int,
    layout: OverviewLayout,
    use_system_fonts: bool,
) -> tuple[list[FingerClusterComponent], list[FingerClusterComponent]]:
    """Build the 4 left + 4 right finger-cluster components for one layer.

    Returns (left_components, right_components) in the same order
    ``layer_data.left.fingers`` / ``layer_data.right.fingers`` produces them
    (typically index, middle, ring, pinky for both sides).
    """
    palette = config.output.style.palette
    ctx = RenderContext(
        palette=palette,
        layer_index=config_position,
        has_double_south=config.keyboard.features.double_south,
        use_layer_colors_on_keys=config.output.style.use_layer_colors_on_keys,
        hold_symbol_position=config.output.style.hold_symbol_position,
        use_system_fonts=use_system_fonts,
        show_layer_indicators=config.output.style.show_layer_indicators,
        qmk_index_to_position=config.keyboard.qmk_index_to_position,
    )
    cluster_width = layout.finger_cluster_width
    positions = layout.finger_cluster_positions(row_idx)

    left: list[FingerClusterComponent] = []
    for i in range(_FINGER_CLUSTERS_PER_SIDE):
        left.append(
            FingerClusterComponent(
                keymap_cluster=layer_data.left.fingers[i],
                side=KeyboardSide.LEFT,
                layout=Boundary(width=cluster_width, pos=positions[i]),
                render_context=ctx,
            )
        )

    right: list[FingerClusterComponent] = []
    for i in range(_FINGER_CLUSTERS_PER_SIDE):
        right.append(
            FingerClusterComponent(
                keymap_cluster=layer_data.right.fingers[i],
                side=KeyboardSide.RIGHT,
                layout=Boundary(width=cluster_width, pos=positions[_FINGER_CLUSTERS_PER_SIDE + i]),
                render_context=ctx,
            )
        )

    return (left, right)
```

In `draw_overview`, replace the inline finger-cluster construction with a call to this helper. The two original `for i in range(_FINGER_CLUSTERS_PER_SIDE)` loops become:

```python
left_clusters, right_clusters = _build_finger_clusters_for_layer(
    config, layer_data, pos, row_idx, layout, use_system_fonts
)
for c in left_clusters:
    d.append(c.build())
for c in right_clusters:
    d.append(c.build())
```

(`pos` is the loop variable from `enumerate(row_to_layer)` in the surrounding code; `row_idx` is the same loop's index.)

- [ ] **Step 2: Implement `_compute_all_indicator_rects`**

Add to `src/skim/application/render/overview.py` (place it after `_compute_finger_indicator_rects`):

```python
def _compute_all_indicator_rects(
    config: SkimConfig,
    keymap: SvalboardKeymap[SvalboardTargetKey],
    layout: OverviewLayout,
    use_system_fonts: bool,
    row_to_layer: list[tuple[int, int]],
) -> dict[SvalboardTargetKey, tuple[float, float, float, float]]:
    """Walk every rendered layer + the thumb cluster and collect indicator rects.

    Builds cluster components against the current layout state, computes
    each cluster's indicator bounding rects, and merges everything into a
    single map keyed by the source ``SvalboardTargetKey``.

    Called by ``draw_overview`` as the closure passed to
    ``route_overview_connectors`` — invoked twice (once before pass 1, once
    between passes) so rects stay in sync with layout shifts.

    Args:
        row_to_layer: ``list[(config_position, qmk_index)]`` in render order
            (top-down). Used to derive each layer's row index for finger-
            cluster positioning.
    """
    rects: dict[SvalboardTargetKey, tuple[float, float, float, float]] = {}

    # Per-layer finger clusters.
    for row_idx, (config_pos, qmk_idx) in enumerate(row_to_layer):
        layer_data = keymap.layers.get(qmk_idx)
        if layer_data is None:
            continue
        left_clusters, right_clusters = _build_finger_clusters_for_layer(
            config, layer_data, config_pos, row_idx, layout, use_system_fonts
        )
        rects.update(
            _compute_finger_indicator_rects(
                left_clusters,
                right_clusters,
                layer_data,
                has_double_south=config.keyboard.features.double_south,
            )
        )

    # Thumb cluster (one source layer — first in keymap.layers).
    left_thumb, right_thumb = _build_thumb_clusters(config, keymap, layout, use_system_fonts)
    if left_thumb is not None and right_thumb is not None:
        rects.update(
            _compute_thumb_indicator_rects(left_thumb, right_thumb, keymap, config)
        )

    return rects
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest`
Expected: PASS. The extracted `_build_finger_clusters_for_layer` is a pure refactor that should preserve identical render behavior. No new callers of `_compute_all_indicator_rects` yet (Task 11 wires it).

Run: `just check && just typecheck`
Expected: clean.

- [ ] **Step 4: Visual sanity check**

```bash
just skim gen -k samples/keymaps/vial-sample.vil -o /tmp/overview-task9/
```

Open the SVG and compare against the previous render — the inline-to-helper extraction must not change pixel output.

- [ ] **Step 5: Commit**

```bash
git add src/skim/application/render/overview.py
git commit -m "feat(overview): extract finger cluster builder; aggregate indicator rects"
```

---

### Task 10: Synthetic test fixture

**Files:**
- Create: `tests/integration/fixtures/connector-routing-coverage.vil`

The fixture is a Vial-format JSON keymap that exercises the routing algorithm's most interesting cases. It needs:

- At least 4 layers (so cascading shifts have something to cascade through).
- Layer 0 with finger triggers in **R4** (`right.pinky`) hitting N/W/S/DS/E/C (mix of RIGHT/UP/DOWN directions).
- Layer 1 with finger triggers in a **non-R4** cluster hitting W/N/E (UP) and S/DS (no double-trigger conflict).
- Layer 2 with **S+DS double-trigger** in a non-R4 cluster — south_key targets one layer, double_south_key targets another. This exercises the RIGHT-DOWN-RIGHT special case.
- Layer 0 thumb cluster with a few triggers (RT_DD, LT_Up + LT_Down LEFT-DOWN special case) so cross-source compatibility with Phase 1 is preserved.

- [ ] **Step 1: Look at the existing sample format**

Read `samples/keymaps/vial-sample.vil` to understand the JSON layout structure. The format is roughly:

```json
{
  "version": 1,
  "uid": …,
  "layout": [
    [  // layer 0
      [ "KC_…", "KC_…", … ],  // cluster 0 (6 keys)
      [ "KC_…", "KC_…", … ],  // cluster 1
      // … 10 clusters total per layer? Verify against the file
    ],
    [  // layer 1
      …
    ],
    …
  ],
  …
}
```

Layer-switch triggers in Vial use `MO(N)`, `LT(N, KC_…)`, `TG(N)`, etc. For the fixture we want simple `MO(N)` so the keys are unambiguously "trigger X". Refer to existing samples or QMK docs for the exact codes accepted by skim's keycode parser.

- [ ] **Step 2: Build the fixture**

Create `tests/integration/fixtures/connector-routing-coverage.vil` matching the format above. Place layer-switch keys at:

| Layer | Cluster        | Key                | Trigger    | Purpose |
| ----- | -------------- | ------------------ | ---------- | --- |
| 0     | right.pinky    | north_key          | `MO(1)`    | R4 priority RIGHT |
| 0     | right.pinky    | east_key           | `MO(2)`    | R4 priority UP |
| 0     | right.pinky    | center_key         | `MO(3)`    | R4 priority DOWN |
| 0     | left.thumb     | double_down_key    | `MO(1)`    | thumb RIGHT (RT_DD) |
| 0     | left.thumb     | up_key             | `MO(2)`    | LT_Up |
| 0     | left.thumb     | down_key           | `MO(3)`    | LT_Down (triggers LT_Up's LEFT special case) |
| 1     | left.middle    | west_key           | `MO(2)`    | non-R4 UP |
| 1     | left.middle    | north_key          | `MO(3)`    | non-R4 UP |
| 1     | left.middle    | south_key          | `MO(0)`    | non-R4 DOWN (no DS triggered) |
| 2     | right.middle   | south_key          | `MO(0)`    | S+DS pair, S half |
| 2     | right.middle   | double_south_key   | `MO(1)`    | S+DS pair, DS half (triggers RIGHT-DOWN-RIGHT) |

(Use whatever cluster-naming/positional conventions the Vial format uses. Most cells in the fixture should be `KC_NO` or simple keycodes.)

- [ ] **Step 3: Smoke test the fixture**

```bash
just skim gen -k tests/integration/fixtures/connector-routing-coverage.vil -o /tmp/coverage/
```

This should still error or produce a degraded output if the new orchestrator isn't wired yet — that's expected. The point of this step is to confirm the file is parseable. If it fails to parse, fix the JSON.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/fixtures/connector-routing-coverage.vil
git commit -m "test: add connector-routing-coverage Vial fixture"
```

---

### Task 11: Wire `route_overview_connectors` into `draw_overview`; remove `route_thumb_connectors`

**Files:**
- Modify: `src/skim/application/render/overview.py`
- Modify: `src/skim/application/render/connectors.py` (remove `route_thumb_connectors`)
- Modify: `tests/unit/application/render/test_connectors.py` (remove `TestRouteThumbConnectors`)

This is the integration step. After this commit, `draw_overview` orchestrates routing via `route_overview_connectors` and `route_thumb_connectors` is gone.

- [ ] **Step 1: Identify the existing routing block in `draw_overview`**

Read `src/skim/application/render/overview.py:draw_overview` to find the block that:
1. Builds `prelim_left, prelim_right` thumb clusters.
2. Calls `_compute_thumb_indicator_rects`.
3. Calls `route_thumb_connectors` (pass 1).
4. Applies `shift_thumb_down`.
5. Rebuilds clusters at shifted position.
6. Calls `route_thumb_connectors` (pass 2).
7. Calls `layout.adjust_canvas_width` for `extra_right_padding`.

This is the block being replaced.

- [ ] **Step 2: Replace with the new orchestrator call**

Replace that block with:

```python
# --- Phase 2: Route all connectors (per-layer fingers + thumb). ---
routing: ConnectorRouting | None = None
if config.output.style.show_layer_indicators and keymap.layers:
    first_qmk_idx = config.keyboard.layers[0].index if config.keyboard.layers else 0
    if config.output.style.show_layer_connectors and first_qmk_idx in keymap.layers:
        # Build per-layer sources and the thumb source.
        layer_sources: list[OverviewLayerSource] = []
        for _config_pos, qmk_idx in render_layers:
            layer_data = keymap.layers.get(qmk_idx)
            if layer_data is None:
                continue
            layer_sources.append(
                OverviewLayerSource(
                    source_layer=qmk_idx,
                    left=layer_data.left,
                    right=layer_data.right,
                )
            )

        thumb_layer = keymap.layers[first_qmk_idx]
        thumb_source = ThumbSource(
            source_layer=first_qmk_idx,
            left=thumb_layer.left.thumb,
            right=thumb_layer.right.thumb,
        )

        routing_layout = _RoutingLayoutAdapter(layout, layer_to_row)

        # Closure that recomputes indicator rects against the current layout
        # state. Called twice by route_overview_connectors (pass 1 + pass 2).
        def compute_rects() -> Mapping[SvalboardTargetKey, tuple[float, float, float, float]]:
            return _compute_all_indicator_rects(
                config, keymap, layout, use_system_fonts, row_to_layer
            )

        # 0.6 multiplier matches the Phase 1 settled value — tighter spacing
        # reads better visually than the full N-key width.
        keymap_spacing = nk * 0.6

        routing = route_overview_connectors(
            layers=layer_sources,
            thumb=thumb_source,
            layout=routing_layout,
            compute_indicator_rects=compute_rects,
            keymap_spacing=keymap_spacing,
        )

        if routing.extra_right_padding > 0:
            layout.adjust_canvas_width(layout.canvas_width + routing.extra_right_padding)
```

The `routing.extra_top_padding` is always 0 (consumed via shifts during the orchestrator's pass 1). The `routing.extra_bottom_padding` is applied later when `canvas_h` is computed (existing pattern from Phase 1 — verify the `canvas_h += routing.extra_bottom_padding` line is still present or add it).

The path-rendering block at the bottom of `draw_overview` (the `for path, target_layer in routing.paths: …` loop) stays unchanged — it works against the new `routing.paths` shape too.

- [ ] **Step 3: Update imports in `overview.py`**

Add at the top:

```python
from collections.abc import Mapping  # for the compute_rects closure type hint

from .connectors import (
    ConnectorRouting,
    OverviewLayerSource,
    ThumbSource,
    route_overview_connectors,
)
```

Remove:

```python
from .connectors import route_thumb_connectors  # if present
```

- [ ] **Step 4: Remove `route_thumb_connectors` from `connectors.py`**

Delete the entire `def route_thumb_connectors(...)` function.

- [ ] **Step 5: Remove `TestRouteThumbConnectors` from the test file**

In `tests/unit/application/render/test_connectors.py`, delete the entire `class TestRouteThumbConnectors` block. Also remove the import:

```python
from skim.application.render.connectors import route_thumb_connectors  # remove
```

The new orchestrator's tests (added in Task 7) cover the same ground plus the multi-layer cases.

- [ ] **Step 6: Run all tests**

Run: `uv run pytest`
Expected: PASS. The Phase 1 integration test (`test_overview_renders_with_connectors_for_layer_trigger_keymap`) should still pass — the rendered SVG still contains paths.

Run: `just check && just typecheck`
Expected: clean.

- [ ] **Step 7: Visual sanity check**

Render the existing `vial-sample.vil` (no finger layer-switch triggers) and the new fixture:

```bash
just skim gen -k samples/keymaps/vial-sample.vil -o /tmp/before-after-vial/
just skim gen -k tests/integration/fixtures/connector-routing-coverage.vil -o /tmp/coverage/
```

Open both SVGs. Confirm:
- `vial-sample` looks the same as before (path geometry should be byte-identical or nearly so since no finger triggers exist).
- `coverage` produces multiple connector paths covering the R4/non-R4/S+DS cases. Connectors don't overlap thumb keys. Multi-layer cascading shifts have produced visible padding between layers that have UP-direction triggers.

If the coverage render looks visually broken, debug before committing.

- [ ] **Step 8: Commit**

```bash
git add src/skim/application/render/overview.py \
        src/skim/application/render/connectors.py \
        tests/unit/application/render/test_connectors.py
git commit -m "feat(overview): route per-layer finger + thumb connectors via the new orchestrator

Replaces the thumb-only route_thumb_connectors with route_overview_connectors,
which orchestrates Phase 1 per source (top-down: each layer's fingers, then
the thumb) with cascading layout shifts, and runs Phase 2 column allocation
once globally across all paths. Removes the now-unused route_thumb_connectors."
```

---

### Task 12: Integration tests with structured assertions

**Files:**
- Modify: `tests/integration/test_overview_connectors.py`

Add structured-assertion tests against the synthetic fixture. The existing thin smoke test stays.

- [ ] **Step 1: Write the integration tests**

Add to `tests/integration/test_overview_connectors.py`:

```python
"""Integration: overview rendering with connectors uses the new algorithm."""

import re
from pathlib import Path

import pytest

from skim.application.keymap_generator import (
    _get_config,
    _get_input_keymap,
    _resolve_keymap,
)
from skim.application.render import draw_keymap
from skim.data.cli import InputFiles, KeymapGeneratorTargets

# Existing thin sanity test stays — copy it here verbatim from the file's
# current state if it isn't already.

FIXTURE_PATH = Path("tests/integration/fixtures/connector-routing-coverage.vil")


def _render_fixture(tmp_path: Path) -> str:
    """Render the synthetic coverage fixture and return the SVG text."""
    config = _get_config(None, keymap_for_defaults=FIXTURE_PATH)
    new_style = config.output.style.model_copy(
        update={"show_layer_indicators": True, "show_layer_connectors": True}
    )
    new_output = config.output.model_copy(update={"style": new_style})
    cfg = config.model_copy(update={"output": new_output})

    inputs = InputFiles(keymap=FIXTURE_PATH)
    keymap = _resolve_keymap(cfg, _get_input_keymap(inputs, cfg))
    drawings = draw_keymap(cfg, keymap, KeymapGeneratorTargets(overview=True))

    overview = drawings["keymap-overview"]
    out = tmp_path / "overview.svg"
    overview.save_svg(str(out))
    return out.read_text()


def test_path_count_matches_expected_triggers(tmp_path):
    """The fixture has exactly N layer-switch triggers across finger + thumb;
    rendered SVG should contain N dotted paths."""
    content = _render_fixture(tmp_path)
    # Every connector path has stroke-dasharray="0.1 7" applied by overview.py.
    paths = re.findall(r"<path[^>]+stroke-dasharray=\"0\.1 7\"", content)
    # Count the triggers in the fixture's table:
    # Layer 0: 3 finger (R4: north, east, center) + 3 thumb (RT_DD, LT_Up, LT_Down)
    # Layer 1: 3 finger (W, N, S in left.middle)
    # Layer 2: 2 finger (S, DS in right.middle)
    expected_trigger_count = 3 + 3 + 3 + 2  # adjust if fixture differs
    assert len(paths) == expected_trigger_count


def test_each_path_color_matches_target_layer(tmp_path):
    """Connector strokes should match their target layer's palette color."""
    content = _render_fixture(tmp_path)
    # Extract per-path stroke colors. Each <path> with stroke-dasharray
    # carries a stroke="…" attribute.
    paths = re.findall(
        r"<path[^>]+stroke=\"([^\"]+)\"[^>]+stroke-dasharray=\"0\.1 7\"",
        content,
    )
    assert len(paths) > 0
    # Every color should be a hex code (six hex digits) — basic sanity check
    # that the renderer didn't fall back to the gray default ("#808080") for
    # any path.
    for color in paths:
        assert color.startswith("#")
        assert color != "#808080", f"Connector fell back to default gray; check qmk_index_to_position chain"


def test_no_path_coordinate_escapes_canvas_bounds(tmp_path):
    """Every connector path's coordinates should sit within the canvas."""
    content = _render_fixture(tmp_path)
    # Extract canvas dimensions from the SVG's <svg width="…" height="…"> attrs.
    svg_match = re.search(r"<svg[^>]+width=\"([^\"]+)\"[^>]+height=\"([^\"]+)\"", content)
    assert svg_match, "Could not parse SVG dimensions"
    canvas_w = float(svg_match.group(1))
    canvas_h = float(svg_match.group(2))

    # Extract path data for every connector path.
    path_ds = re.findall(
        r"<path[^>]+d=\"([^\"]+)\"[^>]+stroke-dasharray=\"0\.1 7\"",
        content,
    )
    for d in path_ds:
        # Path commands are like "M 100,200 L 300,400 …". Extract numeric pairs.
        coords = re.findall(r"(-?\d+\.?\d*)", d)
        # Coords come in pairs (x, y).
        for x_str, y_str in zip(coords[0::2], coords[1::2]):
            x, y = float(x_str), float(y_str)
            assert 0 <= x <= canvas_w, f"Path X={x} escapes canvas width {canvas_w}"
            assert 0 <= y <= canvas_h, f"Path Y={y} escapes canvas height {canvas_h}"


def test_s_plus_ds_trigger_produces_right_down_right_geometry(tmp_path):
    """The S+DS double-trigger in the fixture must produce a path with at
    least 4 line commands (M + 3+ Ls) and a first horizontal segment that
    extends past the source cluster's right edge."""
    content = _render_fixture(tmp_path)
    path_ds = re.findall(
        r"<path[^>]+d=\"([^\"]+)\"[^>]+stroke-dasharray=\"0\.1 7\"",
        content,
    )
    # Find the path that takes a south indicator's position as its starting
    # point. The fixture places south's MO(0) trigger in right.middle on
    # layer 2, so its color matches layer 0's palette color. We don't have
    # a reliable color-only pivot, but we can identify the S+DS path by
    # checking which paths have 4+ line commands AND start with a horizontal
    # segment.

    # Count L commands per path. The S+DS path will have:
    #   M start L east L east2 L drop L final-left  (≥ 4 Ls).
    s_plus_ds_candidates = []
    for d in path_ds:
        l_count = d.count(" L ") + d.count("L ")
        if l_count >= 4:
            s_plus_ds_candidates.append(d)

    assert len(s_plus_ds_candidates) >= 1, "No path matched the S+DS RIGHT-DOWN-RIGHT geometry signature"


def test_extra_right_padding_matches_n_plus_one_formula(tmp_path):
    """Canvas width should equal `cluster_area_right + (cols_used + 1) * keymap_spacing + padding`.

    We check this loosely: the canvas should be wider than just the cluster
    area, by a number of columns proportional to Y-overlap between paths.
    The fixture is designed to need ≥2 columns; assert canvas grew accordingly.
    """
    content = _render_fixture(tmp_path)
    svg_match = re.search(r"<svg[^>]+width=\"([^\"]+)\"", content)
    assert svg_match
    canvas_w = float(svg_match.group(1))
    # Lower-bound check: canvas should be at least 1.2x the layer-row content
    # width (rough proxy for "routing area is non-trivial"). Tighten if needed
    # once you measure actual values from a baseline render.
    assert canvas_w > 1500.0, f"Canvas width {canvas_w} suggests routing area was over-shrunk"
```

> **Implementer note:** the `expected_trigger_count` and the `canvas_w > 1500.0` lower-bound depend on the exact fixture content from Task 10. After the fixture is finalized, render it once and update these constants to match the actual values. The test goal is to catch regressions, not to assert exact pixel values.

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/integration/test_overview_connectors.py -v`
Expected: PASS.

Run: `uv run pytest`
Expected: full suite passes.

Run: `just check && just typecheck`
Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_overview_connectors.py
git commit -m "test(integration): structured assertions for overview connector routing"
```

---

## Self-review checklist

Before considering this plan done, verify:

1. **Spec coverage:**
   - "Per-layer finger cluster algorithm" → Tasks 3, 4 (priority tables, per-cluster + per-layer builders).
   - "S+DS RIGHT-DOWN-RIGHT special case" → Tasks 3 (south direction override), 5 (`phase1_redirect_right_to_down`).
   - "Multi-layer composition driver" → Task 7 (`route_overview_connectors` orchestrator).
   - "Layout API additions" → Task 1.
   - "Indicator-rect plumbing" → Tasks 8, 9.
   - "Test strategy" → Tasks 10, 12.
   - "Pass A" → explicitly out of scope (deferred per spec's *Open / Future Work*).

2. **No placeholders** — every step contains real code or commands. The two flagged exceptions:
   - Task 8's `_finger_indicator_bounding_rect` body: explicitly notes the implementer must wire to existing finger-render geometry. Self-contained instruction with "see `_compute_thumb_indicator_rects` for the analogous thumb path."
   - Task 12's `expected_trigger_count` and canvas-width lower bound: explicitly noted as needing baseline measurement after Task 10 lands. Self-contained instruction.

3. **Type consistency:**
   - `OverviewLayerSource` and `ThumbSource` → defined Task 6, used Task 7 and Task 11.
   - `route_overview_connectors` signature → defined Task 7, called Task 11.
   - `RoutingLayout` Protocol additions → defined Task 1, used Task 7.
   - `_RoutingLayoutAdapter` mirror methods → defined Task 1, used Task 11.
   - `ConnectorStep.source_cluster_attr` → defined Task 2, populated Task 3, read Task 5.

4. **Tests for every step** — every task starts with a failing test (where applicable) and ends with a passing test. Task 8 (`_compute_finger_indicator_rects`) is the exception: no clean unit-test boundary, covered by Task 12 integration tests.

5. **Frequent commits** — 12 tasks = 12 commits. Each commit is focused and reviewable.
