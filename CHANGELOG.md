# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.7.3] - 2026-05-08

### Added

- **`output.layout.spacing` block** with 15 configurable fields covering
  every gap, padding, and inset the renderer paints. Each field accepts
  one of three forms following a single magnitude rule:
  - Float `< 1.0` — proportion of the field's base (usually doc width).
  - Float `≥ 1.0` — absolute SVG units.
  - String `"N%"` — shorthand for `N / 100` (proportion form).
  - `null` — the field's built-in default proportion.

  Fields: `margin`, `inset`, `column_gap`, `section_spacing`,
  `section_title_rule_gap`, `table_header_spacing`, `table_col_spacing`,
  `table_row_spacing`, `finger_key_gap`, `thumb_key_gap`,
  `layer_indicator_spacing`, `chip_padding`, `tap_dance_pill_padding`,
  `macro_action_inset`, `layer_badge_inset`. See
  `docs/configuration/config-file.md` for per-field illustrations.
- **`output.style.strokes` block** for stroke-width styling — fields
  `chip_outline` (1.2/1600 default) and `header_rule` (1.2/1600
  default). Both follow the same magnitude rule as the spacings.
- **`output.style.layer_connector` block** with `show` (default `true`),
  `width` (4.375/1600 default), and `dot_spacing` (12.25/1600 default)
  for the overview's dotted connector paths.
- **`output.style.layer_indicator` block** with `show` (default `true`)
  and `width` (2.0/1600 default) for the layer-indicator badges.
- **`output.style.legend_tables` block** grouping the three legend
  sub-blocks: `macros`, `tap_dances`, `symbols`. Each sub-block carries
  `show` (default `true`) and `scale` (default `1.5`); the `symbols`
  sub-block also carries `flow` and `columns`.
- **`just docs-gen-images`** recipe regenerates every image embedded in
  the published docs in one command — `option-images`, `spacing-mocks`,
  `screenshots`, plus `docs/_static/keymap-1.svg` and
  `docs/_static/svalboard-overview.svg` rendered from
  `samples/config/SvalCOLEMAK-config.yaml` +
  `samples/keymaps/SvalCOLEMAKDHM.vil`. The `release` recipe now invokes
  it instead of running `option-images` + `screenshots` separately, so
  spacing mocks and the keymap images stay coupled to the renderer on
  every release.
- **`scripts/release_changelog.py promote X.Y.Z`** rewrites
  `CHANGELOG.md` for a release: renames `## [Unreleased]` to
  `## [X.Y.Z] - YYYY-MM-DD`, inserts a fresh empty `## [Unreleased]`
  block above it, and updates the link-reference list at the bottom
  (rewrites `[Unreleased]` to compare `vX.Y.Z...HEAD` and inserts a new
  `[X.Y.Z]: ...compare/<prev>...vX.Y.Z` entry, where `<prev>` is parsed
  from the previous `[Unreleased]` link). Idempotent — aborts if a
  `[X.Y.Z]` section already exists. The `release` recipe now invokes it
  so the changelog stays in sync with the released version
  automatically.

### Changed

- `output.style.border.width` accepts the same magnitude rule as the
  spacings — float `< 1` is a proportion of the doc width, float `≥ 1`
  is absolute SVG units, `"N%"` is the proportion shorthand. Default
  value (2 SVG units) is unchanged.
- Section title strips top-anchor the title text (no more dangling
  whitespace above the title); the strip's height equals
  `title_font_size + section_title_rule_gap`.
- The overview's layer badge splits its label into a right-aligned
  index column and a left-aligned name column, with the index column
  sized to fit the widest index across the rendered layers. Variant
  labels now align under the name column (or at the leading inset for
  auto-named `LAYER N` badges, matching the legacy single-text layout).
- The overview's named-macro hairline rule weight is now unified with
  the section-stripe rule weight (1.2/1600, was 1.0/1600).
- The overview's layer-indicator gap is now uniform across finger and
  thumb clusters (12/1600 of doc width). Previously each cluster type
  used its own cluster-relative ratio that produced different gaps.
- `MacroPill` now positions the action icon's *left edge* at
  `macro_action_inset` from the pill border (centre at `inset +
  icon_w/2`) instead of its centre. Result: the visible whitespace
  before the icon, between icon and text, and between text and pill
  border are all uniformly `macro_action_inset` wide, and the
  text-centring math no longer leaves `icon_w/4` of slack on each
  side of the label.
