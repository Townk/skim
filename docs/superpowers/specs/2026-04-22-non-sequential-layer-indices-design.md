# Non-Sequential Layer Index Support

## Problem

The system conflates "position in a list" with "QMK layer index". In QMK, layers can be assigned arbitrary indices (e.g., 0, 1, 2, 3, 4, 5, 6, 7, 15), but skim treats the position of a layer in its internal list as the layer's index. This causes incorrect layer labels, broken layer-switch color matching, and wrong index display throughout the app.

## Design

### Data Model: `KeyboardLayer`

Add a required `index: int` field to `KeyboardLayer`. Every layer must explicitly declare its QMK index.

```yaml
# skim-config.yaml
keyboard:
  layers:
  - id: _BASE
    index: 0
    label: BASE
    name: Letters
  - id: _NAV
    index: 2
    label: NAV
    name: Navigation
  - id: _MBO
    index: 15
    label: MBO
    name: Mouse
```

### Data Model: `Keyboard`

The `Keyboard` model provides lookup methods for mapping between QMK indices and config positions:

- `qmk_index_to_position(qmk_idx: int) -> int | None` -- maps a QMK layer index to the config position (used for palette/color lookup when encountering keycodes like `LT(15, ...)`)
- `layer_qmk_index(position: int) -> int` -- maps a config position to its QMK index (used for display labels like "15 MOUSE")

Palette colors remain position-aligned: `palette.layers[position]` corresponds to `config.keyboard.layers[position]`, regardless of QMK index.

### Data Model: `SvalboardKeymap`

`SvalboardKeymap.layers` changes from `list[SvalboardLayout[T]]` to `dict[int, SvalboardLayout[T]]`, where keys are QMK layer indices.

### Keymap Loading

**Vial & Keybard:** These formats include all layers (typically 16). The loader creates a dict keyed by position index (which equals QMK index since all 16 slots are present):

```python
SvalboardKeymap({i: SvalboardLayout.from_sequence(layer) for i, layer in enumerate(layers)})
```

Only layers with a matching config entry get rendered; the rest are ignored.

**c2json:** Only includes defined layers. The loader uses the config's layer indices to key the dict, since c2json positions don't correspond to QMK indices. The loader accepts an index mapping derived from config:

```python
# config layers define indices [0, 1, 3, 15]
# c2json has 4 layers at positions [0, 1, 2, 3]
# mapping: position 0 -> QMK 0, position 1 -> QMK 1, position 2 -> QMK 3, position 3 -> QMK 15
```

### Rendering

**Overview image (`overview.py`):** Iterates over config layers and their QMK indices instead of a sequential range. Layer badges show the actual QMK index (e.g., "15 MOUSE").

**Single-layer rendering (`render/__init__.py`):** Receives config position for metadata lookup and QMK index for display.

**Render context (`context.py`):** Uses config position for palette lookup. Layer switch color resolution uses `qmk_index_to_position()` to find the palette color for target layers.

**Indicators (`indicators.py`):** Uses `qmk_index_to_position()` to map target layer QMK indices to config positions before indexing the palette.

**Styling (`styling.py`):** `default_layer_color()` uses config position (not QMK index) for hue calculation so colors distribute evenly across defined layers.

### TUI

**Display:** Layer index display shows the QMK index from the `index` field.

**Editing the `index` field:**

- If the new index is unused: accept the change, re-sort the layers list and corresponding palette layer colors by QMK index, update selection to follow the moved layer.
- If the new index is already taken: show an error dialog saying the chosen index is already in use, revert the field to its previous value.
- Validation: the index must be within QMK's valid range (0-31). Invalid values get the same revert + error dialog treatment.

### "Used" Layer Determination

Only layers with a matching `KeyboardLayer` entry in the config are considered "used". If a Vial keymap has 16 layers but the config defines 9, only those 9 are rendered and shown in the TUI. No explicit `used` flag is needed.
