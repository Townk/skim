# Non-Sequential Layer Index Support — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Support arbitrary QMK layer indices (e.g., 0, 1, 2, 15) instead of assuming sequential 0..N-1 indexing throughout the app.

**Architecture:** Add a required `index: int` field to `KeyboardLayer`, change `SvalboardKeymap.layers` from `list` to `dict[int, SvalboardLayout]`, and update all rendering/TUI code to map between QMK indices and config positions via lookup methods on `Keyboard`.

**Tech Stack:** Python, Pydantic, Textual TUI, drawsvg

**Spec:** `docs/superpowers/specs/2026-04-22-non-sequential-layer-indices-design.md`

---

### Task 1: Add `index` field to `KeyboardLayer` and update `Keyboard` lookups

**Files:**
- Modify: `src/skim/data/config.py:57-93` (KeyboardLayer class)
- Modify: `src/skim/data/config.py:123-222` (Keyboard class)
- Test: `tests/unit/data/test_config.py`

- [ ] **Step 1: Update existing tests to include `index` in `KeyboardLayer` constructors**

Every existing test that constructs a `KeyboardLayer` needs the new required `index` field. Update them all:

```python
# tests/unit/data/test_config.py

class TestKeyboardLayerIndex:
    def test_layer_index_with_explicit_ids(self):
        keyboard = Keyboard(
            layers=[
                KeyboardLayer(index=0, id="base", label="1", name="Base"),
                KeyboardLayer(index=1, id="nav", label="N", name="Navigation"),
            ]
        )
        assert keyboard.layer_index("base") == 0
        assert keyboard.layer_index("nav") == 1

    def test_layer_index_without_ids_uses_string_index(self):
        keyboard = Keyboard(
            layers=[
                KeyboardLayer(index=0, label="1", name="Base"),
                KeyboardLayer(index=1, label="2", name="Symbols"),
            ]
        )
        assert keyboard.layer_index("0") == 0
        assert keyboard.layer_index("1") == 1

    def test_layer_index_unknown_key_returns_none(self):
        keyboard = Keyboard(layers=[KeyboardLayer(index=0, id="base", label="1", name="Base")])
        assert keyboard.layer_index("unknown") is None

    def test_layer_index_with_none_returns_none(self):
        keyboard = Keyboard(layers=[KeyboardLayer(index=0, label="1", name="Base")])
        assert keyboard.layer_index(None) is None
```

Also update `TestKeyboardLayerSubtitle`:

```python
class TestKeyboardLayerSubtitle:
    def test_subtitle_defaults_to_none(self):
        layer = KeyboardLayer(index=0, label="1", name="Letters")
        assert layer.subtitle is None

    def test_subtitle_can_be_set(self):
        layer = KeyboardLayer(index=0, label="1", name="Letters", subtitle="COLEMAK")
        assert layer.subtitle == "COLEMAK"

    def test_subtitle_included_in_model_dump(self):
        layer = KeyboardLayer(index=0, label="1", name="Letters", subtitle="COLEMAK")
        dumped = layer.model_dump()
        assert "subtitle" in dumped
        assert dumped["subtitle"] == "COLEMAK"
```

- [ ] **Step 2: Write new tests for `Keyboard` lookup methods with non-sequential indices**

```python
# tests/unit/data/test_config.py — add to TestKeyboardLayerIndex

    def test_qmk_index_to_position_sequential(self):
        keyboard = Keyboard(
            layers=[
                KeyboardLayer(index=0, label="1", name="Base"),
                KeyboardLayer(index=1, label="2", name="Nav"),
            ]
        )
        assert keyboard.qmk_index_to_position(0) == 0
        assert keyboard.qmk_index_to_position(1) == 1
        assert keyboard.qmk_index_to_position(99) is None

    def test_qmk_index_to_position_non_sequential(self):
        keyboard = Keyboard(
            layers=[
                KeyboardLayer(index=0, label="1", name="Base"),
                KeyboardLayer(index=3, label="N", name="Nav"),
                KeyboardLayer(index=15, label="M", name="Mouse"),
            ]
        )
        assert keyboard.qmk_index_to_position(0) == 0
        assert keyboard.qmk_index_to_position(3) == 1
        assert keyboard.qmk_index_to_position(15) == 2
        assert keyboard.qmk_index_to_position(1) is None

    def test_layer_qmk_index(self):
        keyboard = Keyboard(
            layers=[
                KeyboardLayer(index=0, label="1", name="Base"),
                KeyboardLayer(index=15, label="M", name="Mouse"),
            ]
        )
        assert keyboard.layer_qmk_index(0) == 0
        assert keyboard.layer_qmk_index(1) == 15

    def test_layer_index_with_non_sequential_indices(self):
        """layer_index still maps id strings to config position."""
        keyboard = Keyboard(
            layers=[
                KeyboardLayer(index=0, id="base", label="1", name="Base"),
                KeyboardLayer(index=15, id="mouse", label="M", name="Mouse"),
            ]
        )
        assert keyboard.layer_index("base") == 0
        assert keyboard.layer_index("mouse") == 1
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/unit/data/test_config.py -v`
Expected: FAIL — `KeyboardLayer` doesn't have `index` field yet, and `Keyboard` lacks `qmk_index_to_position`/`layer_qmk_index` methods.

- [ ] **Step 4: Add `index` field to `KeyboardLayer`**

In `src/skim/data/config.py`, modify the `KeyboardLayer` class:

