# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Output tab widget for the skim TUI configuration editor."""

import copy
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import Button, Input, Label, ListItem, ListView, Select, Static, Switch


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
    Layer color detail fields are disabled until Enter is pressed on a list item.
    Enter in a field commits, Escape rolls back.
    """

    DEFAULT_CSS = """
    OutputTab {
        height: 1fr;
        padding: 0 1;
    }
    OutputTab .section {
        height: auto;
        border-bottom: solid $accent 20%;
    }
    OutputTab .lc-list-col {
        width: 35;
        min-width: 25;
        height: auto;
    }
    OutputTab #layer-colors-list {
        min-height: 12;
        max-height: 12;
        height: auto;
        border: solid $accent 50%;
    }
    OutputTab .list-buttons {
        height: auto;
        width: 100%;
    }
    OutputTab .list-buttons Button {
        width: 50%;
    }
    OutputTab #layer-color-detail {
        padding: 0 1;
        height: auto;
        max-height: 12;
        overflow-x: hidden;
    }
    OutputTab #layer-colors-container {
        height: auto;
    }
    """

    def __init__(self, config_data: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.config_data = config_data
        self._selected_layer_color: int = 0
        self._editing_lc: bool = False
        self._lc_snapshot: dict[str, Any] | None = None

    def compose(self) -> ComposeResult:
        output = self.config_data.get("output", {})
        layout = output.get("layout", {})
        spacing = layout.get("spacing", {})
        style = output.get("style", {})
        palette = style.get("palette", {})
        border = style.get("border")  # may be None or dict
        copyright_text = output.get("copyright") or ""

        hold_position = style.get("hold_symbol_position", "outward")

        with VerticalScroll(can_focus=False):
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
                    with Vertical(classes="lc-list-col"):
                        yield ListView(id="layer-colors-list")
                        with Horizontal(classes="list-buttons"):
                            yield Button("+ Add", id="add-layer-color", variant="success")
                            yield Button("- Remove", id="remove-layer-color", variant="error")

                    with VerticalScroll(id="layer-color-detail", can_focus=False):
                        with Horizontal(classes="field-row"):
                            yield Label("Base color:", classes="field-label")
                            yield Input(
                                value="", id="lc-base-color",
                                placeholder="#RRGGBB", disabled=True,
                            )
                        with Horizontal(classes="field-row"):
                            yield Label("Color index:", classes="field-label")
                            yield Input(
                                value="", id="lc-color-index",
                                placeholder="2", disabled=True,
                            )

            # --- Copyright section ---
            with Vertical(classes="section"):
                yield Static("Copyright", classes="section-title")
                with Horizontal(classes="field-row"):
                    yield Label("Copyright text:", classes="field-label")
                    yield Input(
                        value=copyright_text,
                        id="copyright-text",
                        placeholder="e.g. (c) 2024 Your Name (leave empty for none)",
                    )

    def on_mount(self) -> None:
        self._rebuild_layer_colors_list()
        layer_colors = self._layer_colors()
        if layer_colors:
            self._selected_layer_color = 0
            self._refresh_lc_fields()
        self._update_lc_list_state()

    def _layer_colors(self) -> list[dict[str, Any]]:
        return self.config_data.get("output", {}).get("style", {}).get("palette", {}).get("layers", [])

    @staticmethod
    def _lc_text(index: int, lc: dict[str, Any]) -> str:
        return f"Layer {index}: {lc.get('base_color', '')}"

    def _rebuild_layer_colors_list(self) -> None:
        layer_colors = self._layer_colors()
        list_view = self.query_one("#layer-colors-list", ListView)
        list_view.clear()
        for i, lc in enumerate(layer_colors):
            list_view.append(ListItem(Static(self._lc_text(i, lc))))

    def _update_lc_list_item(self) -> None:
        layer_colors = self._layer_colors()
        if self._selected_layer_color >= len(layer_colors):
            return
        list_view = self.query_one("#layer-colors-list", ListView)
        if self._selected_layer_color < len(list_view.children):
            item = list_view.children[self._selected_layer_color]
            item.query_one(Static).update(
                self._lc_text(self._selected_layer_color, layer_colors[self._selected_layer_color])
            )

    def _update_lc_list_state(self) -> None:
        has_colors = len(self._layer_colors()) > 0
        self.query_one("#layer-colors-list", ListView).can_focus = has_colors
        self.query_one("#remove-layer-color", Button).disabled = not has_colors

    def _set_lc_fields_enabled(self, enabled: bool) -> None:
        self.query_one("#lc-base-color", Input).disabled = not enabled
        self.query_one("#lc-color-index", Input).disabled = not enabled

    def _refresh_lc_fields(self) -> None:
        layer_colors = self._layer_colors()
        if self._selected_layer_color >= len(layer_colors):
            return
        lc = layer_colors[self._selected_layer_color]
        self.query_one("#lc-base-color", Input).value = lc.get("base_color", "") or ""
        self.query_one("#lc-color-index", Input).value = str(lc.get("color_index", 0))

    def _clear_lc_fields(self) -> None:
        self.query_one("#lc-base-color", Input).value = ""
        self.query_one("#lc-color-index", Input).value = ""

    def _enter_lc_edit_mode(self) -> None:
        layer_colors = self._layer_colors()
        if self._selected_layer_color >= len(layer_colors):
            return
        self._editing_lc = True
        self._lc_snapshot = copy.deepcopy(layer_colors[self._selected_layer_color])
        self._set_lc_fields_enabled(True)
        self.query_one("#lc-base-color", Input).focus()

    def _exit_lc_edit_mode(self, commit: bool) -> None:
        if not commit and self._lc_snapshot is not None:
            layer_colors = self._layer_colors()
            if self._selected_layer_color < len(layer_colors):
                layer_colors[self._selected_layer_color] = self._lc_snapshot
                self._refresh_lc_fields()
                self._update_lc_list_item()
        self._editing_lc = False
        self._lc_snapshot = None
        self._set_lc_fields_enabled(False)
        self.query_one("#layer-colors-list", ListView).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id

        if button_id == "add-layer-color":
            layer_colors = self.config_data["output"]["style"]["palette"].setdefault("layers", [])
            new_lc = {"base_color": "#6F768B", "color_index": 2, "gradient": None}
            layer_colors.append(new_lc)
            lv = self.query_one("#layer-colors-list", ListView)
            lv.append(ListItem(Static(self._lc_text(len(layer_colors) - 1, new_lc))))
            self._selected_layer_color = len(layer_colors) - 1
            self._refresh_lc_fields()
            lv.index = self._selected_layer_color
            self._update_lc_list_state()
            self._enter_lc_edit_mode()

        elif button_id == "remove-layer-color":
            layer_colors = self._layer_colors()
            if not layer_colors or self._selected_layer_color >= len(layer_colors):
                return
            layer_colors.pop(self._selected_layer_color)
            self._rebuild_layer_colors_list()
            if layer_colors:
                self._selected_layer_color = min(self._selected_layer_color, len(layer_colors) - 1)
                self._refresh_lc_fields()
                self.query_one("#layer-colors-list", ListView).index = self._selected_layer_color
            else:
                self._selected_layer_color = 0
                self._clear_lc_fields()
            self._update_lc_list_state()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Enter pressed on a layer color — enter edit mode."""
        if event.list_view.id != "layer-colors-list":
            return
        index = event.list_view.index
        if index is not None:
            self._selected_layer_color = index
            self._refresh_lc_fields()
            self._enter_lc_edit_mode()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.list_view.id != "layer-colors-list":
            return
        index = event.list_view.index
        if index is not None:
            self._selected_layer_color = index
            self._refresh_lc_fields()

    def on_key(self, event) -> None:
        """Handle Enter/Escape in layer color edit mode."""
        if not self._editing_lc:
            return
        if event.key == "enter":
            event.prevent_default()
            event.stop()
            self._exit_lc_edit_mode(commit=True)
        elif event.key == "escape":
            event.prevent_default()
            event.stop()
            self._exit_lc_edit_mode(commit=False)

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
            layer_colors = self._layer_colors()
            if self._selected_layer_color < len(layer_colors):
                layer_colors[self._selected_layer_color]["base_color"] = value
                self._update_lc_list_item()

        elif input_id == "lc-color-index":
            layer_colors = self._layer_colors()
            if self._selected_layer_color < len(layer_colors):
                try:
                    layer_colors[self._selected_layer_color]["color_index"] = int(value)
                except ValueError:
                    pass

        elif input_id == "copyright-text":
            self.config_data["output"]["copyright"] = value if value else None

    def on_switch_changed(self, event: Switch.Changed) -> None:
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
                current = self.config_data["output"]["style"].get("border")
                if current is None:
                    self.config_data["output"]["style"]["border"] = {"width": 2.0, "radius": 10.0}
            else:
                self.config_data["output"]["style"]["border"] = None

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "hold-symbol-position":
            if event.value is not Select.BLANK:
                self.config_data["output"]["style"]["hold_symbol_position"] = str(event.value)
