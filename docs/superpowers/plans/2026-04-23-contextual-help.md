# Contextual Help System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add F1-triggered contextual help modals to the TUI configurator, loading per-field markdown content from bundled assets.

**Architecture:** Each widget carries an optional `help_key` string. On F1, the app walks the DOM from the focused widget upward to find the nearest `help_key`, loads the corresponding markdown file from `assets/help/`, and displays it in a modal using Textual's `Markdown` widget. Falls back to `general.md` when no key is found.

**Tech Stack:** Python 3.12+, Textual TUI framework, Textual `Markdown` widget

---

### Task 1: Add `help_text()` to BundleAssets

**Files:**
- Modify: `src/skim/assets/__init__.py:120-165`
- Test: `tests/unit/test_assets.py`
- Create: `src/skim/assets/help/general.md`

- [ ] **Step 1: Create the `general.md` fallback file**

Create `src/skim/assets/help/general.md`:

```markdown
# skim configure — Help

Press **F1** on any field to see contextual help.

## Navigation

| Key | Action |
|-----|--------|
| Ctrl+P / Ctrl+N | Previous / Next tab |
| Arrow keys | Move between fields |
| Tab / Shift+Tab | Next / Previous field (in edit mode) |
| Enter | Edit selected item / Confirm changes |
| Escape | Cancel edit / Discard changes |
| Ctrl+S | Save configuration |
| Ctrl+Q | Quit |

## Lists

| Key | Action |
|-----|--------|
| A | Add new entry |
| D | Delete selected entry |
| M | Enter move mode (reorder) |
| Enter | Confirm move position |
| Escape | Cancel move |

## Scrolling

| Key | Action |
|-----|--------|
| Ctrl+E | Scroll down |
| Ctrl+Y | Scroll up |
```

- [ ] **Step 2: Write failing tests for `help_text()`**

Add to `tests/unit/test_assets.py`:

```python
class TestHelpText:
    """Tests for the help_text method."""

    def test_help_text_returns_string(self):
        """help_text returns a string for an existing key."""
        assets = BundleAssets()
        content = assets.help_text("general")
        assert isinstance(content, str)
        assert len(content) > 0

    def test_help_text_general_contains_navigation(self):
        """general.md contains navigation info."""
        assets = BundleAssets()
        content = assets.help_text("general")
        assert "Navigation" in content

    def test_help_text_missing_key_falls_back_to_general(self):
        """Missing key falls back to general.md content."""
        assets = BundleAssets()
        general = assets.help_text("general")
        fallback = assets.help_text("nonexistent-key-xyz")
        assert fallback == general

    def test_help_text_fallback_when_no_general(self, tmp_path, monkeypatch):
        """Raises FileNotFoundError when general.md is also missing."""
        import importlib.resources

        original_files = importlib.resources.files

        def fake_files(package):
            if package == "skim.assets":
                return tmp_path
            return original_files(package)

        monkeypatch.setattr(importlib.resources, "files", fake_files)
        assets = BundleAssets()
        with pytest.raises(FileNotFoundError):
            assets.help_text("anything")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/unit/test_assets.py::TestHelpText -v`
Expected: FAIL — `BundleAssets` has no `help_text` method

- [ ] **Step 4: Implement `help_text()` and `_resolve_help()`**

In `src/skim/assets/__init__.py`, add these two methods to `BundleAssets` (after `_resolve` at line 161, before the closing of the class):

```python
    def help_text(self, key: str) -> str:
        """Load markdown help content for the given key.

        Falls back to 'general' if the specific file doesn't exist.

        Args:
            key: Help topic key (maps to help/{key}.md).

        Returns:
            Markdown content as a string.

        Raises:
            FileNotFoundError: If neither the key file nor general.md exists.
        """
        return self._resolve_help(key).read_text()

    def _resolve_help(self, key: str) -> Path:
        """Resolve help asset path with fallback to general.md.

        Args:
            key: Help topic key.

        Returns:
            Path to the help markdown file.

        Raises:
            FileNotFoundError: If neither the key file nor general.md exists.
        """
        path = cast(Path, resources.files("skim.assets") / "help" / f"{key}.md")
        if path.is_file():
            return path
        fallback = cast(Path, resources.files("skim.assets") / "help" / "general.md")
        if fallback.is_file():
            return fallback
        raise FileNotFoundError("No help content available.")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_assets.py::TestHelpText -v`
Expected: All 4 tests PASS

- [ ] **Step 6: Run full asset test suite to check for regressions**

Run: `pytest tests/unit/test_assets.py -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/skim/assets/__init__.py src/skim/assets/help/general.md tests/unit/test_assets.py
git commit -m "feat(assets): add help_text() with fallback to general.md"
```

---

### Task 2: Add `help_key` parameter to custom widgets

**Files:**
- Modify: `src/skim/tui/widgets.py:153-308`
- Test: `tests/unit/tui/test_widgets.py`

- [ ] **Step 1: Write failing tests for `help_key` on widgets**

Add to `tests/unit/tui/test_widgets.py`:

```python
from skim.tui.widgets import (
    SkimButton,
    SkimInput,
    SkimListView,
    SkimSelect,
    SkimStandaloneInput,
    SkimSwitch,
)


class TestWidgetHelpKey:
    """Tests for the help_key parameter on custom widgets."""

    def test_skim_input_help_key_default_none(self):
        widget = SkimInput()
        assert widget.help_key is None

    def test_skim_input_help_key_set(self):
        widget = SkimInput(help_key="layer-index")
        assert widget.help_key == "layer-index"

    def test_skim_standalone_input_help_key_default_none(self):
        widget = SkimStandaloneInput()
        assert widget.help_key is None

    def test_skim_standalone_input_help_key_set(self):
        widget = SkimStandaloneInput(help_key="keymap-title")
        assert widget.help_key == "keymap-title"

    def test_skim_select_help_key_default_none(self):
        widget = SkimSelect(options=[("A", "a")])
        assert widget.help_key is None

    def test_skim_select_help_key_set(self):
        widget = SkimSelect(options=[("A", "a")], help_key="hold-symbol-position")
        assert widget.help_key == "hold-symbol-position"

    def test_skim_switch_help_key_default_none(self):
        widget = SkimSwitch()
        assert widget.help_key is None

    def test_skim_switch_help_key_set(self):
        widget = SkimSwitch(help_key="double-south")
        assert widget.help_key == "double-south"

    def test_skim_button_help_key_default_none(self):
        widget = SkimButton("Click")
        assert widget.help_key is None

    def test_skim_button_help_key_set(self):
        widget = SkimButton("Click", help_key="some-button")
        assert widget.help_key == "some-button"

    def test_skim_list_view_help_key_default_none(self):
        widget = SkimListView()
        assert widget.help_key is None

    def test_skim_list_view_help_key_set(self):
        widget = SkimListView(help_key="layer-list")
        assert widget.help_key == "layer-list"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/tui/test_widgets.py::TestWidgetHelpKey -v`
Expected: FAIL — widgets don't accept `help_key`

- [ ] **Step 3: Add `help_key` to all widget classes**

In `src/skim/tui/widgets.py`, modify each widget class to accept and store `help_key`.

`SkimStandaloneInput` (line 153):
```python
class SkimStandaloneInput(Input):
    """Input for standalone fields outside edit panes."""

    BINDINGS = [
        Binding("tab", "focus_next", "Next field", key_display="\u2193,\u21e5", show=True),
        Binding(
            "shift+tab", "focus_previous", "Previous field", key_display="\u2191,\u21e4", show=True
        ),
    ]

    def __init__(self, *args: Any, help_key: str | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.help_key = help_key
```

`SkimInput` (line 164):
```python
class SkimInput(Input):
    """Input with footer bindings for edit-pane field navigation."""

    BINDINGS = [
        Binding("tab", "focus_next", "Next field", key_display="\u2193,\u21e5", show=True),
        Binding(
            "shift+tab", "focus_previous", "Previous field", key_display="\u2191,\u21e4", show=True
        ),
        Binding("enter", "submit", "Confirm changes", key_display="\u23ce", show=True),
        Binding("escape", "cancel_edit", "Discard changes", key_display="\U000f12b7", show=True),
    ]

    def __init__(self, *args: Any, help_key: str | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.help_key = help_key

    def action_cancel_edit(self) -> None:
        """No-op — handled by ListDetailPane.on_key via event bubbling."""
```

`SkimListView` (line 180):
```python
class SkimListView(ListView):
    """ListView with footer bindings for navigation and edit."""

    BINDINGS = [
        # Normal mode
        Binding("up", "cursor_up", "Prev item", show=True),
        Binding("down", "cursor_down", "Next item", show=True),
        Binding("enter", "select_cursor", "Edit", key_display="\u23ce", show=True),
        Binding("m", "move_mode", "Move", show=True),
        # Move mode (toggled via check_action)
        Binding("up", "move_up", "Move up", show=True),
        Binding("down", "move_down", "Move down", show=True),
        Binding("enter", "confirm_move", "Confirm position", key_display="\u23ce", show=True),
        Binding("escape", "cancel_move", "Discard changes", key_display="\U000f12b7", show=True),
    ]

    def __init__(self, *args: Any, help_key: str | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.help_key = help_key
```

`SkimButton` (line 237):
```python
class SkimButton(Button):
    """Button that responds to both Enter and Space."""

    BINDINGS = [
        Binding("enter", "press", "Activate", key_display="\u23ce,\u2423", show=True),
        Binding("space", "press", "Activate", show=False),
    ]

    def __init__(self, *args: Any, help_key: str | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.help_key = help_key

    async def _on_key(self, event: events.Key) -> None:
        if event.key == "space":
            self.action_press()
            event.stop()
            event.prevent_default()
            return
        await super()._on_key(event)
```

`SkimSwitch` (line 254):
```python
class SkimSwitch(Switch):
    """Switch with footer binding for toggle action."""

    BINDINGS = [
        Binding("enter", "toggle_switch", "Toggle", key_display="\u23ce,\u2423", show=True),
        Binding("space", "toggle_switch", "Toggle", show=False),
    ]

    def __init__(self, *args: Any, help_key: str | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.help_key = help_key
```

`SkimSelect` (line 281):
```python
class SkimSelect(Select):
    """Select with footer binding for menu action."""

    BINDINGS = [
        Binding("enter", "show_overlay", "Show options", key_display="\u23ce,\u2423", show=True),
        Binding("space", "show_overlay", "Show options", show=False),
        Binding("tab", "focus_next", "Next field", key_display="\u2193,\u21e5", show=True),
        Binding(
            "shift+tab", "focus_previous", "Previous field", key_display="\u2191,\u21e4", show=True
        ),
        Binding("escape", "cancel_edit", "Discard changes", key_display="\U000f12b7", show=True),
        Binding("up", "skip_arrow", show=False),
        Binding("down", "skip_arrow", show=False),
    ]

    def __init__(self, *args: Any, help_key: str | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.help_key = help_key
```

Also add `from typing import Any` to the imports at the top of `widgets.py` (line 8 area) if not already present.

Add `"show_help"` to `_ACTION_ORDER` (at line 25 area):

```python
_ACTION_ORDER: dict[str, int] = {
    "show_help": -1,
    # Always-visible (app-level)
    "request_quit": 0,
    ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/tui/test_widgets.py::TestWidgetHelpKey -v`
Expected: All 14 tests PASS

- [ ] **Step 5: Run full widget test suite to check for regressions**

Run: `pytest tests/unit/tui/test_widgets.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/skim/tui/widgets.py tests/unit/tui/test_widgets.py
git commit -m "feat(tui): add help_key parameter to all custom widgets"
```