```python
class KeyboardLayer(BaseModel):
    """Configuration for a single keyboard layer.

    Attributes:
        index: The QMK layer index for this layer. This is the actual
            layer number used in the firmware, which may not be sequential
            (e.g., 0, 1, 2, 15).
        id: Optional unique identifier for the layer.
        label: Short display label shown in the generated image.
        name: Full descriptive name of the layer.
        subtitle: Optional secondary label shown below the layer name.
    """

    model_config = ConfigDict(frozen=True)

    index: int
    id: str | None = None
    label: str
    name: str
    subtitle: str | None = None
```

- [ ] **Step 5: Add `qmk_index_to_position` and `layer_qmk_index` methods to `Keyboard`**

In `src/skim/data/config.py`, update the `Keyboard` class. Add a `_qmk_index_map` private attribute and update `model_post_init`:

```python
class Keyboard(BaseModel):
    model_config = ConfigDict(frozen=True)

    features: KeyboardFeatures = Field(default_factory=KeyboardFeatures)
    layers: Annotated[tuple[KeyboardLayer, ...], BeforeValidator(_coerce_to_tuple)] = ()
    _layer_id_map: dict[str, int] = PrivateAttr(default_factory=dict)
    _qmk_index_map: dict[int, int] = PrivateAttr(default_factory=dict)

    def model_post_init(self, context: object) -> None:
        for idx, layer in enumerate(self.layers):
            if layer.id is not None:
                self._layer_id_map[layer.id] = idx
            else:
                self._layer_id_map[str(idx)] = idx
            self._qmk_index_map[layer.index] = idx

    def layer_index(self, key: str | None) -> int | None:
        # ... existing implementation unchanged ...

    def qmk_index_to_position(self, qmk_idx: int) -> int | None:
        """Map a QMK layer index to the config position.

        Args:
            qmk_idx: The QMK firmware layer index.

        Returns:
            The position in the layers tuple, or None if not found.
        """
        return self._qmk_index_map.get(qmk_idx)

    def layer_qmk_index(self, position: int) -> int:
        """Get the QMK layer index for a config position.

        Args:
            position: The position in the layers tuple.

        Returns:
            The QMK firmware layer index.
        """
        return self.layers[position].index
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/unit/data/test_config.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/skim/data/config.py tests/unit/data/test_config.py
git commit --no-verify -m "feat(data): add index field to KeyboardLayer and QMK index lookups to Keyboard"
```

---

### Task 2: Change `SvalboardKeymap.layers` from `list` to `dict`

**Files:**
- Modify: `src/skim/data/keyboard.py:1088-1124`
- Test: `tests/unit/data/test_keyboard.py`
- Test: `tests/unit/domain/adapters/test_keymap_target_adapter.py`

- [ ] **Step 1: Update existing `SvalboardKeymap` tests to use dict constructor**

Search `tests/unit/data/test_keyboard.py` and `tests/unit/domain/adapters/test_keymap_target_adapter.py` for all `SvalboardKeymap(layers=...)` or `SvalboardKeymap([...])` calls and change them to use dict syntax:

```python
# Before:
SvalboardKeymap(layers=[layer0, layer1])
SvalboardKeymap([layer0, layer1])

# After:
SvalboardKeymap(layers={0: layer0, 1: layer1})
SvalboardKeymap({0: layer0, 1: layer1})
```

Also update any `keymap.layers[i]` access to `keymap.layers[i]` (dict access works the same for integer keys, so iteration patterns like `for layer in keymap.layers` become `for layer in keymap.layers.values()`).

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/data/test_keyboard.py tests/unit/domain/adapters/test_keymap_target_adapter.py -v`
Expected: FAIL — `SvalboardKeymap` still expects `list`.

- [ ] **Step 3: Change `SvalboardKeymap.layers` type from `list` to `dict`**

In `src/skim/data/keyboard.py`:

```python
@dataclass(frozen=True, slots=True)
class SvalboardKeymap(Generic[T]):
    """A complete Svalboard keymap containing multiple layers.

    Attributes:
        layers: A dict mapping QMK layer indices to SvalboardLayout objects.
            Keys are QMK firmware layer numbers (which may be non-sequential).
    """

    layers: dict[int, SvalboardLayout[T]]
```

- [ ] **Step 4: Update `KeymapTargetAdapter.transform` to handle dict**

In `src/skim/domain/adapters/keymap_target_adapter.py`, line 83:

```python
# Before:
return SvalboardKeymap([self._transform_layer(layer) for layer in keymap.layers])

# After:
return SvalboardKeymap({idx: self._transform_layer(layer) for idx, layer in keymap.layers.items()})
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/data/test_keyboard.py tests/unit/domain/adapters/test_keymap_target_adapter.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/skim/data/keyboard.py src/skim/domain/adapters/keymap_target_adapter.py tests/unit/data/test_keyboard.py tests/unit/domain/adapters/test_keymap_target_adapter.py
git commit --no-verify -m "refactor(data): change SvalboardKeymap.layers from list to dict[int, SvalboardLayout]"
```

---

### Task 3: Update keymap loaders to produce dict-based keymaps

**Files:**
- Modify: `src/skim/application/loaders/keymap_loader.py`
- Modify: `src/skim/application/keymap_generator.py:79-89` (pass config to loader)
- Test: `tests/unit/application/loaders/test_keymap_loader.py`

- [ ] **Step 1: Update `load_keymap` tests to expect dict-based keymap**

In `tests/unit/application/loaders/test_keymap_loader.py`, update tests so that assertions check `keymap.layers` is a dict. For example, change `len(keymap.layers)` to `len(keymap.layers)` (dict len works the same) and `keymap.layers[0]` access (dict int-key access also works the same). The key change is in how the keymap is constructed — verify the keys are `{0, 1, 2, ...}` for sequential layers.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/application/loaders/test_keymap_loader.py -v`
Expected: FAIL — loader still constructs list-based keymap.

