# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Main TUI application for skim configuration editing."""

import copy
from pathlib import Path
from typing import Any

import yaml
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.message import Message
from textual.widgets import (
    Button,
    Footer,
    Label,
    ListView,
    Static,
    TabPane,
    TabbedContent,
    Tabs,
)

from skim.tui.widgets import SkimListView

from skim.data.config import SkimConfig


class LayerAdded(Message):
    """Posted when a layer is added in either tab."""

    def __init__(self, index: int, source_tab: str) -> None:
        super().__init__()
        self.index = index
        self.source_tab = source_tab


class LayerRemoved(Message):
    """Posted when a layer is removed in either tab."""

    def __init__(self, index: int, source_tab: str) -> None:
        super().__init__()
        self.index = index
        self.source_tab = source_tab


class LayerUpdated(Message):
    """Posted when a layer's metadata (name, label, etc.) is changed."""


class QuitConfirmScreen(ModalScreen[str]):
    """Modal dialog for save-on-quit with unsaved changes.

    Returns "save" to save and quit, "discard" to quit without saving,
    or None if dismissed.
    """

    BINDINGS = [
        Binding(key="s", action="save_quit", description="Save & Quit", show=False),
        Binding(key="d", action="discard", description="Discard", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="quit-dialog"):
            yield Label(
                "You have unsaved changes.\nDo you want to save before quitting?",
                id="question",
            )
            with Horizontal(id="quit-buttons"):
                yield Button("Save & Quit (s)", variant="success", id="save")
                yield Button("Discard (d)", variant="error", id="discard")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id)

    def action_save_quit(self) -> None:
        self.dismiss("save")

    def action_discard(self) -> None:
        self.dismiss("discard")


_DEFAULT_CONFIG_NAME = "skim-config.yaml"


class SaveTargetScreen(ModalScreen[str | None]):
    """Modal dialog to choose where to save when -c was used without -o.

    Returns "overwrite" to save back to the config file,
    "default" to save to skim-config.yaml in cwd, or None if dismissed.
    """

    BINDINGS = [
        Binding(key="escape", action="dismiss_dialog", description="Cancel", show=False),
    ]

    def __init__(self, config_path: Path) -> None:
        super().__init__()
        self.config_path = config_path

    def compose(self) -> ComposeResult:
        with Vertical(id="save-target-dialog"):
            yield Label(
                "Where do you want to save?",
                id="question",
            )
            with Vertical(id="save-target-buttons"):
                yield Button(
                    f"Overwrite {self.config_path.name} (o)",
                    variant="warning",
                    id="overwrite",
                )
                yield Button(
                    f"Create ./{_DEFAULT_CONFIG_NAME} (c)",
                    variant="success",
                    id="default",
                )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id)

    def on_key(self, event) -> None:
        if event.key == "o":
            self.dismiss("overwrite")
        elif event.key == "c":
            self.dismiss("default")

    def action_dismiss_dialog(self) -> None:
        self.dismiss(None)


class OverwriteConfirmScreen(ModalScreen[bool]):
    """Modal dialog to confirm overwriting an existing file.

    Returns True to overwrite, False to cancel.
    """

    BINDINGS = [
        Binding(key="escape", action="dismiss_dialog", description="Cancel", show=False),
    ]

    def __init__(self, path: Path, display_name: str | None = None) -> None:
        super().__init__()
        self.path = path
        self._display_name = display_name or str(path)

    def compose(self) -> ComposeResult:
        with Vertical(id="overwrite-dialog"):
            yield Label(
                f"File '{self._display_name}' already exists.\nOverwrite?",
                id="question",
            )
            with Horizontal(id="overwrite-buttons"):
                yield Button("Overwrite (y)", variant="warning", id="confirm")
                yield Button("Cancel (n)", variant="default", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm")

    def on_key(self, event) -> None:
        if event.key == "y":
            self.dismiss(True)
        elif event.key == "n":
            self.dismiss(False)

    def action_dismiss_dialog(self) -> None:
        self.dismiss(False)


class ErrorDialog(ModalScreen[None]):
    """Modal dialog to show an error message."""

    BINDINGS = [
        Binding(key="escape", action="dismiss_dialog", description="OK", show=False),
    ]

    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="error-dialog"):
            yield Label(self.message, id="error-message")
            with Horizontal(id="error-buttons"):
                yield Button("OK", variant="primary", id="ok")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)

    def action_dismiss_dialog(self) -> None:
        self.dismiss(None)