- `MacroRow` named-header chip→name gap switched from `chip_padding`
  to `table_header_spacing`. The chip→name gap is conceptually a
  "row-header → row-content" boundary — the same role
  `table_header_spacing` already plays for column-header→first-row
  and chip→first-cell. `chip_padding` is the symmetric inset *inside*
  a chip (border ↔ glyph / name text), not a between-elements gap.
- `using_render_context` accepts an optional
  `font_usage_collector` parameter so callers that compose multiple
  panels under different `ctx` instances can share one collector and
  get the union of every panel's character usage when embedding
  fonts. Default behaviour (a fresh per-block collector) is
  unchanged.

### Fixed

- Connector-router source rects in `KeymapOverview` were keyed by
  `id(key)`. Reusing the same `SvalboardTargetKey` instance across
  multiple cluster slots (e.g. binding `LT(NAV) =
  SvalboardTargetKey(label="LT(NAV)", layer_switch=1)` to both thumb
  pads) collapsed every reuse onto a single dict slot — only one
  connector ever painted, from whichever slot wrote the rect last.
  Each `ConnectorStep` now carries its `source_layer` and
  `source_side`, and the rect dict is keyed by structural position
  (`finger.<source_layer>.<cluster_attr>.<slot>` /
  `thumb.<source_layer>.<source_side>.<slot>`), so every source slot
  gets its own indicator regardless of the underlying key's Python
  identity.
- `Spacing.finger_key_gap` source docstring corrected from `3.8%` to
  `1.8%` — the renderer uses `_INSET_WIDTH_PROPORTION = 0.018`, and the
  user-facing reference already documented `1.8%`.
- `samples/config/{skim,SvalCOLEMAK,SvalQWERTY}-config.yaml` migrated to
  the current nested schema. The samples were silently broken — Pydantic
  rejected the legacy flat fields (`show_layer_indicators`,
  `show_layer_connectors`, `show_special_keys_legend`,
  `show_symbol_legend`, `symbol_legend_flow`, `symbol_legend_columns`,
  `macros_scale`, `tap_dances_scale`, `symbols_scale`) as
  `extra_forbidden`, so `skim generate -c samples/config/...yaml` failed
  validation. The samples now exercise `layer_indicator.show`,
  `layer_connector.show`, and `legend_tables.{macros,tap_dances,symbols}`.
- CHANGELOG dates for the `0.7.0` and `0.7.2` releases were inverted;
  corrected to chronological order (0.7.0 on 2026-05-03, 0.7.2 on
  2026-05-04).
- CHANGELOG link-reference list at the bottom of the file was stale —
  the `[Unreleased]` link pointed at `compare/v0.5.3...HEAD` despite
  v0.7.2 being the latest release, and `[0.5.4]`, `[0.5.5]`, `[0.7.0]`,
  `[0.7.2]` had no entries. Backfilled the missing entries and
  rewrote `[Unreleased]` to compare `v0.7.2...HEAD` so the existing
  links resolve correctly on GitHub.

### Documentation

- `output.style.palette.layers` reference now accurately describes
  the gradient auto-derivation behaviour (the keymap-generation
  pipeline replaces `gradient: null` with
  `make_gradient(base_color, color_index)` before rendering, so the
  rendered output always sees a 6-stop tuple). `color_index`'s
  dual role as gradient anchor and primary-stop selector is
  explicit. Two double-south finger-cluster images illustrate the
  auto-derived and explicit gradient YAML forms side by side.
- Added fully-coloured sample images under each
  `output.style.legend_tables` sub-block (`macros`, `tap_dances`,
  `symbols`) — the macros and tap-dances samples mix named and
  unnamed entries so the named-vs-unnamed layout split reads at
  a glance.
- Chrome-colour table now carries inline colour swatches next to
  each default value.
- Tables now keep all columns single-line except the description
  column, which absorbs the wrapping. Stops the renderer from
  choosing a Type / Default column to wrap when the description
  column is long.
- Spacing-mock illustrations refined: every band aligns precisely
  with the option it represents (no overlap with borders, glyphs,
  or labels), Nerd-Font glyphs render across all viewers (bundled
  fonts subset and embedded), and several sets of related mocks
  (section-spacing / section-title-rule-gap / table-*-spacing /
  header-rule-stroke) share a single canvas shape so the docs
  render them at matching font sizes.