- [ ] **Step 3: Update `load_keymap` to produce dict-based keymap**

In `src/skim/application/loaders/keymap_loader.py`, update `load_keymap` (line 243) and add an optional `layer_indices` parameter:

```python
def load_keymap(
    file_path: Path | None,
    layer_indices: list[int] | None = None,
) -> SvalboardKeymap[str]:
    """Load a complete keymap from file or stdin.

    Args:
        file_path: Path to the keymap file, or None to read from stdin.
        layer_indices: Optional list mapping each layer position to its
            QMK layer index. Used for c2json format where layers are
            sequential but may correspond to non-sequential QMK indices.
            If None, position is used as the QMK index.

    Returns:
        A SvalboardKeymap containing raw keycode strings for all layers.
    """
    keymap_json = None
    if file_path is None:
        keymap_json = load_keymap_from_stdin()
    elif file_path.is_file():
        keymap_json = load_keymap_file(file_path)

    if keymap_json is not None:
        indices = layer_indices or list(range(len(keymap_json)))
        return SvalboardKeymap({
            idx: SvalboardLayout[str].from_sequence(layer)
            for idx, layer in zip(indices, keymap_json)
        })

    raise ValueError("The provided keymap file path does not exist")
```

- [ ] **Step 4: Update `_get_input_keymap` in `keymap_generator.py` to pass layer indices from config**

In `src/skim/application/keymap_generator.py`, update the `_get_input_keymap` function to accept config and pass layer indices:

```python
def _get_input_keymap(inputs: InputFiles, config: SkimConfig) -> SvalboardKeymap[str]:
    layer_indices = [layer.index for layer in config.keyboard.layers] or None
    return load_keymap(
        None if inputs.force_stdin_keymap else inputs.keymap,
        layer_indices=layer_indices,
    )
```

Update the call in `generate_keymap` (line 148):

```python
input_keymap = _get_input_keymap(inputs, config)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/application/loaders/test_keymap_loader.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/skim/application/loaders/keymap_loader.py src/skim/application/keymap_generator.py tests/unit/application/loaders/test_keymap_loader.py
git commit --no-verify -m "feat(loaders): produce dict-based keymaps with QMK layer index keys"
```

---

### Task 4: Update `RenderContext` to use config position for palette lookup

**Files:**
- Modify: `src/skim/application/render/context.py`
- Test: `tests/unit/application/render/test_context.py`

The key insight: `RenderContext.layer_index` currently means "sequential index into palette". We need to change it so that:
- `layer_index` is the **config position** (used for palette lookup)
- A new `qmk_index_to_position` callable is available for resolving `key.layer_switch` (which is a QMK index) to palette position

- [ ] **Step 1: Write tests for the new layer_switch → position resolution**

```python
# tests/unit/application/render/test_context.py — update TestRenderContextKeyFillColor

    def test_returns_layer_color_using_qmk_position_mapping(self, sample_palette):
        """layer_switch QMK index is mapped to palette position via qmk_index_to_position."""
        # QMK index 15 maps to config position 1 (second layer)
        ctx = RenderContext(
            palette=sample_palette,
            layer_index=0,
            has_double_south=False,
            use_layer_colors_on_keys=True,
            hold_symbol_position=SplitSidePosition.OUTWARD,
            qmk_index_to_position=lambda idx: {0: 0, 15: 1, 3: 2}.get(idx),
        )
        key = SvalboardTargetKey(label="L15", layer_switch=15)
        result = ctx.key_fill_color(key, default="#AABBCC")
        # Should return color from position 1 (second palette layer) at color_index 2
        assert result == "#003300"

    def test_returns_default_for_unmapped_layer_switch(self, sample_palette):
        """Returns default when layer_switch QMK index has no position mapping."""
        ctx = RenderContext(
            palette=sample_palette,
            layer_index=0,
            has_double_south=False,
            use_layer_colors_on_keys=True,
            hold_symbol_position=SplitSidePosition.OUTWARD,
            qmk_index_to_position=lambda idx: None,
        )
        key = SvalboardTargetKey(label="L99", layer_switch=99)
        result = ctx.key_fill_color(key, default="#AABBCC")
        assert result == "#AABBCC"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/application/render/test_context.py -v`
Expected: FAIL — `qmk_index_to_position` parameter doesn't exist.

- [ ] **Step 3: Update `RenderContext` to accept and use `qmk_index_to_position`**

In `src/skim/application/render/context.py`:

```python
from collections.abc import Callable

@dataclass(frozen=True)
class RenderContext:
    palette: Palette
    layer_index: int  # config position, used for palette lookup
    has_double_south: bool
    use_layer_colors_on_keys: bool
    hold_symbol_position: SplitSidePosition
    use_system_fonts: bool = False
    show_layer_indicators: bool = False
    qmk_index_to_position: Callable[[int], int | None] = field(
        default=lambda idx: idx, repr=False, compare=False, hash=False
    )
    layer_colors: LayerColor = field(init=False, repr=False, compare=False, hash=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "layer_colors", self.palette.layers[self.layer_index])

    def key_fill_color(
        self, key: SvalboardTargetKey, default: str, use_accent: bool = False
    ) -> str:
        if not self.use_layer_colors_on_keys:
            return default

        if key.layer_switch is None:
            return default

        position = self.qmk_index_to_position(key.layer_switch)
        if position is not None and 0 <= position < len(self.palette.layers):
            lc = self.palette.layers[position]
            return lc[lc.color_index - (1 if use_accent else 0)]

        return default
```

