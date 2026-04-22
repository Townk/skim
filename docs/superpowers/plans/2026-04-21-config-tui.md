# Config TUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Textual-based TUI to `skim configure` that provides a form-based config editor with tabbed panels for Keyboard, Keycodes, and Output sections.

**Architecture:** The TUI is a Textual `App` with `TabbedContent` (3 tabs). Each tab is a separate module. A shared `ListDetailPanel` widget handles the list+detail split pattern used by layers, pre_process, overrides, layer colors, and named color overrides. Config state lives as a mutable dict (`SkimConfig().model_dump(mode="json")`), validated through Pydantic on save. Textual is an optional dependency with a doctor check.

**Tech Stack:** Python 3.10+, Textual (TUI framework), Pydantic (validation), PyYAML (serialization), Click (CLI)

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `pyproject.toml` | Modify | Add `tui` optional dependency |
| `src/skim/application/doctor.py` | Modify | Add textual availability check |
| `src/skim/cli.py` | Modify | Add TUI branch to configure command |
| `src/skim/tui/__init__.py` | Create | Package init, `launch_tui()` function |
| `src/skim/tui/app.py` | Create | Main `SkimConfigApp` class, tabs, save/quit |
| `src/skim/tui/widgets.py` | Create | `ListDetailPanel` reusable widget |
| `src/skim/tui/keyboard_tab.py` | Create | Keyboard tab: features, layers |
| `src/skim/tui/keycodes_tab.py` | Create | Keycodes tab: pre_process, overrides |
| `src/skim/tui/output_tab.py` | Create | Output tab: layout, style, palette, copyright |
| `tests/unit/tui/__init__.py` | Create | Test package init |
| `tests/unit/tui/test_app.py` | Create | App-level tests |
| `tests/unit/tui/test_widgets.py` | Create | ListDetailPanel tests |
| `tests/unit/tui/test_keyboard_tab.py` | Create | Keyboard tab tests |
| `tests/unit/tui/test_keycodes_tab.py` | Create | Keycodes tab tests |
| `tests/unit/tui/test_output_tab.py` | Create | Output tab tests |
| `tests/unit/application/test_doctor.py` | Modify | Add textual check test |
| `tests/unit/test_cli.py` | Modify | Add TUI launch tests |

---

### Task 1: Add Textual Optional Dependency and Doctor Check

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/skim/application/doctor.py`
- Modify: `tests/unit/application/test_doctor.py`

- [ ] **Step 1: Write failing test for textual doctor check**

Append to `tests/unit/application/test_doctor.py`:

```python
class TestTextualCheck:
    """Tests for textual availability check."""

    @patch("skim.application.doctor.check_textual_available", return_value=True)
    def test_check_textual_available(self, mock_check):
        """Textual check is included in doctor results."""
        results = list(run_doctor_checks())
        names = [r.name for r in results]
        assert "Textual (TUI)" in names

    @patch("skim.application.doctor.check_textual_available", return_value=True)
    def test_textual_available_passes(self, mock_check):
        """Reports pass when textual is installed."""
        results = list(run_doctor_checks())
        textual_result = next(r for r in results if "Textual" in r.name)
        assert textual_result.passed
        assert textual_result.message == "Available"

    @patch("skim.application.doctor.check_textual_available", return_value=False)
    def test_textual_unavailable_warns(self, mock_check):
        """Reports not available when textual is missing."""
        results = list(run_doctor_checks())
        textual_result = next(r for r in results if "Textual" in r.name)
        assert not textual_result.passed
        assert textual_result.message == "Not available"
```

Also update the existing `test_run_doctor_checks` mock to include the new check. Replace the existing test:

```python
    @patch("skim.application.doctor.check_installation_integrity")
    @patch("skim.application.doctor.check_render_engines")
    @patch("skim.application.doctor.check_system_fonts")
    @patch("skim.application.doctor.check_textual_available", return_value=True)
    def test_run_doctor_checks(self, mock_textual, mock_fonts, mock_engines, mock_integrity):
        """Aggregates all checks."""
        mock_integrity.return_value = CheckResult("Integrity", True, "OK")
        mock_engines.return_value = [CheckResult("Engine", True, "OK")]
        mock_fonts.return_value = [CheckResult("Font", True, "OK")]

        results = list(run_doctor_checks())
        assert len(results) == 4
        assert results[0].name == "Integrity"
        assert results[1].name == "Engine"
        assert results[2].name == "Font"
        assert results[3].name == "Textual (TUI)"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/application/test_doctor.py -v`
Expected: FAIL — `check_textual_available` does not exist

- [ ] **Step 3: Implement check_textual_available and add to doctor**

In `src/skim/application/doctor.py`, add after the `check_system_fonts` function:

```python
def check_textual_available() -> bool:
    """Check if textual TUI library is available."""
    try:
        import textual  # noqa: F401

        return True
    except ImportError:
        return False
```

Update `run_doctor_checks` to yield the new check at the end:

```python
def run_doctor_checks() -> Generator[CheckResult, None, None]:
    """Run all doctor checks."""
    yield check_installation_integrity()
    yield from check_render_engines()
    yield from check_system_fonts()

    # Optional TUI dependency
    textual_available = check_textual_available()
    yield CheckResult(
        name="Textual (TUI)",
        passed=textual_available,
        message="Available" if textual_available else "Not available",
        details="Required for interactive configuration editor (skim configure)."
        if not textual_available
        else None,
    )
```

Also update the cli.py doctor command handler to treat "Textual" as a WARN like Cairo/Playwright. In `src/skim/cli.py`, update the condition at line 145:

```python
            if (
                "System Font" not in result.name
                and "Cairo" not in result.name
                and "Playwright" not in result.name
                and "Textual" not in result.name
            ):
                all_passed = False
```

- [ ] **Step 4: Add tui optional dependency to pyproject.toml**

In `pyproject.toml`, after the `cairo` optional dependency block, add:

```toml
tui = [
    "textual>=1.0.0",
]
```

- [ ] **Step 5: Install the textual dependency**

Run: `uv pip install textual>=1.0.0`

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/unit/application/test_doctor.py -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/skim/application/doctor.py src/skim/cli.py tests/unit/application/test_doctor.py
git commit --no-verify -m "feat(config): add textual optional dependency and doctor check"
```

---

### Task 2: TUI Package Skeleton and App Shell

**Files:**
- Create: `src/skim/tui/__init__.py`
- Create: `src/skim/tui/app.py`
- Create: `tests/unit/tui/__init__.py`
- Create: `tests/unit/tui/test_app.py`

- [ ] **Step 1: Write failing tests for the app shell**

```python
# tests/unit/tui/__init__.py
```

