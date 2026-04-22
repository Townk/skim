# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Keyboard tab widget for the skim TUI configuration editor."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import Input, Label, ListItem, ListView, Static, Switch


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
    KeyboardTab #layer-list {
        width: 30;
        min-width: 20;
        max-height: 100%;
        border: solid $accent 50%;
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

        layers = self.config_data.get("keyboard", {}).get("layers", [])

        with Vertical(id="features-section"):
            yield Static("Features", classes="section-title")
            with Horizontal(id="features-row"):
                yield Label("Double South: ", classes="field-label")
                yield Switch(value=double_south, id="double-south")

        with Horizontal(id="layers-section"):
            list_items = []
            for i, layer in enumerate(layers):
                label = layer.get("label", str(i))
                name = layer.get("name", "")
                list_items.append(ListItem(Static(f"{i}: {label} - {name}"), id=f"layer-item-{i}"))
            yield ListView(*list_items, id="layer-list")

            with VerticalScroll(id="layer-detail"):
                yield Static("Layer Detail", classes="section-title")
                first_layer = layers[0] if layers else {}
                with Horizontal(classes="field-row"):
                    yield Label("Label:", classes="field-label")
                    yield Input(
                        value=first_layer.get("label", "") or "",
                        id="layer-label",
                        placeholder="e.g. BASE",
                    )
                with Horizontal(classes="field-row"):
                    yield Label("Name:", classes="field-label")
                    yield Input(
                        value=first_layer.get("name", "") or "",
                        id="layer-name",
                        placeholder="e.g. Letters",
                    )
                with Horizontal(classes="field-row"):
                    yield Label("ID:", classes="field-label")
                    yield Input(
                        value=first_layer.get("id", "") or "",
                        id="layer-id",
                        placeholder="e.g. _BASE (optional)",
                    )
                with Horizontal(classes="field-row"):
                    yield Label("Subtitle:", classes="field-label")
                    yield Input(
                        value=first_layer.get("subtitle", "") or "",
                        id="layer-subtitle",
                        placeholder="e.g. COLEMAK (optional)",
                    )

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

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle Input.Changed events for layer fields."""
        input_id = event.input.id
        if input_id not in _FIELD_MAP:
            return
        config_key = _FIELD_MAP[input_id]
        layers = self.config_data.get("keyboard", {}).get("layers", [])
        if self._selected_layer >= len(layers):
            return
        # Empty string maps to None for optional fields (id, subtitle)
        value: str | None = event.value
        if config_key in ("id", "subtitle") and value == "":
            value = None
        layers[self._selected_layer][config_key] = value