Also update `ClusterRenderContext.from_render_context` to propagate the new field:

```python
    @classmethod
    def from_render_context(cls, render_context: RenderContext, side: KeyboardSide) -> Self:
        return cls(
            palette=render_context.palette,
            layer_index=render_context.layer_index,
            has_double_south=render_context.has_double_south,
            use_layer_colors_on_keys=render_context.use_layer_colors_on_keys,
            hold_symbol_position=render_context.hold_symbol_position,
            use_system_fonts=render_context.use_system_fonts,
            show_layer_indicators=render_context.show_layer_indicators,
            qmk_index_to_position=render_context.qmk_index_to_position,
            side=side,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/application/render/test_context.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/skim/application/render/context.py tests/unit/application/render/test_context.py
git commit --no-verify -m "feat(render): add qmk_index_to_position mapping to RenderContext"
```

---

### Task 5: Update single-layer rendering to use config position and QMK index

**Files:**
- Modify: `src/skim/application/render/__init__.py`
- Test: `tests/unit/application/render/test_render.py`

- [ ] **Step 1: Update tests in `test_render.py`**

Search `tests/unit/application/render/test_render.py` for all `SvalboardKeymap(layers=...)` or `SvalboardKeymap([...])` calls and update them to dict syntax. Also update any `KeyboardLayer(...)` calls to include `index`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/application/render/test_render.py -v`
Expected: FAIL

- [ ] **Step 3: Update `_draw_layer` to accept config position and QMK index**

In `src/skim/application/render/__init__.py`:

```python
def _draw_layer(
    config: SkimConfig, layer: SvalboardLayout[SvalboardTargetKey],
    config_position: int, qmk_index: int,
) -> draw.Drawing:
    use_system_fonts = config.output.style.use_system_fonts
    render_context = RenderContext(
        palette=config.output.style.palette,
        layer_index=config_position,
        has_double_south=config.keyboard.features.double_south,
        use_layer_colors_on_keys=config.output.style.use_layer_colors_on_keys,
        hold_symbol_position=config.output.style.hold_symbol_position,
        use_system_fonts=use_system_fonts,
        show_layer_indicators=config.output.style.show_layer_indicators,
        qmk_index_to_position=config.keyboard.qmk_index_to_position,
    )
    # ...

    # Layer title — use config position for lookup, QMK index for display
    layer_cfg = config.keyboard.layers[config_position]
    layer_title = layer_cfg.name
    if "layer" not in layer_title.lower():
        layer_title += " Layer"
    # ... rest unchanged
```

Update `_selected_layers` to yield `(qmk_index, config_position, layer)`:

```python
def _selected_layers(
    keymap: SvalboardKeymap[SvalboardTargetKey],
    targets: KeymapGeneratorTargets,
    config: SkimConfig,
):
    if targets.selected_layers:
        for qmk_idx in targets.selected_layers:
            pos = config.keyboard.qmk_index_to_position(qmk_idx)
            if pos is not None and qmk_idx in keymap.layers:
                yield qmk_idx, pos, keymap.layers[qmk_idx]
    elif targets.all_layers:
        for pos, layer_cfg in enumerate(config.keyboard.layers):
            qmk_idx = layer_cfg.index
            if qmk_idx in keymap.layers:
                yield qmk_idx, pos, keymap.layers[qmk_idx]
```

Update `draw_keymap`:

```python
def draw_keymap(
    config: SkimConfig,
    keymap: SvalboardKeymap[SvalboardTargetKey],
    targets: KeymapGeneratorTargets,
) -> dict[str, draw.Drawing]:
    keymap_images: dict[str, draw.Drawing] = {}
    for qmk_idx, pos, layer in _selected_layers(keymap, targets, config):
        keymap_images[f"keymap-layer-{qmk_idx}"] = _draw_layer(config, layer, pos, qmk_idx)

    if targets.overview:
        keymap_images["keymap-overview"] = draw_overview(config, keymap)

    return keymap_images
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/application/render/test_render.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/skim/application/render/__init__.py tests/unit/application/render/test_render.py
git commit --no-verify -m "feat(render): use config position and QMK index in single-layer rendering"
```

---

### Task 6: Update overview rendering to use config-driven layer mapping

**Files:**
- Modify: `src/skim/application/render/overview.py`
- Test: `tests/unit/application/render/test_overview.py`

- [ ] **Step 1: Update `test_overview.py` helper functions**

Update `_make_config` to include `index` in layers and `_make_keymap` to produce dict:

```python
def _make_config(num_layers: int = 3, width: float = 1600) -> SkimConfig:
    layers_cfg = tuple(
        KeyboardLayer(index=i, label=str(i), name=f"Layer{i}")
        for i in range(num_layers)
    )
    layer_colors = tuple(
        LayerColor(base_color=f"#{(i+1)*30:02x}5050")
        for i in range(num_layers)
    )
    return SkimConfig(
        keyboard=Keyboard(layers=layers_cfg),
        output=Output(
            style=Style(palette=Palette(layers=layer_colors)),
        ),
    )


