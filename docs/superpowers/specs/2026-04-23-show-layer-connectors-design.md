# Show Layer Connectors Config Option

## Summary

Add a `show_layer_connectors` boolean to `Style` config that controls whether dotted connector lines are drawn between layer indicator circles (on thumb keys) and layer rows in the overview image. When `false`, the connector lines are not drawn and layout adjustments for connector space (thumb cluster shift, canvas expansion) are skipped.

## Behavior

| `show_layer_indicators` | `show_layer_connectors` | Indicators | Connectors | Connector space adjustments |
|---|---|---|---|---|
| false | (ignored) | No | No | No |
| true | false | Yes | No | No |
| true | true | Yes | Yes | Yes |

- `show_layer_connectors` only takes effect when `show_layer_indicators` is `true`
- Default value: `true` (preserves current behavior)
- Indicator padding (15% clearance, 18% inward padding) remains whenever `show_layer_indicators` is `true`, regardless of `show_layer_connectors`

## Changes

### 1. Config model (`src/skim/data/config.py`)

Add `show_layer_connectors: bool = True` to the `Style` class, after `show_layer_indicators` (line 652).

### 2. Overview rendering (`src/skim/application/render/overview.py`)

In `draw_overview()`, the existing guard at line 472 checks `show_layer_indicators`. The connector-specific code within that block (lines 491-557: path computation, clearance calculation, `adjust_for_connectors`, rebuild, width adjustment) needs an additional guard on `show_layer_connectors`.

When `show_layer_indicators=true` but `show_layer_connectors=false`:
- Thumb clusters are still built (needed for indicator rendering)
- `_collect_thumb_indicators()` is still called (indicators are still drawn)
- Skip: `_compute_connector_paths()`, escape Y calculation, `adjust_for_connectors()`, thumb cluster rebuild, `adjust_canvas_width()` for routing columns
- `connector_paths` remains empty, so `_draw_connector_paths()` at line 764-765 is naturally skipped

Concretely, split the block at line 472 so that:
- Lines 473-481 (build thumb clusters, collect indicators) run when `show_layer_indicators` is true
- Lines 483-557 (connector path computation and layout adjustments) run only when `show_layer_connectors` is also true

### 3. Config TUI (`src/skim/tui/output_tab.py`)

Add a switch row for "Show layer connectors:" after the existing "Show layer indicators:" row (after line 645). Pattern:

```python
with Horizontal(classes="field-row"):
    yield Label("Show layer connectors:", classes="field-label")
    yield Static(" ", classes="swatch-spacer")
    yield SkimSwitch(
        value=style.get("show_layer_connectors", True),
        id="show-layer-connectors",
    )
```

Add handler in `on_switch_changed()` (after line 870):

```python
elif switch_id == "show-layer-connectors":
    self.config_data["output"]["style"]["show_layer_connectors"] = value
```

## Testing

- Existing overview rendering tests should continue to pass (default is `true`)
- Manual verification: generate overview with `show_layer_connectors: false` and confirm no dotted lines appear and layout is more compact
