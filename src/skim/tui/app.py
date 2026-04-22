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
        from skim.tui.keyboard_tab import KeyboardTab

        with TabbedContent(initial="keyboard-tab"):
            with TabPane("Keyboard", id="keyboard-tab"):
                yield KeyboardTab(config_data=self.config_data)
            with TabPane("Keycodes", id="keycodes-tab"):
                from skim.tui.keycodes_tab import KeycodesTab
                yield KeycodesTab(config_data=self.config_data)
            with TabPane("Output", id="output-tab"):
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