def _make_keymap(num_layers: int = 3) -> SvalboardKeymap[SvalboardTargetKey]:
    layers = {}
    for layer_idx in range(num_layers):
        layer = SvalboardLayout.from_sequence(
            [SvalboardTargetKey(label=f"L{layer_idx}K{i}") for i in range(60)]
        )
        layers[layer_idx] = layer
    return SvalboardKeymap(layers=layers)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/application/render/test_overview.py -v`
Expected: FAIL

- [ ] **Step 3: Update `draw_overview` to iterate config layers instead of sequential range**

In `src/skim/application/render/overview.py`, update `draw_overview` (starting at line 419):

```python
def draw_overview(
    config: SkimConfig,
    keymap: SvalboardKeymap[SvalboardTargetKey],
) -> draw.Drawing:
    num_layers = len(config.keyboard.layers)
    # Only render layers that exist in both config and keymap
    render_layers: list[tuple[int, int]] = []  # (config_position, qmk_index)
    for pos, layer_cfg in enumerate(config.keyboard.layers):
        if layer_cfg.index in keymap.layers:
            render_layers.append((pos, layer_cfg.index))

    render_layer_count = len(render_layers)
    # ...

    # row_to_layer now maps row index to (config_position, qmk_index)
    row_to_layer = list(reversed(render_layers))
    layer_to_row = {qmk_idx: ri for ri, (_pos, qmk_idx) in enumerate(row_to_layer)}
```

Update badge text computation in `_compute_badge_dims` to accept the render_layers list:

```python
def _compute_badge_dims(
    config: SkimConfig,
    render_layers: list[tuple[int, int]],  # (config_position, qmk_index)
    finger_cluster_width: float,
) -> BadgeDimensions:
    badge_height = finger_cluster_width * _OUTER_KEY_WIDTH_PROPORTION
    badge_texts: list[str] = []
    for pos, qmk_idx in render_layers:
        name = config.keyboard.layers[pos].name.upper()
        badge_texts.append(f"{qmk_idx} {name}")
    badge_texts.append("THUMBS")
    # ... rest unchanged
```

Update layer badge rendering (lines 584-609):

```python
    for row_idx, (pos, qmk_idx) in enumerate(row_to_layer):
        row_y = layout.layer_row_y_positions[row_idx]
        layer_cfg = config.keyboard.layers[pos]
        layer_color = (
            palette.layers[pos].base_color
            if pos < len(palette.layers) else palette.neutral_color
        )
        badge_y = row_y + ew_offset
        d.append(draw.Rectangle(
            x=badge_x, y=badge_y, width=badge_w, height=badge_h,
            rx=badge_r, ry=badge_r, fill=layer_color,
        ))
        d.append(draw.Text(
            f"{qmk_idx} {layer_cfg.name.upper()}", font_size=badge_font_size,
            # ...
        ))
```

Update finger cluster rendering (lines 625-648):

```python
    for row_idx, (pos, qmk_idx) in enumerate(row_to_layer):
        layer_data = keymap.layers[qmk_idx]
        ctx = RenderContext(
            palette=palette, layer_index=pos,
            has_double_south=config.keyboard.features.double_south,
            use_layer_colors_on_keys=config.output.style.use_layer_colors_on_keys,
            hold_symbol_position=config.output.style.hold_symbol_position,
            use_system_fonts=use_system_fonts,
            show_layer_indicators=config.output.style.show_layer_indicators,
            qmk_index_to_position=config.keyboard.qmk_index_to_position,
        )
        # ... rest unchanged
```

Update `_build_thumb_clusters` to look up layer 0 by QMK index:

```python
def _build_thumb_clusters(config, keymap, layout, use_system_fonts):
    if not keymap.layers:
        return None, None
    # Use the first config layer's QMK index to find the base layer
    first_qmk_idx = config.keyboard.layers[0].index if config.keyboard.layers else 0
    if first_qmk_idx not in keymap.layers:
        return None, None
    layer0 = keymap.layers[first_qmk_idx]
    palette = config.output.style.palette
    thumb_ctx = RenderContext(
        palette=palette, layer_index=0,
        # ...
        qmk_index_to_position=config.keyboard.qmk_index_to_position,
    )
    # ...
```

Update `_collect_thumb_indicators` similarly to use the first config layer's QMK index:

```python
def _collect_thumb_indicators(left_thumb, right_thumb, keymap, config):
    results = []
    first_qmk_idx = config.keyboard.layers[0].index if config.keyboard.layers else 0
    if first_qmk_idx not in keymap.layers:
        return results
    layer0 = keymap.layers[first_qmk_idx]
    # ... rest unchanged
```

Update `_draw_connector_paths` to use `qmk_index_to_position`:

```python
def _draw_connector_paths(d, paths, palette, qmk_index_to_position):
    for pts, target_layer in paths:
        pos = qmk_index_to_position(target_layer)
        if pos is not None and 0 <= pos < len(palette.layers):
            stroke_color = palette.layers[pos][4]
        else:
            stroke_color = "#808080"
        # ... rest unchanged
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/application/render/test_overview.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/skim/application/render/overview.py tests/unit/application/render/test_overview.py
git commit --no-verify -m "feat(render): update overview to use config-driven layer mapping with QMK indices"
```

---

### Task 7: Update indicators to use `qmk_index_to_position` for palette lookup

**Files:**
- Modify: `src/skim/application/render/indicators.py:78-111`
- Test: `tests/unit/application/render/test_indicators.py`

- [ ] **Step 1: Update indicator tests**

Update any `LayerIndicator` construction and `Palette` fixture in `test_indicators.py` to pass a `qmk_index_to_position` callable. Update `KeyboardLayer` usages to include `index`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/application/render/test_indicators.py -v`

