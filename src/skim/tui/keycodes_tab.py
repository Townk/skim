# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Keycodes tab widget for the skim TUI configuration editor."""

import copy
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import Button, Input, Label, ListItem, ListView, Static


class KeycodesTab(Widget):
    """Keycodes configuration tab.

    Shows two sections — Pre-process and Overrides — each using a
    list/detail split for editing individual keycode mapping entries.

    Detail fields are disabled until Enter is pressed on a list item.
    Enter in a field commits, Escape rolls back.
    """

    DEFAULT_CSS = """
    KeycodesTab {
        height: 1fr;
        padding: 0 1;
    }
    KeycodesTab .keycodes-section {
        height: 50%;
    }
    KeycodesTab .list-col {
        width: 35;
        min-width: 25;
        height: 100%;
    }
    KeycodesTab .keycode-list {
        max-height: 100%;
        border: solid $accent 50%;
    }
    KeycodesTab .list-buttons {
        dock: bottom;
        height: auto;
        width: 100%;
    }
    KeycodesTab .list-buttons Button {
        width: 50%;
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
        self._editing_section: str | None = None  # "pre-process" or "override"
        self._snapshot: dict[str, str] | None = None

    @staticmethod
    def _entry_text(entry: dict[str, str]) -> str:
        return f"{entry.get('keycode', '')} -> {entry.get('target', '')}"

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

                with VerticalScroll(id="pre-process-detail", classes="keycode-detail", can_focus=False):
                    with Horizontal(classes="field-row"):
                        yield Label("Keycode:", classes="field-label")
                        yield Input(
                            value="", id="pre-process-keycode",
                            placeholder="e.g. LSFT(KC_TAB)", disabled=True,
                        )
                    with Horizontal(classes="field-row"):
                        yield Label("Target:", classes="field-label")
                        yield Input(
                            value="", id="pre-process-target",
                            placeholder="e.g. MKC_BKTAB", disabled=True,
                        )

        # Overrides section
        with Vertical(id="overrides-section", classes="keycodes-section"):
            yield Static("Overrides", classes="section-title")
            with Horizontal():
                with Vertical(classes="list-col"):
                    yield ListView(id="overrides-list", classes="keycode-list")
                    with Horizontal(classes="list-buttons"):
                        yield Button("+ Add", id="add-override", variant="success")
                        yield Button("- Remove", id="remove-override", variant="error")

                with VerticalScroll(id="override-detail", classes="keycode-detail", can_focus=False):
                    with Horizontal(classes="field-row"):
                        yield Label("Keycode:", classes="field-label")
                        yield Input(
                            value="", id="override-keycode",
                            placeholder="e.g. KC_ESC", disabled=True,
                        )
                    with Horizontal(classes="field-row"):
                        yield Label("Target:", classes="field-label")
                        yield Input(
                            value="", id="override-target",
                            placeholder="e.g. ESC", disabled=True,
                        )

    def on_mount(self) -> None:
        self._rebuild_pre_process_list()
        self._rebuild_overrides_list()
        if self.config_data.get("keycodes", {}).get("pre_process", []):
            self._selected_pre_process = 0
            self._refresh_fields("pre-process")
        if self.config_data.get("keycodes", {}).get("overrides", []):
            self._selected_override = 0
            self._refresh_fields("override")
        self._update_list_states()

    def _entries_for(self, section: str) -> list[dict[str, str]]:
        """Get the entries list for a section."""
        key = "pre_process" if section == "pre-process" else "overrides"
        return self.config_data.get("keycodes", {}).get(key, [])

    def _selected_for(self, section: str) -> int:
        return self._selected_pre_process if section == "pre-process" else self._selected_override

    def _set_selected(self, section: str, index: int) -> None:
        if section == "pre-process":
            self._selected_pre_process = index
        else:
            self._selected_override = index

    def _list_id(self, section: str) -> str:
        return "pre-process-list" if section == "pre-process" else "overrides-list"

    def _rebuild_list(self, section: str) -> None:
        entries = self._entries_for(section)
        list_view = self.query_one(f"#{self._list_id(section)}", ListView)
        list_view.clear()
        for entry in entries:
            list_view.append(ListItem(Static(self._entry_text(entry))))

    def _rebuild_pre_process_list(self) -> None:
        self._rebuild_list("pre-process")

    def _rebuild_overrides_list(self) -> None:
        self._rebuild_list("override")

    def _update_list_item(self, section: str) -> None:
        entries = self._entries_for(section)
        index = self._selected_for(section)
        if index >= len(entries):
            return
        list_view = self.query_one(f"#{self._list_id(section)}", ListView)
        if index < len(list_view.children):
            item = list_view.children[index]
            item.query_one(Static).update(self._entry_text(entries[index]))

    def _update_list_states(self) -> None:
        """Update list focusability and Remove button state for both sections."""
        for section, remove_id in [("pre-process", "remove-pre-process"), ("override", "remove-override")]:
            entries = self._entries_for(section)
            has_entries = len(entries) > 0
            self.query_one(f"#{self._list_id(section)}", ListView).can_focus = has_entries
            self.query_one(f"#{remove_id}", Button).disabled = not has_entries

    def _set_fields_enabled(self, section: str, enabled: bool) -> None:
        self.query_one(f"#{section}-keycode", Input).disabled = not enabled
        self.query_one(f"#{section}-target", Input).disabled = not enabled

    def _refresh_fields(self, section: str) -> None:
        entries = self._entries_for(section)
        index = self._selected_for(section)
        if index >= len(entries):
            return
        entry = entries[index]
        self.query_one(f"#{section}-keycode", Input).value = entry.get("keycode", "") or ""
        self.query_one(f"#{section}-target", Input).value = entry.get("target", "") or ""

    def _clear_fields(self, section: str) -> None:
        self.query_one(f"#{section}-keycode", Input).value = ""
        self.query_one(f"#{section}-target", Input).value = ""

    def _enter_edit_mode(self, section: str) -> None:
        entries = self._entries_for(section)
        index = self._selected_for(section)
        if index >= len(entries):
            return
        self._editing_section = section
        self._snapshot = copy.deepcopy(entries[index])
        self._set_fields_enabled(section, True)
        self.query_one(f"#{section}-keycode", Input).focus()

    def _exit_edit_mode(self, commit: bool) -> None:
        section = self._editing_section
        if section is None:
            return
        if not commit and self._snapshot is not None:
            entries = self._entries_for(section)
            index = self._selected_for(section)
            if index < len(entries):
                entries[index] = self._snapshot
                self._refresh_fields(section)
                self._update_list_item(section)
        self._editing_section = None
        self._snapshot = None
        self._set_fields_enabled(section, False)
        self.query_one(f"#{self._list_id(section)}", ListView).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id

        if button_id == "add-pre-process":
            entries = self.config_data.setdefault("keycodes", {}).setdefault("pre_process", [])
            entries.append({"keycode": "", "target": ""})
            lv = self.query_one("#pre-process-list", ListView)
            lv.append(ListItem(Static(self._entry_text(entries[-1]))))
            self._selected_pre_process = len(entries) - 1
            self._refresh_fields("pre-process")
            lv.index = self._selected_pre_process
            self._update_list_states()
            self._enter_edit_mode("pre-process")

        elif button_id == "remove-pre-process":
            entries = self._entries_for("pre-process")
            if not entries or self._selected_pre_process >= len(entries):
                return
            entries.pop(self._selected_pre_process)
            self._rebuild_pre_process_list()
            if entries:
                self._selected_pre_process = min(self._selected_pre_process, len(entries) - 1)
                self._refresh_fields("pre-process")
                self.query_one("#pre-process-list", ListView).index = self._selected_pre_process
            else:
                self._selected_pre_process = 0
                self._clear_fields("pre-process")
            self._update_list_states()

        elif button_id == "add-override":
            entries = self.config_data.setdefault("keycodes", {}).setdefault("overrides", [])
            entries.append({"keycode": "", "target": ""})
            lv = self.query_one("#overrides-list", ListView)
            lv.append(ListItem(Static(self._entry_text(entries[-1]))))
            self._selected_override = len(entries) - 1
            self._refresh_fields("override")
            lv.index = self._selected_override
            self._update_list_states()
            self._enter_edit_mode("override")

        elif button_id == "remove-override":
            entries = self._entries_for("override")
            if not entries or self._selected_override >= len(entries):
                return
            entries.pop(self._selected_override)
            self._rebuild_overrides_list()
            if entries:
                self._selected_override = min(self._selected_override, len(entries) - 1)
                self._refresh_fields("override")
                self.query_one("#overrides-list", ListView).index = self._selected_override
            else:
                self._selected_override = 0
                self._clear_fields("override")
            self._update_list_states()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Enter pressed on a list item — enter edit mode."""
        if event.list_view.id == "pre-process-list":
            index = event.list_view.index
            if index is not None:
                self._selected_pre_process = index
                self._refresh_fields("pre-process")
                self._enter_edit_mode("pre-process")
        elif event.list_view.id == "overrides-list":
            index = event.list_view.index
            if index is not None:
                self._selected_override = index
                self._refresh_fields("override")
                self._enter_edit_mode("override")

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.list_view.id == "pre-process-list":
            index = event.list_view.index
            if index is not None:
                self._selected_pre_process = index
                self._refresh_fields("pre-process")
        elif event.list_view.id == "overrides-list":
            index = event.list_view.index
            if index is not None:
                self._selected_override = index
                self._refresh_fields("override")

    def on_key(self, event) -> None:
        """Handle Enter/Escape in edit mode."""
        if self._editing_section is None:
            return
        if event.key == "enter":
            event.prevent_default()
            event.stop()
            self._exit_edit_mode(commit=True)
        elif event.key == "escape":
            event.prevent_default()
            event.stop()
            self._exit_edit_mode(commit=False)

    def on_input_changed(self, event: Input.Changed) -> None:
        input_id = event.input.id or ""

        if input_id.startswith("pre-process-"):
            field = input_id[len("pre-process-"):]
            entries = self._entries_for("pre-process")
            if self._selected_pre_process < len(entries):
                entries[self._selected_pre_process][field] = event.value
                self._update_list_item("pre-process")

        elif input_id.startswith("override-"):
            field = input_id[len("override-"):]
            entries = self._entries_for("override")
            if self._selected_override < len(entries):
                entries[self._selected_override][field] = event.value
                self._update_list_item("override")
