# Command Line Options

This page documents every Skim subcommand and every flag it accepts. The
[Configuration File](config-file.md) page is the source of truth for what
each visual option *does*; this page documents how to drive those options
from the command line.

CLI flags take the highest priority and override anything set in the config
file for that run. Commands and flags that change a config field link back
to the matching field in the configuration reference.

---

## How to read this reference

- Each command gets one H2 section (`## generate`, `## configure`, `## doctor`).
- Each section opens with a short prose description and a **schema sketch**
  showing the full invocation form (`skim <command> [options] <args>`).
- Each flag gets one H3 section with an explicit anchor ID
  (`#generate-config`, `#configure-keymap`, …) so other docs can link directly.
- A flag's section starts with the canonical type table (`Type | Default` or
  `Type | Default | Allowed values` for enums) and is followed by prose
  describing the flag's effect on the rendered output.
- Flags that change a config value link to the corresponding field in
  [`config-file.md`](config-file.md) via its anchor instead of repeating
  the visual. Flags that change which artefact the command writes to disk
  show a short fenced terminal block listing the resulting file names.

Notation conventions:

- `<placeholder>` in a schema sketch is a runtime value you supply.
- `"literal"` in a schema sketch is a literal token you write verbatim.
- `[option]` is optional; arguments without brackets are required when the
  command runs.
- Short forms (`-c`) and long forms (`--config`) of every flag are listed
  side-by-side in the H3 heading.

Command names can be abbreviated to any unique prefix — `skim gen` resolves
to `skim generate`, `skim conf` to `skim configure`, `skim doc` to
`skim doctor`. Ambiguous prefixes raise a usage error.

---

## Commands