- `docs/configuration/cli-options.md` is now a full reference for
  every `skim` subcommand — `generate`, `configure`, `doctor` —
  plus the global `--version`, `--verbosity`, and `--quiet` flags.
  Each flag carries the canonical type table, an explicit anchor
  ID, and (where the flag drives a config field) a link to the
  matching field in `config-file.md`. Added the missing
  `keyboard.features.double_south` anchor in `config-file.md` so
  the cross-reference resolves.
- `docs/configuration/cli-options.md` and
  `docs/configuration/config-file.md` now insert a `---` separator
  above every H2/H3/H4 heading (and every H5 inside `config-file.md`,
  where each H5 documents its own reference field), matching the visual
  rhythm already used in `docs/configuration/configurator-ui.md`.
- `docs/configuration/cli-options.md` scale-flag ranges
  (`--macros-scale`, `--tap-dances-scale`, `--symbols-scale`) corrected
  from `> 0.1` to `≥ 0.1` — `click.FloatRange(min=0.1)` is inclusive.
- `docs/configuration/config-file.md` bundled-fonts list now includes
  JetBrains Mono Nerd Font Mono (used by the Configurator UI screenshot
  pipeline; previously omitted).
- `docs/api/ui.md` heading "Style Tab" → "Output Tab" so the heading
  matches the actual module (`skim.tui.output_tab`) and the UI label.
- `docs/api/application.md` adds a `Doctor` section so
  `skim.application.doctor` is rendered alongside the other application
  modules.
- `docs/_static/keymap-1.svg` and `docs/_static/svalboard-overview.svg`
  regenerated against the current renderer. Previously the files were
  hand-copied from a one-shot run; they are now reproducible via
  `just docs-gen-images`.

### Removed

> [!IMPORTANT]
> The renames below are **breaking schema changes**. Existing YAML
> configs that set any of the listed fields will fail validation
> against the new schema. Pre-1.0 migration is by manual rewrite —
> no deprecation aliases are shipped. Update your config to the new
> nested paths.

- `output.style.macros_scale` → `output.style.legend_tables.macros.scale`
- `output.style.tap_dances_scale` → `output.style.legend_tables.tap_dances.scale`
- `output.style.symbols_scale` → `output.style.legend_tables.symbols.scale`
- `output.style.show_special_keys_legend` → splits into
  `output.style.legend_tables.macros.show` and
  `output.style.legend_tables.tap_dances.show`. Set both to the same
  value to preserve the legacy combined behaviour, or set them
  independently to selectively hide one legend.
- `output.style.show_symbol_legend` → `output.style.legend_tables.symbols.show`
- `output.style.symbol_legend_flow` → `output.style.legend_tables.symbols.flow`
- `output.style.symbol_legend_columns` → `output.style.legend_tables.symbols.columns`
- `output.style.show_layer_connectors` → `output.style.layer_connector.show`
- `output.style.show_layer_indicators` → `output.style.layer_indicator.show`
- (Internal): the legacy field `Style.name_gap` was renamed to
  `chip_padding` and its default value doubled (10/1600 → 20/1600) so
  the derived `chip_vertical_padding = chip_padding * 0.25` matches the
  legacy chip height. Visible name-area horizontal padding inside
  TD chip outlines therefore widens.
- **`output.style.palette.overrides`** field removed entirely. The
  feature was added before CSS-named-color support (`"crimson"`,
  `"steelblue"`, etc.) was wired through `webcolors.name_to_rgb`,
  intended to let users redefine the W3C named colors. In practice
  the resolved override dict was never consumed by the rendering
  pipeline — `parse_color` always reached straight for the W3C
  values — so the feature has been a no-op since 0.5.0. Existing
  YAML configs that include `palette.overrides` will fail validation;
  delete the block.
- **`skim configure --qmk-color-header` / `-C`** flag removed. The
  flag parsed `HSV_*` / `RGB_*` `#define`s out of a QMK `color.h`
  file and dumped them into `palette.overrides`. With that field
  gone, the import has no destination.
- Internal: `ConfigGenerator._parse_qmk_colors` and the
  `qmk_header_content` parameter on `generate_from_keybard` removed
  alongside the CLI flag.