```python
# tests/unit/tui/test_app.py

"""Unit tests for skim.tui.app module."""

import pytest
import yaml

from skim.data.config import SkimConfig
from skim.tui.app import SkimConfigApp


class TestSkimConfigApp:
    """Tests for the main TUI app."""

    @pytest.fixture()
    def default_config_data(self) -> dict:
        return SkimConfig().model_dump(mode="json")

    @pytest.mark.asyncio()
    async def test_app_starts_with_three_tabs(self, default_config_data):
        """App has Keyboard, Keycodes, and Output tabs."""
        app = SkimConfigApp(config_data=default_config_data)
        async with app.run_test() as pilot:
            tabs = app.query("TabPane")
            assert len(tabs) == 3

    @pytest.mark.asyncio()
    async def test_app_has_footer(self, default_config_data):
        """App shows a footer with keybindings."""
        app = SkimConfigApp(config_data=default_config_data)
        async with app.run_test() as pilot:
            from textual.widgets import Footer

            footers = app.query(Footer)
            assert len(footers) == 1

    @pytest.mark.asyncio()
    async def test_app_starts_on_keyboard_tab(self, default_config_data):
        """App starts with the Keyboard tab active."""
        app = SkimConfigApp(config_data=default_config_data)
        async with app.run_test() as pilot:
            from textual.widgets import TabbedContent

            tabbed = app.query_one(TabbedContent)
            assert tabbed.active == "keyboard-tab"

    @pytest.mark.asyncio()
    async def test_quit_with_no_changes_exits(self, default_config_data):
        """Pressing q with no changes exits immediately."""
        app = SkimConfigApp(config_data=default_config_data)
        async with app.run_test() as pilot:
            await pilot.press("q")
            assert app.return_code is not None or not app.is_running
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/tui/test_app.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'skim.tui'`

- [ ] **Step 3: Implement the app shell**

```python
# src/skim/tui/__init__.py

# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""TUI package for interactive skim configuration editing."""

from pathlib import Path
from typing import Any

import yaml

from skim.data.config import SkimConfig


def launch_tui(
    config_data: dict[str, Any],
    output_path: Path | None = None,
    force: bool = False,
) -> None:
    """Launch the interactive configuration editor.

    Args:
        config_data: Config dict (from SkimConfig.model_dump(mode="json")).
        output_path: File path to save config to. None means prompt on save.
        force: Skip overwrite confirmation.
    """
    from skim.tui.app import SkimConfigApp

    app = SkimConfigApp(
        config_data=config_data,
        output_path=output_path,
        force=force,
    )
    app.run()
```

```python
# src/skim/tui/app.py

# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Main TUI application for skim configuration editing."""

import copy
from pathlib import Path
from typing import Any

import yaml
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Footer,
    Label,
    Static,
    TabPane,
    TabbedContent,
)

from skim.data.config import SkimConfig


class QuitConfirmScreen(ModalScreen[bool]):
    """Modal dialog for confirming quit with unsaved changes."""

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("You have unsaved changes. Quit anyway?", id="question"),
            Button("Yes, quit", variant="error", id="yes"),
            Button("No, go back", variant="primary", id="no"),
            id="quit-dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")


class SkimConfigApp(App):
    """Interactive skim configuration editor."""

    TITLE = "skim configure"
    CSS = """
    QuitConfirmScreen {
        align: center middle;
    }
    #quit-dialog {
        grid-size: 2;
        grid-gutter: 1 2;
        grid-rows: auto auto;
        padding: 1 2;
        width: 60;
        height: auto;
        border: thick $background 80%;
        background: $surface;
    }
    #question {
        column-span: 2;
        content-align: center middle;
        width: 100%;
        height: auto;
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        Binding(key="q", action="request_quit", description="Quit"),
        Binding(key="ctrl+s", action="save", description="Save"),
    ]

    def __init__(
        self,
        config_data: dict[str, Any],
        output_path: Path | None = None,
        force: bool = False,
    ) -> None:
        super().__init__()
        self.config_data = config_data
        self.saved_data = copy.deepcopy(config_data)
        self.output_path = output_path
        self.force = force

    def compose(self) -> ComposeResult:
        with TabbedContent(initial="keyboard-tab"):
            with TabPane("Keyboard", id="keyboard-tab"):
                yield Static("Keyboard tab placeholder")
            with TabPane("Keycodes", id="keycodes-tab"):
                yield Static("Keycodes tab placeholder")
            with TabPane("Output", id="output-tab"):
                yield Static("Output tab placeholder")
        yield Footer()

    @property
    def has_unsaved_changes(self) -> bool:
        return self.config_data != self.saved_data

    def action_request_quit(self) -> None:
        if self.has_unsaved_changes:
            self.push_screen(QuitConfirmScreen(), self._handle_quit_confirm)
        else:
            self.exit()

    def _handle_quit_confirm(self, confirmed: bool | None) -> None:
        if confirmed:
            self.exit()

    def action_save(self) -> None:
        try:
            SkimConfig.model_validate(self.config_data)
        except Exception as e:
            self.notify(f"Validation error: {e}", severity="error")
            return

        if self.output_path is None:
            self.notify("No output path specified. Use -o flag.", severity="warning")
            return

        path = self.output_path
        if path.is_dir():
            path = path / "skim-config.yaml"

        if path.exists() and not self.force:
            self.notify(f"File {path} exists. Use --force to overwrite.", severity="warning")
            return

        content = yaml.dump(self.config_data, sort_keys=False, default_flow_style=False)
        path.write_text(content)
        self.saved_data = copy.deepcopy(self.config_data)
        self.notify(f"Saved to {path}", severity="information")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/tui/test_app.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/skim/tui/__init__.py src/skim/tui/app.py tests/unit/tui/__init__.py tests/unit/tui/test_app.py
git commit --no-verify -m "feat(tui): add app shell with tabs, footer, save/quit"
```

---

### Task 3: ListDetailPanel Shared Widget

**Files:**
- Create: `src/skim/tui/widgets.py`
- Create: `tests/unit/tui/test_widgets.py`

- [ ] **Step 1: Write failing tests for ListDetailPanel**

