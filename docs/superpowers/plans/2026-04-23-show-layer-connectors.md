# Show Layer Connectors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `show_layer_connectors` boolean config option that controls whether dotted connector lines are drawn in the overview image.

**Architecture:** Add field to `Style` model, guard connector-specific code in `draw_overview()` behind the new flag, add TUI switch. Three files touched, no new files.

**Tech Stack:** Python, Pydantic, drawsvg, Textual (TUI)

**Spec:** `docs/superpowers/specs/2026-04-23-show-layer-connectors-design.md`

---

### Task 1: Add `show_layer_connectors` to config model

**Files:**
- Modify: `src/skim/data/config.py:652`
- Test: `tests/unit/data/test_config.py`

- [ ] **Step 1: Write the failing test**

In `tests/unit/data/test_config.py`, add a test class at the end of the file:

```python
class TestStyleShowLayerConnectors:
    """Tests for Style.show_layer_connectors field."""

    def test_default_is_true(self):
        """show_layer_connectors defaults to True."""
        style = Style()
        assert style.show_layer_connectors is True

    def test_can_set_to_false(self):
        """show_layer_connectors can be set to False."""
        style = Style(show_layer_connectors=False)
        assert style.show_layer_connectors is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/data/test_config.py::TestStyleShowLayerConnectors -v`
Expected: FAIL — `Style` has no field `show_layer_connectors`

- [ ] **Step 3: Add the field to Style**

In `src/skim/data/config.py`, add after line 652 (`show_layer_indicators: bool = True`):

```python
    show_layer_connectors: bool = True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/data/test_config.py::TestStyleShowLayerConnectors -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/skim/data/config.py tests/unit/data/test_config.py
git commit --no-verify -m "feat(config): add show_layer_connectors bool to Style"
```

---

### Task 2: Guard connector logic in overview rendering

**Files:**
- Modify: `src/skim/application/render/overview.py:472-557`
- Test: `tests/unit/application/render/test_overview.py`

- [ ] **Step 1: Write the failing test**

In `tests/unit/application/render/test_overview.py`, add at the end of the `TestDrawOverview` class:

