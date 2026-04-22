# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Keycodes tab widget for the skim TUI configuration editor."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import Button, Input, Label, ListItem, ListView, Static


class KeycodesTab(Widget):
    """Keycodes configuration tab.

    Shows two sections — Pre-process and Overrides — each using a
    list/detail split for editing individual keycode mapping entries.
    """

    DEFAULT_CSS = """
    KeycodesTab {
        height: 1fr;
        padding: 0 1;
    }
    KeycodesTab .keycodes-section {
        height: 1fr;
    }
    KeycodesTab .list-col {
        width: 35;
        min-width: 20;
        height: 100%;
    }
    KeycodesTab .keycode-list {
        max-height: 100%;
        border: solid $accent 50%;
    }
    KeycodesTab .list-buttons {
        dock: bottom;
    }
    KeycodesTab .keycode-detail {
        padding: 0 1;
        height: auto;
        overflow-x: hidden;
    }
    """

    def __init__(self, config_data: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.config_data = config_data
        self._selected_pre_process: int = 0
        self._selected_override: int = 0

    def compose(self) -> ComposeResult:
        # Pre-process section
        with Vertical(id="pre-process-section", classes="keycodes-section"):
            yield Static("Pre-process", classes="section-title")
            with Horizontal():
                with Vertical(classes="list-col"):
                    yield ListView(id="pre-process-list", classes="keycode-list")
                    with Horizontal(classes="list-buttons"):
                        yield Button("+ Add", id="add-pre-process", variant="success")
                        yield Button("- Remove", id="remove-pre-process", variant="error")

                with VerticalScroll(id="pre-process-detail", classes="keycode-detail"):
                    with Horizontal(classes="field-row"):
                        yield Label("Keycode:", classes="field-label")
                        yield Input(value="", id="pre-process-keycode", placeholder="e.g. LSFT(KC_TAB)")
                    with Horizontal(classes="field-row"):
                        yield Label("Target:", classes="field-label")
                        yield Input(value="", id="pre-process-target", placeholder="e.g. MKC_BKTAB")

        # Overrides section
        with Vertical(id="overrides-section", classes="keycodes-section"):
            yield Static("Overrides", classes="section-title")
            with Horizontal():
                with Vertical(classes="list-col"):
                    yield ListView(id="overrides-list", classes="keycode-list")
                    with Horizontal(classes="list-buttons"):
                        yield Button("+ Add", id="add-override", variant="success")
                        yield Button("- Remove", id="remove-override", variant="error")

                with VerticalScroll(id="override-detail", classes="keycode-detail"):
                    with Horizontal(classes="field-row"):
                        yield Label("Keycode:", classes="field-label")
                        yield Input(value="", id="override-keycode", placeholder="e.g. KC_ESC")
                    with Horizontal(classes="field-row"):
                        yield Label("Target:", classes="field-label")
                        yield Input(value="", id="override-target", placeholder="e.g. ESC")

    def on_mount(self) -> None:
        """Populate lists after mount."""
        self._rebuild_pre_process_list()
        self._rebuild_overrides_list()
        pre_process = self.config_data.get("keycodes", {}).get("pre_process", [])
        if pre_process:
            self._selected_pre_process = 0
            self._refresh_pre_process_fields()
        overrides = self.config_data.get("keycodes", {}).get("overrides", [])
        if overrides:
            self._selected_override = 0
            self._refresh_override_fields()

    def _rebuild_pre_process_list(self) -> None:
        entries = self.config_data.get("keycodes", {}).get("pre_process", [])
        list_view = self.query_one("#pre-process-list", ListView)
        list_view.clear()
        for i, entry in enumerate(entries):
            kc = entry.get("keycode", "")
            tgt = entry.get("target", "")
            list_view.append(ListItem(Static(f"{kc} -> {tgt}"), id=f"pre-process-item-{i}"))

    def _rebuild_overrides_list(self) -> None:
        entries = self.config_data.get("keycodes", {}).get("overrides", [])
        list_view = self.query_one("#overrides-list", ListView)
        list_view.clear()
        for i, entry in enumerate(entries):
            kc = entry.get("keycode", "")
            tgt = entry.get("target", "")
            list_view.append(ListItem(Static(f"{kc} -> {tgt}"), id=f"override-item-{i}"))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id

        if button_id == "add-pre-process":
            entries = self.config_data.setdefault("keycodes", {}).setdefault("pre_process", [])
            entries.append({"keycode": "", "target": ""})
            self._rebuild_pre_process_list()
            self._selected_pre_process = len(entries) - 1
            self._refresh_pre_process_fields()
            self.query_one("#pre-process-list", ListView).index = self._selected_pre_process

        elif button_id == "remove-pre-process":
            entries = self.config_data.get("keycodes", {}).get("pre_process", [])
            if not entries or self._selected_pre_process >= len(entries):
                return
            entries.pop(self._selected_pre_process)
            self._rebuild_pre_process_list()
            if entries:
                self._selected_pre_process = min(self._selected_pre_process, len(entries) - 1)
                self._refresh_pre_process_fields()
                self.query_one("#pre-process-list", ListView).index = self._selected_pre_process
            else:
                self._selected_pre_process = 0
                self._clear_fields("pre-process")

        elif button_id == "add-override":
            entries = self.config_data.setdefault("keycodes", {}).setdefault("overrides", [])
            entries.append({"keycode": "", "target": ""})
            self._rebuild_overrides_list()
            self._selected_override = len(entries) - 1
            self._refresh_override_fields()
            self.query_one("#overrides-list", ListView).index = self._selected_override

        elif button_id == "remove-override":
            entries = self.config_data.get("keycodes", {}).get("overrides", [])
            if not entries or self._selected_override >= len(entries):
                return
            entries.pop(self._selected_override)
            self._rebuild_overrides_list()
            if entries:
                self._selected_override = min(self._selected_override, len(entries) - 1)
                self._refresh_override_fields()
                self.query_one("#overrides-list", ListView).index = self._selected_override
            else:
                self._selected_override = 0
                self._clear_fields("override")

    def _clear_fields(self, prefix: str) -> None:
        self.query_one(f"#{prefix}-keycode", Input).value = ""
        self.query_one(f"#{prefix}-target", Input).value = ""

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item is None:
            return
        item_id = event.item.id or ""

        if event.list_view.id == "pre-process-list" and item_id.startswith("pre-process-item-"):
            try:
                index = int(item_id[len("pre-process-item-"):])
            except ValueError:
                return
            self._selected_pre_process = index
            self._refresh_pre_process_fields()

        elif event.list_view.id == "overrides-list" and item_id.startswith("override-item-"):
            try:
                index = int(item_id[len("override-item-"):])
            except ValueError:
                return
            self._selected_override = index
            self._refresh_override_fields()

    def _refresh_pre_process_fields(self) -> None:
        entries = self.config_data.get("keycodes", {}).get("pre_process", [])
        if self._selected_pre_process >= len(entries):
            return
        entry = entries[self._selected_pre_process]
        self.query_one("#pre-process-keycode", Input).value = entry.get("keycode", "") or ""
        self.query_one("#pre-process-target", Input).value = entry.get("target", "") or ""

    def _refresh_override_fields(self) -> None:
        entries = self.config_data.get("keycodes", {}).get("overrides", [])
        if self._selected_override >= len(entries):
            return
        entry = entries[self._selected_override]
        self.query_one("#override-keycode", Input).value = entry.get("keycode", "") or ""
        self.query_one("#override-target", Input).value = entry.get("target", "") or ""

    def on_input_changed(self, event: Input.Changed) -> None:
        input_id = event.input.id or ""

        if input_id.startswith("pre-process-"):
            field = input_id[len("pre-process-"):]
            entries = self.config_data.get("keycodes", {}).get("pre_process", [])
            if self._selected_pre_process < len(entries):
                entries[self._selected_pre_process][field] = event.value

        elif input_id.startswith("override-"):
            field = input_id[len("override-"):]
            entries = self.config_data.get("keycodes", {}).get("overrides", [])
            if self._selected_override < len(entries):
                entries[self._selected_override][field] = event.value