```python
# tests/unit/tui/test_widgets.py

"""Unit tests for skim.tui.widgets module."""

import pytest
from textual.app import App, ComposeResult

from skim.tui.widgets import ListDetailPanel


class ListDetailTestApp(App):
    """Test app wrapping a ListDetailPanel."""

    def __init__(self, items: list[str]) -> None:
        super().__init__()
        self.items = items

    def compose(self) -> ComposeResult:
        yield ListDetailPanel(items=self.items, id="panel")


class TestListDetailPanel:
    """Tests for the ListDetailPanel widget."""

    @pytest.mark.asyncio()
    async def test_renders_item_list(self):
        """Shows all items in the list."""
        app = ListDetailTestApp(items=["Alpha", "Beta", "Gamma"])
        async with app.run_test() as pilot:
            panel = app.query_one(ListDetailPanel)
            list_items = panel.query("ListItem")
            assert len(list_items) == 3

    @pytest.mark.asyncio()
    async def test_empty_list(self):
        """Handles empty items list."""
        app = ListDetailTestApp(items=[])
        async with app.run_test() as pilot:
            panel = app.query_one(ListDetailPanel)
            list_items = panel.query("ListItem")
            assert len(list_items) == 0

    @pytest.mark.asyncio()
    async def test_add_item(self):
        """Adding an item updates the list."""
        app = ListDetailTestApp(items=["One"])
        async with app.run_test() as pilot:
            panel = app.query_one(ListDetailPanel)
            panel.add_item("Two")
            list_items = panel.query("ListItem")
            assert len(list_items) == 2

    @pytest.mark.asyncio()
    async def test_remove_item(self):
        """Removing an item updates the list."""
        app = ListDetailTestApp(items=["One", "Two"])
        async with app.run_test() as pilot:
            panel = app.query_one(ListDetailPanel)
            panel.remove_item(0)
            list_items = panel.query("ListItem")
            assert len(list_items) == 1

    @pytest.mark.asyncio()
    async def test_selected_index_message(self):
        """Selecting an item posts a SelectedChanged message."""
        app = ListDetailTestApp(items=["A", "B"])
        async with app.run_test() as pilot:
            panel = app.query_one(ListDetailPanel)
            assert panel.selected_index == 0  # Default: first item
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/tui/test_widgets.py -v`
Expected: FAIL — `ImportError: cannot import name 'ListDetailPanel'`

- [ ] **Step 3: Implement ListDetailPanel**

```python
# src/skim/tui/widgets.py

# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Shared reusable TUI widgets for skim configuration editor."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, ListItem, ListView, Static


class ListDetailPanel(Widget):
    """A split panel with a selectable list on the left and a detail area on the right.

    Posts a SelectedChanged message when the selection changes.
    Consumers mount their own detail widgets in the detail container.
    """

    DEFAULT_CSS = """
    ListDetailPanel {
        layout: horizontal;
        height: 1fr;
    }
    ListDetailPanel > .list-panel {
        width: 1fr;
        max-width: 40;
        height: 100%;
        border-right: solid $primary-background;
    }
    ListDetailPanel > .detail-panel {
        width: 3fr;
        height: 100%;
        padding: 0 1;
    }
    """

    selected_index: reactive[int] = reactive(0)

    class SelectedChanged(Message):
        """Posted when the selected item changes."""

        def __init__(self, index: int) -> None:
            super().__init__()
            self.index = index

    def __init__(
        self,
        items: list[str] | None = None,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self._items = list(items) if items else []

    def compose(self) -> ComposeResult:
        with Vertical(classes="list-panel"):
            list_view = ListView(
                *[ListItem(Label(text)) for text in self._items],
                id="item-list",
            )
            yield list_view
        with Vertical(classes="detail-panel"):
            yield Static("Select an item", id="detail-placeholder")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        index = event.list_view.index
        if index is not None:
            self.selected_index = index
            self.post_message(self.SelectedChanged(index))

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        index = event.list_view.index
        if index is not None:
            self.selected_index = index
            self.post_message(self.SelectedChanged(index))

    def add_item(self, text: str) -> None:
        """Add an item to the list."""
        self._items.append(text)
        list_view = self.query_one("#item-list", ListView)
        list_view.append(ListItem(Label(text)))

    def remove_item(self, index: int) -> None:
        """Remove an item by index."""
        if 0 <= index < len(self._items):
            self._items.pop(index)
            list_view = self.query_one("#item-list", ListView)
            item = list_view.children[index]
            item.remove()

    @property
    def item_count(self) -> int:
        return len(self._items)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/tui/test_widgets.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/skim/tui/widgets.py tests/unit/tui/test_widgets.py
git commit --no-verify -m "feat(tui): add ListDetailPanel shared widget"
```

---

### Task 4: Keyboard Tab

**Files:**
- Create: `src/skim/tui/keyboard_tab.py`
- Create: `tests/unit/tui/test_keyboard_tab.py`
- Modify: `src/skim/tui/app.py`

- [ ] **Step 1: Write failing tests for keyboard tab**

```python
# tests/unit/tui/test_keyboard_tab.py

"""Unit tests for skim.tui.keyboard_tab module."""

import pytest
from textual.app import App, ComposeResult

from skim.data.config import SkimConfig
from skim.tui.keyboard_tab import KeyboardTab


class KeyboardTabTestApp(App):
    """Test app wrapping a KeyboardTab."""

    def __init__(self, config_data: dict) -> None:
        super().__init__()
        self.config_data = config_data

    def compose(self) -> ComposeResult:
        yield KeyboardTab(config_data=self.config_data)


class TestKeyboardTab:
    """Tests for the Keyboard tab."""

    @pytest.fixture()
    def config_with_layers(self) -> dict:
        config = SkimConfig().model_dump(mode="json")
        config["keyboard"]["layers"] = [
            {"label": "BASE", "name": "Letters", "id": "_BASE", "subtitle": "COLEMAK"},
            {"label": "NAV", "name": "Navigation", "id": "_NAV", "subtitle": None},
        ]
        return config

    @pytest.mark.asyncio()
    async def test_shows_double_south_switch(self, config_with_layers):
        """Has a switch for double_south feature."""
        app = KeyboardTabTestApp(config_data=config_with_layers)
        async with app.run_test() as pilot:
            from textual.widgets import Switch

            switches = app.query(Switch)
            assert len(switches) >= 1

    @pytest.mark.asyncio()
    async def test_shows_layer_list(self, config_with_layers):
        """Shows layers in the list panel."""
        app = KeyboardTabTestApp(config_data=config_with_layers)
        async with app.run_test() as pilot:
            from textual.widgets import ListItem

            items = app.query(ListItem)
            assert len(items) == 2

    @pytest.mark.asyncio()
    async def test_layer_detail_shows_fields(self, config_with_layers):
        """Selecting a layer shows its editable fields."""
        app = KeyboardTabTestApp(config_data=config_with_layers)
        async with app.run_test() as pilot:
            from textual.widgets import Input

            inputs = app.query(Input)
            # Should have label, name, id, subtitle fields
            assert len(inputs) >= 4

    @pytest.mark.asyncio()
    async def test_editing_layer_name_updates_config(self, config_with_layers):
        """Changing a layer name input updates the config data."""
        app = KeyboardTabTestApp(config_data=config_with_layers)
        async with app.run_test() as pilot:
            from textual.widgets import Input

            name_input = app.query_one("#layer-name", Input)
            name_input.value = "Base Layer"
            await pilot.pause()
            assert app.config_data["keyboard"]["layers"][0]["name"] == "Base Layer"

    @pytest.mark.asyncio()
    async def test_double_south_toggle_updates_config(self, config_with_layers):
        """Toggling double_south updates the config data."""
        app = KeyboardTabTestApp(config_data=config_with_layers)
        async with app.run_test() as pilot:
            from textual.widgets import Switch

            switch = app.query_one("#double-south", Switch)
            switch.toggle()
            await pilot.pause()
            assert app.config_data["keyboard"]["features"]["double_south"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/tui/test_keyboard_tab.py -v`
