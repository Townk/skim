# Config TUI Design Spec

## Goal

Add a terminal UI (TUI) to the `skim configure` command that provides a form-based editor for skim configuration files. Launched when `skim configure` is run without the `-k` flag.

## Entry Point

- `skim configure` (no `-k`) launches the TUI
- `skim configure -o existing-config.yaml` loads the existing file as initial state
- `skim configure -k file.kbi` runs the existing CLI path (no TUI)
- TUI is skipped if stdout is not a TTY (piping) — falls back to printing default YAML to stdout

## Library

Textual, added as an optional dependency (like playwright/cairo). Core skim functionality does not require it. If the user runs `skim configure` without textual installed, show a helpful error message explaining how to install it.

## Layout

Tabbed panels with three tabs: **Keyboard** | **Keycodes** | **Output**. A persistent footer bar shows keybindings (Save, Quit, Help). Tab key or number keys (1/2/3) switch between tabs.

## Keyboard Tab

### Features Section

- Checkbox toggle for `double_south`

### Layers Section

List+detail split layout:
- **Left panel**: scrollable layer list showing index, label, and a color dot (read-only, color is edited in Output tab). Keybindings for add (`+`), remove (`-`/`Delete`), reorder (`Ctrl+Up`/`Ctrl+Down`).
- **Right panel**: edit form for the selected layer with text inputs for `label`, `name`, `id`, and `subtitle`. All fields are editable strings. `id` and `subtitle` may be empty (stored as `null`).

Layer colors are displayed as read-only context in the layer list. They are edited in the Output > Palette > Layer Colors section.

## Keycodes Tab

Two sections, each using the same list+detail split pattern:

### Pre-process Section

- **Left panel**: list of keycode-to-keycode mappings (shows `keycode -> target`). Add/remove keybindings.
- **Right panel**: edit form with `keycode` and `target` text inputs.

### Overrides Section

- **Left panel**: list of keycode-to-label mappings (shows `keycode -> target`). Add/remove keybindings.
- **Right panel**: edit form with `keycode` and `target` text inputs.

## Output Tab

### Layout Section

Numeric inputs for:
- `width` (float, default 800)
- `spacing.margin` (float, default 0)
- `spacing.inset` (float, default 20)

### Style Section

- `use_layer_colors_on_keys`: checkbox (default true)
- `hold_symbol_position`: dropdown/select with options: qmk, inward, outward (default outward)
- `show_layer_indicators`: checkbox (default true)
- `use_system_fonts`: checkbox (default false)
- Border: checkbox to enable/disable. When enabled, shows `width` (float, default 2) and `radius` (float, default 10) inputs.

### Palette Section

Color inputs (text fields accepting hex values or named colors) for:
- `neutral_color` (default #6F768B)
- `text_color` (default black)
- `key_label_color` (default white)
- `background_color` (default white)
- `border_color` (default black)

**Layer colors**: list matched by index to `keyboard.layers`. Each entry has `base_color` (text input), `color_index` (numeric input, default 2), and optional `gradient` (6-color tuple, editable as comma-separated hex values or left empty for auto-generation).

**Named color overrides**: key-value list (name -> hex color). Add/remove entries.

### Copyright Section

Single text input for the optional copyright string. Empty means `null`.

## Save Behavior

- `Ctrl+S` saves to the output path (from `-o` argument)
- If no `-o` was provided, prompts for a file path on first save
- If the target file exists, confirms overwrite (unless `--force` was passed)
- Saving validates the config through `SkimConfig.model_validate()` before writing YAML. If validation fails, shows an error message and does not write.
- `Q` or `Ctrl+C` quits. If there are unsaved changes, confirms before exiting.

## No YAML Preview

The TUI does not show a live YAML preview. Users save and inspect the file externally. This avoids the expectation that the YAML should be editable inline.

## Dependency Management

`textual` is added as an optional dependency in `pyproject.toml`:

```toml
[project.optional-dependencies]
tui = ["textual>=1.0.0"]
```

The TUI import is guarded with a try/except in the CLI. If textual is not installed and the user invokes the TUI path, a clear error message is shown:

```
Error: The TUI requires the 'textual' package. Install it with:
    pip install qmk-skim[tui]
```

### Doctor Check

The `skim doctor` command gains a check for textual availability, following the same pattern as the existing Playwright and Cairo checks. It reports PASS/WARN with installation instructions. Since textual is optional (only needed for the TUI), a missing textual should be a WARN, not a FAIL — same treatment as Cairo and Playwright.

## Architecture

### File Structure

| File | Responsibility |
|------|---------------|
| `src/skim/tui/app.py` | Main Textual App class, tab layout, save/quit logic |
| `src/skim/tui/keyboard_tab.py` | Keyboard tab: features checkboxes, layers list+detail |
| `src/skim/tui/keycodes_tab.py` | Keycodes tab: pre_process and overrides list+detail |
| `src/skim/tui/output_tab.py` | Output tab: layout, style, palette, copyright |
| `src/skim/tui/widgets.py` | Shared reusable widgets (list+detail split, key-value editor) |
| `src/skim/tui/__init__.py` | Package init, public launch function |

### Data Flow

1. CLI parses args, loads existing config (if `-o` points to a file) or creates `SkimConfig()` default
2. Config is converted to a mutable dict (`model_dump(mode="json")`) and passed to the TUI app
3. TUI widgets read from and write to the mutable dict
4. On save: dict is validated through `SkimConfig.model_validate()`, serialized to YAML, written to file
5. On quit: if dict differs from last-saved state, prompt to save or discard

### Integration with CLI

The `configure` function in `cli.py` gains a branch: if no `-k` and stdout is a TTY, import and launch the TUI. The lazy import pattern (import inside function) keeps startup fast and avoids ImportError when textual is not installed.
