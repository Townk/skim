# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Keycodes tab widget for the skim TUI configuration editor."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import Input, Label, ListItem, ListView, Static


class KeycodesTab(Widget):
    """Keycodes configuration tab.

    Shows two sections — Pre-process and Overrides — each using a
    list/detail split for editing individual keycode mapping entries.
    """

    DEFAULT_CSS = """
    KeycodesTab {
        height: 1fr;
    }
    KeycodesTab .keycodes-section {
        height: 1fr;
        padding: 1 2;
    }
    KeycodesTab .keycode-list {
        width: 35;
        min-width: 20;
        border: solid $accent;
    }
    KeycodesTab .keycode-detail {
        padding: 0 2;
        height: auto;
    }
    KeycodesTab .field-row {
        height: auto;
        margin-bottom: 1;
    }
    KeycodesTab .field-label {
        width: 12;
        padding-top: 1;
    }
    """

    def __init__(self, config_data: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.config_data = config_data
        self._selected_pre_process: int = 0
        self._selected_override: int = 0

    def compose(self) -> ComposeResult:
        pre_process = self.config_data.get("keycodes", {}).get("pre_process", [])
        overrides = self.config_data.get("keycodes", {}).get("overrides", [])

        with Vertical(id="pre-process-section", classes="keycodes-section"):
            yield Static("Pre-process", classes="section-title")
            with Horizontal():
                pp_items = []
                for i, entry in enumerate(pre_process):
                    keycode = entry.get("keycode", "")
                    target = entry.get("target", "")
                    pp_items.append(
                        ListItem(Static(f"{keycode} -> {target}"), id=f"pre-process-item-{i}")
                    )
                yield ListView(*pp_items, id="pre-process-list", classes="keycode-list")

                first_pp = pre_process[0] if pre_process else {}
                with VerticalScroll(id="pre-process-detail", classes="keycode-detail"):
                    yield Static("Pre-process Detail", classes="section-title")
                    with Horizontal(classes="field-row"):
                        yield Label("Keycode:", classes="field-label")
                        yield Input(
                            value=first_pp.get("keycode", "") or "",
                            id="pre-process-keycode",
                            placeholder="e.g. LSFT(KC_TAB)",
                        )
                    with Horizontal(classes="field-row"):
                        yield Label("Target:", classes="field-label")
                        yield Input(
                            value=first_pp.get("target", "") or "",
                            id="pre-process-target",
                            placeholder="e.g. MKC_BKTAB",
                        )

        with Vertical(id="overrides-section", classes="keycodes-section"):
            yield Static("Overrides", classes="section-title")
            with Horizontal():
                ov_items = []
                for i, entry in enumerate(overrides):
                    keycode = entry.get("keycode", "")
                    target = entry.get("target", "")
                    ov_items.append(
                        ListItem(Static(f"{keycode} -> {target}"), id=f"override-item-{i}")
                    )
                yield ListView(*ov_items, id="overrides-list", classes="keycode-list")

                first_ov = overrides[0] if overrides else {}
                with VerticalScroll(id="override-detail", classes="keycode-detail"):
                    yield Static("Override Detail", classes="section-title")
                    with Horizontal(classes="field-row"):
                        yield Label("Keycode:", classes="field-label")
                        yield Input(
                            value=first_ov.get("keycode", "") or "",
                            id="override-keycode",
                            placeholder="e.g. KC_ESC",
                        )
                    with Horizontal(classes="field-row"):
                        yield Label("Target:", classes="field-label")
                        yield Input(
                            value=first_ov.get("target", "") or "",
                            id="override-target",
                            placeholder="e.g. ESC",
                        )

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Handle entry selection in the lists."""
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
        """Update pre-process Input fields to reflect the current selection."""
        entries = self.config_data.get("keycodes", {}).get("pre_process", [])
        if self._selected_pre_process >= len(entries):
            return
        entry = entries[self._selected_pre_process]
        self.query_one("#pre-process-keycode", Input).value = entry.get("keycode", "") or ""
        self.query_one("#pre-process-target", Input).value = entry.get("target", "") or ""

    def _refresh_override_fields(self) -> None:
        """Update override Input fields to reflect the current selection."""
        entries = self.config_data.get("keycodes", {}).get("overrides", [])
        if self._selected_override >= len(entries):
            return
        entry = entries[self._selected_override]
        self.query_one("#override-keycode", Input).value = entry.get("keycode", "") or ""
        self.query_one("#override-target", Input).value = entry.get("target", "") or ""

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle Input.Changed events for keycode fields."""
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