- [ ] **Step 3: Update `LayerIndicator.__init__` to accept `qmk_index_to_position`**

In `src/skim/application/render/indicators.py`, add a `qmk_index_to_position` parameter:

```python
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
    connector_target_y: float | None = None,
    qmk_index_to_position: Callable[[int], int | None] = lambda idx: idx,
) -> None:
    # ...
    # Resolve colors using position mapping
    position = qmk_index_to_position(target_layer)
    if position is not None and 0 <= position < len(palette.layers):
        lc = palette.layers[position]
        self._fill_color = lc.base_color
        self._stroke_color = lc[4]
    else:
        self._fill_color = _FALLBACK_FILL
        self._stroke_color = _FALLBACK_STROKE
```

Add `from collections.abc import Callable` to the imports.

Update all call sites that create `LayerIndicator` (in `overview.py`'s `_collect_thumb_indicators` and in `indicators.py`'s `LayerIndicatorOverlay.for_finger_cluster`/`for_thumb_cluster`) to pass `qmk_index_to_position` from the render context.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/application/render/test_indicators.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/skim/application/render/indicators.py tests/unit/application/render/test_indicators.py
git commit --no-verify -m "feat(render): use qmk_index_to_position in LayerIndicator palette lookup"
```

---

### Task 8: Update styling `default_layer_color` to use config position

**Files:**
- Modify: `src/skim/application/render/styling.py:160-191`
- Test: `tests/unit/application/render/test_styling.py`

- [ ] **Step 1: Verify `default_layer_color` is only called with position**

Search for all call sites of `default_layer_color`. It should already receive position values after the previous tasks since it's called from the config generator. If call sites pass QMK indices, update them to pass position instead.

- [ ] **Step 2: Run full test suite for styling**

Run: `uv run pytest tests/unit/application/render/test_styling.py -v`
Expected: PASS (this may require no code changes if callers already pass position)

- [ ] **Step 3: Commit (if changes were needed)**

```bash
git add src/skim/application/render/styling.py
git commit --no-verify -m "fix(render): ensure default_layer_color uses config position for hue"
```

---

### Task 9: Update config generator to include `index` field

**Files:**
- Modify: `src/skim/application/config_generator.py:113-122`
- Test: `tests/unit/application/test_config_generator.py`

- [ ] **Step 1: Update tests**

Update `test_config_generator.py` to verify generated configs include `index` field in layers.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/application/test_config_generator.py -v`

- [ ] **Step 3: Update `_build_layers` to include `index`**

In `src/skim/application/config_generator.py`:

```python
def _build_layers(
    self, num_layers: int, layer_names: dict[str, str]
) -> list[dict[str, str | int | None]]:
    layers = []
    for idx in range(num_layers):
        name = layer_names.get(str(idx), f"Layer {idx}")
        label = name.upper()[:4].strip() if name != f"Layer {idx}" else f"L{idx}"
        layers.append({"index": idx, "label": label, "name": name, "id": None, "subtitle": None})
    return layers
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/application/test_config_generator.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/skim/application/config_generator.py tests/unit/application/test_config_generator.py
git commit --no-verify -m "feat(config): include index field in generated layer configs"
```

---

### Task 10: Update TUI keyboard tab — add `index` field editing with validation

**Files:**
- Modify: `src/skim/tui/keyboard_tab.py`
- Test: `tests/unit/tui/test_keyboard_tab.py`

- [ ] **Step 1: Update tests for index field in TUI**

In `tests/unit/tui/test_keyboard_tab.py`, update any test config data to include `index` in layer dicts. Add tests for:
- Index field is displayed and editable
- Changing index to an unused value re-sorts layers and palette colors
- Changing index to a taken value shows error dialog and reverts

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/tui/test_keyboard_tab.py -v`

- [ ] **Step 3: Add `index` field to TUI**

In `src/skim/tui/keyboard_tab.py`:

Add `"layer-index": "index"` to `_FIELD_MAP`:

```python
_FIELD_MAP = {
    "layer-index": "index",
    "layer-label": "label",
    "layer-name": "name",
    "layer-id": "id",
    "layer-subtitle": "subtitle",
}
```

Add an `index` Input field to the `compose` method (before the label field):

```python
with Horizontal(classes="field-row"):
    yield Label("Index:", classes="field-label")
    yield Input(value="", id="layer-index", placeholder="e.g. 0", disabled=True)
```

Update `_refresh_detail_fields` to populate the index:

```python
def _refresh_detail_fields(self) -> None:
    layers = self.config_data.get("keyboard", {}).get("layers", [])
    if self._selected_layer >= len(layers):
        return
    layer = layers[self._selected_layer]
    self.query_one("#layer-index", Input).value = str(layer.get("index", self._selected_layer))
    self.query_one("#layer-label", Input).value = layer.get("label", "") or ""
    self.query_one("#layer-name", Input).value = layer.get("name", "") or ""
    self.query_one("#layer-id", Input).value = layer.get("id", "") or ""
    self.query_one("#layer-subtitle", Input).value = layer.get("subtitle", "") or ""
```

Update `_clear_detail_fields` to include the index field:

```python
def _clear_detail_fields(self) -> None:
    self.query_one("#layer-index", Input).value = ""
    self.query_one("#layer-label", Input).value = ""
    self.query_one("#layer-name", Input).value = ""
    self.query_one("#layer-id", Input).value = ""
    self.query_one("#layer-subtitle", Input).value = ""
