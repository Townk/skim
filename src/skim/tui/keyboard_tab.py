# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Keyboard tab widget for the skim TUI configuration editor."""

import copy
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import Button, Input, Label, ListItem, ListView, Static, Switch


_FIELD_MAP = {
    "layer-label": "label",
    "layer-name": "name",
    "layer-id": "id",
    "layer-subtitle": "subtitle",
}


class KeyboardTab(Widget):
    """Keyboard configuration tab.

    Shows a Features section (with double_south toggle) and a Layers section
    with a list/detail split for editing individual layer metadata.

    Detail fields are read-only until the user presses Enter on a list item.
    Enter in a field commits changes, Escape rolls them back.
    """

    DEFAULT_CSS = """
    KeyboardTab {
        height: 1fr;
        padding: 0 1;
    }
    KeyboardTab #features-section {
        height: auto;
    }
    KeyboardTab #features-row {
        height: auto;
    }
    KeyboardTab #layers-section {
        height: 1fr;
    }
    KeyboardTab .list-col {
        width: 35;
        min-width: 25;
        height: 100%;
    }
    KeyboardTab #layer-list {
        max-height: 100%;
        border: solid $accent 50%;
    }
    KeyboardTab .list-buttons {
        dock: bottom;
        height: auto;
        width: 41;
    }
    KeyboardTab .list-buttons Button {
        width: 1fr;
    }
    KeyboardTab #layer-detail {
        padding: 0 1;
        height: auto;
        overflow-x: hidden;
    }
    """

    def __init__(self, config_data: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.config_data = config_data
        self._selected_layer: int = 0
        self._editing: bool = False
        self._snapshot: dict[str, Any] | None = None

    def compose(self) -> ComposeResult:
        features = self.config_data.get("keyboard", {}).get("features", {})
        double_south = features.get("double_south", False)

        with Vertical(id="features-section"):
            yield Static("Features", classes="section-title")
            with Horizontal(id="features-row"):
                yield Label("Double South: ", classes="field-label")
                yield Switch(value=double_south, id="double-south")

        yield Static("Layers", classes="section-title")
        with Horizontal(id="layers-section"):
            with Vertical(classes="list-col"):
                yield ListView(id="layer-list")
                with Horizontal(classes="list-buttons"):
                    yield Button("+ Add", id="add-layer", variant="success")
                    yield Button("- Remove", id="remove-layer", variant="error")

            with VerticalScroll(id="layer-detail", can_focus=False):
                yield Static("Press Enter on a layer to edit", id="layer-detail-hint")
                with Horizontal(classes="field-row"):
                    yield Label("Label:", classes="field-label")
                    yield Input(value="", id="layer-label", placeholder="e.g. BASE", disabled=True)
                with Horizontal(classes="field-row"):
                    yield Label("Name:", classes="field-label")
                    yield Input(value="", id="layer-name", placeholder="e.g. Letters", disabled=True)
                with Horizontal(classes="field-row"):
                    yield Label("ID:", classes="field-label")
                    yield Input(value="", id="layer-id", placeholder="e.g. _BASE (optional)", disabled=True)
                with Horizontal(classes="field-row"):
                    yield Label("Subtitle:", classes="field-label")
                    yield Input(
                        value="", id="layer-subtitle", placeholder="e.g. COLEMAK (optional)", disabled=True
                    )

    def on_mount(self) -> None:
        """Populate the list after mount."""
        self._rebuild_list()
        if self.config_data.get("keyboard", {}).get("layers", []):
            self._selected_layer = 0
            self._refresh_detail_fields()
        self._update_list_state()

    def _layer_text(self, index: int, layer: dict[str, Any]) -> str:
        label = layer.get("label", str(index))
        name = layer.get("name", "")
        return f"{index}: {label} - {name}"

    def _rebuild_list(self) -> None:
        layers = self.config_data.get("keyboard", {}).get("layers", [])
        list_view = self.query_one("#layer-list", ListView)
        list_view.clear()
        for i, layer in enumerate(layers):
            list_view.append(ListItem(Static(self._layer_text(i, layer))))

    def _update_selected_list_item(self) -> None:
        layers = self.config_data.get("keyboard", {}).get("layers", [])
        if self._selected_layer >= len(layers):
            return
        list_view = self.query_one("#layer-list", ListView)
        if self._selected_layer < len(list_view.children):
            item = list_view.children[self._selected_layer]
            static = item.query_one(Static)
            static.update(self._layer_text(self._selected_layer, layers[self._selected_layer]))

    def _update_list_state(self) -> None:
        """Update list focusability and Remove button state based on layer count."""
        layers = self.config_data.get("keyboard", {}).get("layers", [])
        has_layers = len(layers) > 0
        self.query_one("#layer-list", ListView).can_focus = has_layers
        self.query_one("#remove-layer", Button).disabled = not has_layers

    def _set_fields_enabled(self, enabled: bool) -> None:
        """Enable or disable all detail Input fields."""
        for field_id in _FIELD_MAP:
            self.query_one(f"#{field_id}", Input).disabled = not enabled

    def _enter_edit_mode(self) -> None:
        """Enter edit mode: snapshot data, enable fields, focus first field."""
        layers = self.config_data.get("keyboard", {}).get("layers", [])
        if self._selected_layer >= len(layers):
            return
        self._editing = True
        self._snapshot = copy.deepcopy(layers[self._selected_layer])
        self._set_fields_enabled(True)
        self.query_one("#layer-label", Input).focus()

    def _exit_edit_mode(self, commit: bool) -> None:
        """Exit edit mode: commit or rollback, disable fields, focus list."""
        if not commit and self._snapshot is not None:
            layers = self.config_data.get("keyboard", {}).get("layers", [])
            if self._selected_layer < len(layers):
                layers[self._selected_layer] = self._snapshot
                self._refresh_detail_fields()
                self._update_selected_list_item()
        self._editing = False
        self._snapshot = None
        self._set_fields_enabled(False)
        self.query_one("#layer-list", ListView).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-layer":
            layers = self.config_data.setdefault("keyboard", {}).setdefault("layers", [])
            idx = len(layers)
            new_layer = {"label": f"L{idx}", "name": f"Layer {idx}", "id": None, "subtitle": None}
            layers.append(new_layer)
            list_view = self.query_one("#layer-list", ListView)
            list_view.append(ListItem(Static(self._layer_text(idx, new_layer))))
            self._selected_layer = idx
            self._refresh_detail_fields()
            list_view.index = idx
            self._update_list_state()
            # Immediately enter edit mode for the new layer
            self._enter_edit_mode()

        elif event.button.id == "remove-layer":
            layers = self.config_data.get("keyboard", {}).get("layers", [])
            if not layers or self._selected_layer >= len(layers):
                return
            layers.pop(self._selected_layer)
            self._rebuild_list()
            if layers:
                self._selected_layer = min(self._selected_layer, len(layers) - 1)
                self._refresh_detail_fields()
                list_view = self.query_one("#layer-list", ListView)
                list_view.index = self._selected_layer
            else:
                self._selected_layer = 0
                self._clear_detail_fields()
            self._update_list_state()

    def on_switch_changed(self, event: Switch.Changed) -> None:
        if event.switch.id == "double-south":
            self.config_data.setdefault("keyboard", {}).setdefault("features", {})
            self.config_data["keyboard"]["features"]["double_south"] = event.value

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Enter pressed on a list item — enter edit mode."""
        if event.list_view.id != "layer-list":
            return
        index = event.list_view.index
        if index is not None:
            self._selected_layer = index
            self._refresh_detail_fields()
            self._enter_edit_mode()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.list_view.id != "layer-list":
            return
        index = event.list_view.index
        if index is not None:
            self._selected_layer = index
            self._refresh_detail_fields()

    def on_key(self, event) -> None:
        """Handle Enter/Escape in edit mode."""
        if not self._editing:
            return
        if event.key == "enter":
            event.prevent_default()
            event.stop()
            self._exit_edit_mode(commit=True)
        elif event.key == "escape":
            event.prevent_default()
            event.stop()
            self._exit_edit_mode(commit=False)

    def _refresh_detail_fields(self) -> None:
        layers = self.config_data.get("keyboard", {}).get("layers", [])
        if self._selected_layer >= len(layers):
            return
        layer = layers[self._selected_layer]
        self.query_one("#layer-label", Input).value = layer.get("label", "") or ""
        self.query_one("#layer-name", Input).value = layer.get("name", "") or ""
        self.query_one("#layer-id", Input).value = layer.get("id", "") or ""
        self.query_one("#layer-subtitle", Input).value = layer.get("subtitle", "") or ""

    def _clear_detail_fields(self) -> None:
        self.query_one("#layer-label", Input).value = ""
        self.query_one("#layer-name", Input).value = ""
        self.query_one("#layer-id", Input).value = ""
        self.query_one("#layer-subtitle", Input).value = ""

    def on_input_changed(self, event: Input.Changed) -> None:
        input_id = event.input.id
        if input_id not in _FIELD_MAP:
            return
        config_key = _FIELD_MAP[input_id]
        layers = self.config_data.get("keyboard", {}).get("layers", [])
        if self._selected_layer >= len(layers):
            return
        value: str | None = event.value
        if config_key in ("id", "subtitle") and value == "":
            value = None
        layers[self._selected_layer][config_key] = value
        self._update_selected_list_item()