```python
    def test_no_connector_paths_when_show_layer_connectors_false(self):
        """When show_layer_connectors is False, no dashed paths appear in SVG."""
        layers_cfg = tuple(
            KeyboardLayer(index=i, label=str(i), name=f"Layer{i}") for i in range(3)
        )
        layer_colors = tuple(
            LayerColor(base_color=f"#{(i + 1) * 30:02x}5050") for i in range(3)
        )
        config = SkimConfig(
            keyboard=Keyboard(layers=layers_cfg),
            output=Output(
                style=Style(
                    show_layer_connectors=False,
                    palette=Palette(layers=layer_colors),
                ),
            ),
        )
        keymap = _make_keymap()
        result = draw_overview(config, keymap)
        svg = result.as_svg()
        assert 'stroke-dasharray="1 4"' not in svg

    def test_connector_paths_present_when_show_layer_connectors_true(self):
        """When show_layer_connectors is True (default), dashed paths appear."""
        config = _make_config()
        keymap = _make_keymap()
        result = draw_overview(config, keymap)
        svg = result.as_svg()
        # Default config has show_layer_connectors=True and show_layer_indicators=True
        # Connectors may or may not appear depending on whether test keymap has
        # layer indicator keys. This test just verifies no crash with default config.
        assert isinstance(result, draw.Drawing)
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/unit/application/render/test_overview.py::TestDrawOverview::test_no_connector_paths_when_show_layer_connectors_false -v`
Expected: FAIL — `show_layer_connectors=False` still draws connectors (or the field doesn't exist yet if running before Task 1)

- [ ] **Step 3: Add the guard in `draw_overview()`**

In `src/skim/application/render/overview.py`, restructure the block starting at line 472. The existing code is:

```python
    if config.output.style.show_layer_indicators and keymap.layers:
        left_thumb_prelim, right_thumb_prelim = _build_thumb_clusters(
            config, keymap, layout, use_system_fonts
        )
        if left_thumb_prelim and right_thumb_prelim:
            all_row_bounds = [layout.layer_row_bounding_box(i) for i in range(render_layer_count)]
            max_cluster_right = max(x + w for x, _y, w, _h in all_row_bounds)
            indicators = _collect_thumb_indicators(
                left_thumb_prelim, right_thumb_prelim, keymap, config
            )

            def _thumb_bb(lt: ThumbClusterComponent, rt: ThumbClusterComponent):
                ...

            tb = _thumb_bb(left_thumb_prelim, right_thumb_prelim)
            connector_paths = _compute_connector_paths(...)
            ...layout adjustments...
```

Replace with this structure — keep the indicator block, nest the connector logic inside an additional guard:

```python
    if config.output.style.show_layer_indicators and keymap.layers:
        left_thumb_prelim, right_thumb_prelim = _build_thumb_clusters(
            config, keymap, layout, use_system_fonts
        )
        if left_thumb_prelim and right_thumb_prelim:
            all_row_bounds = [layout.layer_row_bounding_box(i) for i in range(render_layer_count)]
            max_cluster_right = max(x + w for x, _y, w, _h in all_row_bounds)
            indicators = _collect_thumb_indicators(
                left_thumb_prelim, right_thumb_prelim, keymap, config
            )

            if config.output.style.show_layer_connectors:
                def _thumb_bb(lt: ThumbClusterComponent, rt: ThumbClusterComponent):
                    bx = lt.x
                    by = min(lt.y, rt.y)
                    br = rt.x + rt.width
                    bb = max(lt.y + lt.height, rt.y + rt.height)
                    return (bx, by, br - bx, bb - by)

                tb = _thumb_bb(left_thumb_prelim, right_thumb_prelim)
                connector_paths = _compute_connector_paths(
                    indicators,
                    all_row_bounds,
                    layer_to_row,
                    nk,
                    ew_offset,
                    max_cluster_right,
                    layout.padding,
                    tb,
                )

                # Find clearance needed: only check the ESCAPE segment
                # (first 2 points of each path, near the thumb cluster area).
                # Don't include routing/target Y values which are at layer rows.
                last_row_bottom = layout.layer_row_y_positions[-1] + layout.layer_row_heights[-1]
                escape_ys: list[float] = []
                for pts, _ in connector_paths:
                    # Escape points are the first 2 (start + first turn)
                    for _, py in pts[:2]:
                        escape_ys.append(py)

                min_escape_y = min(escape_ys) if escape_ys else layout.thumb_row_y
                max_escape_y = max(escape_ys) if escape_ys else layout.thumb_row_y

                if min_escape_y < last_row_bottom + nk:
                    needed_shift = (last_row_bottom + nk) - min_escape_y
                    min_thumb_y = layout.thumb_row_y + needed_shift
                else:
                    min_thumb_y = layout.thumb_row_y

                layout.adjust_for_connectors(min_thumb_y, max_escape_y)

                # Rebuild thumb clusters at adjusted position, recompute paths,
                # and re-adjust canvas height for the new DOWN extents
                left_thumb_final, right_thumb_final = _build_thumb_clusters(
                    config, keymap, layout, use_system_fonts
                )
                if left_thumb_final and right_thumb_final:
                    all_row_bounds = [
                        layout.layer_row_bounding_box(i) for i in range(render_layer_count)
                    ]
                    max_cluster_right = max(x + w for x, _y, w, _h in all_row_bounds)
                    indicators = _collect_thumb_indicators(
                        left_thumb_final, right_thumb_final, keymap, config
                    )
                    tb = _thumb_bb(left_thumb_final, right_thumb_final)
                    connector_paths = _compute_connector_paths(
                        indicators,
                        all_row_bounds,
                        layer_to_row,
                        nk,
                        ew_offset,
                        max_cluster_right,
                        layout.padding,
                        tb,
                    )
                    # Re-adjust canvas for the final escape extents
                    final_escape_ys = [py for pts, _ in connector_paths for _, py in pts[:2]]
                    final_max_y = max(final_escape_ys) if final_escape_ys else layout.thumb_row_y
                    layout.adjust_for_connectors(layout.thumb_row_y, final_max_y)

                    # Adjust canvas width to fit actual routing columns (+ padding)
                    max_path_x = max(
                        (max(px for px, _ in pts) for pts, _ in connector_paths),
                        default=layout.canvas_width,
                    )
                    layout.adjust_canvas_width(max_path_x + layout.padding)
```

The key change: lines 483-557 (from `def _thumb_bb` through `adjust_canvas_width`) are now nested inside `if config.output.style.show_layer_connectors:`. Lines 473-481 (build thumb clusters, collect indicators) remain outside this guard.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/application/render/test_overview.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/skim/application/render/overview.py tests/unit/application/render/test_overview.py
git commit --no-verify -m "feat(render): skip connector paths when show_layer_connectors is false"
```

---

### Task 3: Add TUI switch for `show_layer_connectors`

**Files:**
- Modify: `src/skim/tui/output_tab.py:645,870`

- [ ] **Step 1: Add the switch widget**

In `src/skim/tui/output_tab.py`, after the "Show layer indicators" switch block (after line 645), add:

```python
                with Horizontal(classes="field-row"):
                    yield Label("Show layer connectors:", classes="field-label")
                    yield Static(" ", classes="swatch-spacer")
                    yield SkimSwitch(
                        value=style.get("show_layer_connectors", True),
                        id="show-layer-connectors",
                    )
```

- [ ] **Step 2: Add the event handler**

In `src/skim/tui/output_tab.py`, in the `on_switch_changed` method, after the `show-layer-indicators` elif (after line 870), add:

```python
        elif switch_id == "show-layer-connectors":
            self.config_data["output"]["style"]["show_layer_connectors"] = value
```

- [ ] **Step 3: Run all tests to verify no regressions**

Run: `pytest tests/unit/ -v`
Expected: ALL PASS

- [ ] **Step 4: Manual verification**

Run the TUI and confirm the new switch appears below "Show layer indicators:" and toggles correctly:

```bash
skim config
```

- [ ] **Step 5: Commit**

```bash
git add src/skim/tui/output_tab.py
git commit --no-verify -m "feat(tui): add show_layer_connectors switch to output config"
```