```

Update `on_input_changed` to handle the index field with validation:

```python
def on_input_changed(self, event: Input.Changed) -> None:
    input_id = event.input.id
    if input_id == "keymap-title-text":
        self.config_data["output"]["keymap_title"] = event.value if event.value else None
        return
    if input_id == "copyright-text":
        self.config_data["output"]["copyright"] = event.value if event.value else None
        return
    if input_id not in _FIELD_MAP:
        return
    config_key = _FIELD_MAP[input_id]
    layers = self.config_data.get("keyboard", {}).get("layers", [])
    if self._selected_layer >= len(layers):
        return
    value: str | int | None = event.value
    if config_key == "index":
        return  # index is validated on commit, not on change
    if config_key in ("id", "subtitle") and value == "":
        value = None
    layers[self._selected_layer][config_key] = value
    self._update_selected_list_item()
```

Update `_col0_text` to show QMK index:

```python
def _col0_text(self, index: int, layer: dict[str, Any]) -> str:
    qmk_idx = layer.get("index", index)
    layer_id = layer.get("id") or ""
    if layer_id:
        return f"{layer_id}[{qmk_idx}]:"
    return f"[{qmk_idx}]:"
```

Update `on_button_pressed` for "add-layer" to assign the next available index:

```python
elif event.button.id == "add-layer":
    layers = self.config_data.setdefault("keyboard", {}).setdefault("layers", [])
    used_indices = {l.get("index", i) for i, l in enumerate(layers)}
    next_index = 0
    while next_index in used_indices:
        next_index += 1
    idx = len(layers)
    new_layer = {
        "index": next_index,
        "label": f"L{next_index}",
        "name": f"Layer {next_index}",
        "id": None,
        "subtitle": None,
    }
    layers.append(new_layer)
    # ... rest unchanged
```

- [ ] **Step 4: Add index validation to `_exit_edit_mode`**

When committing edits, validate the index value:

```python
def _exit_edit_mode(self, commit: bool) -> None:
    if commit:
        layers = self.config_data.get("keyboard", {}).get("layers", [])
        if self._selected_layer < len(layers):
            # Validate and apply index
            index_input = self.query_one("#layer-index", Input)
            try:
                new_index = int(index_input.value)
            except ValueError:
                self.app.push_screen(
                    ErrorDialog("Invalid layer index. Must be a number between 0 and 31.")
                )
                if self._snapshot is not None:
                    layers[self._selected_layer] = self._snapshot
                    self._refresh_detail_fields()
                self._editing = False
                self._snapshot = None
                self._set_fields_enabled(False)
                self.query_one("#layer-list", ListView).focus()
                return

            if new_index < 0 or new_index > 31:
                self.app.push_screen(
                    ErrorDialog("Layer index must be between 0 and 31.")
                )
                if self._snapshot is not None:
                    layers[self._selected_layer] = self._snapshot
                    self._refresh_detail_fields()
                self._editing = False
                self._snapshot = None
                self._set_fields_enabled(False)
                self.query_one("#layer-list", ListView).focus()
                return

            # Check for duplicates
            old_index = self._snapshot.get("index") if self._snapshot else None
            if new_index != old_index:
                for i, l in enumerate(layers):
                    if i != self._selected_layer and l.get("index") == new_index:
                        self.app.push_screen(
                            ErrorDialog(f"Layer index {new_index} is already in use.")
                        )
                        if self._snapshot is not None:
                            layers[self._selected_layer] = self._snapshot
                            self._refresh_detail_fields()
                        self._editing = False
                        self._snapshot = None
                        self._set_fields_enabled(False)
                        self.query_one("#layer-list", ListView).focus()
                        return

            layers[self._selected_layer]["index"] = new_index

            # Re-sort layers by index
            palette_layers = (
                self.config_data.get("output", {})
                .get("style", {})
                .get("palette", {})
                .get("layers", [])
            )
            # Build paired list, sort, unpack
            paired = list(zip(layers, palette_layers)) if len(palette_layers) == len(layers) else None
            layers.sort(key=lambda l: l.get("index", 0))
            if paired:
                paired.sort(key=lambda p: p[0].get("index", 0))
                palette_layers[:] = [p[1] for p in paired]

            # Update selection to follow the moved layer
            for i, l in enumerate(layers):
                if l.get("index") == new_index:
                    self._selected_layer = i
                    break

    if not commit and self._snapshot is not None:
        layers = self.config_data.get("keyboard", {}).get("layers", [])
        if self._selected_layer < len(layers):
            layers[self._selected_layer] = self._snapshot
            self._refresh_detail_fields()
    self._editing = False
    self._snapshot = None
    self._set_fields_enabled(False)
    self._rebuild_list()
    list_view = self.query_one("#layer-list", ListView)
    list_view.index = self._selected_layer
    list_view.focus()
    if commit:
        self.post_message(LayerUpdated())
