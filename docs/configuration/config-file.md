# Configuration File

Skim's configuration lives in a single YAML file. YAML was chosen over JSON
because it tolerates comments, optional quoting, and trailing-comma slips —
small ergonomic wins that matter when a non-developer is hand-editing the
file from a tutorial.

The file is hierarchical and **every field is optional**. Skim fills in
sensible defaults for anything you leave out, so a working configuration can
be as short as a single `keyboard.layers` list. The full schema is large only
because it lets you fine-tune nearly every visual element.

You point Skim at a config with the `--config <path>` flag (see
[Command Line Options](cli-options.md)). If you'd rather generate or edit the
file interactively, see the [Configurator UI](configurator-ui.md).

## Top-level structure

The file has three top-level sections:

| Section     | What it controls                                        |
| ----------- | ------------------------------------------------------- |
| `keyboard`  | Physical hardware features and per-layer metadata.      |
| `keycodes`  | How QMK keycodes are transformed and labelled on keys.  |
| `output`    | Image dimensions, colors, borders, legends, and styling. |

A minimal file looks like:

```yaml
keyboard:
  layers:
    - index: 0
      name: "Base"
    - index: 1
      name: "Symbols"
```

A complete reference file with every section populated lives at
[`samples/config/skim-config.yaml`](https://github.com/Townk/skim/blob/mainline/samples/config/skim-config.yaml)
in the repository.

---

## `keyboard`

Describes the hardware variant you're rendering and gives each layer in the
keymap a human-readable identity.

```yaml
keyboard:
  features:
    double_south: false
  layers:
    - index: 0
      id: "base"
      name: "Letters"
      variant: "QWERTY"
    - index: 1
      name: "Numbers / Navigation"
```

### `keyboard.features`

A bag of hardware-feature toggles. Today there's only one knob, but the
sub-section exists to keep room for future hardware variants without
breaking the schema.

Current schema:

```yaml
keyboard:
  features:
    double_south: <boolean>
```

#### `double_south`

| Type      | Default |
| --------- | ------- |
| `boolean` | `false` |

Whether the finger clusters render the double-south (DS) key positions. Set
to `true` only if your physical keyboard has these extra southern switches.

On a stock Svalboard build, leave it `false` — those positions will be
hidden in the output.

<div class="option-comparison" markdown="1">

<figure markdown="1">
<figcaption><code>double_south: false</code></figcaption>
![Finger cluster without double-south](../_static/options/double-south/without.svg){ width="180" loading=lazy }
</figure>

<figure markdown="1">
<figcaption><code>double_south: true</code></figcaption>
![Finger cluster with double-south](../_static/options/double-south/with.svg){ width="180" loading=lazy }
</figure>

</div>

### `keyboard.layers`

A list of layer descriptors. The list does two unrelated jobs at once, and
it helps to keep them separate when reading the rest of this section:

- **Order of the list** controls how layers stack in the **overview image**.
  The first entry renders on the *bottom* row and the last on the top, so
  reading the list top-to-bottom corresponds to reading the overview
  bottom-to-top. This is intentional: layer 0 is conventionally the base
  layer, and stacking it at the bottom matches how most users think about
  layer "depth."
- **`index` field** on each entry is the layer's **QMK firmware index** —
  the slot the layer occupies in the compiled binary, and the integer that
  keycodes like `MO(...)`, `LT(...)`, and `TG(...)` target.

List position and firmware index are independent. You can list a layer first
and give it `index: 14` if your firmware skips middle slots — useful for Vial
and Keybard keymaps that can populate non-sequential layers like `0, 1, 2, 14,
15`.

Current schema:

```yaml
keyboard:
  layers:
    - index: <int>
      id: <string>
      name: <string>
      variant: <string>
```

Each entry has these fields:

#### `index`

| Type      | Required | Range |
| --------- | -------- | ----- |
| `integer` | yes      | `0`–`31` |

The QMK firmware layer index — what the `.hex` ends up with after
`qmk compile`, and what `LT(...)` / `MO(...)` / `TG(...)` keycodes target.
If this doesn't match what's actually programmed into your firmware,
layer-switching keys will point at the wrong layer in the rendered image.

The range matches QMK's stock `MAX_LAYERS` of 32. The Configurator UI enforces
`0`–`31`; the YAML schema itself doesn't bound the value, so hand-edited config
files can technically set higher indices, but the renderer and the default
color generator are calibrated for `0`–`31`.

This value is used in the "Overview" keymap and on the "Layer Indicators" to
represent the layers defined in your keymap.

<div class="option-comparison" markdown="1">

<figure markdown="1">
<figcaption>Indicator on a finger-cluster centre key</figcaption>
![Finger cluster with layer indicator](../_static/options/keyboard-layers/finger-with-indicator.svg){ height="160" loading=lazy }
</figure>

<figure markdown="1">
<figcaption>Indicator on a thumb-cluster down key</figcaption>
![Thumb cluster with layer indicator](../_static/options/keyboard-layers/thumb-with-indicator.svg){ height="160" loading=lazy }
</figure>

</div>

#### `name`

| Type     | Required |
| -------- | -------- |
| `string` | yes      |

The full descriptive name shown as the title of the per-layer image and as
the layer's row label in the overview. Long names are fine — the overview
sizes them automatically.

<div class="option-comparison" markdown="1">

<figure markdown="1">
<figcaption>Auto-named layer badge</figcaption>
![Layer badge reading "LAYER 3"](../_static/options/keyboard-layers/badge-unnamed.svg){ width="200" loading=lazy }
</figure>

<figure markdown="1">
<figcaption>Custom-named layer badge</figcaption>
![Layer badge reading "2 MY CUSTOM NAME"](../_static/options/keyboard-layers/badge-named.svg){ width="280" loading=lazy }
</figure>

</div>

When no name is provided, Skim simply uses the word _LAYER_ followed by the QMK firmware layer index.

#### `id`

| Type     | Default |
| -------- | ------- |
| `string \| null` | `null` |

An optional alphanumeric handle for this layer, used when your keymap
references layers by C `#define` macros (the form `qmk c2json` produces). If
your `LT(...)` / `MO(...)` arguments use literal integers, you don't need this.
If they use `#define`d names like `_BASE` or `_NAV`, set `id: "_BASE"` so Skim
can resolve them back to the firmware index.

> [!NOTE]
> This option has no visual impact in the final image, but is required to produce
> an image with the correct connections between layers.

#### `variant`

| Type     | Default |
| -------- | ------- |
| `string \| null` | `null` |

A short secondary label rendered below the layer name in the overview
image — typically used to tag the keymap variant (`"QWERTY"`, `"COLEMAK"`,
`"DVORAK"`). Leave `null` to not display any text below the layer name.

<div class="option-comparison" markdown="1">

<figure markdown="1">
<figcaption>Layer badge with a variant label</figcaption>
![Layer badge reading "0 LETTERS" with "QWERTY" below](../_static/options/keyboard-layers/badge-with-variant.svg){ width="240" loading=lazy }
</figure>

</div>

---

## `keycodes`

Customizes how Skim turns raw QMK keycode strings into the labels that
appear on rendered keys, plus metadata for macros, tap-dances, and the
legends Skim emits.

```yaml
keycodes:
  pre_process:
    - { keycode: "MY_CUSTOM_LT", target: "LT(1, KC_SPC)" }
  overrides:
    - { keycode: "KC_SPC", target: "Space" }
    - { keycode: "KC_ENT", target: "Enter" }
  macros:
    - { id: "0", name: "Send password", preview: "type p4ssw0rd" }
  tap_dances:
    - { id: "TD_SHIFT", name: "Shift / Caps", preview: "shift • caps" }
  symbol_descriptions: {}
  function_descriptions: {}
  symbol_legend_aliases: {}
```

The pipeline that produces a key's label runs in this order:

1. **`pre_process`** rewrites the *input* keycode string before any
   resolution happens.
2. Skim's **bundled keycode-to-label table** turns the (possibly rewritten)
   keycode into a label.
3. **`overrides`** has the final word — it can replace the resolved label
   with anything you like.

### `keycodes.pre_process`

| Type | Default |
| ---- | ------- |
| list of `{keycode, target}` | `[]` |

Use this to **normalise non-standard keycodes** so the standard resolver
recognises them. A common case: a custom keycode in your firmware that
behaves like a stock QMK construct.

```yaml
keycodes:
  pre_process:
    - keycode: "LCTL_T(KC_A)"
      target: "MT(MOD_LCTL,KC_A)"
```

After this rule, every appearance of `LCTL_T(KC_A)` in the keymap is
treated as `MT(MOD_LCTL,KC_A)`, which the bundled resolver knows how to
render.

!!! note
    `pre_process` rules are **textual substitutions** that happen before
    label resolution, so they should not rely on alias-resolution features
    in keycode strings. Use plain canonical QMK syntax in the `target`.

### `keycodes.overrides`

| Type | Default |
| ---- | ------- |
| list of `{keycode, target}` | `[]` |

Force the rendered label for a specific keycode, regardless of what the
default mapping produces. Common uses: spelling words out
(`KC_SPC` → `"Space"`), choosing a glyph (`KC_ENT` → `"⏎"`), or hiding a
key with a blank string.

```yaml
keycodes:
  overrides:
    - keycode: "KC_SPC"
      target: "Space"
    - keycode: "KC_NO"
      target: ""
```

### `keycodes.macros`

| Type | Default |
| ---- | ------- |
| list of `{id, name, preview}` | `[]` |

Metadata for QMK macros. Each entry binds a macro identifier to a friendly
name and a one-line preview that Skim uses in the macros legend table on
generated images.

| Field     | Required | Description |
| --------- | -------- | ----------- |
| `id`      | yes | The string used to reference this macro in your keymap (`"0"` for `MACRO_0`, `"MY_MACRO"` for `MACRO_MY_MACRO`). |
| `name`    | no  | Short human-readable label shown in the macros legend. Defaults to `null`. |
| `preview` | no  | One-line description of what the macro produces (e.g., `"types p4ssw0rd"`). Defaults to an empty string. The Configurator UI generates these automatically; for manually-added entries the value is `"Undefined"`. |

### `keycodes.tap_dances`

| Type | Default |
| ---- | ------- |
| list of `{id, name, preview}` | `[]` |

Same shape as `macros`, but for tap-dance entries. The `id` matches the
identifier inside the `TD(...)` keycode (`"0"` for `TD(0)`, `"MY_TD"` for
`TD(MY_TD)`).

### `keycodes.symbol_descriptions`

| Type | Default |
| ---- | ------- |
| `{category: {keycode: description}}` | `{}` |

Per-keycode description overrides for the symbol legend. The legend ships
with a curated default table; entries here either override an existing
keycode within a bundled category or add brand-new categories.

```yaml
keycodes:
  symbol_descriptions:
    Modifiers:
      KC_LEFT_CTRL: "Control (my custom label)"
    "My Section":
      MY_KEY: "Does the thing"
```

User keys in an existing bundled category take precedence over the bundled
description for the same keycode. Brand-new categories are appended after
the bundled ones in the legend.

### `keycodes.function_descriptions`

| Type | Default |
| ---- | ------- |
| `{category: {keycode: description}}` | `{}` |

Same shape and merge rules as `symbol_descriptions`, but applied to the
function-keycode legend (the table that explains constructs like `MO`,
`LT`, `OSM`, etc.).

```yaml
keycodes:
  function_descriptions:
    Layers:
      MO: "Custom MO description with @0;"
```

### `keycodes.symbol_legend_aliases`

| Type | Default |
| ---- | ------- |
| `{keycode: canonical_keycode}` | `{}` |

Tells the symbol legend to render two keycodes as a single combined entry
sharing the legend description of the canonical one. Handy when your
keymap uses left/right variants of the same conceptual key and you don't
want each to occupy a separate row.

```yaml
keycodes:
  symbol_legend_aliases:
    KC_RIGHT_GUI: KC_LEFT_GUI
```

---

## `output`

Controls everything visual: image dimensions, layer colors, borders, fonts,
which legends to draw, and the relative scale of standalone tables.

```yaml
output:
  keymap_title: "My Svalboard Layout"
  copyright: "© 2026 Your Name"
  layout: { ... }
  style:  { ... }
```

### `output.keymap_title`

| Type             | Default |
| ---------------- | ------- |
| `string \| null` | `null`  |

Override for the auto-generated title rendered at the top of the overview
image. Leave `null` to use the auto-generated one (typically derived from
the input file's name).

### `output.copyright`

| Type             | Default |
| ---------------- | ------- |
| `string \| null` | `null`  |

A copyright notice rendered in the footer area of the overview image.
Leave `null` to omit it. Standard conventions apply
(`"© 2026 Your Name"`); Skim does not enforce a format.

### `output.layout`

Image dimensions and whitespace.

#### `output.layout.width`

| Type    | Default |
| ------- | ------- |
| `float` | `1600`  |

Total image width in SVG units (effectively pixels at the default scale).
The image height is computed automatically to preserve the Svalboard
aspect ratio, so you only specify width.

Increase this for prints/documentation that need extra detail; decrease
for thumbnails or sharing on width-constrained platforms.

#### `output.layout.spacing.margin`

| Type             | Default       |
| ---------------- | ------------- |
| `float \| null`  | `null` (→ `0`) |

The **outer** margin between the image edge and the rounded keyboard
border, in SVG units. `null` and `0` are equivalent — the keyboard sits
flush against the image edge.

```yaml
output:
  layout:
    spacing:
      margin: 12   # 12-unit blank ring around the keyboard
```

#### `output.layout.spacing.inset`

| Type             | Default                          |
| ---------------- | -------------------------------- |
| `float \| null`  | `null` (→ width-proportional)    |

The **inner** padding inside the keyboard border. Used both as the gap
between the border and the first content row, and as the spacing between
stacked elements (clusters, legends) inside the document column.

`null` (the default) lets Skim choose a width-proportional value at render
time, which scales nicely as you change `width`. Set an explicit number
when you want a fixed look across multiple sizes.

### `output.style`

The largest sub-section. Every visual switch and color knob lives here.

#### `output.style.use_layer_colors_on_keys`

| Type      | Default |
| --------- | ------- |
| `boolean` | `true`  |

When `true`, layer-switching keys (the keys that activate or hold a layer)
get tinted using the activating layer's color from `palette.layers`. When
`false`, every key uses the standard neutral background regardless of the
layer it activates. Useful when you want a more uniform look or when you
prefer to encode layer membership only in the badge column of the
overview.

#### `output.style.hold_symbol_position`

| Type     | Default     | Allowed values                |
| -------- | ----------- | ----------------------------- |
| `string` | `"outward"` | `"qmk"`, `"inward"`, `"outward"` |

For hold-tap keys (`LT`, `MT`, etc.) Skim splits the key visually into the
"hold" portion and the "tap" portion. This setting controls which side of
the split each portion goes on:

- **`"outward"`** — the **hold** side faces outward from the cluster's
  centre. Left-hand keys put hold on the left, right-hand keys put hold
  on the right. Reads naturally because the "modifier-ish" hold action
  ends up on the outer edge of the keyboard.
- **`"inward"`** — the mirror of the above. Hold faces the cluster
  centre; tap faces the outer edge.
- **`"qmk"`** — uses the argument order QMK macros define. Since QMK
  always lists hold first and tap second (e.g., `LT(layer, key)`), this
  mode draws hold on the left and tap on the right regardless of which
  side of the keyboard the key is on.

#### `output.style.border`

Configures the rounded rectangle border drawn around the entire keyboard.
Set the whole `border` object to `null` to suppress the border.

```yaml
output:
  style:
    border:
      width: 2
      radius: 10
```

##### `output.style.border.width`

| Type    | Default |
| ------- | ------- |
| `float` | `2`     |

Stroke width of the border line in SVG units.

##### `output.style.border.radius`

| Type    | Default |
| ------- | ------- |
| `float` | `10`    |

Corner radius for the rounded rectangle. Set to `0` for square corners.

#### `output.style.palette`

Color tokens used throughout the rendered image.

```yaml
output:
  style:
    palette:
      background_color: "#FFFFFF"
      text_color: "#1F2933"
      key_label_color: "#FFFFFF"
      neutral_color: "#6F768B"
      border_color: "#000000"
      macro_color: "#89511C"
      tap_dance_color: "#41687F"
      overrides: {}
      layers:
        - base_color: "#3366CC"
        - base_color: "#CC6633"
```

##### Chrome colors

These apply to the document chrome (background, headings, borders) and to
keys that don't get a layer-specific tint.

| Field              | Default     | What it tints |
| ------------------ | ----------- | ------------- |
| `background_color` | `"white"`   | The image background. |
| `text_color`       | `"black"`   | Body text outside of keys (titles, legends, footer). |
| `key_label_color`  | `"white"`   | Text on key faces (chosen for contrast against typically dark key backgrounds). |
| `neutral_color`    | `"#6F768B"` | Keys without a layer-specific color (most thumb cluster keys, transparent fall-throughs). |
| `border_color`     | `"black"`   | Keyboard outer border and cluster outlines. |
| `macro_color`      | `"#89511C"` | Macro badges on keys and the title bar of the macros legend. |
| `tap_dance_color`  | `"#41687F"` | Tap-dance badges on keys and the title bar of the tap-dances legend. |

All accept any CSS color string (`"red"`, `"#3366CC"`, `"rgb(51,102,204)"`,
`"hsl(218 60% 50%)"`).

##### `output.style.palette.overrides`

| Type | Default |
| ---- | ------- |
| `{name: color}` | `{}` |

Lets you **redefine** the W3C named colors that SVG renderers ship with
(147 of them). Useful when you want a name like `"crimson"` to refer to
your brand red instead of the W3C-spec value, and you've referenced
`"crimson"` in several places in your config.

```yaml
output:
  style:
    palette:
      overrides:
        crimson: "#B11226"
```

Empty by default, so the standard W3C names apply unmodified.

##### `output.style.palette.layers`

| Type | Default |
| ---- | ------- |
| list of `LayerColor` | `[]` |

Per-layer color configurations. The list aligns by **position** with
`keyboard.layers`: the *N*-th palette entry colors the *N*-th keyboard
layer. If `palette.layers` is shorter than `keyboard.layers`, the extra
layers get auto-generated colors — so you can leave the list empty for
a quick start and fill it in later.

##### Auto-generated layer colors

When a layer has no explicit `palette.layers` entry, Skim derives a
base color from its `index` field. Sixteen visually-distinct colors
are produced from **8 hues × 2 lightness levels**, walked in
bit-reversed order so consecutive indices always land on
maximally-distant hues. Layers 16–31 fill in the gaps with eight
*intermediate* hues at the same two lightness levels:

| `index`  | Hue band                              | Lightness |
| -------- | ------------------------------------- | --------- |
| `0`–`7`  | 8 base hues, 45° apart (starting on green) | bright    |
| `8`–`15` | the same 8 base hues                  | dim       |
| `16`–`23` | 8 intermediate hues (22.5° offset)    | bright    |
| `24`–`31` | the same 8 intermediate hues          | dim       |

Why 45° between hues instead of 22.5°? Sixteen evenly-spaced hues sit
22.5° apart — narrow enough that several adjacent ones (especially in
the green region) blur together. Eight hues at 45° apart read as
decisively different colors, and the bright/dim alternation gives a
second axis of distinction so layers `0` and `8` (both green) still
look like separate layers.

The hue sequence for layers `0`–`7` lands on green, magenta, blue,
orange, yellow-green, red, purple, and yellow — eight slots that read
clearly as different colors. Layers `8`–`15` repeat the same hue walk
at the dim lightness; layers `16`–`23` and `24`–`31` do the same with
the intermediate hue set.

Saturation is capped at `0.65` so auto-generated colors share
the muted profile of the curated sample palettes shipped with Skim.

###### `base_color`

| Type     | Required |
| -------- | -------- |
| `string` | yes      |

The primary CSS color for the layer. In single-color mode (no `gradient`),
every key on the layer uses this color. In gradient mode, this is the
"anchor" color used to derive the gradient automatically when one isn't
provided explicitly.

###### `color_index`

| Type      | Default |
| --------- | ------- |
| `integer` | `2`     |

Which gradient stop (`0`–`5`) is the "primary" color for this layer.
Cluster keys use this index to pick their fill, and adjacent positions
get progressively darker/lighter shades of the gradient. Only meaningful
when `gradient` is set or auto-generated.

###### `gradient`

| Type | Default |
| ---- | ------- |
| 6-tuple of CSS color strings, or `null` | `null` |

Six colors that map to the six positions in a finger cluster (centre,
north, east, south, west, double-south). When `null`, Skim derives a
gradient automatically from `base_color` and `color_index` — six tints
ranging from very dark to very light, with `base_color` placed at
`color_index`.

```yaml
output:
  style:
    palette:
      layers:
        # Layer 0: single red, no gradient — every key the same shade.
        - base_color: "#FF0000"

        # Layer 1: explicit 6-stop gradient for cluster depth.
        - base_color: "#CC6633"
          color_index: 2
          gradient:
            - "#CC6633"
            - "#AA5522"
            - "#884411"
            - "#663300"
            - "#442200"
            - "#221100"
```

#### `output.style.use_system_fonts`

| Type      | Default |
| --------- | ------- |
| `boolean` | `false` |

When `false` (default), the SVG embeds the bundled fonts so the rendered
image looks identical on every machine. When `true`, the SVG references
system fonts by name — the file is smaller and may pick up your system's
preferred typefaces, but viewers without those fonts installed will see a
fallback.

#### `output.style.show_layer_indicators`

| Type      | Default |
| --------- | ------- |
| `boolean` | `true`  |

Enables the small colored circles drawn in the corner of keys that
activate a layer. Each circle is tinted with the destination layer's
color, giving an at-a-glance hint of "where does this key take me." Set
to `false` to suppress them.

#### `output.style.show_layer_connectors`

| Type      | Default |
| --------- | ------- |
| `boolean` | `true`  |

In the **overview** image only, draws faint dashed lines from each layer
indicator to the row representing the destination layer, making the
layer-graph explicit. Has no effect on per-layer images. Set to `false`
to suppress the connectors for a cleaner overview.

#### `output.style.show_transparent_fallthrough`

| Type      | Default |
| --------- | ------- |
| `boolean` | `true`  |

When `true`, transparent keycodes (`KC_TRNS` / `_______`) on layers above
0 render the label from layer 0 in a faded "ghost" color, so you can see
what's underneath. Set to `false` to leave transparent keys completely
blank.

#### `output.style.show_special_keys_legend`

| Type      | Default |
| --------- | ------- |
| `boolean` | `true`  |

Toggles two related legend tables:

- On **per-layer images**, a table of every macro and tap-dance referenced
  on that layer, with its `name` and `preview` from `keycodes.macros` /
  `keycodes.tap_dances`.
- On the **overview image**, a single combined legend covering every
  macro and tap-dance used anywhere in the keymap.

Set to `false` to omit both legends.

#### `output.style.show_symbol_legend`

| Type      | Default |
| --------- | ------- |
| `boolean` | `true`  |

Toggles the symbol legend — the table that explains the non-obvious
glyphs Skim renders on keys (modifier symbols, function indicators, etc.).
Per-layer images carry only the symbols actually used on that layer; the
overview carries the union across all rendered layers.

#### `output.style.symbol_legend_flow`

| Type     | Default      | Allowed values        |
| -------- | ------------ | --------------------- |
| `string` | `"column"`   | `"row"`, `"column"`   |

Controls how multi-column symbol-legend layouts fill themselves:

- **`"column"`** — fills each column top-to-bottom before starting the
  next column. Reads top-to-bottom first.
- **`"row"`** — fills each row left-to-right before dropping to the next
  row. Reads left-to-right first.

#### `output.style.symbol_legend_columns`

| Type            | Default |
| --------------- | ------- |
| `integer \| null` | `null`  |

Forces the **standalone** symbols image to lay out at exactly this many
columns and shrinks the canvas to fit. `null` (the default) lets the
layout pick the largest column count that fits the canvas budget — the
behaviour used in per-layer and overview images. Has no effect on the
embedded legends inside per-layer / overview images, only on the
standalone symbols-only output.

#### `output.style.macros_scale`

| Type    | Default |
| ------- | ------- |
| `float` | `1.5`   |

Body-scale multiplier for the **standalone macros** image (the one Skim
emits when you ask for just the macros legend on its own). Body chips and
pills scale by this factor; the chrome (title, footer, outer padding)
stays unscaled. Default `1.5` matches the body scale Skim uses internally
in per-image renders.

#### `output.style.tap_dances_scale`

| Type    | Default |
| ------- | ------- |
| `float` | `1.5`   |

Body-scale multiplier for the **standalone tap-dances** image. Same
semantics as `macros_scale`.

#### `output.style.symbols_scale`

| Type    | Default |
| ------- | ------- |
| `float` | `1.5`   |

Body-scale multiplier for the **standalone symbols** image. Same
semantics as `macros_scale`.