| Command                         | What it does                                                           |
| ------------------------------- | ---------------------------------------------------------------------- |
| [`generate`](#generate)         | Render keymap visualisation images from a keymap file.                 |
| [`configure`](#configure)       | Generate a YAML config from a keymap file or launch the configurator. |
| [`doctor`](#doctor)             | Check the local environment for required and optional dependencies.   |

The top-level `skim` command also accepts a small set of [global
flags](#global-options) that apply to every subcommand.

---

## Global options

```bash
skim --help
Usage: skim [OPTIONS] COMMAND [ARGS]...

  Svalboard Keymap Image Maker (skim).

  Generate visual keyboard layout images from keymap configuration files.
  Supports Keybard (.kbi), Vial (.vil), and QMK c2json formats.

  Use --verbosity to control output detail level:     DEBUG: Detailed debug
  information     INFO: Progress updates and summaries     WARNING: Only
  warnings and errors (default)     ERROR: Only errors     CRITICAL: Only
  critical errors     NONE: Silence all output

Options:
  --version                       Show the version and exit.
  -v, --verbosity [debug|info|warning|error|critical|none]
                                  Logging verbosity level.
  -q, --quiet                     Silence all output (overrides --verbosity).
  --help                          Show this message and exit.

Commands:
  configure  Generate or edit a configuration file.
  doctor     Check system environment and dependencies.
  generate   Generate keymap visualization images.
```

Flags listed before the subcommand name apply to the whole invocation:

```bash
skim [global-options] <command> [command-options]
```

---

### `--version` { #global-version }

| Type   | Default |
| ------ | ------- |
| `flag` | —       |

Print the program name and version, then exit. Does not run any subcommand.

---

### `--verbosity`, `-v` { #global-verbosity }

| Type     | Default     | Allowed values                                              |
| -------- | ----------- | ----------------------------------------------------------- |
| `string` | `"WARNING"` | `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`, `"CRITICAL"`, `"NONE"` |

Set the logging verbosity. `"DEBUG"` emits the most detail; `"NONE"`
silences every log line. The value is case-insensitive.

---

### `--quiet`, `-q` { #global-quiet }

| Type   | Default |
| ------ | ------- |
| `flag` | `false` |

Silence all log output. Wins over `--verbosity` when both are passed.

---

## `generate`

```bash
skim generate --help
Usage: skim generate [OPTIONS] [STDIN_MARKER]

  Generate keymap visualization images.

  Parses a keymap file and generates a keymap image for each layer. Optionally
  generates an overview image showing all layers.

  The supported output formats depend on the dependencies installed. For non-
  vector images (PNG, JPEG, WEBP, and AVIF), the Playwright Chromium Browser,
  or the Cairo library must be installed in the system.

  STDIN_MARKER: Pass '-' to read keymap from stdin instead of file.

  Layer selection examples:
      -l overview       Generate only the overview image
      -l macros         Generate only the macros image
      -l tap-dances     Generate only the tap-dances image
      -l special-keys   Generate only the macros + tap-dances combined image
      -l symbols        Generate only the symbols image
      -l 1              Generate only layer 1
      -l 1-3            Generate layers 1, 2, and 3
      -l 1 -l 3 -l 5    Generate layers 1, 3, and 5
      -l all-layers     Generate every individual layer
      -l all            Generate every layer + overview + macros + tap-dances
                        + symbols
                        (skips the combined special-keys image; opt in
                        explicitly with -l special-keys)
      (no -l)           Generate every layer plus overview

Options:
  -c, --config PATH               Configuration file path.
  -k, --keymap PATH               Keymap file path (.vil, .kbi, .json).
  -o, --output-dir PATH           Output directory for generated images.
  -f, --format [svg]              Output format. Raster formats (png, jpeg,
                                  webp, avif) require a render engine.
  -l, --layer TEXT                Layers/images to generate (all, all-layers,
                                  overview, macros, tap-dances, special-keys,
                                  symbols, N, N-M).
  -F, --use-system-fonts          Use system fonts instead of embedding fonts
                                  in SVG.
  -e, --render-engine [chromium|cairo]
                                  Render engine for non-vector formats.
                                  'chromium' uses Playwright, 'cairo' uses
                                  Cairo library. Only shown when both are
                                  available.
  --force                         Overwrite existing files without
                                  confirmation.
  -N, --no-special-keys           Omit the macro and tap-dance legend tables
                                  from the rendered SVGs.
  -Y, --no-symbols                Omit the symbol legend from the rendered
                                  SVGs.
  --symbol-legend-flow [row|column]
                                  Flow direction for the symbol legend table.
                                  'row' fills rows first; 'column' fills
                                  columns first. Default: column.
  --symbol-columns INTEGER RANGE  Force the standalone symbols image to lay
                                  out at exactly N columns; the canvas shrinks
                                  to fit the resulting natural width. Without
                                  this flag the table picks the largest column
                                  count that fits the canvas budget.  [x>=1]
  --macros-scale FLOAT RANGE      Body-scale multiplier for the standalone
                                  macros image (chips and pills scale by this
                                  factor; chrome stays at the unscaled per-
                                  image size). Default: 1.5.  [x>=0.1]
  --tap-dances-scale FLOAT RANGE  Body-scale multiplier for the standalone
                                  tap-dances image. Default: 1.5.  [x>=0.1]
  --symbols-scale FLOAT RANGE     Body-scale multiplier for the standalone
                                  symbols image. Default: 1.5.  [x>=0.1]
  -t, --title TEXT                Override the overview keymap title
                                  (output.keymap_title).
  -r, --copyright TEXT            Override the copyright notice
                                  (output.copyright).
  -d, --double-south              Force the double-south keyboard feature on
                                  (keyboard.features.double_south).
  -w, --width FLOAT               Override the keymap canvas width in SVG
                                  units (output.layout.width).
  -L, --adjust-lightness FLOAT    Target lightness (0.0-1.0) applied to every
                                  layer base color. Ignored when --config is
                                  provided.
  -S, --adjust-saturation FLOAT   Cap saturation (0.0-1.0) on every layer base
                                  color. Ignored when --config is provided.
  --help                          Show this message and exit.
```

Render keymap visualisation images. Reads a keymap from a file (or stdin),
optionally merges in a YAML config, and writes one image per requested
layer/legend into the output directory.

```bash
skim generate [options] [-]
```

The trailing `-` is the optional stdin marker (see [`STDIN_MARKER`](#generate-stdin-marker)).
Without it, `--keymap` selects the input file.

A typical invocation:

```bash
$ skim generate --config my-keymap.yaml --output-dir ./out
out/keymap-layer-0.svg
out/keymap-layer-1.svg
out/keymap-overview.svg
```

Each file's stem matches the layer or artefact it represents:
`keymap-layer-<qmk-index>`, `keymap-overview`, `keymap-macros`,
`keymap-tap-dances`, `keymap-special-keys`, `keymap-symbols`. The
extension is set by [`--format`](#generate-format).

---

### `--config`, `-c` { #generate-config }

| Type   | Default |
| ------ | ------- |
| `path` | `null`  |

Path to a YAML configuration file (must already exist). Settings from this
file populate the run; any field omitted falls back to Skim's built-in
defaults.

When `--config` is provided, [`--adjust-lightness`](#generate-adjust-lightness)
and [`--adjust-saturation`](#generate-adjust-saturation) are ignored — color
adjustments only apply to the auto-derived defaults, not to colors the
user has already chosen.

---

### `--keymap`, `-k` { #generate-keymap }

| Type   | Default |
| ------ | ------- |
| `path` | `null`  |

Path to a keymap file. Format is detected from the extension and content:
Keybard (`.kbi`), Vial (`.vil`), or QMK c2json (`.json`). Without `--keymap`
and without [`STDIN_MARKER`](#generate-stdin-marker), Skim reads from stdin
if data is piped in and errors out otherwise.

---

### `--output-dir`, `-o` { #generate-output-dir }

| Type   | Default     |
| ------ | ----------- |
| `path` | current dir |

Directory the rendered images are written to. The directory must exist as
a directory (Skim refuses to write into a regular file at that path) but is
created if it doesn't yet exist.

---

### `--format`, `-f` { #generate-format }

| Type     | Default | Allowed values                                              |
| -------- | ------- | ----------------------------------------------------------- |
| `string` | `"svg"` | `"svg"`, `"png"`, `"jpeg"`, `"webp"`, `"avif"`              |

Output image format. Raster formats (`png`, `jpeg`, `webp`, `avif`)
require either Playwright/Chromium or the Cairo library to be installed —
when neither is available, `svg` is the only allowed value. Run
[`skim doctor`](#doctor) to check which engines the local install can
reach.

```bash
$ skim generate -k layout.kbi -o ./out -f png
out/keymap-layer-0.png
out/keymap-overview.png
```

---

### `--layer`, `-l` { #generate-layer }

| Type     | Default |
| -------- | ------- |
| `string` | —       |

Selects which images to write. Repeat the flag or comma-separate values to
combine selections. Tokens are interpreted as:

| Token            | Effect                                                                          |
| ---------------- | ------------------------------------------------------------------------------- |
| `N`              | Render the per-layer image for QMK layer `N`.                                   |
| `N-M`            | Render every per-layer image from `N` to `M` inclusive.                         |
| `overview`       | Render the overview image (every layer in one canvas).                          |
| `macros`         | Render the standalone macros legend image.                                      |
| `tap-dances`     | Render the standalone tap-dances legend image.                                  |
| `special-keys`   | Render the combined macros + tap-dances image.                                  |
| `symbols`        | Render the standalone symbols legend image.                                     |
| `all-layers`     | Render every per-layer image; clear any prior `N`/`N-M` selection.              |
| `all`            | Render every per-layer image, the overview, and the standalone macros, tap-dances, and symbols images. Skips `special-keys` (already covered) — opt in explicitly with `-l special-keys`. |

Without `--layer`, Skim renders every per-layer image plus the overview.
Macros, tap-dances, and symbols images are emitted only when the keymap
actually defines content for them; otherwise Skim warns and skips the
empty image.

```bash
$ skim generate -k layout.kbi -o ./out -l 0 -l overview -l macros
out/keymap-layer-0.svg
out/keymap-overview.svg
out/keymap-macros.svg
```

---

### `--use-system-fonts`, `-F` { #generate-use-system-fonts }

| Type   | Default |
| ------ | ------- |
| `flag` | `false` |

When set, generated SVGs reference font families by name and rely on the
viewer's system to provide them. By default Skim embeds the fonts it
ships with directly into each SVG so the file renders identically
regardless of the viewer's installed fonts. Maps to
[`output.style.use_system_fonts`](config-file.md#output-style-use-system-fonts).

Toggling this flag changes file content, not which files are written.
Run [`skim doctor`](#doctor) to confirm the bundled fonts are installed
locally before relying on it.

---

### `--render-engine`, `-e` { #generate-render-engine }

| Type     | Default | Allowed values         |
| -------- | ------- | ---------------------- |
| `string` | `null`  | `"chromium"`, `"cairo"` |

For non-vector formats, choose which engine renders the SVG to a raster.
`"chromium"` uses Playwright and matches what a browser would paint;
`"cairo"` uses the Cairo graphics library and is faster. Ignored for
`--format svg`.

When unset, Skim picks the first available engine. If neither engine is
installed, raster formats fail.

---

### `--force` { #generate-force }

| Type   | Default |
| ------ | ------- |
| `flag` | `false` |

Overwrite existing output files without prompting. Without this flag,
existing files are kept and Skim aborts the run.

---

### `--no-special-keys`, `-N` { #generate-no-special-keys }

| Type   | Default |
| ------ | ------- |
| `flag` | `false` |

Omit the macros and tap-dances legend tables from each rendered SVG.
Equivalent to setting both
[`output.style.legend_tables.macros.show`](config-file.md#output-style-legend-tables-macros-show)
and
[`output.style.legend_tables.tap_dances.show`](config-file.md#output-style-legend-tables-tap-dances-show)
to `false`.

This flag changes file content, not which files are written. The
standalone macros / tap-dances images requested via [`--layer`](#generate-layer)
are still emitted — only the in-line legend tables on per-layer and overview
images are suppressed.

---

### `--no-symbols`, `-Y` { #generate-no-symbols }

| Type   | Default |
| ------ | ------- |
| `flag` | `false` |

Omit the symbol legend from each rendered SVG. Equivalent to setting
[`output.style.legend_tables.symbols.show`](config-file.md#output-style-legend-tables-symbols-show)
to `false`. The standalone symbols image (when requested via `-l symbols`)
is still emitted; only the in-line legend on per-layer and overview images
is suppressed.

---

### `--symbol-legend-flow` { #generate-symbol-legend-flow }

| Type     | Default | Allowed values        |
| -------- | ------- | --------------------- |
| `string` | `null`  | `"row"`, `"column"`   |

Override the flow direction of the symbols legend table.
Maps to [`output.style.legend_tables.symbols.flow`](config-file.md#output-style-legend-tables-symbols-flow).
When unset, the config's value applies.

---

### `--symbol-columns` { #generate-symbol-columns }

| Type      | Default | Range  |
| --------- | ------- | ------ |
| `integer` | `null`  | `≥ 1`  |

Force the standalone symbols image to lay out at exactly N columns; the
canvas shrinks to fit the resulting natural width. Without this flag the
table picks the largest column count that fits the canvas budget. Maps to
[`output.style.legend_tables.symbols.columns`](config-file.md#output-style-legend-tables-symbols-columns).

---

### `--macros-scale` { #generate-macros-scale }

| Type    | Default | Range   |
| ------- | ------- | ------- |
| `float` | `1.5`   | `≥ 0.1` |

Body-scale multiplier for the standalone macros image. Chips and pills
scale by this factor; the image's chrome (border, header, footer) stays
at the unscaled per-image size. Maps to
[`output.style.legend_tables.macros.scale`](config-file.md#output-style-legend-tables-macros-scale).

---

### `--tap-dances-scale` { #generate-tap-dances-scale }

| Type    | Default | Range   |
| ------- | ------- | ------- |
| `float` | `1.5`   | `≥ 0.1` |

Body-scale multiplier for the standalone tap-dances image. Same shape as
[`--macros-scale`](#generate-macros-scale). Maps to
[`output.style.legend_tables.tap_dances.scale`](config-file.md#output-style-legend-tables-tap-dances-scale).

---

### `--symbols-scale` { #generate-symbols-scale }

| Type    | Default | Range   |
| ------- | ------- | ------- |
| `float` | `1.5`   | `≥ 0.1` |

Body-scale multiplier for the standalone symbols image. Same shape as
[`--macros-scale`](#generate-macros-scale). Maps to
[`output.style.legend_tables.symbols.scale`](config-file.md#output-style-legend-tables-symbols-scale).

---

### `--title`, `-t` { #generate-title }

| Type     | Default |
| -------- | ------- |
| `string` | `null`  |

Override the overview keymap title. Maps to
[`output.keymap_title`](config-file.md#output-keymap-title). When unset,
the title from the config file applies; when no title is set anywhere
and a keymap file is provided, Skim derives one from the keymap's
filename.

---

### `--copyright`, `-r` { #generate-copyright }

| Type     | Default |
| -------- | ------- |
| `string` | `null`  |

Override the copyright notice rendered in the overview footer. Maps to
[`output.copyright`](config-file.md#output-copyright).

---

### `--double-south`, `-d` { #generate-double-south }

| Type   | Default |
| ------ | ------- |
| `flag` | `false` |

Force the double-south finger-cluster feature on. Maps to
[`keyboard.features.double_south`](config-file.md#keyboard-features-double-south).
The flag can only set the feature to `true`; to render without it, leave
the flag off and let the config (default `false`) apply.

---

### `--width`, `-w` { #generate-width }

| Type    | Default |
| ------- | ------- |
| `float` | `null`  |

Override the canvas width in SVG units. Maps to
[`output.layout.width`](config-file.md#output-layout-width). The default
when no config and no flag is provided is `1600`.

---

### `--adjust-lightness`, `-L` { #generate-adjust-lightness }

| Type    | Default | Range     |
| ------- | ------- | --------- |
| `float` | `null`  | `0.0–1.0` |

Target lightness applied to every layer's auto-derived base color before
the gradient is built. Useful when the bundled defaults clash with a
specific output medium (e.g. for paper printing, lower the lightness so
key labels stay legible). Adjusts the
[`output.style.palette.layers`](config-file.md#output-style-palette-layers)
entries Skim would otherwise auto-derive from the keymap.

Ignored when [`--config`](#generate-config) is provided — Skim emits a
note on stderr and uses the config's colors unmodified.

---

### `--adjust-saturation`, `-S` { #generate-adjust-saturation }

| Type    | Default | Range     |
| ------- | ------- | --------- |
| `float` | `null`  | `0.0–1.0` |

Cap saturation on every layer's auto-derived base color. Adjusts the
[`output.style.palette.layers`](config-file.md#output-style-palette-layers)
entries Skim would otherwise auto-derive from the keymap. Same gating
rule as [`--adjust-lightness`](#generate-adjust-lightness): ignored when
`--config` is provided.

---

### `STDIN_MARKER` { #generate-stdin-marker }

| Type     | Default |
| -------- | ------- |
| `string` | —       |

Optional positional argument. Pass the literal `-` to read the keymap
from stdin even when [`--keymap`](#generate-keymap) is provided. Without
either, Skim reads from stdin only when data is actually piped in.

```bash
$ qmk c2json -kb svalboard/...] -km vial keymap.c | skim generate - -o ./out
```

---

## `configure`

```bash
skim configure --help
Usage: skim configure [OPTIONS]

  Generate or edit a configuration file.

  With no flags, shows this help message.

  Use -i/--interactive to launch the TUI configuration editor. Optionally pass
  -c/--config to load an existing config file into the editor.

  Use -k to extract metadata (layer colors, names, custom keycodes) from a
  Keybard file.

  Color adjustments (--adjust-lightness, --adjust-saturation) are applied to
  all extracted colors to ensure readable contrast in generated images.

Options:
  -i, --interactive              Launch interactive configuration editor
                                 (TUI).
  -c, --config PATH              Load an existing configuration file
                                 (interactive mode).
  -k, --keymap PATH              Keymap file path (.kbi, .vil, .json).
  -o, --output PATH              Output configuration file path.
  --force                        Overwrite existing file.
  -L, --adjust-lightness FLOAT   Adjust lightness (0.0-1.0) (non-interactive).
  -S, --adjust-saturation FLOAT  Adjust saturation (0.0-1.0) (non-
                                 interactive).
  -t, --title TEXT               Set the keymap title (output.keymap_title).
  -r, --copyright TEXT           Set the copyright notice (output.copyright).
  -d, --double-south             Enable the double-south keyboard feature
                                 (keyboard.features.double_south).
  -w, --width FLOAT              Set the keymap canvas width in SVG units
                                 (output.layout.width).
  -n, --layer-count INTEGER      Number of layers to pre-create with defaults
                                 (interactive mode).
  --help                         Show this message and exit.
```

Generate, edit, or scaffold a YAML configuration file. Without flags,
prints help. With `-k`, extracts metadata (layer names, palette, custom
keycodes) from a keymap file and writes a config. With `-i`, launches the
[Configurator UI](configurator-ui.md).

```bash
skim configure [options]
```

The most common forms:

```bash
$ skim configure -k layout.kbi -o my-config.yaml
$ skim configure -i -c my-config.yaml
$ skim configure -t "My Keymap" -r "© 2026 Me" -o my-config.yaml
```

---

### `--interactive`, `-i` { #configure-interactive }

| Type   | Default |
| ------ | ------- |
| `flag` | `false` |

Launch the Configurator UI (TUI) instead of writing a config to disk. The
TUI is provided by the optional `textual` extra; install with
`pip install qmk-skim[tui]` if missing.

When combined with [`--config`](#configure-config), the existing file is
loaded into the editor. When combined with [`--keymap`](#configure-keymap),
the keymap-derived config is fed into the editor as the starting point.

---

### `--config`, `-c` { #configure-config }

| Type   | Default |
| ------ | ------- |
| `path` | `null`  |

Load an existing configuration file. Required to be readable.

When combined with `--keymap`, the keymap-derived config is treated as a
scaffold and the contents of `--config` are deep-merged on top — so user
edits like custom palette colors, titles, and copyrights are preserved
across reloads.

---

### `--keymap`, `-k` { #configure-keymap }

| Type   | Default |
| ------ | ------- |
| `path` | `null`  |

Path to a keymap file (`.kbi`, `.vil`, or `.json`). Skim extracts layer
names, palette base colors, and any custom keycodes it can resolve, then
writes a YAML config. For Keybard (`.kbi`) files, palette colors are
extracted from the firmware metadata; for Vial / c2json files they're
auto-derived.

---

### `--output`, `-o` { #configure-output }

| Type   | Default |
| ------ | ------- |
| `path` | `null`  |

Where to write the generated YAML. When the path points at a directory,
Skim writes `skim-config.yaml` inside it. Without `--output`, the YAML
prints to stdout (non-interactive) or is held in the TUI's save dialog
(interactive).

---

### `--force` { #configure-force }

| Type   | Default |
| ------ | ------- |
| `flag` | `false` |

Overwrite an existing output file without prompting. Without this flag,
Skim asks for confirmation; if stdin is a pipe, confirmation reads from
the controlling terminal.

---

### `--adjust-lightness`, `-L` { #configure-adjust-lightness }

| Type    | Default | Range     |
| ------- | ------- | --------- |
| `float` | `null`  | `0.0–1.0` |

Target lightness applied to layer base colors when generating from a
**Keybard** file. Has no effect for Vial or c2json input (those formats
don't carry layer colors). Modifies the
[`output.style.palette.layers`](config-file.md#output-style-palette-layers)
entries written to the generated config.

---

### `--adjust-saturation`, `-S` { #configure-adjust-saturation }

| Type    | Default | Range     |
| ------- | ------- | --------- |
| `float` | `null`  | `0.0–1.0` |

Cap saturation on layer base colors when generating from a Keybard file.
Modifies the
[`output.style.palette.layers`](config-file.md#output-style-palette-layers)
entries written to the generated config. Same input-format restriction as
[`--adjust-lightness`](#configure-adjust-lightness).

---

### `--title`, `-t` { #configure-title }

| Type     | Default |
| -------- | ------- |
| `string` | `null`  |

Set the value of [`output.keymap_title`](config-file.md#output-keymap-title)
in the generated config. Combines with every other flag — passing `-t`
alone writes a near-default config with just the title set.

---

### `--copyright`, `-r` { #configure-copyright }

| Type     | Default |
| -------- | ------- |
| `string` | `null`  |

Set the value of [`output.copyright`](config-file.md#output-copyright)
in the generated config.

---

### `--double-south`, `-d` { #configure-double-south }

| Type   | Default |
| ------ | ------- |
| `flag` | `false` |

Set [`keyboard.features.double_south`](config-file.md#keyboard-features-double-south)
to `true` in the generated config.

---

### `--width`, `-w` { #configure-width }

| Type    | Default |
| ------- | ------- |
| `float` | `null`  |

Set [`output.layout.width`](config-file.md#output-layout-width) in the
generated config.

---

### `--layer-count`, `-n` { #configure-layer-count }

| Type      | Default |
| --------- | ------- |
| `integer` | `null`  |

Pre-create N layers with default names (`Layer 0`, `Layer 1`, …) and
default palette colors. Writes to both
[`keyboard.layers`](config-file.md#keyboard-layers) and
[`output.style.palette.layers`](config-file.md#output-style-palette-layers).
Existing layer entries from `--config` or `--keymap` are preserved; any
indices below `N` that aren't yet defined are filled in. The resulting
list is sorted by layer index.

When the existing config already has at least N distinct layer indices,
the flag is a no-op.

---

## `doctor`

```bash
skim doctor --help
Usage: skim doctor [OPTIONS]

  Check system environment and dependencies.

Options:
  --help  Show this message and exit.
```

Check the local environment for everything Skim depends on. The command
takes no flags.

```bash
skim doctor
```

What it reports:

- **Installation Integrity** — every bundled font and asset (Roboto
  variants, Symbols Nerd Font, keycode-mapping table, glyph table,
  Svalboard logo) is reachable from the install.
- **Playwright (Chromium)** — required for raster export via Chromium.
- **Cairo Graphics** — required for raster export via Cairo (faster than
  Chromium).
- **System Font: \<name\>** — once per bundled font (`Roboto-Regular.ttf`,
  `Roboto-Black.ttf`, `Roboto-Thin.ttf`, `SymbolsNerdFont-Regular.ttf`).
  Failures are warnings, not errors — system fonts only matter when
  [`--use-system-fonts`](#generate-use-system-fonts) is set on `skim
  generate`.
- **Textual (TUI)** — required for the
  [Configurator UI](configurator-ui.md). Optional; absence is reported
  as a warning.

The command exits zero when every non-optional check passes. Failures on
optional checks (system fonts, render engines, Textual) print as `WARN`
lines and don't fail the run.

---

## Examples

A quick tour of common invocations.

---

### Render every layer plus the overview as SVG

```bash
$ skim generate -k layout.kbi -o ./out
out/keymap-layer-0.svg
out/keymap-layer-1.svg
out/keymap-overview.svg
```

The default behaviour: every per-layer image plus the overview, no
standalone legend images.

---

### Render a single layer as PNG

```bash
$ skim generate -k layout.kbi -o ./out -l 1 -f png
out/keymap-layer-1.png
```

---

### Render the overview plus the macros legend

```bash
$ skim generate -k layout.kbi -o ./out -l overview -l macros
out/keymap-overview.svg
out/keymap-macros.svg
```

---

### Render with a custom palette via config + width override

```bash
$ skim generate -c my-config.yaml -k layout.kbi -o ./out -w 2400
out/keymap-layer-0.svg
out/keymap-overview.svg
```

The CLI's `-w 2400` wins over any `output.layout.width` in
`my-config.yaml`.

---

### Pipe a c2json keymap through `skim generate`

```bash
$ qmk c2json -kb my/board -km vial --no-cpp keymap.c | skim generate - -o ./out -l overview
out/keymap-overview.svg
```

---

### Scaffold a config from a Keybard file

```bash
$ skim configure -k layout.kbi -o skim-config.yaml -t "My Layout" -r "© 2026 Me"
Configuration written to skim-config.yaml
```

The `-k` flag extracts layer names + palette; `-t` and `-r` populate
`output.keymap_title` and `output.copyright`.

---

### Edit an existing config in the TUI

```bash
$ skim configure -i -c skim-config.yaml
```

---

### Check render-engine availability

```bash
$ skim doctor
[PASS] Installation Integrity: All bundled assets are present.
[PASS] Playwright (Chromium): Available
[WARN] Cairo Graphics: Not available
       Details: Required for PNG/JPEG/WEBP export using Cairo (faster than Chromium).
...
```