```

Note: You'll need to import or create an `ErrorDialog` screen. Check what dialog mechanism the app already uses (look at `src/skim/tui/app.py` for existing dialog patterns like the quit dialog) and follow the same pattern.

- [ ] **Step 5: Update `sync_layer_added` to assign next available index**

```python
def sync_layer_added(self, index: int) -> None:
    layers = self.config_data.setdefault("keyboard", {}).setdefault("layers", [])
    used_indices = {l.get("index", i) for i, l in enumerate(layers)}
    next_index = 0
    while next_index in used_indices:
        next_index += 1
    new_layer = {
        "index": next_index,
        "label": f"L{next_index}",
        "name": f"Layer {next_index}",
        "id": None,
        "subtitle": None,
    }
    layers.insert(index, new_layer)
    self._rebuild_list()
    self._selected_layer = index
    self._refresh_detail_fields()
    self._update_list_state()
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/unit/tui/test_keyboard_tab.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/skim/tui/keyboard_tab.py tests/unit/tui/test_keyboard_tab.py
git commit --no-verify -m "feat(tui): add layer index field with validation, re-sort, and error dialogs"
```

---

### Task 11: Update TUI output/style tab to show QMK index in layer color list

**Files:**
- Modify: `src/skim/tui/output_tab.py:344-365`
- Test: `tests/unit/tui/test_output_tab.py`

- [ ] **Step 1: Update `_layer_name` and `_lc_text` to show QMK index**

In `src/skim/tui/output_tab.py`:

```python
def _layer_name(self, index: int) -> str:
    layers = self.config_data.get("keyboard", {}).get("layers", [])
    if index < len(layers):
        return layers[index].get("name", "")
    return ""

def _layer_qmk_index(self, index: int) -> int:
    layers = self.config_data.get("keyboard", {}).get("layers", [])
    if index < len(layers):
        return layers[index].get("index", index)
    return index

def _lc_text(self, index: int, lc: dict[str, Any], col0_w: int, col1_w: int) -> str:
    name = self._layer_name(index)
    qmk_idx = self._layer_qmk_index(index)
    col0 = f"{name} ({qmk_idx})" if name else f"({qmk_idx})"
    color = lc.get("base_color", "")
    return f"{col0:<{col0_w}}  {color:<{col1_w}}"

def _lc_column_widths(self) -> tuple[int, int]:
    layer_colors = self._layer_colors()
    col0_w = 0
    col1_w = 0
    for i, lc in enumerate(layer_colors):
        name = self._layer_name(i)
        qmk_idx = self._layer_qmk_index(i)
        col0 = f"{name} ({qmk_idx})" if name else f"({qmk_idx})"
        col0_w = max(col0_w, len(col0))
        col1_w = max(col1_w, len(lc.get("base_color", "")))
    return col0_w, col1_w
```

- [ ] **Step 2: Update tests**

Update any test data in `tests/unit/tui/test_output_tab.py` to include `index` in layer dicts.

- [ ] **Step 3: Run tests to verify they pass**

Run: `uv run pytest tests/unit/tui/test_output_tab.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/skim/tui/output_tab.py tests/unit/tui/test_output_tab.py
git commit --no-verify -m "feat(tui): show QMK layer index in style tab layer color list"
```

---

### Task 12: Update remaining test files and fix any broken tests

**Files:**
- Test: `tests/unit/application/render/test_components.py`
- Test: `tests/unit/application/render/test_render.py`
- Test: `tests/unit/application/test_keymap_generator.py`
- Test: `tests/unit/tui/test_app.py`
- Test: `tests/unit/test_cli.py`
- Test: Any other test file that constructs `KeyboardLayer` or `SvalboardKeymap`

- [ ] **Step 1: Run full test suite to find all remaining failures**

Run: `uv run pytest tests/ -v --tb=short 2>&1 | head -100`

- [ ] **Step 2: Fix each failing test**

For each failing test:
- Add `index=N` to all `KeyboardLayer(...)` constructors
- Change `SvalboardKeymap(layers=[...])` to `SvalboardKeymap(layers={0: ..., 1: ..., ...})`
- Update any `keymap.layers[N]` access that relied on list semantics (e.g., `enumerate(keymap.layers)` → `keymap.layers.items()`)
- Update any `len(keymap.layers)` (works the same for dict)

- [ ] **Step 3: Run full test suite to verify all pass**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add tests/
git commit --no-verify -m "fix(tests): update all remaining tests for non-sequential layer indices"
```

---

### Task 13: Update sample config file

**Files:**
- Modify: `samples/config/skim-config.yaml`

- [ ] **Step 1: Add `index` field to each layer in the sample config**

```yaml
keyboard:
  features:
    double_south: true
  layers:
  - id: _BASE
    index: 0
    label: BASE
    name: Letters
    subtitle: COLEMAK
  - id: _GAME
    index: 1
    label: GAME
    name: Gaming
    subtitle: null
  - id: _NAV
    index: 2
    label: NAV
    name: Navigation
    subtitle: null
  - id: _NUM
    index: 3
    label: NUM
    name: Numbers
    subtitle: null
  - id: _SYM
    index: 4
    label: SYM
    name: Symbols
    subtitle: null
  - id: _FUN
    index: 5
    label: FN
    name: Function Keys
    subtitle: null
  - id: _MED
    index: 6
    label: MED
    name: Multimedia
    subtitle: null
  - id: _SYS
    index: 7
    label: SYS
    name: System
    subtitle: null
  - id: _MBO
    index: 15
    label: MBO
    name: Mouse
    subtitle: null
```

- [ ] **Step 2: Commit**

```bash
git add samples/config/skim-config.yaml
git commit --no-verify -m "docs: add index field to sample config layers"
```

---

### Task 14: Final integration test — run the full generation pipeline

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 2: Run the CLI with the sample config and a keymap**

Run: `uv run skim generate -k samples/keymaps/c2json-sample.json -c samples/config/skim-config.yaml -o /tmp/skim-test -f svg`

Verify: SVG files are generated without errors. Check that layer badges in the overview SVG show correct QMK indices (e.g., "15 MOUSE" for the mouse layer).

- [ ] **Step 3: Commit any final fixes**

If any issues were found, fix and commit them.