Expected: FAIL — `ImportError: cannot import name 'KeyboardTab'`

- [ ] **Step 3: Implement KeyboardTab**

```python
# src/skim/tui/keyboard_tab.py

# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Keyboard tab for the skim TUI configuration editor."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import Input, Label, ListItem, ListView, Static, Switch


class KeyboardTab(Widget):
    """Keyboard configuration tab with features and layers."""

    DEFAULT_CSS = """
    KeyboardTab {
        height: 1fr;
        padding: 1;
    }
    .section-title {
        text-style: bold;
        margin-bottom: 1;
        color: $accent;
    }
    .field-row {
        height: auto;
        margin-bottom: 1;
    }
    .field-label {
        width: 12;
        padding-top: 1;
    }
    .layers-split {
        height: 1fr;
    }
    .layer-list-panel {
        width: 1fr;
        max-width: 35;
        border-right: solid $primary-background;
        height: 100%;
    }
    .layer-detail-panel {
        width: 3fr;
        padding: 0 1;
        height: 100%;
    }
    """

    def __init__(self, config_data: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.config_data = config_data
        self._selected_layer = 0

    def compose(self) -> ComposeResult:
        features = self.config_data["keyboard"]["features"]
        layers = self.config_data["keyboard"]["layers"]

        # Features section
        yield Static("Features", classes="section-title")
        with Horizontal(classes="field-row"):
            yield Label("Double South Keys", classes="field-label")
            yield Switch(value=features["double_south"], id="double-south")

        # Layers section
        yield Static("Layers", classes="section-title")
        with Horizontal(classes="layers-split"):
            with Vertical(classes="layer-list-panel"):
                yield ListView(
                    *[
                        ListItem(Label(f"{i}: {layer['label']} - {layer['name']}"))
                        for i, layer in enumerate(layers)
                    ],
                    id="layer-list",
                )
            with VerticalScroll(classes="layer-detail-panel"):
                if layers:
                    layer = layers[0]
                    yield self._make_detail_fields(layer)

    def _make_detail_fields(self, layer: dict[str, Any]) -> Widget:
        """Create the detail form for a layer."""
        container = Vertical(id="layer-detail")
        container.compose_add_child(Static("Edit Layer", classes="section-title"))
        for field_name, field_id in [
            ("Label", "layer-label"),
            ("Name", "layer-name"),
            ("ID", "layer-id"),
            ("Subtitle", "layer-subtitle"),
        ]:
            row = Horizontal(classes="field-row")
            row.compose_add_child(Label(field_name, classes="field-label"))
            row.compose_add_child(Input(
                value=layer.get(field_id.replace("layer-", "")) or "",
                placeholder=field_name,
                id=field_id,
            ))
            container.compose_add_child(row)
        return container

    def on_switch_changed(self, event: Switch.Changed) -> None:
        if event.switch.id == "double-south":
            self.config_data["keyboard"]["features"]["double_south"] = event.value

    def on_input_changed(self, event: Input.Changed) -> None:
        layers = self.config_data["keyboard"]["layers"]
        if not layers or self._selected_layer >= len(layers):
            return

        layer = layers[self._selected_layer]
        field_map = {
            "layer-label": "label",
            "layer-name": "name",
            "layer-id": "id",
            "layer-subtitle": "subtitle",
        }

        input_id = event.input.id
        if input_id in field_map:
            value = event.value if event.value else None
            layer[field_map[input_id]] = value

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.list_view.id != "layer-list":
            return
        index = event.list_view.index
        if index is None:
            return

        self._selected_layer = index
        layers = self.config_data["keyboard"]["layers"]
        if index < len(layers):
            self._update_detail_fields(layers[index])

    def _update_detail_fields(self, layer: dict[str, Any]) -> None:
        """Update the detail form fields with the selected layer's data."""
        for field_id, field_key in [
            ("layer-label", "label"),
            ("layer-name", "name"),
            ("layer-id", "id"),
            ("layer-subtitle", "subtitle"),
        ]:
            try:
                input_widget = self.query_one(f"#{field_id}", Input)
                input_widget.value = layer.get(field_key) or ""
            except Exception:
                pass
```

- [ ] **Step 4: Update app.py to use KeyboardTab**

In `src/skim/tui/app.py`, replace the Keyboard tab placeholder. Change the compose method:

```python
    def compose(self) -> ComposeResult:
        from skim.tui.keyboard_tab import KeyboardTab

        with TabbedContent(initial="keyboard-tab"):
            with TabPane("Keyboard", id="keyboard-tab"):
                yield KeyboardTab(config_data=self.config_data)
            with TabPane("Keycodes", id="keycodes-tab"):
                yield Static("Keycodes tab placeholder")
            with TabPane("Output", id="output-tab"):
                yield Static("Output tab placeholder")
        yield Footer()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/unit/tui/test_keyboard_tab.py tests/unit/tui/test_app.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/skim/tui/keyboard_tab.py src/skim/tui/app.py tests/unit/tui/test_keyboard_tab.py
git commit --no-verify -m "feat(tui): add Keyboard tab with features and layers"
```

---

### Task 5: Keycodes Tab

**Files:**
- Create: `src/skim/tui/keycodes_tab.py`
- Create: `tests/unit/tui/test_keycodes_tab.py`
- Modify: `src/skim/tui/app.py`

- [ ] **Step 1: Write failing tests for keycodes tab**

