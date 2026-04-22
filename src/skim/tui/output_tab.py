# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Output tab widget for the skim TUI configuration editor."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import Input, Label, ListItem, ListView, Select, Static, Switch


_HOLD_SYMBOL_OPTIONS = [
    ("Outward", "outward"),
    ("Inward", "inward"),
    ("QMK", "qmk"),
]

_PALETTE_FIELD_MAP = {
    "palette-neutral-color": "neutral_color",
    "palette-text-color": "text_color",
    "palette-key-label-color": "key_label_color",
    "palette-background-color": "background_color",
    "palette-border-color": "border_color",
}


class OutputTab(Widget):
    """Output configuration tab.

    Has sections for layout, style, palette, layer colors, and copyright.
    """

    DEFAULT_CSS = """
    OutputTab {
        height: 1fr;
    }
    OutputTab .section {
        height: auto;
        padding: 1 2;
        border-bottom: solid $accent 30%;
    }
    OutputTab .field-row {
        height: auto;
        margin-bottom: 1;
    }
    OutputTab .field-label {
        width: 20;
        padding-top: 1;
    }
    OutputTab #layer-colors-list {
        width: 35;
        min-width: 20;
        border: solid $accent;
        height: 10;
    }
    OutputTab #layer-color-detail {
        padding: 0 2;
        height: auto;
    }
    OutputTab #layer-colors-container {
        height: auto;
    }
    """

    def __init__(self, config_data: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.config_data = config_data
        self._selected_layer_color: int = 0

    def compose(self) -> ComposeResult:
        output = self.config_data.get("output", {})
        layout = output.get("layout", {})
        spacing = layout.get("spacing", {})
        style = output.get("style", {})
        palette = style.get("palette", {})
        border = style.get("border")  # may be None or dict
        layer_colors = palette.get("layers", [])
        copyright_text = output.get("copyright") or ""

        hold_position = style.get("hold_symbol_position", "outward")

        with VerticalScroll():
            # --- Layout section ---
            with Vertical(classes="section"):
                yield Static("Layout", classes="section-title")
                with Horizontal(classes="field-row"):
                    yield Label("Width:", classes="field-label")
                    yield Input(
                        value=str(layout.get("width", 800.0)),
                        id="layout-width",
                        placeholder="800.0",
                    )
                with Horizontal(classes="field-row"):
                    yield Label("Margin:", classes="field-label")
                    yield Input(
                        value=str(spacing.get("margin", 0.0)),
                        id="layout-margin",
                        placeholder="0.0",
                    )
                with Horizontal(classes="field-row"):
                    yield Label("Inset:", classes="field-label")
                    yield Input(
                        value=str(spacing.get("inset", 20.0)),
                        id="layout-inset",
                        placeholder="20.0",
                    )

            # --- Style section ---
            with Vertical(classes="section"):
                yield Static("Style", classes="section-title")
                with Horizontal(classes="field-row"):
                    yield Label("Use layer colors on keys:", classes="field-label")
                    yield Switch(
                        value=style.get("use_layer_colors_on_keys", True),
                        id="use-layer-colors",
                    )
                with Horizontal(classes="field-row"):
                    yield Label("Hold symbol position:", classes="field-label")
                    yield Select(
                        options=_HOLD_SYMBOL_OPTIONS,
                        value=hold_position,
                        id="hold-symbol-position",
                    )
                with Horizontal(classes="field-row"):
                    yield Label("Show layer indicators:", classes="field-label")
                    yield Switch(
                        value=style.get("show_layer_indicators", True),
                        id="show-layer-indicators",
                    )
                with Horizontal(classes="field-row"):
                    yield Label("Use system fonts:", classes="field-label")
                    yield Switch(
                        value=style.get("use_system_fonts", False),
                        id="use-system-fonts",
                    )
                with Horizontal(classes="field-row"):
                    yield Label("Border enabled:", classes="field-label")
                    yield Switch(
                        value=border is not None,
                        id="border-enabled",
                    )
                with Horizontal(classes="field-row"):
                    yield Label("Border width:", classes="field-label")
                    yield Input(
                        value=str(border.get("width", 2.0)) if border else "2.0",
                        id="border-width",
                        placeholder="2.0",
                    )
                with Horizontal(classes="field-row"):
                    yield Label("Border radius:", classes="field-label")
                    yield Input(
                        value=str(border.get("radius", 10.0)) if border else "10.0",
                        id="border-radius",
                        placeholder="10.0",
                    )

            # --- Palette section ---
            with Vertical(classes="section"):
                yield Static("Palette", classes="section-title")
                with Horizontal(classes="field-row"):
                    yield Label("Neutral color:", classes="field-label")
                    yield Input(
                        value=palette.get("neutral_color", "") or "",
                        id="palette-neutral-color",
                        placeholder="#6F768B",
                    )
                with Horizontal(classes="field-row"):
                    yield Label("Text color:", classes="field-label")
                    yield Input(
                        value=palette.get("text_color", "") or "",
                        id="palette-text-color",
                        placeholder="black",
                    )
                with Horizontal(classes="field-row"):
                    yield Label("Key label color:", classes="field-label")
                    yield Input(
                        value=palette.get("key_label_color", "") or "",
                        id="palette-key-label-color",
                        placeholder="white",
                    )
                with Horizontal(classes="field-row"):
                    yield Label("Background color:", classes="field-label")
                    yield Input(
                        value=palette.get("background_color", "") or "",
                        id="palette-background-color",
                        placeholder="white",
                    )
                with Horizontal(classes="field-row"):
                    yield Label("Border color:", classes="field-label")
                    yield Input(
                        value=palette.get("border_color", "") or "",
                        id="palette-border-color",
                        placeholder="black",
                    )

            # --- Layer colors section ---
            with Vertical(classes="section"):
                yield Static("Layer Colors", classes="section-title")
                with Horizontal(id="layer-colors-container"):
                    lc_items = []
                    for i, lc in enumerate(layer_colors):
                        color = lc.get("base_color", "")
                        lc_items.append(
                            ListItem(Static(f"Layer {i}: {color}"), id=f"lc-item-{i}")
                        )
                    yield ListView(*lc_items, id="layer-colors-list")

                    first_lc = layer_colors[0] if layer_colors else {}
                    with VerticalScroll(id="layer-color-detail"):
                        yield Static("Layer Color Detail", classes="section-title")
                        with Horizontal(classes="field-row"):
                            yield Label("Base color:", classes="field-label")
                            yield Input(
                                value=first_lc.get("base_color", "") or "",
                                id="lc-base-color",
                                placeholder="#RRGGBB",
                            )
                        with Horizontal(classes="field-row"):
                            yield Label("Color index:", classes="field-label")
                            yield Input(
                                value=str(first_lc.get("color_index", 0)) if first_lc else "0",
                                id="lc-color-index",
                                placeholder="0",
                            )

            # --- Copyright section ---
            with Vertical(classes="section"):
                yield Static("Copyright", classes="section-title")
                with Horizontal(classes="field-row"):
                    yield Label("Copyright text:", classes="field-label")
                    yield Input(
                        value=copyright_text,
                        id="copyright-text",
                        placeholder="e.g. © 2024 Your Name (leave empty for none)",
                    )

    def on_input_changed(self, event: Input.Changed) -> None:
        """Route input changes to the correct config path."""
        input_id = event.input.id or ""
        value = event.value

        if input_id == "layout-width":
            try:
                self.config_data["output"]["layout"]["width"] = float(value)
            except ValueError:
                pass

        elif input_id == "layout-margin":
            try:
                self.config_data["output"]["layout"]["spacing"]["margin"] = float(value)
            except ValueError:
                pass

        elif input_id == "layout-inset":
            try:
                self.config_data["output"]["layout"]["spacing"]["inset"] = float(value)
            except ValueError:
                pass

        elif input_id in _PALETTE_FIELD_MAP:
            config_key = _PALETTE_FIELD_MAP[input_id]
            self.config_data["output"]["style"]["palette"][config_key] = value

        elif input_id == "border-width":
            border = self.config_data["output"]["style"].get("border")
            if border is not None:
                try:
                    border["width"] = float(value)
                except ValueError:
                    pass

        elif input_id == "border-radius":
            border = self.config_data["output"]["style"].get("border")
            if border is not None:
                try:
                    border["radius"] = float(value)
                except ValueError:
                    pass

        elif input_id == "lc-base-color":
            layer_colors = self.config_data["output"]["style"]["palette"].get("layers", [])
            if self._selected_layer_color < len(layer_colors):
                layer_colors[self._selected_layer_color]["base_color"] = value

        elif input_id == "lc-color-index":
            layer_colors = self.config_data["output"]["style"]["palette"].get("layers", [])
            if self._selected_layer_color < len(layer_colors):
                try:
                    layer_colors[self._selected_layer_color]["color_index"] = int(value)
                except ValueError:
                    pass

        elif input_id == "copyright-text":
            self.config_data["output"]["copyright"] = value if value else None

    def on_switch_changed(self, event: Switch.Changed) -> None:
        """Route switch changes to the correct config field."""
        switch_id = event.switch.id or ""
        value = event.value

        if switch_id == "use-layer-colors":
            self.config_data["output"]["style"]["use_layer_colors_on_keys"] = value

        elif switch_id == "show-layer-indicators":
            self.config_data["output"]["style"]["show_layer_indicators"] = value

        elif switch_id == "use-system-fonts":
            self.config_data["output"]["style"]["use_system_fonts"] = value

        elif switch_id == "border-enabled":
            if value:
                # Enable border with defaults if it was None
                current = self.config_data["output"]["style"].get("border")
                if current is None:
                    self.config_data["output"]["style"]["border"] = {"width": 2.0, "radius": 10.0}
            else:
                self.config_data["output"]["style"]["border"] = None

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle hold_symbol_position select changes."""
        if event.select.id == "hold-symbol-position":
            if event.value is not Select.BLANK:
                self.config_data["output"]["style"]["hold_symbol_position"] = str(event.value)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Handle layer color selection in the list."""
        if event.list_view.id != "layer-colors-list":
            return
        if event.item is None:
            return
        item_id = event.item.id or ""
        if item_id.startswith("lc-item-"):
            try:
                index = int(item_id[len("lc-item-"):])
            except ValueError:
                return
            self._selected_layer_color = index
            self._refresh_layer_color_fields()

    def _refresh_layer_color_fields(self) -> None:
        """Update layer color Input fields to reflect the current selection."""
        layer_colors = self.config_data["output"]["style"]["palette"].get("layers", [])
        if self._selected_layer_color >= len(layer_colors):
            return
        lc = layer_colors[self._selected_layer_color]
        self.query_one("#lc-base-color", Input).value = lc.get("base_color", "") or ""
        self.query_one("#lc-color-index", Input).value = str(lc.get("color_index", 0))
