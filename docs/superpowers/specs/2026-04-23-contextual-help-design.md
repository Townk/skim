# Contextual Help System for the TUI Configurator

## Problem

Documentation for CLI/TUI tools goes unread because it's disconnected from where users need it. Users shouldn't have to leave the application to understand what a field does or how to interact with it.

## Solution

Press F1 anywhere in the TUI to get a help modal showing a rendered markdown document specific to the focused field. The help content lives in `src/skim/assets/help/` as individual `.md` files, loaded at runtime via the existing `BundleAssets` pattern.

## Architecture

### Help content loading

Add a `help_text(key: str) -> str` method and a private `_resolve_help(key: str) -> Path` helper to `BundleAssets` in `src/skim/assets/__init__.py`.

```python
def help_text(self, key: str) -> str:
    return self._resolve_help(key).read_text()

def _resolve_help(self, key: str) -> Path:
    path = cast(Path, resources.files("skim.assets") / "help" / f"{key}.md")
    if path.is_file():
        return path
    fallback = cast(Path, resources.files("skim.assets") / "help" / "general.md")
    if fallback.is_file():
        return fallback
    raise FileNotFoundError("No help content available.")
```

Unlike the existing `_resolve()` method (which raises on missing files), `_resolve_help` gracefully falls back to `general.md` when a specific help file doesn't exist. The `_get_cached` caching pattern is not used here since help is accessed infrequently (on F1 press only).

### Widget `help_key` parameter

Add an optional `help_key: str | None = None` keyword argument to all custom Skim widget `__init__` methods, stored as a public instance attribute:

- `SkimInput`
- `SkimStandaloneInput`
- `SkimSelect`
- `SkimSwitch`
- `SkimButton`
- `SkimListView`

Pattern for each:

```python
class SkimInput(Input):
    def __init__(self, *args, help_key: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.help_key = help_key
```

### HelpScreen modal

A new `ModalScreen` in `app.py`, following the existing modal pattern (`ErrorDialog`, `QuitConfirmScreen`, etc.):

```python
class HelpScreen(ModalScreen[None]):
    BINDINGS = [
        Binding(key="escape", action="dismiss_help", description="Close", show=False),
        Binding(key="q", action="dismiss_help", description="Close", show=False),
    ]

    def __init__(self, content: str) -> None:
        super().__init__()
        self.content = content

    def compose(self) -> ComposeResult:
        with Vertical(id="help-dialog"):
            yield Markdown(self.content)

    def action_dismiss_help(self) -> None:
        self.dismiss(None)
```

CSS:

```css
HelpScreen {
    align: center middle;
}
#help-dialog {
    padding: 1 2;
    width: 80%;
    max-width: 90;
    max-height: 80%;
    border: thick $background 80%;
    background: $surface;
    overflow-y: auto;
}
```

The modal uses Textual's `Markdown` widget for rendering. It is read-only and scrollable. Dismissed with Escape or `q`.

### F1 binding and DOM walk

In `SkimConfigApp`:

- Add binding: `Binding(key="f1", action="show_help", description="Help", key_display="F1", priority=True)`
- Add `"show_help"` to `_ACTION_ORDER` in `widgets.py` at priority `-1` (leftmost in the footer, always visible)

Action implementation:

```python
def action_show_help(self) -> None:
    widget = self.focused
    help_key = None
    while widget is not None:
        if hasattr(widget, "help_key") and widget.help_key:
            help_key = widget.help_key
            break
        widget = widget.parent
    content = ASSETS.help_text(help_key or "general")
    self.push_screen(HelpScreen(content))
```

The DOM walk starts from the focused widget and moves upward through parents. The first widget with a non-None `help_key` wins. If no widget in the chain has a `help_key`, the `"general"` fallback is used.

### Help content file catalog

Directory: `src/skim/assets/help/`

Each file is pure markdown — no frontmatter, no special format. Content describes what the field does, valid values, and interaction tips.

**General fallback:**
- `general.md` — keyboard shortcuts, navigation overview, how contextual help works

**Keyboard tab:**
- `keymap-title.md` — the keymap title field (`#keymap-title-text`)
- `copyright.md` — the copyright field (`#copyright-text`)
- `double-south.md` — the double south feature toggle (`#double-south`)
- `layer-list.md` — the layers list view (`#layer-list`)
- `layer-index.md` — layer QMK index field (`#layer-index`)
- `layer-id.md` — layer ID field (`#layer-id`)
- `layer-label.md` — layer label field (`#layer-label`)
- `layer-name.md` — layer name field (`#layer-name`)
- `layer-variant.md` — layer variant field (`#layer-variant`)

**Keycodes tab:**
- `preprocess-list.md` — pre-process list view (`#pre-process-list`)
- `preprocess-keycode.md` — pre-process keycode field (`#pre-process-keycode`)
- `preprocess-target.md` — pre-process target field (`#pre-process-target`)
- `override-list.md` — overrides list view (`#override-list`)
- `override-keycode.md` — override keycode field (`#override-keycode`)
- `override-target.md` — override target field (`#override-target`)

