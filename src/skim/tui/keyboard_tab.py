# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Keyboard tab widget for the skim TUI configuration editor."""

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
        width: 30;
        min-width: 20;
        height: 100%;
    }
    KeyboardTab #layer-list {
        max-height: 100%;
        border: solid $accent 50%;
    }
    KeyboardTab .list-buttons {
        dock: bottom;
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

            with VerticalScroll(id="layer-detail"):
                yield Static("Select a layer to edit", id="layer-detail-hint")
                with Horizontal(classes="field-row"):
                    yield Label("Label:", classes="field-label")
                    yield Input(value="", id="layer-label", placeholder="e.g. BASE")
                with Horizontal(classes="field-row"):
                    yield Label("Name:", classes="field-label")
                    yield Input(value="", id="layer-name", placeholder="e.g. Letters")
                with Horizontal(classes="field-row"):
                    yield Label("ID:", classes="field-label")
                    yield Input(value="", id="layer-id", placeholder="e.g. _BASE (optional)")
                with Horizontal(classes="field-row"):
                    yield Label("Subtitle:", classes="field-label")
                    yield Input(value="", id="layer-subtitle", placeholder="e.g. COLEMAK (optional)")

    def on_mount(self) -> None:
        """Populate the list after mount."""
        self._rebuild_list()
        if self.config_data.get("keyboard", {}).get("layers", []):
            self._selected_layer = 0
            self._refresh_detail_fields()

    def _rebuild_list(self) -> None:
        """Rebuild the ListView from config data."""
        layers = self.config_data.get("keyboard", {}).get("layers", [])
        list_view = self.query_one("#layer-list", ListView)
        list_view.clear()
        for i, layer in enumerate(layers):
            label = layer.get("label", str(i))
            name = layer.get("name", "")
            list_view.append(ListItem(Static(f"{i}: {label} - {name}"), id=f"layer-item-{i}"))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle Add/Remove button presses."""
        if event.button.id == "add-layer":
            layers = self.config_data.setdefault("keyboard", {}).setdefault("layers", [])
            idx = len(layers)
            layers.append({"label": f"L{idx}", "name": f"Layer {idx}", "id": None, "subtitle": None})
            self._rebuild_list()
            self._selected_layer = idx
            self._refresh_detail_fields()
            # Focus the list on the new item
            list_view = self.query_one("#layer-list", ListView)
            list_view.index = idx

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

    def on_switch_changed(self, event: Switch.Changed) -> None:
        """Handle Switch.Changed events."""
        if event.switch.id == "double-south":
            self.config_data.setdefault("keyboard", {}).setdefault("features", {})
            self.config_data["keyboard"]["features"]["double_south"] = event.value

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Handle layer selection in the list."""
        if event.list_view.id != "layer-list":
            return
        if event.item is None:
            return
        item_id = event.item.id or ""
        if item_id.startswith("layer-item-"):
            try:
                index = int(item_id[len("layer-item-"):])
            except ValueError:
                return
            self._selected_layer = index
            self._refresh_detail_fields()

    def _refresh_detail_fields(self) -> None:
        """Update Input fields to reflect the currently selected layer."""
        layers = self.config_data.get("keyboard", {}).get("layers", [])
        if self._selected_layer >= len(layers):
            return
        layer = layers[self._selected_layer]
        self.query_one("#layer-label", Input).value = layer.get("label", "") or ""
        self.query_one("#layer-name", Input).value = layer.get("name", "") or ""
        self.query_one("#layer-id", Input).value = layer.get("id", "") or ""
        self.query_one("#layer-subtitle", Input).value = layer.get("subtitle", "") or ""

    def _clear_detail_fields(self) -> None:
        """Clear all detail Input fields."""
        self.query_one("#layer-label", Input).value = ""
        self.query_one("#layer-name", Input).value = ""
        self.query_one("#layer-id", Input).value = ""
        self.query_one("#layer-subtitle", Input).value = ""

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle Input.Changed events for layer fields."""
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