- Internal: dropped three unused TUI screenshot shots (`keycodes-tab`,
  `output-tab`, `output-style-tab`) from `scripts/screenshots.py` and
  the corresponding orphan SVGs from `docs/_static/tui/`. They were
  generated by `just screenshots` but no documentation referenced them.

## [0.7.2] - 2026-05-04

### Fixed

- ``hold_symbol_position`` now actually reorders hold/tap labels.
  The setting was silent for the entire 0.7.0 lifecycle:
  ``_adjust_hold_symbol_label`` checked for the ASCII pipe ``|``
  while real labels carry the box-drawing ``│`` (U+2502), so the
  function early-returned every time. Once the swap path runs, the
  semantics are now cluster-relative — ``OUTWARD`` puts HOLD on
  the side of the cluster the key sits on (LEFT-side keys keep
  the default ``HOLD│TAP`` order; RIGHT-side keys swap to
  ``TAP│HOLD``). Applies uniformly to finger east/west keys and
  to thumb pad / up / nail / knuckle keys regardless of which
  keyboard half the cluster sits on.
- Missing modifier-union mappings for the L/R OPT, CMD, and WIN
  aliases (``MOD_LOPT``, ``MOD_LCMD``, ``MOD_LWIN``, ``MOD_ROPT``,
  ``MOD_RCMD``, ``MOD_RWIN``) so labels referencing those modifiers
  resolve to the same glyph as their ``ALT`` / ``GUI`` canonical
  forms.

### Changed

- Thumb cluster label alignment is now uniformly centred for the
  Pad, Nail, Knuckle, Down, and Double-down keys. Up keeps its
  inward-aligned label (the trapezoid wants the text on the wide
  outer face). Previously Pad / Nail / Knuckle anchored to the
  slanted edge, which read inconsistently next to the centred
  Down / Double-down labels.

## [0.7.0] - 2026-05-03

This release replaces the imperative SVG renderer with a composable
rendering framework, adds automatic font subsetting, and ships a wave
of layout-quality fixes.

### Added

- **Composable rendering framework.** Every image — per-layer keymaps,
  multi-layer overview, macros, tap-dances, special-keys, symbols — is
  now built as a tree of small, single-purpose composables that report
  a `Size` plus a `draw_at(d, origin)` painter. Replaces ~5K lines of
  positional layout math with a uniform tree-building model.
  - `RenderContext` carries config / keymap / theme / document metrics
    via a `ContextVar`; `@Composable(use_context=True)` factories
    receive it implicitly.
  - `MetricsComponent[M]` lets composables expose typed metrics
    (e.g., `LayerIndicatorMetrics.routing_origin`,
    `FingerHalfMetrics.overflow_size`) without exposing internals.
  - Overflow-aware geometry — every cluster / half reports
    `(size, overflow_size, overflow_offset)` so parents can place
    chrome like layer-switch indicators without hidden assumptions.
  - Single-page documents: `KeymapLayerDocument`,
    `KeymapOverviewDocument`, `KeymapMacroDocument`,
    `KeymapTapDanceDocument`, `KeymapSpecialKeysDocument`,
    `KeymapSymbolDocument`. Each entry point reduces to
    `render(<Document>(...))`.
- **Automatic font subsetting** in SVG output. `FontUsageCollector`
  records every character painted via `AdjustableText` / `RichText` /
  the title text; on render, only the glyphs actually used are
  embedded. SVG output sizes drop dramatically (overview: ~5MB → ~360KB;
  per-layer: ~104KB → ~89KB). `--use-system-fonts` skips embedding
  entirely.
- **`AdjustableText` and `RichText` composables.** Single-style and
  multi-span text with synchronised shrink-to-fit, per-span
  proportional `min_font_size` floors, and ellipsis truncation.
  RichText accepts a markup string with Nerd Font tokens
  (`%%nf-md-keyboard;`) and the `│` separator character; the parser
  handles font routing (Symbols / Unicode Symbols fallbacks)
  automatically.