---

### Task 3: Add `list_help_key` to ListDetailPane

**Files:**
- Modify: `src/skim/tui/list_detail_pane.py:88-101`

- [ ] **Step 1: Add `list_help_key` parameter to `ListDetailPane.__init__`**

In `src/skim/tui/list_detail_pane.py`, modify `__init__` (line 88):

```python
    def __init__(self, pane_id: str, list_help_key: str | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.pane_id = pane_id
        self.list_help_key = list_help_key
        self._selected: int = 0
        self._editing: bool = False
        self._snapshot: dict | None = None
        self._adding: bool = False
        self._moving: bool = False
        self._move_snapshots: list[tuple[list[dict], list[dict]]] | None = None
```

- [ ] **Step 2: Pass `list_help_key` to `SkimListView` in `compose()`**

In `src/skim/tui/list_detail_pane.py`, modify line 101:

Change:
```python
                yield SkimListView(id=f"{self.pane_id}-list", classes="ldp-list")
```
To:
```python
                yield SkimListView(
                    id=f"{self.pane_id}-list",
                    classes="ldp-list",
                    help_key=self.list_help_key,
                )
```

- [ ] **Step 3: Run existing tests to verify no regressions**

Run: `pytest tests/unit/tui/ -v`
Expected: All tests PASS (existing code doesn't pass `list_help_key`, so it defaults to `None`)

- [ ] **Step 4: Commit**

```bash
git add src/skim/tui/list_detail_pane.py
git commit -m "feat(tui): add list_help_key parameter to ListDetailPane"
```

---

### Task 4: Add HelpScreen modal and F1 binding

**Files:**
- Modify: `src/skim/tui/app.py:177-357`
- Test: `tests/unit/tui/test_app.py`

- [ ] **Step 1: Write failing tests for HelpScreen and F1 action**

Add to `tests/unit/tui/test_app.py`:

```python
from skim.tui.app import HelpScreen, SkimConfigApp


class TestHelpScreen:
    """Tests for the HelpScreen modal."""

    @pytest.fixture()
    def default_config_data(self) -> dict:
        return SkimConfig().model_dump(mode="json")

    @pytest.mark.asyncio()
    async def test_f1_opens_help_screen(self, default_config_data):
        """Pressing F1 opens a HelpScreen."""
        app = SkimConfigApp(config_data=default_config_data)
        async with app.run_test() as pilot:
            await pilot.press("f1")
            assert isinstance(app.screen, HelpScreen)

    @pytest.mark.asyncio()
    async def test_help_screen_dismiss_with_escape(self, default_config_data):
        """HelpScreen can be dismissed with Escape."""
        app = SkimConfigApp(config_data=default_config_data)
        async with app.run_test() as pilot:
            await pilot.press("f1")
            assert isinstance(app.screen, HelpScreen)
            await pilot.press("escape")
            assert not isinstance(app.screen, HelpScreen)

    @pytest.mark.asyncio()
    async def test_help_screen_dismiss_with_q(self, default_config_data):
        """HelpScreen can be dismissed with q."""
        app = SkimConfigApp(config_data=default_config_data)
        async with app.run_test() as pilot:
            await pilot.press("f1")
            assert isinstance(app.screen, HelpScreen)
            await pilot.press("q")
            assert not isinstance(app.screen, HelpScreen)

    @pytest.mark.asyncio()
    async def test_help_screen_shows_general_by_default(self, default_config_data):
        """F1 with no help_key on focused widget shows general help."""
        app = SkimConfigApp(config_data=default_config_data)
        async with app.run_test() as pilot:
            await pilot.press("f1")
            from textual.widgets import Markdown

            md = app.screen.query_one(Markdown)
            assert md is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/tui/test_app.py::TestHelpScreen -v`
Expected: FAIL — `HelpScreen` doesn't exist

- [ ] **Step 3: Add `HelpScreen` class and imports**

In `src/skim/tui/app.py`, add `Markdown` to imports (line 22 area):

```python
from textual.widgets import (
    Button,
    Input,
    Label,
    ListView,
    Markdown,
    OptionList,
    TabbedContent,
    TabPane,
    Tabs,
)
```

Add `ASSETS` import at the top:

```python
from skim.assets import ASSETS
```

Add `HelpScreen` class after `ErrorDialog` (after line 199):

```python
class HelpScreen(ModalScreen[None]):
    """Modal dialog to show contextual help as rendered markdown."""

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

- [ ] **Step 4: Add CSS for HelpScreen**

In `SkimConfigApp.CSS`, modify the first selector (line 207):

Change:
```css
    QuitConfirmScreen, SaveTargetScreen, OverwriteConfirmScreen, ErrorDialog {
        align: center middle;
    }
```
To:
```css
    QuitConfirmScreen, SaveTargetScreen, OverwriteConfirmScreen, ErrorDialog, HelpScreen {
        align: center middle;
    }
```

Add the `#help-dialog` block after the `#error-buttons` rule (after line 244):

```css
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

- [ ] **Step 5: Add F1 binding to `SkimConfigApp.BINDINGS`**

In the `BINDINGS` list (after line 357, before the closing `]`):

```python
        Binding(
            key="f1",
            action="show_help",
            description="Help",
            key_display="F1",
            priority=True,
        ),
