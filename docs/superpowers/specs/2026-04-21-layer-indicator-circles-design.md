# Layer Indicator Circles — Design Spec

## Overview

Add colored circle indicators next to layer-switching keys in the per-layer keymap images. Each circle shows the 0-indexed target layer number and is colored with the target layer's palette colors. A connector line links each circle to its key.

This feature complements the existing `use_layer_colors_on_keys` feature (which colors the key background) by adding an external visual marker that is unambiguous even when key coloring is disabled.

## Visual Spec

### Circle

- **Diameter:** Half the finger cluster North key width (`FingerClusterKeySizes.outer_key_width / 2`).
- **Fill:** `palette.layers[target_layer].base_color`.
- **Outline:** 2px stroke, `palette.layers[target_layer].gradient[1]` (2nd lightest color in the gradient). When no custom gradient is defined, the gradient is auto-generated from `base_color`, so `gradient[1]` is always available via `LayerColor[1]`.
- **Label:** 0-indexed layer number, white, same font family as key labels.

### Connector Line

- **Width:** 2px.
- **Color:** Same as circle outline (`LayerColor[1]` of the target layer).
- **Direction:** Horizontal or vertical for all keys, except Center key which uses a 45-degree diagonal.
- **Endpoint:** 4px filled circle (same color as line), drawn 4px inside the target key boundary.

### Uniform Gap

The distance between a circle's edge and its key's edge is constant across all keys, with two exceptions:

1. **Center key:** The diagonal connector naturally places the circle further from the center key to avoid overlapping adjacent keys.
2. **Double-Down:** The gap is measured from the circle to the Down key (since DD sits inside Down), not to the DD key itself.

## Placement Rules

### Finger Cluster

| Key Position   | Circle Direction                                        | Connector   |
|----------------|---------------------------------------------------------|-------------|
| North          | Above key                                               | Vertical    |
| West           | Above key                                               | Vertical    |
| East           | Above key                                               | Vertical    |
| Center         | 45-deg diagonal toward opposite-hand side and downward  | Diagonal    |
| South          | Hand-side (left for left hand, right for right hand)    | Horizontal  |
| Double-South   | Hand-side (same as South)                               | Horizontal  |

**Center key detail:** For the left hand, the circle is placed below-right of the East key (right of the South key). For the right hand, it mirrors to below-left (left of the South key). The connector enters the center key at exactly 45 degrees.

### Thumb Cluster

| Key Position   | Circle Direction                                        | Connector   |
|----------------|---------------------------------------------------------|-------------|
| Pad            | Outward side (left for left hand, right for right hand) | Horizontal  |
| Nail           | Outward side (opposite of Pad)                          | Horizontal  |
| Up             | Same side as Pad                                        | Horizontal  |
| Knuckle        | Same side as Nail                                       | Horizontal  |
| Down           | Same side as Pad, vertically below Up                   | Horizontal  |
| Double-Down    | Above the Down key                                      | Vertical    |

## Architecture

### Approach: Separate Rendering Pass

Indicators are drawn as a separate pass after keys, not integrated into key classes. This keeps key rendering untouched and centralizes placement logic.

### New File: `src/skim/application/render/indicators.py`

Two classes:

- **`LayerIndicator`** — A `draw.Group` that renders a single circle + connector + endpoint for one key. Constructor takes:
  - Key layout boundary (position + size)
  - Target layer index
  - Circle offset direction (computed from key position, cluster type, side)
  - Palette (to resolve target layer colors)
  - Circle diameter
  - Connector type (horizontal, vertical, or diagonal)

- **`LayerIndicatorOverlay`** — Orchestrates indicator drawing for an entire cluster. Iterates over keys, skips keys without `layer_switch`, computes the offset direction from a placement lookup, and creates `LayerIndicator` instances.

### Placement Lookup

The offset direction is encoded as a mapping from `(key_position, cluster_type, keyboard_side)` to an offset specification (direction + axis). This can be a dictionary or a method with match/case logic.

### Config

- **`Style.show_layer_indicators: bool`** — New field, default `True`. Controls whether indicators are rendered.
- Passed through `RenderContext` to the cluster components.

### Integration Points

- **`src/skim/data/config.py`** — Add `show_layer_indicators: bool = True` to `Style`.
- **`src/skim/application/render/context.py`** — Add `show_layer_indicators` to `RenderContext` and `ClusterRenderContext.from_render_context()`.
- **`src/skim/application/render/components.py`** — In `FingerClusterComponent.build()` and `ThumbClusterComponent.build()`, after appending keys, call `LayerIndicatorOverlay` if `show_layer_indicators` is true.
- **`src/skim/application/render/indicators.py`** — New file with `LayerIndicator` and `LayerIndicatorOverlay`.

### Data Flow

1. YAML config sets `output.style.show_layer_indicators: true`.
2. `RenderContext` carries the flag.
3. Cluster `build()` methods check the flag.
4. For each key with `layer_switch is not None`, `LayerIndicatorOverlay` computes circle position from the key's layout boundary + offset direction.
5. `LayerIndicator` draws circle, label, connector line, and endpoint into a `draw.Group`.
6. The group is appended to the cluster's SVG group (renders on top of keys; connector lines may cross over other elements).

## Testing

- Unit tests for `LayerIndicator` rendering (correct SVG elements, colors, positions).
- Unit tests for `LayerIndicatorOverlay` placement logic (correct offset directions per key position/side).
- Unit tests for the uniform gap calculation.
- Integration test verifying that generated SVG contains indicator elements when `show_layer_indicators` is true and omits them when false.
- Visual verification with sample config after implementation.