- **Transparent fall-through rendering** — `KC_TRANSPARENT` /
  `KC_TRNS` / `_______` keys on layers above 0 borrow the layer-0
  label and are drawn as a faded "ghost".
  - Ghost text colour is the key's fill colour with HSL lightness
    shifted by 0.12 — lighter when the fill sits at or below the
    layer's base colour in the gradient, darker when it sits above.
  - When the layer-0 source maps to a layer change (`MO()`, `LT()`,
    etc.), the ghost key inherits that `layer_switch` and is treated
    as a layer-triggering key — getting the destination layer's
    background colour, indicator badge, and overview connector.
  - New `style.show_transparent_fallthrough` option (default `true`)
    lets users opt out and revert to blank transparent keys. TUI
    configurator gets a matching toggle and contextual help blurb.
- **Per-image body-scale flags** for the standalone images:
  `--macros-scale`, `--tap-dances-scale`, `--symbols-scale`. Body
  content (chips, pills, glyphs, symbol descriptions) scales by the
  multiplier; chrome (title, footer, padding) stays at the unscaled
  per-image size. CLI overrides matching config fields persist on
  the resolved `Style`.
- **Symbols image and symbol legend.** A new standalone `keymap-symbols`
  image plus a per-layer / overview symbol legend. Walks each key's
  raw keycode, recurses through wrapper functions (`LT(N, KC_A)`),
  tap-dance variants, and macro action keys; resolves alias chains;
  renders one row per distinct canonical keycode or function name.
  Categories are read from `keycode-mappings.yaml`'s
  `symbol_descriptions` insertion order — edit the YAML to reorder
  legend groupings.
  - `--symbol-columns` flag forces an exact column count (canvas
    shrinks to the resulting width).
  - `--no-symbols` opts out of the legend.
- **Cross-layer connector routing in the overview.** Multi-source
  Phase-1/Phase-2 router that draws dotted lines from each
  layer-trigger key (in finger or thumb clusters) to its target
  layer's row. Paths share routing columns when their Y-spans don't
  overlap; paths to the same target merge their final horizontal
  segment so a single visible LEFT segment connects all sources to
  that layer's row. Special-cases: LT_Up/LT_Down on the same thumb
  cluster, S+DS triggers on non-R4 finger clusters.
- **Auto-derived configuration** from the input keymap when
  `--config` isn't provided.
- **DejaVu Sans Mono / Condensed** as Unicode-symbol fallback —
  covers `⎇`, `│`, and other characters Roboto doesn't carry.
- **Per-image `wrap_content` semantics** on `MacroSection`,
  `TapDanceSection`, `SymbolSection`. The standalone images snug
  the canvas to natural content width; combined / per-layer
  documents inflate sections to fill the column budget.

### Changed

- **Layout overhaul of the multi-layer overview.**
  - Badge column → cluster column gap pinned at exactly
    `2 × column_gap`. Indicators that bleed left of the keys-only
    edge paint visually into the gap (paint-only, no layout claim).
  - Central gap between the two halves pinned at `2 × column_gap`
    measured between the finger halves' inward-indicator extents.
  - Thumb clusters align with the finger halves' keys-only edges
    (left thumb's right edge with the left half's right edge; right
    thumb's left edge with the right half's left edge). When BOTH
    thumbs have inward-bleeding indicators (knuckle / nail keys
    with a `layer_switch`), the central column widens so the
    visible chrome-to-chrome gap is at least `column_gap`.
  - Layers render highest-to-lowest QMK index — most-specialised
    layers read first, layer 0 at the bottom.
  - Layer-row spacing is indicator-aware; canvas extents account
    for layer-switch indicator circles that overflow cluster bounds.
  - Default canvas width bumped from 800 to 1600 SVG units.
  - Title and copyright font sizes are now doc-width-proportional
    (~31pt title, ~17pt copyright at the canonical width).
- **Spacing convention is uniform across every image.** `inset` for
  vertical spacing (Column gaps, outer chrome border-to-content
  gap), `column_gap` for horizontal spacing (inter-cluster gap
  inside a half), `2 × column_gap` for primary visual dividers
  (central halves gap, badge → cluster gap, macro/TD pair gap).
- **Connector spacing** pinned at `0.6 × outer_key_width` for
  tighter, more readable lane / column placement.
- **Macro / tap-dance display.**
  - Named macros sort first (named-block then unnamed-block,
    separated by `section_spacing` instead of the usual row gap).
  - Tap-dance name column resizes dynamically to fit the longest
    name within the available budget; per-row ellipsis truncation
    when names still overflow.
  - Macro pills and tap-dance cells render through `RichText`, so
    labels containing Nerd Font tokens render with the right
    per-span fonts.