```

- [ ] **Step 6: Add `action_show_help` method**

Add to `SkimConfigApp`, after `action_request_quit` (after line 399):

```python
    def action_show_help(self) -> None:
        """Show contextual help for the currently focused widget."""
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

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/unit/tui/test_app.py::TestHelpScreen -v`
Expected: All 4 tests PASS

- [ ] **Step 8: Run full app test suite to check for regressions**

Run: `pytest tests/unit/tui/test_app.py -v`
Expected: All tests PASS

- [ ] **Step 9: Commit**

```bash
git add src/skim/tui/app.py tests/unit/tui/test_app.py
git commit -m "feat(tui): add HelpScreen modal and F1 binding"
```

---

### Task 5: Wire `help_key` into Keyboard tab widgets

**Files:**
- Modify: `src/skim/tui/keyboard_tab.py:37-39, 71-91, 276-307`
- Create: `src/skim/assets/help/keymap-title.md`
- Create: `src/skim/assets/help/copyright.md`
- Create: `src/skim/assets/help/double-south.md`
- Create: `src/skim/assets/help/layer-list.md`
- Create: `src/skim/assets/help/layer-index.md`
- Create: `src/skim/assets/help/layer-id.md`
- Create: `src/skim/assets/help/layer-label.md`
- Create: `src/skim/assets/help/layer-name.md`
- Create: `src/skim/assets/help/layer-variant.md`

- [ ] **Step 1: Add `list_help_key` to `LayerListPane.__init__`**

In `src/skim/tui/keyboard_tab.py`, modify `LayerListPane.__init__` (line 37):

Change:
```python
    def __init__(self, config_data: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(pane_id="layer", **kwargs)
```
To:
```python
    def __init__(self, config_data: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(pane_id="layer", list_help_key="layer-list", **kwargs)
```

- [ ] **Step 2: Add `help_key` to all `LayerListPane.compose_detail_fields()` widgets**

In `src/skim/tui/keyboard_tab.py`, modify `compose_detail_fields` (lines 71-91):

```python
    def compose_detail_fields(self) -> ComposeResult:
        with Horizontal(classes="field-row"):
            yield Label("Index:", classes="field-label")
            yield SkimInput(
                value="", id="layer-index", placeholder="e.g. 0",
                disabled=True, help_key="layer-index",
            )
        with Horizontal(classes="field-row"):
            yield Label("ID:", classes="field-label")
            yield SkimInput(
                value="", id="layer-id", placeholder="e.g. _BASE (optional)",
                disabled=True, help_key="layer-id",
            )
        with Horizontal(classes="field-row"):
            yield Label("Label:", classes="field-label")
            yield SkimInput(
                value="", id="layer-label", placeholder="e.g. BASE",
                disabled=True, help_key="layer-label",
            )
        with Horizontal(classes="field-row"):
            yield Label("Name:", classes="field-label")
            yield SkimInput(
                value="", id="layer-name", placeholder="e.g. Letters",
                disabled=True, help_key="layer-name",
            )
        with Horizontal(classes="field-row"):
            yield Label("Variant:", classes="field-label")
            yield SkimInput(
                value="", id="layer-variant", placeholder="e.g. COLEMAK (optional)",
                disabled=True, help_key="layer-variant",
            )
```

- [ ] **Step 3: Add `help_key` to `KeyboardTab.compose()` standalone widgets**

In `src/skim/tui/keyboard_tab.py`, modify `KeyboardTab.compose` (lines 276-307):

Change the `SkimStandaloneInput` for keymap title:
```python
                    yield SkimStandaloneInput(
                        value=keymap_title,
                        id="keymap-title-text",
                        placeholder="e.g. My Keymap (leave empty for auto)",
                        help_key="keymap-title",
                    )
```

Change the `SkimStandaloneInput` for copyright:
```python
                    yield SkimStandaloneInput(
                        value=copyright_text,
                        id="copyright-text",
                        placeholder="e.g. (c) 2024 Your Name (leave empty for none)",
                        help_key="copyright",
                    )
```

Change the `SkimSwitch` for double south:
```python
                    yield SkimSwitch(value=double_south, id="double-south", help_key="double-south")
```

- [ ] **Step 4: Create help markdown files**

Create `src/skim/assets/help/keymap-title.md`:
```markdown
# Keymap Title

The title displayed at the top of the rendered keymap SVG.

Leave empty to use an auto-generated title based on the config filename.

**Examples:** `My Svalboard Layout`, `COLEMAK-DH`, `Gaming Keymap`
```

Create `src/skim/assets/help/copyright.md`:
```markdown
# Copyright

Copyright text displayed at the bottom of the rendered keymap SVG.

Leave empty to omit the copyright notice.

**Example:** `(c) 2024 Your Name`
```

Create `src/skim/assets/help/double-south.md`:
```markdown
# Double South

When enabled, each key cluster renders with two south-facing thumb keys instead of one.

This matches the Svalboard hardware configuration with an additional south key per side. Enable this if your physical keyboard has the extra south keys installed.
```

Create `src/skim/assets/help/layer-list.md`:
```markdown
# Layers

The list of keyboard layers in your configuration. Each layer maps to a QMK firmware layer.

## Interaction

| Key | Action |
|-----|--------|
| Enter | Edit the selected layer's details |
| A | Add a new layer |
| D | Delete the selected layer |
| M | Enter move mode to reorder layers |

In **move mode**, use Up/Down to reposition, Enter to confirm, Escape to cancel.

Layers are kept sorted by their QMK index. Adding or removing a layer here also syncs with the layer colors in the Style tab.
```

Create `src/skim/assets/help/layer-index.md`:
```markdown
# Layer Index

The QMK firmware layer number (0–31).

This must be a unique integer matching the layer index defined in your QMK keymap. Layer 0 is typically the base/default layer.

Changing the index will re-sort the layer list automatically.
```

Create `src/skim/assets/help/layer-id.md`:
```markdown
# Layer ID

An optional identifier matching the QMK layer enum name (e.g. `_BASE`, `_NAV`, `_SYM`).

Used for display purposes in the rendered keymap. Leave empty if your firmware doesn't use named layer constants.
```

Create `src/skim/assets/help/layer-label.md`:
```markdown
# Layer Label

A short label displayed on the layer indicator in the rendered keymap (e.g. `BASE`, `NAV`, `SYM`).

Keep it short — 3-5 characters works best for readability in the SVG output.
```

Create `src/skim/assets/help/layer-name.md`:
```markdown
# Layer Name

A human-readable name for the layer (e.g. `Letters`, `Navigation`, `Symbols`).

This is displayed in the rendered keymap as the layer's full name, alongside the label.
```

Create `src/skim/assets/help/layer-variant.md`:
```markdown
# Layer Variant

An optional variant descriptor for the layer (e.g. `COLEMAK`, `QWERTY`, `GAMING`).

When set, the variant is displayed in parentheses after the layer name in the rendered keymap. Leave empty if the layer has no variant.
```

- [ ] **Step 5: Run existing Keyboard tab tests to check for regressions**

Run: `pytest tests/unit/tui/test_keyboard_tab.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/skim/tui/keyboard_tab.py src/skim/assets/help/keymap-title.md src/skim/assets/help/copyright.md src/skim/assets/help/double-south.md src/skim/assets/help/layer-list.md src/skim/assets/help/layer-index.md src/skim/assets/help/layer-id.md src/skim/assets/help/layer-label.md src/skim/assets/help/layer-name.md src/skim/assets/help/layer-variant.md
git commit -m "feat(tui): wire help_key into Keyboard tab widgets"
```

---

### Task 6: Wire `help_key` into Keycodes tab widgets

**Files:**
- Modify: `src/skim/tui/keycodes_tab.py:258-260, 294-318, 378-380, 415-447`
- Create: `src/skim/assets/help/preprocess-list.md`
- Create: `src/skim/assets/help/preprocess-keycode.md`
- Create: `src/skim/assets/help/preprocess-target.md`
- Create: `src/skim/assets/help/override-list.md`
- Create: `src/skim/assets/help/override-keycode.md`
- Create: `src/skim/assets/help/override-target.md`

- [ ] **Step 1: Add `list_help_key` to `PreProcessListPane.__init__`**

In `src/skim/tui/keycodes_tab.py`, modify `PreProcessListPane.__init__` (line 258):

Change:
```python
    def __init__(self, config_data: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(pane_id="pre-process", **kwargs)
```
To:
```python
    def __init__(self, config_data: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(pane_id="pre-process", list_help_key="preprocess-list", **kwargs)
```

- [ ] **Step 2: Add `help_key` to `PreProcessListPane.compose_detail_fields()` widgets**

In `src/skim/tui/keycodes_tab.py`, modify `compose_detail_fields` (lines 294-327):

Change the keycode input (line 299):
```python
            pp_kc_input = SkimInput(
                value="",
                id="pre-process-keycode",
                placeholder="e.g. MKC_BKTAB",
                disabled=True,
                suggester=suggester,
                help_key="preprocess-keycode",
            )
```

Change the target input (line 310):
```python
            pp_tg_input = SkimInput(
                value="",
                id="pre-process-target",
                placeholder="e.g. LSFT(KC_TAB)",
                disabled=True,
                suggester=suggester,
                help_key="preprocess-target",
            )
```

- [ ] **Step 3: Add `list_help_key` to `OverrideListPane.__init__`**

In `src/skim/tui/keycodes_tab.py`, modify `OverrideListPane.__init__` (line 378):

Change:
```python
    def __init__(self, config_data: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(pane_id="override", **kwargs)
```
To:
```python
    def __init__(self, config_data: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(pane_id="override", list_help_key="override-list", **kwargs)
```

- [ ] **Step 4: Add `help_key` to `OverrideListPane.compose_detail_fields()` widgets**

In `src/skim/tui/keycodes_tab.py`, modify `compose_detail_fields` (lines 415-447):

Change the keycode input (line 420):
```python
            ov_kc_input = SkimInput(
                value="",
                id="override-keycode",
                placeholder="e.g. KC_ESC",
                disabled=True,
                suggester=suggester,
                help_key="override-keycode",
            )
```

Change the target input (line 431):
```python
            ov_tg_input = SkimInput(
                value="",
                id="override-target",
                placeholder="e.g. @@KC_ESC; or %%nf-md-icon;",
                disabled=True,
                help_key="override-target",
            )
```

- [ ] **Step 5: Create help markdown files**

Create `src/skim/assets/help/preprocess-list.md`:
```markdown
# Pre-process Keycodes

A list of keycode pre-processing rules. Each rule maps a custom keycode to a target keycode expression that replaces it before rendering.

Use this to define custom keycodes (like `MKC_BKTAB`) that expand to QMK expressions (like `LSFT(KC_TAB)`) in the rendered keymap.

## Interaction

| Key | Action |
|-----|--------|
| Enter | Edit the selected rule |
| A | Add a new rule |
| D | Delete the selected rule |
```

Create `src/skim/assets/help/preprocess-keycode.md`:
```markdown
# Pre-process — Keycode

The source keycode to match. This is the keycode as it appears in your QMK keymap.

Typically a custom macro keycode (e.g. `MKC_BKTAB`, `MKC_COPY`). Autocomplete is available — start typing to see suggestions.

Multiple keycodes can use macro syntax like `LSFT(KC_A)`.
```

Create `src/skim/assets/help/preprocess-target.md`:
```markdown
# Pre-process — Target

The replacement keycode expression. This is what the source keycode expands to for rendering.

Supports QMK keycode expressions including macros like `LSFT(KC_TAB)`, `LT(2,KC_SPC)`, etc.

The **Preview** field below shows how the resolved label will appear in the rendered keymap.
```

Create `src/skim/assets/help/override-list.md`:
```markdown
# Keycode Overrides

A list of label overrides for keycodes. Each override customizes how a specific keycode is displayed in the rendered keymap.

Use this to replace default keycode labels with custom text, icons, or NerdFont glyphs.

## Interaction

| Key | Action |
|-----|--------|
| Enter | Edit the selected override |
| A | Add a new override |
| D | Delete the selected override |
```

Create `src/skim/assets/help/override-keycode.md`:
```markdown
# Override — Keycode

The keycode whose display label you want to customize.

This should match a keycode exactly as it appears in your QMK keymap or in the pre-process rules. Autocomplete is available — start typing to see suggestions.
```

Create `src/skim/assets/help/override-target.md`:
```markdown
# Override — Target

The custom label to display for this keycode. Supports three formats:

- **Plain text:** `Escape` — displays the text as-is
- **Keycode reference:** `@@KC_ESC;` — resolves to the label of another keycode
- **NerdFont glyph:** `%%nf-md-keyboard;` — inserts a NerdFont icon

You can combine formats: `%%nf-md-arrow-left; Back`

Type `@@` to trigger keycode autocomplete, or `%%` to trigger NerdFont glyph autocomplete.
```

- [ ] **Step 6: Run existing Keycodes tab tests to check for regressions**

Run: `pytest tests/unit/tui/test_keycodes_tab.py -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/skim/tui/keycodes_tab.py src/skim/assets/help/preprocess-list.md src/skim/assets/help/preprocess-keycode.md src/skim/assets/help/preprocess-target.md src/skim/assets/help/override-list.md src/skim/assets/help/override-keycode.md src/skim/assets/help/override-target.md
git commit -m "feat(tui): wire help_key into Keycodes tab widgets"
```

---

### Task 7: Wire `help_key` into Output tab widgets

**Files:**
- Modify: `src/skim/tui/output_tab.py:153-155, 212-280, 625-756`
- Create: `src/skim/assets/help/layout-width.md`
- Create: `src/skim/assets/help/layout-margin.md`
- Create: `src/skim/assets/help/layout-inset.md`
- Create: `src/skim/assets/help/use-layer-colors.md`
- Create: `src/skim/assets/help/hold-symbol-position.md`
- Create: `src/skim/assets/help/show-layer-indicators.md`
- Create: `src/skim/assets/help/show-layer-connectors.md`
- Create: `src/skim/assets/help/use-system-fonts.md`
- Create: `src/skim/assets/help/border-enabled.md`
- Create: `src/skim/assets/help/border-width.md`
- Create: `src/skim/assets/help/border-radius.md`
- Create: `src/skim/assets/help/palette-neutral-color.md`
- Create: `src/skim/assets/help/palette-text-color.md`
- Create: `src/skim/assets/help/palette-key-label-color.md`
- Create: `src/skim/assets/help/palette-background-color.md`
- Create: `src/skim/assets/help/palette-border-color.md`
- Create: `src/skim/assets/help/layer-color-list.md`
- Create: `src/skim/assets/help/lc-gradient-type.md`
- Create: `src/skim/assets/help/lc-color-index.md`
- Create: `src/skim/assets/help/lc-base-color.md`
- Create: `src/skim/assets/help/lc-step.md`

- [ ] **Step 1: Add `list_help_key` to `LayerColorListPane.__init__`**

In `src/skim/tui/output_tab.py`, modify `LayerColorListPane.__init__` (line 153):

Change:
```python
    def __init__(self, config_data: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(pane_id="layer-colors", **kwargs)
```
To:
```python
    def __init__(self, config_data: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(pane_id="layer-colors", list_help_key="layer-color-list", **kwargs)
```

- [ ] **Step 2: Add `help_key` to `LayerColorListPane.compose_detail_fields()` widgets**

In `src/skim/tui/output_tab.py`, modify `compose_detail_fields` (lines 212-280):

Change the gradient type select (line 216):
```python
            yield SkimSelect(
                options=[("Dynamic", "dynamic"), ("Manual", "manual")],
                value="dynamic",
                id="lc-gradient-type",
                disabled=True,
                help_key="lc-gradient-type",
            )
```

Change the color index input (line 225):
```python
            yield SkimInput(
                value="",
                id="lc-color-index",
                placeholder="2",
                disabled=True,
                help_key="lc-color-index",
            )
```

Change the base color input (line 237):
```python
            lc_color_input = SkimInput(
                value="",
                id="lc-base-color",
                placeholder="#RRGGBB",
                disabled=True,
                suggester=_COLOR_SUGGESTER,
                help_key="lc-base-color",
            )
```

Change the manual step inputs (line 272, inside the `for i in range(6)` loop):
```python
                step_input = SkimInput(
                    value="",
                    id=f"lc-step-{i}",
                    placeholder="#RRGGBB",
                    disabled=True,
                    suggester=_COLOR_SUGGESTER,
                    help_key="lc-step",
                )
```

- [ ] **Step 3: Add `help_key` to `OutputTab.compose()` standalone widgets**

In `src/skim/tui/output_tab.py`, modify `OutputTab.compose` (lines 625-756):

Layout section — width (line 641):
```python
                    yield SkimStandaloneInput(
                        value=str(layout.get("width", 800.0)),
                        id="layout-width",
                        placeholder="800.0",
                        help_key="layout-width",
                    )
```

Layout section — margin (line 649):
```python
                    yield SkimStandaloneInput(
                        value=str(spacing.get("margin", 0.0)),
                        id="layout-margin",
                        placeholder="0.0",
                        help_key="layout-margin",
                    )
```

Layout section — inset (line 657):
```python
                    yield SkimStandaloneInput(
                        value=str(spacing.get("inset", 20.0)),
                        id="layout-inset",
                        placeholder="20.0",
                        help_key="layout-inset",
                    )
```

Style section — use layer colors (line 669):
```python
                    yield SkimSwitch(
                        value=style.get("use_layer_colors_on_keys", True),
                        id="use-layer-colors",
                        help_key="use-layer-colors",
                    )
```

Style section — hold symbol position (line 676):
```python
                    yield SkimSelect(
                        options=_HOLD_SYMBOL_OPTIONS,
                        value=hold_position,
                        id="hold-symbol-position",
                        help_key="hold-symbol-position",
                    )
```

Style section — show layer indicators (line 684):
```python
                    yield SkimSwitch(
                        value=style.get("show_layer_indicators", True),
                        id="show-layer-indicators",
                        help_key="show-layer-indicators",
                    )
```

Style section — show layer connectors (line 691):
```python
                    yield SkimSwitch(
                        value=style.get("show_layer_connectors", True),
                        id="show-layer-connectors",
                        help_key="show-layer-connectors",
                    )
```

Style section — use system fonts (line 698):
```python
                    yield SkimSwitch(
                        value=style.get("use_system_fonts", False),
                        id="use-system-fonts",
                        help_key="use-system-fonts",
                    )
```

Style section — border enabled (line 705):
```python
                    yield SkimSwitch(
                        value=border is not None,
                        id="border-enabled",
                        help_key="border-enabled",
                    )
```

Style section — border width (line 712):
```python
                    yield SkimStandaloneInput(
                        value=str(border.get("width", 2.0)) if border else "2.0",
                        id="border-width",
                        placeholder="2.0",
                        help_key="border-width",
                    )
```

Style section — border radius (line 720):
```python
                    yield SkimStandaloneInput(
                        value=str(border.get("radius", 10.0)) if border else "10.0",
                        id="border-radius",
                        placeholder="10.0",
                        help_key="border-radius",
                    )
```

Palette section — the color inputs are created in a loop (line 744). Add a `help_key` mapping and use it:

Change the palette loop (lines 729-751) to include `help_key`:
```python
                for color_label, field_id, config_key, placeholder in [
                    ("Neutral color:", "palette-neutral-color", "neutral_color", "#6F768B"),
                    ("Text color:", "palette-text-color", "text_color", "black"),
                    ("Key label color:", "palette-key-label-color", "key_label_color", "white"),
                    ("Background color:", "palette-background-color", "background_color", "white"),
                    ("Border color:", "palette-border-color", "border_color", "black"),
                ]:
                    color_val = palette.get(config_key, "") or ""
                    with Horizontal(classes="field-row"):
                        yield Label(color_label, classes="field-label")
                        yield Static(
                            "\ue0b6\u2588\u2588\ue0b4",
                            classes="color-swatch",
                            id=f"swatch-{field_id}",
                        )
                        color_input = SkimStandaloneInput(
                            value=color_val,
                            id=field_id,
                            placeholder=placeholder,
                            suggester=_COLOR_SUGGESTER,
                            help_key=field_id,
                        )
                        yield color_input
                    yield ColorAutoComplete(color_input, candidates=_color_candidates)
```

- [ ] **Step 4: Create help markdown files**

Create `src/skim/assets/help/layout-width.md`:
```markdown
# Layout Width

The total width of the rendered SVG output in pixels.

**Default:** `800.0`

Larger values produce wider keymaps. The height adjusts automatically based on the number of layers.
```

Create `src/skim/assets/help/layout-margin.md`:
```markdown
# Layout Margin

Outer margin around the entire keymap in pixels.

**Default:** `0.0`

Adds empty space outside the keymap border (if enabled) or content edge.
```

Create `src/skim/assets/help/layout-inset.md`:
```markdown
# Layout Inset

Inner padding between the keymap border and the key content in pixels.

**Default:** `20.0`

Controls the spacing between the outer border and the first row of keys.
```

Create `src/skim/assets/help/use-layer-colors.md`:
```markdown
# Use Layer Colors on Keys

When enabled, individual key backgrounds are tinted with the layer's color to visually distinguish which layer a key belongs to.

When disabled, all keys use the same neutral background color regardless of layer.
```

Create `src/skim/assets/help/hold-symbol-position.md`:
```markdown
# Hold Symbol Position

Controls where the hold function indicator appears on dual-function keys (keys that have both a tap and hold action).

- **Outward** — hold indicator faces away from the center of the keyboard
- **Inward** — hold indicator faces toward the center
- **QMK** — uses QMK's default positioning
```

Create `src/skim/assets/help/show-layer-indicators.md`:
```markdown
# Show Layer Indicators

When enabled, colored layer indicator labels are displayed alongside each layer in the rendered keymap.

These indicators show the layer label and color, helping identify which layer is being shown.
```

Create `src/skim/assets/help/show-layer-connectors.md`:
```markdown
# Show Layer Connectors

When enabled, circular dot connectors are drawn between layers in the rendered keymap to show the visual flow between them.

Disable this for a cleaner look without the connecting elements between layers.
```

Create `src/skim/assets/help/use-system-fonts.md`:
```markdown
# Use System Fonts

When enabled, the rendered SVG uses system fonts instead of the bundled Roboto font.

Enable this if you want the keymap to use fonts available on the viewing system. Disable to ensure consistent rendering across all platforms using the bundled fonts.
```

Create `src/skim/assets/help/border-enabled.md`:
```markdown
# Border Enabled

When enabled, a rounded border is drawn around the entire keymap.

The border width and corner radius can be configured separately.
```

Create `src/skim/assets/help/border-width.md`:
```markdown
# Border Width

The stroke width of the keymap border in pixels.

**Default:** `2.0`

Only applies when the border is enabled.
```

Create `src/skim/assets/help/border-radius.md`:
```markdown
# Border Radius

The corner radius of the keymap border in pixels.

**Default:** `10.0`

Higher values create more rounded corners. Set to `0` for sharp corners. Only applies when the border is enabled.
```

Create `src/skim/assets/help/palette-neutral-color.md`:
```markdown
# Neutral Color

The color used for non-layer-specific elements like key borders and secondary labels.

**Default:** `#6F768B`

Accepts CSS color names (e.g. `slategray`) or hex values (e.g. `#6F768B`). Autocomplete is available for named colors.
```

Create `src/skim/assets/help/palette-text-color.md`:
```markdown
# Text Color

The primary text color used for labels and headings in the rendered keymap.

**Default:** `black`

Accepts CSS color names or hex values. Autocomplete is available for named colors.
```

Create `src/skim/assets/help/palette-key-label-color.md`:
```markdown
# Key Label Color

The color used for the text on individual key caps in the rendered keymap.

**Default:** `white`

Accepts CSS color names or hex values. Should contrast well with the key background colors. Autocomplete is available for named colors.
```

Create `src/skim/assets/help/palette-background-color.md`:
```markdown
# Background Color

The background color of the entire keymap SVG.

**Default:** `white`

Accepts CSS color names or hex values. Autocomplete is available for named colors.
```

Create `src/skim/assets/help/palette-border-color.md`:
```markdown
# Border Color

The color of the keymap border stroke.

**Default:** `black`

Only visible when the border is enabled. Accepts CSS color names or hex values. Autocomplete is available for named colors.
```

Create `src/skim/assets/help/layer-color-list.md`:
```markdown
# Layer Colors

The list of color settings for each layer. Each entry defines how a layer's keys and indicator are colored in the rendered keymap.

## Interaction

| Key | Action |
|-----|--------|
| Enter | Edit the selected layer's color settings |
| A | Add a new layer color entry |
| D | Delete the selected entry |
| M | Enter move mode to reorder |

Adding or removing entries here syncs with the layers in the Keyboard tab.
```

Create `src/skim/assets/help/lc-gradient-type.md`:
```markdown
# Gradient Type

Controls how the 6-step color gradient is generated for this layer.

- **Dynamic** — automatically generates a gradient from the base color. You set one color and the gradient steps are computed.
- **Manual** — lets you specify each of the 6 gradient step colors individually.
```

Create `src/skim/assets/help/lc-color-index.md`:
```markdown
# Main Gradient Step Index

Which of the 6 gradient steps (0–5) is the "main" color for this layer.

**Default:** `2`

In dynamic mode, this is the position where your chosen base color appears. Steps before it are lighter, steps after are darker. In manual mode, this marks which step is treated as the primary color.
```

Create `src/skim/assets/help/lc-base-color.md`:
```markdown
# Main Gradient Step Color

The base color for this layer's gradient (dynamic mode only).

The gradient is generated around this color at the step position defined by the gradient step index. Enter a CSS color name (e.g. `dodgerblue`) or hex value (e.g. `#1E90FF`).

Autocomplete is available for named colors.
```

Create `src/skim/assets/help/lc-step.md`:
```markdown
# Manual Gradient Step Color

An individual color in the 6-step gradient (manual mode only).

Each step (0–5) can have its own color. Step 0 is typically the lightest and step 5 the darkest, but you are free to set any colors.

Enter a CSS color name (e.g. `dodgerblue`) or hex value (e.g. `#1E90FF`). Autocomplete is available for named colors.
```

- [ ] **Step 5: Run existing Output tab tests to check for regressions**

Run: `pytest tests/unit/tui/test_output_tab.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/skim/tui/output_tab.py src/skim/assets/help/layout-width.md src/skim/assets/help/layout-margin.md src/skim/assets/help/layout-inset.md src/skim/assets/help/use-layer-colors.md src/skim/assets/help/hold-symbol-position.md src/skim/assets/help/show-layer-indicators.md src/skim/assets/help/show-layer-connectors.md src/skim/assets/help/use-system-fonts.md src/skim/assets/help/border-enabled.md src/skim/assets/help/border-width.md src/skim/assets/help/border-radius.md src/skim/assets/help/palette-neutral-color.md src/skim/assets/help/palette-text-color.md src/skim/assets/help/palette-key-label-color.md src/skim/assets/help/palette-background-color.md src/skim/assets/help/palette-border-color.md src/skim/assets/help/layer-color-list.md src/skim/assets/help/lc-gradient-type.md src/skim/assets/help/lc-color-index.md src/skim/assets/help/lc-base-color.md src/skim/assets/help/lc-step.md
git commit -m "feat(tui): wire help_key into Output/Style tab widgets"
```

---

### Task 8: Integration test — F1 loads contextual help

**Files:**
- Test: `tests/unit/tui/test_app.py`

- [ ] **Step 1: Write integration test for field-specific help**

Add to `tests/unit/tui/test_app.py`:

```python
class TestHelpScreenIntegration:
    """Integration tests for contextual help per field."""

    @pytest.fixture()
    def default_config_data(self) -> dict:
        return SkimConfig().model_dump(mode="json")

    @pytest.mark.asyncio()
    async def test_f1_on_keymap_title_shows_specific_help(self, default_config_data):
        """F1 on keymap title field shows keymap-title help."""
        app = SkimConfigApp(config_data=default_config_data)
        async with app.run_test() as pilot:
            # Focus the keymap title input
            title_input = app.query_one("#keymap-title-text")
            title_input.focus()
            await pilot.pause()
            await pilot.press("f1")
            from textual.widgets import Markdown

            md = app.screen.query_one(Markdown)
            # The help screen should contain content from keymap-title.md
            assert "Keymap Title" in md._markdown

    @pytest.mark.asyncio()
    async def test_f1_on_widget_without_help_key_shows_general(self, default_config_data):
        """F1 on a widget without help_key falls back to general help."""
        app = SkimConfigApp(config_data=default_config_data)
        async with app.run_test() as pilot:
            await pilot.press("f1")
            from textual.widgets import Markdown

            md = app.screen.query_one(Markdown)
            assert "Navigation" in md._markdown
```

- [ ] **Step 2: Run integration tests**

Run: `pytest tests/unit/tui/test_app.py::TestHelpScreenIntegration -v`
Expected: All 2 tests PASS

- [ ] **Step 3: Run full test suite to verify everything works together**

Run: `pytest tests/unit/ -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/unit/tui/test_app.py
git commit -m "test(tui): add integration tests for contextual help"
```