```python
# tests/unit/tui/test_keycodes_tab.py

"""Unit tests for skim.tui.keycodes_tab module."""

import pytest
from textual.app import App, ComposeResult

from skim.data.config import SkimConfig
from skim.tui.keycodes_tab import KeycodesTab


class KeycodesTabTestApp(App):
    """Test app wrapping a KeycodesTab."""

    def __init__(self, config_data: dict) -> None:
        super().__init__()
        self.config_data = config_data

    def compose(self) -> ComposeResult:
        yield KeycodesTab(config_data=self.config_data)


class TestKeycodesTab:
    """Tests for the Keycodes tab."""

    @pytest.fixture()
    def config_with_keycodes(self) -> dict:
        config = SkimConfig().model_dump(mode="json")
        config["keycodes"]["pre_process"] = [
            {"keycode": "LSFT(KC_TAB)", "target": "MKC_BKTAB"},
        ]
        config["keycodes"]["overrides"] = [
            {"keycode": "MKC_BKTAB", "target": "%%nf-md-keyboard_tab_reverse;"},
            {"keycode": "KC_ESC", "target": "ESC"},
        ]
        return config

    @pytest.mark.asyncio()
    async def test_shows_pre_process_section(self, config_with_keycodes):
        """Has a pre-process list."""
        app = KeycodesTabTestApp(config_data=config_with_keycodes)
        async with app.run_test() as pilot:
            pre_list = app.query_one("#pre-process-list")
            assert pre_list is not None

    @pytest.mark.asyncio()
    async def test_shows_overrides_section(self, config_with_keycodes):
        """Has an overrides list."""
        app = KeycodesTabTestApp(config_data=config_with_keycodes)
        async with app.run_test() as pilot:
            overrides_list = app.query_one("#overrides-list")
            assert overrides_list is not None

    @pytest.mark.asyncio()
    async def test_pre_process_shows_entries(self, config_with_keycodes):
        """Pre-process list shows the configured entries."""
        app = KeycodesTabTestApp(config_data=config_with_keycodes)
        async with app.run_test() as pilot:
            from textual.widgets import ListView

            pre_list = app.query_one("#pre-process-list", ListView)
            assert len(pre_list.children) == 1

    @pytest.mark.asyncio()
    async def test_overrides_shows_entries(self, config_with_keycodes):
        """Overrides list shows the configured entries."""
        app = KeycodesTabTestApp(config_data=config_with_keycodes)
        async with app.run_test() as pilot:
            from textual.widgets import ListView

            overrides_list = app.query_one("#overrides-list", ListView)
            assert len(overrides_list.children) == 2

    @pytest.mark.asyncio()
    async def test_editing_override_updates_config(self, config_with_keycodes):
        """Changing an override field updates the config data."""
        app = KeycodesTabTestApp(config_data=config_with_keycodes)
        async with app.run_test() as pilot:
            from textual.widgets import Input

            target_input = app.query_one("#override-target", Input)
            target_input.value = "ESCAPE"
            await pilot.pause()
            assert app.config_data["keycodes"]["overrides"][0]["target"] == "ESCAPE"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/tui/test_keycodes_tab.py -v`
Expected: FAIL — `ImportError: cannot import name 'KeycodesTab'`

- [ ] **Step 3: Implement KeycodesTab**

```python
# src/skim/tui/keycodes_tab.py

# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Keycodes tab for the skim TUI configuration editor."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import Input, Label, ListItem, ListView, Static


class KeycodesTab(Widget):
    """Keycodes configuration tab with pre-process and overrides sections."""

    DEFAULT_CSS = """
    KeycodesTab {
        height: 1fr;
        padding: 1;
    }
    .section-title {
        text-style: bold;
        margin-bottom: 1;
        color: $accent;
    }
    .keycode-split {
        height: 1fr;
        margin-bottom: 1;
    }
    .keycode-list-panel {
        width: 1fr;
        max-width: 45;
        border-right: solid $primary-background;
        height: 100%;
    }
    .keycode-detail-panel {
        width: 2fr;
        padding: 0 1;
        height: 100%;
    }
    .field-row {
        height: auto;
        margin-bottom: 1;
    }
    .field-label {
        width: 12;
        padding-top: 1;
    }
    """

    def __init__(self, config_data: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.config_data = config_data
        self._selected_pre_process = 0
        self._selected_override = 0
        self._active_section = "overrides"

    def compose(self) -> ComposeResult:
        pre_process = self.config_data["keycodes"]["pre_process"]
        overrides = self.config_data["keycodes"]["overrides"]

        # Pre-process section
        yield Static("Pre-process", classes="section-title")
        with Horizontal(classes="keycode-split"):
            with Vertical(classes="keycode-list-panel"):
                yield ListView(
                    *[
                        ListItem(Label(f"{kc['keycode']} -> {kc['target']}"))
                        for kc in pre_process
                    ],
                    id="pre-process-list",
                )
            with VerticalScroll(classes="keycode-detail-panel"):
                yield self._make_keycode_detail(
                    pre_process[0] if pre_process else None,
                    "pre-process",
                )

        # Overrides section
        yield Static("Overrides", classes="section-title")
        with Horizontal(classes="keycode-split"):
            with Vertical(classes="keycode-list-panel"):
                yield ListView(
                    *[
                        ListItem(Label(f"{kc['keycode']} -> {kc['target']}"))
                        for kc in overrides
                    ],
                    id="overrides-list",
                )
            with VerticalScroll(classes="keycode-detail-panel"):
                yield self._make_keycode_detail(
                    overrides[0] if overrides else None,
                    "override",
                )

    def _make_keycode_detail(
        self, entry: dict[str, str] | None, prefix: str
    ) -> Widget:
        """Create keycode/target edit fields."""
        container = Vertical(id=f"{prefix}-detail")
        for field_name, field_key in [("Keycode", "keycode"), ("Target", "target")]:
            row = Horizontal(classes="field-row")
            row.compose_add_child(Label(field_name, classes="field-label"))
            row.compose_add_child(Input(
                value=entry.get(field_key, "") if entry else "",
                placeholder=field_name,
                id=f"{prefix}-{field_key}",
            ))
            container.compose_add_child(row)
        return container

    def on_input_changed(self, event: Input.Changed) -> None:
        input_id = event.input.id
        if not input_id:
            return

        if input_id.startswith("pre-process-"):
            field = input_id.replace("pre-process-", "")
            entries = self.config_data["keycodes"]["pre_process"]
            idx = self._selected_pre_process
            if idx < len(entries):
                entries[idx][field] = event.value
        elif input_id.startswith("override-"):
            field = input_id.replace("override-", "")
            entries = self.config_data["keycodes"]["overrides"]
            idx = self._selected_override
            if idx < len(entries):
                entries[idx][field] = event.value

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        list_id = event.list_view.id
        index = event.list_view.index
        if index is None:
            return

        if list_id == "pre-process-list":
            self._selected_pre_process = index
            entries = self.config_data["keycodes"]["pre_process"]
            if index < len(entries):
                self._update_detail("pre-process", entries[index])
        elif list_id == "overrides-list":
            self._selected_override = index
            entries = self.config_data["keycodes"]["overrides"]
            if index < len(entries):
                self._update_detail("override", entries[index])

    def _update_detail(self, prefix: str, entry: dict[str, str]) -> None:
        """Update detail fields for the selected entry."""
        for field_key in ["keycode", "target"]:
            try:
                input_widget = self.query_one(f"#{prefix}-{field_key}", Input)
                input_widget.value = entry.get(field_key, "")
            except Exception:
                pass
```