**Output tab:**
- `layout-width.md` — SVG output width (`#layout-width`)
- `layout-margin.md` — outer margin (`#layout-margin`)
- `layout-inset.md` — inner inset padding (`#layout-inset`)
- `use-layer-colors.md` — use layer colors on keys toggle (`#use-layer-colors`)
- `hold-symbol-position.md` — hold symbol position select (`#hold-symbol-position`)
- `show-layer-indicators.md` — show layer indicators toggle (`#show-layer-indicators`)
- `show-layer-connectors.md` — show layer connectors toggle (`#show-layer-connectors`)
- `use-system-fonts.md` — use system fonts toggle (`#use-system-fonts`)
- `border-enabled.md` — border enabled toggle (`#border-enabled`)
- `border-width.md` — border width field (`#border-width`)
- `border-radius.md` — border radius field (`#border-radius`)
- `palette-neutral-color.md` — palette neutral color (`#palette-neutral-color`)
- `palette-text-color.md` — palette text color (`#palette-text-color`)
- `palette-key-label-color.md` — palette key label color (`#palette-key-label-color`)
- `palette-background-color.md` — palette background color (`#palette-background-color`)
- `palette-border-color.md` — palette border color (`#palette-border-color`)
- `layer-color-list.md` — layer colors list view (`#layer-colors-list`)
- `lc-gradient-type.md` — gradient type select (`#lc-gradient-type`)
- `lc-color-index.md` — main gradient step index (`#lc-color-index`)
- `lc-base-color.md` — main gradient step color (`#lc-base-color`)
- `lc-step.md` — manual gradient step color (shared by `#lc-step-0` through `#lc-step-5`)

### Help key assignments at call sites

Each widget construction in `compose()` methods gets a `help_key=` argument. Examples:

**keyboard_tab.py — `KeyboardTab.compose()`:**
```python
yield SkimStandaloneInput(value=keymap_title, id="keymap-title-text",
                          placeholder="...", help_key="keymap-title")
yield SkimSwitch(value=double_south, id="double-south", help_key="double-south")
```

**keyboard_tab.py — `LayerListPane.compose_detail_fields()`:**
```python
yield SkimInput(value="", id="layer-index", placeholder="e.g. 0",
                disabled=True, help_key="layer-index")
```

**list_detail_pane.py — `ListDetailPane.compose()`:**
The `SkimListView` is constructed in `ListDetailPane.compose()`. Since the list ID is `f"{self.pane_id}-list"`, the `help_key` needs to be set by subclasses. Add an optional `list_help_key: str | None = None` parameter to `ListDetailPane.__init__()`, passed through to the `SkimListView`:

```python
# In ListDetailPane.__init__:
self.list_help_key = list_help_key

# In ListDetailPane.compose:
yield SkimListView(id=f"{self.pane_id}-list", help_key=self.list_help_key)
```

Subclasses pass it:
```python
class LayerListPane(ListDetailPane):
    def __init__(self, config_data, **kwargs):
        super().__init__(pane_id="layer", list_help_key="layer-list", **kwargs)
```

**Manual gradient steps (shared help key):**
The six `lc-step-{i}` inputs all share `help_key="lc-step"` — one help file describes all gradient steps.

### CSS addition for HelpScreen

Add `HelpScreen` to the existing modal alignment rule in `SkimConfigApp.CSS`:

```css
QuitConfirmScreen, SaveTargetScreen, OverwriteConfirmScreen, ErrorDialog, HelpScreen {
    align: center middle;
}
```

And add the `#help-dialog` styling block.

## Files changed

| File | Change |
|------|--------|
| `src/skim/assets/__init__.py` | Add `help_text()` and `_resolve_help()` methods |
| `src/skim/tui/widgets.py` | Add `help_key` param to all Skim widgets; add `show_help` to `_ACTION_ORDER` |
| `src/skim/tui/app.py` | Add `HelpScreen` modal, F1 binding, `action_show_help()`, CSS |
| `src/skim/tui/list_detail_pane.py` | Add `list_help_key` param, pass to `SkimListView` |
| `src/skim/tui/keyboard_tab.py` | Add `help_key=` to all widget constructions, `list_help_key=` to `LayerListPane` |
| `src/skim/tui/keycodes_tab.py` | Add `help_key=` to all widget constructions, `list_help_key=` to pane subclasses |
| `src/skim/tui/output_tab.py` | Add `help_key=` to all widget constructions, `list_help_key=` to `LayerColorListPane` |
| `src/skim/assets/help/*.md` | ~37 new markdown files with help content |

## Testing

- Unit test for `BundleAssets.help_text()`: existing key returns content, missing key returns `general.md` content, missing general raises `FileNotFoundError`
- Unit test for `HelpScreen`: renders markdown, dismisses on Escape and on `q`
- Unit test for `action_show_help()`: focused widget with `help_key` loads correct file; focused widget without `help_key` loads general fallback
- Integration: F1 on a field in each tab opens the correct help content