- **Function-description templates** in `keycode-mappings.yaml` use
  `@N;` / `#N;` placeholders for argument substitution and `|;` for
  the separator character. Per-instance descriptions (e.g. specific
  layer numbers) and generic descriptions (one entry per function
  name) are both supported.
- **Renamed CLI flag** `--keybard-keymap` → `--keymap`.
- **Render-engine selection** via `--render-engine chromium|cairo`.
  The Cairo path converts text elements to SVG paths so output
  rasterises consistently regardless of which fonts the system has
  installed.

### Fixed

- Title text now correctly renders in Roboto Thin — the title
  characters are registered with the font subsetter so the embedded
  `@font-face` rule is included in the output SVG.
- `--width` is honoured as the final SVG / PNG canvas width.
- Tap-dance name truncation measures actually-painted text width
  instead of overshooting from font-metrics estimates.
- Symbol legend's `symbol_legend_aliases` apply to function-call
  patterns (e.g. `A(KC_RGHT)` resolves to `A(KC_RIGHT)`'s entry).
- F-keys in the `c2json-sample.json` Function Keys layer are
  positioned correctly (previously mirrored across the right
  cluster's E↔W axis).
- `skim` prompts for overwrite confirmation via `/dev/tty` when
  stdin is a pipe.

### Internal

- Module structure consolidated. `text.py` → `font.py`; `legend.py`
  → `section_data.py` (now also hosts the symbol-entry resolution
  layer that previously lived in a now-deleted `symbol_legend.py`).
  `text_to_paths.py` moved from `render/` to `exporter/` (its only
  consumer is the Cairo exporter). `layout.py` deleted.
- All concrete document composables consolidated in
  `keymap_document.py`. Body composables stay in their per-image
  modules (`keymap_layer.py`, `keymap_overview.py`).
- Entry points in `__init__.py` own all data prep — pre-resolving
  macros / tap-dances / symbol entries before passing pre-resolved
  lists to the document composables. Documents are pure layout
  consumers.
- `__all__` exports tightened across the rendering layer to advertise
  only what other production modules actually import.

## [0.5.5] - 2026-04-26

### Added

- Multi-source overview connector routing — dotted lines from each layer-trigger key (in finger and thumb clusters) to its target layer's row.
  - Per-layer finger-cluster routing across every rendered layer; `MO()` / `LT()` / equivalent layer-switch keys produce a connector regardless of which layer they live on.
  - Thumb-cluster routing with the LT_Up + LT_Down LEFT-DOWN special case (the LT_Up path detours west of LT_Down's drop column when both trigger).
  - Non-R4 finger clusters with both `south_key` and `double_south_key` triggering produce a RIGHT-DOWN-RIGHT South path that clears the DS drop column.
  - Global Phase 2 column allocation: paths from all sources share routing columns when their vertical Y-spans don't overlap, so column count tracks Y-overlap instead of total path count.
  - Multi-target merge: paths targeting the same layer share a final horizontal segment, so a single visible LEFT segment connects all sources to that layer's row.
- Macro (`M1`–`M50`) and tap-dance keycode mappings, rendered with distinct nf-md icon glyphs in the overview.
- Synthetic Vial fixture (`tests/integration/fixtures/connector-routing-coverage.vil`) plus structured-assertion integration tests covering R4 / non-R4 / S+DS / multi-layer routing.

### Changed

- Connector spacing pinned at `0.6 × outer_key_width` for tighter, more readable lane/column placement.
- Layer-badge column gap pinned at `4 × KEYMAP_SPACING` so the visual rhythm tracks the connector router instead of canvas-relative inset units.
- Layer badges now align exactly with the West finger key in their row — same Y (top edge) and same height (`outer_key_size`).
- Default canvas width bumped from 800 to 1600 SVG units for better legibility.
- Inter-row spacing rhythm in the overview is now consistent regardless of Double-South presence.
- Layer-row spacing is now indicator-aware — canvas extents account for layer-switch indicator circles that overflow cluster bounds.
- `skim` derives a default config from the input keymap when `--config` isn't provided.

### Fixed

- `skim` now prompts for overwrite confirmation via `/dev/tty` when stdin is a pipe (previously silently overwrote or hung).
- F-keys in the `c2json-sample.json` Function Keys layer were mirrored across the right cluster's E↔W axis (F1↔F4 and F2↔F3); now positioned correctly.

## [0.5.4] - 2026-04-24

### Fixed

- Pydantic 2.13+ compatibility: `SplitSidePosition` enum used as a `BeforeValidator` caused a crash on Python 3.12+ due to stricter validator signature inspection.

### Changed

- Development environment now uses the latest Python version (via mise) to catch compatibility issues earlier. The project still supports Python 3.10+.

## [0.5.3] - 2026-04-24

### Added

- Contextual help system for the TUI configurator — press F1 or Alt+H on any field to see a help modal with field-specific documentation.
  - Per-field markdown help content for all fields across Keyboard, Keycodes, and Style tabs.
  - Vim-style scroll bindings in help modal (j/k, Ctrl+D/U, Ctrl+F/B, G/g).
  - General help fallback with keyboard shortcuts overview.
- `show_layer_connectors` configuration option to toggle layer connector lines in overview images.
- `--title` and `--copyright` options to `configure` command.
- `--layer-count` option with sparse fill logic for `configure` command.
- `--keymap` option to `configure` for Vial and c2json format support.
- Layer move mode to reorder layers in list views.
- Custom `SkimButton` widget with Space and Enter activation.

### Changed

- Renamed `--keybard-keymap` CLI option to `--keymap`.
- Non-standard keycode scanning for configuration generation.
- Skip empty layers and simplify keycode override detection.
- Updated documentation: README, Sphinx docs, and example SVGs to reflect current features.

### Fixed

- Directional focus navigation inside modal dialogs.
- QMK firmware index used for layer lookup, fixing overview rendering issues.
- Circular dots for overview layer connectors (previously rendered as pills).
- Footer keybind display order and styling standardised.
- GitHub Actions and PyPI publishing fixes.

## [0.5.2] - 2026-04-22

### Fixed

- GitHub Actions and PyPI publishing fixes.

## [0.5.1] - 2026-04-22

### Fixed

- GitHub Actions and PyPI publishing fixes.

## [0.5.0] - 2026-04-22

### Added

- Interactive TUI for configuration editing via `skim configure --interactive`.
  - Tabbed interface with Keyboard, Keycodes, and Style tabs.
  - List/detail panels for layers, keycodes, and layer colors.
  - Enter-to-edit, Escape-to-rollback field editing with commit/cancel hints.
  - Add/Remove buttons for layers, keycodes, and layer colors.
  - Color swatches and W3C named color suggestions for color input fields.
  - Gradient preview on dark and light backgrounds with index numbers.
  - Dynamic/Manual gradient type selector for layer colors.
  - Keycode autocomplete and spatial arrow-key focus navigation.
  - Save & quit dialog with confirmation.
- Overview image rendering with layer badges and cluster layout.
  - Dotted connector lines from layer indicator circles to target layers.
  - Intelligent connector routing with per-key escape directions.
- Layer indicator circles on individual layer images.
- Non-sequential layer index support (QMK index independent of config position).
  - Layer index field editing with validation in TUI.
  - Dict-based keymap layers in data model.
- `skim doctor` command with cairo optional dependency check.
- `ConfigGenerator` for generating default and keybard-based configurations.
- Font subsetting support via `FontUsageAnalyzer` and `FontSubsetter`.
- `subtitle` (later renamed to `variant`) field for `KeyboardLayer`.
- Optional `copyright` field in Output configuration.
- `--interactive` and `--config` flags for `configure` command.

### Changed

- Renamed `KeyboardLayer.subtitle` to `variant`.
- Extracted reusable `ListDetailPane` base class for TUI widgets.
- Major overview layout overhaul with improved badge positioning and connector routing.
- Upgraded dependencies.

### Fixed

- Resolved all ruff lint, formatting, and basedpyright errors.
- Granted `id-token` permission for PyPI trusted publishing.
- Numerous TUI layout, focus, and interaction fixes.

## [0.4.4] - 2026-01-19

### Added

- Support for QMK hold-tap keys (e.g., `LT(1, KC_SPC)`, `LSFT_T(KC_A)`).
- Support for complex macro functions via `macro_functions` mapping.
- Support for modifier union arguments (e.g., `OSM(MOD_LCTL|MOD_LSFT)`).

### Changed

- Updated config generator to create `USER##` mappings for custom keycodes found in Keybard files.
- Improved config generator to prevent duplicate custom key entries if they already exist in internal mappings.
- Refactored keycode transformer to use a unified, data-driven pipeline for
  resolving all function-style keycodes (modifiers, layers, macros).
- Modified the release workflow to call the publish workflow directly to
  guarantee PyPI always receives a new release version when there is one.

### Fixed

- Fixed incorrect nesting of `named_colors` in generated configuration files (now directly under `appearance`).
- Fixed issue where layer toggle targets were not identified when using aliased keycodes in `reversed_alias`.
- Fixed bug where `skim generate` would create files even when user aborted the overwrite prompt.
- Fixed inconsistent behavior in `skim configure` by adding an overwrite confirmation prompt (matching `generate`).
- Fixed false positive overwrite prompt in `skim configure` when output is an existing directory (now targets `skim-config.yaml` inside it).

## [0.4.3] - 2026-01-15

### Added

- Version validation script (`scripts/validate_version.py`)
- Git hooks for release automation (`scripts/hooks/`)
- Hook setup script (`scripts/setup-hooks.sh`)

### Changed

- Release workflow now supports both dev and release versions from
  `pyproject.toml`
- Renamed `prerelease.yml` to `release.yml`
- Release automation via `reference-transaction` hook auto-bumps and pushes
  dev version after release push

## [0.4.2] - 2026-01-15

### Added

- Overwrite protection with interactive confirmation prompt when output files
  exist
- `--force` flag for `skim generate` to skip overwrite confirmation
- OpenSpec framework for AI-assisted change management (`openspec/`)

## [0.4.1] - 2026-01-14

### Added

- Pre-release GitHub Actions workflow to auto-build versions on commit
- Package keywords and classifiers in `pyproject.toml`
- Automated coverage badge updates via pre-commit hook
- Sphinx documentation theme changed to Furo with GitHub integration
- New helper script `scripts/update_coverage.py`

### Changed

- Renamed package to `qmk-skim`
- Updated uv build configuration
- Updated README badges for coverage, build status, and PyPI version

## [0.4.0] - 2025-01-14

### Added

- Initial public release of skim (Svalboard Keymap Image Maker)
- CLI tool for generating keyboard layout images from keymap files
- Support for Keybard (`.kbi`), Vial (`.vil`), and QMK c2json (`.json`) formats
- SVG and PNG output format support
- Layer selection options (all, overview, specific layers, ranges)
- Configuration file support for customizing appearance
- Configuration generator for extracting metadata from Keybard files
- QMK color.h import support with lightness/saturation adjustment
- Stdin support for piping keymap data
- Comprehensive test suite with 96% code coverage
- Google-style docstrings for all public APIs
- Sphinx documentation with GitHub Pages deployment workflow
- Pre-commit hooks for ruff formatting/linting and basedpyright type checking

[Unreleased]: https://github.com/Townk/skim/compare/v0.7.3...HEAD
[0.7.3]: https://github.com/Townk/skim/compare/v0.7.2...v0.7.3
[0.7.2]: https://github.com/Townk/skim/compare/v0.7.0...v0.7.2
[0.7.0]: https://github.com/Townk/skim/compare/v0.5.5...v0.7.0
[0.5.5]: https://github.com/Townk/skim/compare/v0.5.4...v0.5.5
[0.5.4]: https://github.com/Townk/skim/compare/v0.5.3...v0.5.4
[0.5.3]: https://github.com/Townk/skim/compare/v0.5.2...v0.5.3
[0.5.2]: https://github.com/Townk/skim/compare/v0.5.1...v0.5.2
[0.5.1]: https://github.com/Townk/skim/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/Townk/skim/compare/v0.4.4...v0.5.0
[0.4.4]: https://github.com/Townk/skim/compare/v0.4.3...v0.4.4
[0.4.3]: https://github.com/Townk/skim/compare/v0.4.2...v0.4.3
[0.4.2]: https://github.com/Townk/skim/compare/v0.4.1...v0.4.2
[0.4.1]: https://github.com/Townk/skim/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/Townk/skim/releases/tag/v0.4.0