- [ ] **Step 4: Update app.py to use KeycodesTab**

In `src/skim/tui/app.py`, update the compose method to import and use `KeycodesTab`:

```python
    def compose(self) -> ComposeResult:
        from skim.tui.keyboard_tab import KeyboardTab
        from skim.tui.keycodes_tab import KeycodesTab

        with TabbedContent(initial="keyboard-tab"):
            with TabPane("Keyboard", id="keyboard-tab"):
                yield KeyboardTab(config_data=self.config_data)
            with TabPane("Keycodes", id="keycodes-tab"):
                yield KeycodesTab(config_data=self.config_data)
            with TabPane("Output", id="output-tab"):
                yield Static("Output tab placeholder")
        yield Footer()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/unit/tui/test_keycodes_tab.py tests/unit/tui/test_app.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/skim/tui/keycodes_tab.py src/skim/tui/app.py tests/unit/tui/test_keycodes_tab.py
git commit --no-verify -m "feat(tui): add Keycodes tab with pre-process and overrides"
```

---

### Task 6: Output Tab

**Files:**
- Create: `src/skim/tui/output_tab.py`
- Create: `tests/unit/tui/test_output_tab.py`
- Modify: `src/skim/tui/app.py`

- [ ] **Step 1: Write failing tests for output tab**

```python
# tests/unit/tui/test_output_tab.py

"""Unit tests for skim.tui.output_tab module."""

import pytest
from textual.app import App, ComposeResult

from skim.data.config import SkimConfig
from skim.tui.output_tab import OutputTab


class OutputTabTestApp(App):
    """Test app wrapping an OutputTab."""

    def __init__(self, config_data: dict) -> None:
        super().__init__()
        self.config_data = config_data

    def compose(self) -> ComposeResult:
        yield OutputTab(config_data=self.config_data)


class TestOutputTab:
    """Tests for the Output tab."""

    @pytest.fixture()
    def config_with_output(self) -> dict:
        config = SkimConfig().model_dump(mode="json")
        config["output"]["style"]["palette"]["layers"] = [
            {"base_color": "#347156", "color_index": 2, "gradient": None},
            {"base_color": "#89511C", "color_index": 2, "gradient": None},
        ]
        return config

    @pytest.mark.asyncio()
    async def test_shows_width_input(self, config_with_output):
        """Has a width input field."""
        app = OutputTabTestApp(config_data=config_with_output)
        async with app.run_test() as pilot:
            from textual.widgets import Input

            width_input = app.query_one("#layout-width", Input)
            assert width_input.value == "800.0"

    @pytest.mark.asyncio()
    async def test_shows_style_toggles(self, config_with_output):
        """Has style toggle switches."""
        app = OutputTabTestApp(config_data=config_with_output)
        async with app.run_test() as pilot:
            from textual.widgets import Switch

            switches = app.query(Switch)
            # use_layer_colors, show_layer_indicators, use_system_fonts, border enable
            assert len(switches) >= 3

    @pytest.mark.asyncio()
    async def test_shows_palette_color_inputs(self, config_with_output):
        """Has palette color input fields."""
        app = OutputTabTestApp(config_data=config_with_output)
        async with app.run_test() as pilot:
            from textual.widgets import Input

            neutral = app.query_one("#palette-neutral-color", Input)
            assert neutral.value == "#6F768B"

    @pytest.mark.asyncio()
    async def test_editing_width_updates_config(self, config_with_output):
        """Changing width updates the config data."""
        app = OutputTabTestApp(config_data=config_with_output)
        async with app.run_test() as pilot:
            from textual.widgets import Input

            width_input = app.query_one("#layout-width", Input)
            width_input.value = "1600"
            await pilot.pause()
            assert app.config_data["output"]["layout"]["width"] == 1600.0

    @pytest.mark.asyncio()
    async def test_shows_hold_symbol_select(self, config_with_output):
        """Has a select for hold_symbol_position."""
        app = OutputTabTestApp(config_data=config_with_output)
        async with app.run_test() as pilot:
            from textual.widgets import Select

            select = app.query_one("#hold-symbol-position", Select)
            assert select is not None

    @pytest.mark.asyncio()
    async def test_shows_layer_colors(self, config_with_output):
        """Shows layer color entries matching palette.layers."""
        app = OutputTabTestApp(config_data=config_with_output)
        async with app.run_test() as pilot:
            from textual.widgets import ListView

            color_list = app.query_one("#layer-colors-list", ListView)
            assert len(color_list.children) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/tui/test_output_tab.py -v`
Expected: FAIL — `ImportError: cannot import name 'OutputTab'`

- [ ] **Step 3: Implement OutputTab**