class SkimConfigApp(App):
    """Interactive skim configuration editor."""

    ENABLE_COMMAND_PALETTE = False
    TITLE = "skim configure"
    CSS = """
    QuitConfirmScreen, SaveTargetScreen, OverwriteConfirmScreen, ErrorDialog {
        align: center middle;
    }
    #quit-dialog, #save-target-dialog, #error-dialog {
        padding: 1 2;
        width: 55;
        height: auto;
        border: thick $background 80%;
        background: $surface;
    }
    #overwrite-dialog {
        padding: 1 2;
        width: 82;
        height: auto;
        border: thick $background 80%;
        background: $surface;
    }
    #question {
        text-align: center;
        width: 100%;
        height: auto;
        margin-bottom: 1;
    }
    #error-message {
        text-align: center;
        width: 100%;
        height: auto;
        margin-bottom: 1;
    }
    #quit-buttons, #overwrite-buttons, #error-buttons {
        width: 100%;
        height: auto;
        align-horizontal: center;
    }
    #quit-buttons Button, #overwrite-buttons Button, #error-buttons Button {
        margin: 0 1;
        padding: 0 3;
    }
    #save-target-buttons {
        width: 100%;
        height: auto;
        align-horizontal: center;
    }
    #save-target-buttons Button {
        width: 100%;
        margin: 0 0 1 0;
    }
    /* Global compact styling */
    Input {
        height: 3;
        width: 1fr;
        margin: 0;
    }
    Switch {
        height: auto;
        min-height: 1;
    }
    Select {
        width: 1fr;
        max-width: 30;
    }
    .field-row {
        height: auto;
        margin: 0;
        padding: 0;
    }
    .field-label {
        width: 22;
        height: 3;
        padding: 1 0 0 0;
    }
    .section-title {
        text-style: bold;
        color: $accent;
        margin: 1 0 0 0;
    }
    .section-title-first {
        margin: 0;
    }
    AutoComplete {
        & AutoCompleteList {
            border-left: wide $accent;
        }
    }
    ListItem > Static {
        text-wrap: nowrap;
        text-overflow: ellipsis;
        width: 1fr;
    }
    ListItem > .lc-swatch {
        width: 4;
    }
    .list-buttons {
        height: auto;
    }
    .list-buttons Button {
        min-width: 12;
        margin: 0 1 0 0;
    }
    """

    BINDINGS = [
        Binding(key="ctrl+q", action="request_quit", description="Quit"),
        Binding(key="ctrl+s", action="save", description="Save"),
        Binding(key="ctrl+p", action="previous_tab", description="Previous Tab", priority=True),
        Binding(key="ctrl+n", action="next_tab", description="Next Tab", priority=True),
    ]

    def __init__(
        self,
        config_data: dict[str, Any],
        output_path: Path | None = None,
        config_path: Path | None = None,
        force: bool = False,
    ) -> None:
        super().__init__()
        self.config_data = config_data
        self.saved_data = copy.deepcopy(config_data)
        self._tab_focus: dict[str, str] = {}
        self.output_path = output_path
        self.config_path = config_path
        self.force = force

    def compose(self) -> ComposeResult:
        from skim.tui.keyboard_tab import KeyboardTab

        with TabbedContent(initial="keyboard-tab"):
            with TabPane("Keyboard", id="keyboard-tab"):
                yield KeyboardTab(config_data=self.config_data)
            with TabPane("Keycodes", id="keycodes-tab"):
                from skim.tui.keycodes_tab import KeycodesTab
                yield KeycodesTab(config_data=self.config_data)
            with TabPane("Style", id="output-tab"):
                from skim.tui.output_tab import OutputTab
                yield OutputTab(config_data=self.config_data)
        yield Footer()

    @property
    def has_unsaved_changes(self) -> bool:
        return self.config_data != self.saved_data

    def action_request_quit(self) -> None:
        if self.has_unsaved_changes:
            self.push_screen(QuitConfirmScreen(), self._handle_quit_confirm)
        else:
            self.exit()

    def _handle_quit_confirm(self, result: str | None) -> None:
        if result == "save":
            self.action_save(exit_after=True)
        elif result == "discard":
            self.exit()

    def _save_current_tab_focus(self) -> None:
        """Save the currently focused widget for the active tab pane."""
        tabbed = self.query_one(TabbedContent)
        pane = tabbed.active_pane
        focused = self.focused
        if pane is not None and focused is not None and focused.id is not None:
            if focused in pane.query("*"):
                self._tab_focus[pane.id] = focused.id

    def action_previous_tab(self) -> None:
        self._save_current_tab_focus()
        self.query_one(Tabs).action_previous_tab()
        self.call_after_refresh(self._restore_tab_focus)

    def action_next_tab(self) -> None:
        self._save_current_tab_focus()
        self.query_one(Tabs).action_next_tab()
        self.call_after_refresh(self._restore_tab_focus)

    def _restore_tab_focus(self) -> None:
        """Restore previously focused widget for the active tab pane, or focus the first focusable child."""
        tabbed = self.query_one(TabbedContent)
        pane = tabbed.active_pane
        if pane is None:
            return
        saved_id = self._tab_focus.get(pane.id)
        if saved_id is not None:
            try:
                widget = pane.query_one(f"#{saved_id}")
                if widget.can_focus:
                    widget.focus()
                    return
            except Exception:
                pass
        for widget in pane.query("*"):
            if widget.can_focus:
                widget.focus()
                return

    def action_save(self, *, exit_after: bool = False) -> None:
        try:
            SkimConfig.model_validate(self.config_data)
        except Exception as e:
            self.notify(f"Validation error: {e}", severity="error")
            return

        if self.output_path is not None:
            # -o was provided: save directly to that path
            path = self.output_path
            if path.is_dir():
                path = path / _DEFAULT_CONFIG_NAME
            self._save_to_path(path, exit_after=exit_after)
        elif self.config_path is not None:
            # -c was provided without -o: ask where to save
            self.push_screen(
                SaveTargetScreen(self.config_path),
                lambda result: self._handle_save_target(result, exit_after=exit_after),
            )
        else:
            # No -o or -c: save to default in cwd
            path = Path.cwd() / _DEFAULT_CONFIG_NAME
            self._save_to_path(path, prettify_name=True, exit_after=exit_after)

    def _handle_save_target(self, result: str | None, *, exit_after: bool = False) -> None:
        if result == "overwrite":
            assert self.config_path is not None
            # User already confirmed overwrite intent via the dialog choice
            self._do_write(self.config_path, exit_after=exit_after)
        elif result == "default":
            self._save_to_path(
                Path.cwd() / _DEFAULT_CONFIG_NAME, prettify_name=True, exit_after=exit_after,
            )

    @staticmethod
    def _friendly_path(path: Path) -> str:
        """Return a user-friendly display name for a path."""
        try:
            rel = path.relative_to(Path.cwd())
        except ValueError:
            rel = path
        path_str = str(rel)
        if not path_str.startswith((".", "/")):
            path_str = f"./{path_str}"
        return path_str

    def _save_to_path(
        self, path: Path, *, prettify_name: bool = False, exit_after: bool = False,
    ) -> None:
        if path.exists() and not self.force:
            display_name = self._friendly_path(path) if prettify_name else None
            self.push_screen(
                OverwriteConfirmScreen(path, display_name=display_name),
                lambda confirmed: self._do_write(path, exit_after=exit_after) if confirmed else None,
            )
            return
        self._do_write(path, exit_after=exit_after)

    def _do_write(self, path: Path, *, exit_after: bool = False) -> None:
        content = yaml.dump(self.config_data, sort_keys=False, default_flow_style=False)
        path.write_text(content)
        self.saved_data = copy.deepcopy(self.config_data)
        self.notify(f"Saved to {path}", severity="information")
        if exit_after:
            self.exit()

    def on_layer_added(self, event: LayerAdded) -> None:
        from skim.tui.keyboard_tab import KeyboardTab
        from skim.tui.output_tab import OutputTab

        if event.source_tab == "keyboard":
            self.query_one(OutputTab).sync_layer_added(event.index)
        elif event.source_tab == "style":
            self.query_one(KeyboardTab).sync_layer_added(event.index)

    def on_layer_updated(self, event: LayerUpdated) -> None:
        from skim.tui.output_tab import OutputTab

        self.query_one(OutputTab)._rebuild_layer_colors_list()

    def on_layer_removed(self, event: LayerRemoved) -> None:
        from skim.tui.keyboard_tab import KeyboardTab
        from skim.tui.output_tab import OutputTab

        if event.source_tab == "keyboard":
            self.query_one(OutputTab).sync_layer_removed(event.index)
        elif event.source_tab == "style":
            self.query_one(KeyboardTab).sync_layer_removed(event.index)

    def on_descendant_focus(self, event: events.DescendantFocus) -> None:
        widget = event.widget
        if isinstance(widget, (ListView, SkimListView)) and widget.index is None and len(widget.children) > 0:
            widget.index = 0