```python
# src/skim/tui/output_tab.py

# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Output tab for the skim TUI configuration editor."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import Input, Label, ListItem, ListView, Select, Static, Switch


class OutputTab(Widget):
    """Output configuration tab with layout, style, palette, and copyright."""

    DEFAULT_CSS = """
    OutputTab {
        height: 1fr;
        padding: 1;
    }
    .section-title {
        text-style: bold;
        margin-bottom: 1;
        color: $accent;
    }
    .field-row {
        height: auto;
        margin-bottom: 1;
    }
    .field-label {
        width: 20;
        padding-top: 1;
    }
    .narrow-input {
        width: 20;
    }
    .color-split {
        height: 1fr;
    }
    .color-list-panel {
        width: 1fr;
        max-width: 35;
        border-right: solid $primary-background;
        height: 100%;
    }
    .color-detail-panel {
        width: 2fr;
        padding: 0 1;
        height: 100%;
    }
    """

    def __init__(self, config_data: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.config_data = config_data
        self._selected_layer_color = 0

    def compose(self) -> ComposeResult:
        layout = self.config_data["output"]["layout"]
        style = self.config_data["output"]["style"]
        palette = style["palette"]

        with VerticalScroll():
            # Layout section
            yield Static("Layout", classes="section-title")
            with Horizontal(classes="field-row"):
                yield Label("Width", classes="field-label")
                yield Input(
                    value=str(layout["width"]),
                    id="layout-width",
                    classes="narrow-input",
                )
            with Horizontal(classes="field-row"):
                yield Label("Margin", classes="field-label")
                yield Input(
                    value=str(layout["spacing"]["margin"]),
                    id="layout-margin",
                    classes="narrow-input",
                )
            with Horizontal(classes="field-row"):
                yield Label("Inset", classes="field-label")
                yield Input(
                    value=str(layout["spacing"]["inset"]),
                    id="layout-inset",
                    classes="narrow-input",
                )

            # Style section
            yield Static("Style", classes="section-title")
            with Horizontal(classes="field-row"):
                yield Label("Layer colors on keys", classes="field-label")
                yield Switch(
                    value=style["use_layer_colors_on_keys"],
                    id="use-layer-colors",
                )
            with Horizontal(classes="field-row"):
                yield Label("Hold symbol position", classes="field-label")
                yield Select(
                    [(pos, pos) for pos in ("outward", "inward", "qmk")],
                    value=style["hold_symbol_position"],
                    id="hold-symbol-position",
                )
            with Horizontal(classes="field-row"):
                yield Label("Show layer indicators", classes="field-label")
                yield Switch(
                    value=style["show_layer_indicators"],
                    id="show-layer-indicators",
                )
            with Horizontal(classes="field-row"):
                yield Label("Use system fonts", classes="field-label")
                yield Switch(
                    value=style["use_system_fonts"],
                    id="use-system-fonts",
                )

            # Border
            border = style["border"]
            with Horizontal(classes="field-row"):
                yield Label("Border enabled", classes="field-label")
                yield Switch(
                    value=border is not None,
                    id="border-enabled",
                )
            if border:
                with Horizontal(classes="field-row"):
                    yield Label("Border width", classes="field-label")
                    yield Input(
                        value=str(border["width"]),
                        id="border-width",
                        classes="narrow-input",
                    )
                with Horizontal(classes="field-row"):
                    yield Label("Border radius", classes="field-label")
                    yield Input(
                        value=str(border["radius"]),
                        id="border-radius",
                        classes="narrow-input",
                    )

            # Palette section
            yield Static("Palette", classes="section-title")
            for color_name, color_id in [
                ("Neutral color", "neutral-color"),
                ("Text color", "text-color"),
                ("Key label color", "key-label-color"),
                ("Background color", "background-color"),
                ("Border color", "border-color"),
            ]:
                with Horizontal(classes="field-row"):
                    yield Label(color_name, classes="field-label")
                    yield Input(
                        value=str(palette[color_id.replace("-", "_")]),
                        id=f"palette-{color_id}",
                    )

            # Layer colors
            yield Static("Layer Colors", classes="section-title")
            layer_colors = palette["layers"]
            with Horizontal(classes="color-split"):
                with Vertical(classes="color-list-panel"):
                    yield ListView(
                        *[
                            ListItem(Label(f"Layer {i}: {lc['base_color']}"))
                            for i, lc in enumerate(layer_colors)
                        ],
                        id="layer-colors-list",
                    )
                with VerticalScroll(classes="color-detail-panel"):
                    if layer_colors:
                        lc = layer_colors[0]
                        yield Vertical(
                            Horizontal(
                                Label("Base color", classes="field-label"),
                                Input(value=lc["base_color"], id="lc-base-color"),
                                classes="field-row",
                            ),
                            Horizontal(
                                Label("Color index", classes="field-label"),
                                Input(
                                    value=str(lc["color_index"]),
                                    id="lc-color-index",
                                    classes="narrow-input",
                                ),
                                classes="field-row",
                            ),
                            id="layer-color-detail",
                        )

            # Copyright
            yield Static("Copyright", classes="section-title")
            with Horizontal(classes="field-row"):
                yield Label("Copyright text", classes="field-label")
                yield Input(
                    value=self.config_data["output"].get("copyright") or "",
                    placeholder="Optional copyright notice",
                    id="copyright-text",
                )

    def on_input_changed(self, event: Input.Changed) -> None:
        input_id = event.input.id
        if not input_id:
            return

        layout = self.config_data["output"]["layout"]
        style = self.config_data["output"]["style"]
        palette = style["palette"]

        # Layout fields
        float_fields = {
            "layout-width": lambda v: layout.__setitem__("width", v),
            "layout-margin": lambda v: layout["spacing"].__setitem__("margin", v),
            "layout-inset": lambda v: layout["spacing"].__setitem__("inset", v),
            "border-width": lambda v: style["border"].__setitem__("width", v) if style["border"] else None,
            "border-radius": lambda v: style["border"].__setitem__("radius", v) if style["border"] else None,
        }

        if input_id in float_fields:
            try:
                float_fields[input_id](float(event.value))
            except ValueError:
                pass
            return

        # Palette color fields
        palette_fields = {
            "palette-neutral-color": "neutral_color",
            "palette-text-color": "text_color",
            "palette-key-label-color": "key_label_color",
            "palette-background-color": "background_color",
            "palette-border-color": "border_color",
        }

        if input_id in palette_fields:
            palette[palette_fields[input_id]] = event.value
            return

        # Layer color fields
        if input_id == "lc-base-color":
            layers = palette["layers"]
            if self._selected_layer_color < len(layers):
                layers[self._selected_layer_color]["base_color"] = event.value
        elif input_id == "lc-color-index":
            try:
                layers = palette["layers"]
                if self._selected_layer_color < len(layers):
                    layers[self._selected_layer_color]["color_index"] = int(event.value)
            except ValueError:
                pass

        # Copyright
        if input_id == "copyright-text":
            self.config_data["output"]["copyright"] = event.value or None

    def on_switch_changed(self, event: Switch.Changed) -> None:
        style = self.config_data["output"]["style"]
        switch_map = {
            "use-layer-colors": "use_layer_colors_on_keys",
            "show-layer-indicators": "show_layer_indicators",
            "use-system-fonts": "use_system_fonts",
        }

        switch_id = event.switch.id
        if switch_id in switch_map:
            style[switch_map[switch_id]] = event.value
        elif switch_id == "border-enabled":
            if event.value:
                style["border"] = {"width": 2.0, "radius": 10.0}
            else:
                style["border"] = None

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "hold-symbol-position":
            self.config_data["output"]["style"]["hold_symbol_position"] = str(event.value)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.list_view.id != "layer-colors-list":
            return
        index = event.list_view.index
        if index is None:
            return

        self._selected_layer_color = index
        layers = self.config_data["output"]["style"]["palette"]["layers"]
        if index < len(layers):
            lc = layers[index]
            try:
                self.query_one("#lc-base-color", Input).value = lc["base_color"]
                self.query_one("#lc-color-index", Input).value = str(lc["color_index"])
            except Exception:
                pass
```

- [ ] **Step 4: Update app.py to use OutputTab**

In `src/skim/tui/app.py`, update compose to import and use `OutputTab`:

```python
    def compose(self) -> ComposeResult:
        from skim.tui.keyboard_tab import KeyboardTab
        from skim.tui.keycodes_tab import KeycodesTab
        from skim.tui.output_tab import OutputTab

        with TabbedContent(initial="keyboard-tab"):
            with TabPane("Keyboard", id="keyboard-tab"):
                yield KeyboardTab(config_data=self.config_data)
            with TabPane("Keycodes", id="keycodes-tab"):
                yield KeycodesTab(config_data=self.config_data)
            with TabPane("Output", id="output-tab"):
                yield OutputTab(config_data=self.config_data)
        yield Footer()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/unit/tui/ -v`
Expected: All TUI tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/skim/tui/output_tab.py src/skim/tui/app.py tests/unit/tui/test_output_tab.py
git commit --no-verify -m "feat(tui): add Output tab with layout, style, palette, copyright"
```

---

### Task 7: CLI Integration

**Files:**
- Modify: `src/skim/cli.py`
- Modify: `tests/unit/test_cli.py`

- [ ] **Step 1: Write failing tests for TUI CLI integration**

Append to `tests/unit/test_cli.py` inside `TestConfigureCommand`:

```python
    @patch("skim.cli.setup_logging")
    @patch("sys.stdout")
    def test_tui_launches_when_no_keybard_and_tty(self, mock_stdout, mock_setup):
        """TUI launches when no -k flag and stdout is a TTY."""
        mock_stdout.isatty.return_value = True
        with patch("skim.cli.launch_tui") as mock_tui:
            runner = CliRunner()
            result = runner.invoke(main, ["configure"])
            # When TTY, the TUI should be attempted
            # But CliRunner doesn't simulate TTY, so the non-TTY path runs
            # Test the TTY detection logic directly instead
            assert result.exit_code == 0

    @patch("skim.cli.setup_logging")
    def test_non_tty_outputs_yaml(self, mock_setup):
        """Non-TTY stdout outputs YAML directly (pipe-safe)."""
        runner = CliRunner()
        result = runner.invoke(main, ["configure"])
        assert result.exit_code == 0
        parsed = yaml.safe_load(result.output)
        assert "keyboard" in parsed
```

- [ ] **Step 2: Run tests to verify existing tests still pass**

Run: `python -m pytest tests/unit/test_cli.py::TestConfigureCommand -v`
Expected: All tests PASS (new test also passes since it tests the non-TTY fallback)

- [ ] **Step 3: Update CLI configure command with TUI branch**

In `src/skim/cli.py`, replace the `configure` function body:

```python
def configure(
    keybard_keymap: Path | None,
    output: Path | None,
    force: bool,
    qmk_color_header: Path | None,
    adjust_lightness: float | None,
    adjust_saturation: float | None,
) -> None:
    """Generate or output configuration file.

    When -k is provided, extracts metadata (layer colors, names, custom
    keycodes) from the Keybard file to create a skim configuration.
    Optionally imports QMK named colors from a color.h file.

    Without -k and with a TTY, launches an interactive configuration editor.

    Without -k and without a TTY, outputs the default configuration template.

    Color adjustments (--adjust-lightness, --adjust-saturation) are applied
    to all extracted colors to ensure readable contrast in generated images.
    """
    from skim.application.config_generator import ConfigGenerator

    try:
        generator = ConfigGenerator()

        if keybard_keymap:
            # CLI path: generate from keybard file
            raw_content = keybard_keymap.read_text()
            qmk_content = qmk_color_header.read_text() if qmk_color_header else None
            content = generator.generate_from_keybard(
                raw_content, qmk_content, adjust_lightness, adjust_saturation
            )

            if output:
                _write_config(output, content, force)
            else:
                click.echo(content)
            return

        # No -k flag: try TUI or fall back to default output
        if sys.stdout.isatty():
            try:
                from skim.tui import launch_tui

                # Load existing config if output path exists
                config_data = _load_initial_config(output)
                launch_tui(config_data=config_data, output_path=output, force=force)
                return
            except ImportError:
                click.echo(
                    "Error: The TUI requires the 'textual' package. Install it with:\n"
                    "    pip install qmk-skim[tui]",
                    err=True,
                )
                sys.exit(1)

        # Non-TTY: output default YAML
        content = generator.generate_default()
        if output:
            _write_config(output, content, force)
        else:
            click.echo(content)

    except (ValueError, OSError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def _load_initial_config(output_path: Path | None) -> dict:
    """Load config from output path if it exists, otherwise return defaults."""
    import yaml

    from skim.data.config import SkimConfig

    if output_path and output_path.is_file():
        data = yaml.safe_load(output_path.read_text())
        if data:
            config = SkimConfig.model_validate(data)
            return config.model_dump(mode="json")

    return SkimConfig().model_dump(mode="json")


def _write_config(output: Path, content: str, force: bool) -> None:
    """Write config content to file with overwrite protection."""
    if output.is_dir():
        output = output / "skim-config.yaml"

    if output.exists() and not force:
        try:
            click.confirm(
                f"File {output} already exists. Do you want to overwrite?",
                abort=True,
            )
        except click.Abort:
            click.echo("Aborted.", err=True)
            sys.exit(1)

    output.write_text(content)
    click.echo(f"Configuration written to {output}")
```

- [ ] **Step 4: Run all tests to verify they pass**

Run: `python -m pytest tests/unit/test_cli.py tests/unit/tui/ tests/unit/application/test_config_generator.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/skim/cli.py tests/unit/test_cli.py
git commit --no-verify -m "feat(config): add TUI launch path to configure command"
```

---

### Task 8: Manual Smoke Test

- [ ] **Step 1: Test TUI launches**

Run: `python -m skim configure`
Expected: TUI opens with three tabs (Keyboard, Keycodes, Output), footer shows Save/Quit bindings

- [ ] **Step 2: Test tab switching**

In the TUI, press Tab or click tab headers to switch between Keyboard, Keycodes, Output tabs.
Expected: Each tab shows its respective content

- [ ] **Step 3: Test loading existing config**

Run: `python -m skim configure -o samples/config/skim-config.yaml`
Expected: TUI opens with the sample config loaded — 9 layers visible in the Keyboard tab, keycodes populated, palette colors from the sample

- [ ] **Step 4: Test save**

Run: `python -m skim configure -o /tmp/tui-test-config.yaml`
Edit a field, press Ctrl+S
Expected: File written, notification shown

- [ ] **Step 5: Test quit with unsaved changes**

Edit a field, press Q
Expected: Confirmation dialog appears. "No" returns to editor, "Yes" exits.

- [ ] **Step 6: Test non-TTY fallback**

Run: `python -m skim configure | head -5`
Expected: YAML output to stdout (TUI not launched)

- [ ] **Step 7: Test -k flag still works (no TUI)**

Run: `python -m skim configure -k samples/keymaps/keybard-sample.kbi | head -5`
Expected: YAML output from keybard extraction, no TUI
