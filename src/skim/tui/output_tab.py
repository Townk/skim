# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Output tab widget for the skim TUI configuration editor."""

import copy
from typing import Any

import webcolors
from textual.app import ComposeResult
from textual.content import Content
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.events import DescendantBlur
from textual.suggester import SuggestFromList
from textual.widget import Widget
from textual.widgets import Button, Input, Label, ListItem, ListView, Select, Static, Switch
from textual_autocomplete import AutoComplete, DropdownItem, TargetState

from skim.application.render.styling import default_layer_color
from skim.tui.app import LayerAdded, LayerRemoved

_COLOR_NAMES = sorted(webcolors.names())


_MAX_COLOR_NAME_LEN = max(len(n) for n in _COLOR_NAMES)
_COLOR_SUGGESTER = SuggestFromList(_COLOR_NAMES, case_sensitive=False)


def _color_candidates(state: TargetState) -> list[DropdownItem]:
    """Return color candidates with a right-aligned colored swatch."""
    items = []
    for name in _COLOR_NAMES:
        hex_color = webcolors.name_to_hex(name)
        label = Content.assemble(
            name,
            " " * (_MAX_COLOR_NAME_LEN - len(name) + 1),
            Content.styled("\uebb4", hex_color),
        )
        items.append(DropdownItem(main=label))
    return items


class ColorAutoComplete(AutoComplete):
    """AutoComplete that re-posts Input.Changed after dropdown selection.

    The base AutoComplete suppresses Input.Changed during completion
    via ``self.prevent(Input.Changed)``. This subclass re-fires the
    event so that parent widgets (e.g. swatch updates) react to the
    new value.
    """

    def should_show_dropdown(self, search_string: str) -> bool:
        option_list = self.option_list
        if option_list.option_count <= 1:
            return False
        return super().should_show_dropdown(search_string)

    def apply_completion(self, value: str, state: TargetState) -> None:
        # value is the full plain text (name + padding + swatch);
        # extract just the color name (first word)
        color_name = value.split()[0] if value.strip() else value
        super().apply_completion(color_name, state)

    def post_completion(self) -> None:
        super().post_completion()
        self.target.post_message(Input.Changed(self.target, self.target.value))


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
        border: solid $accent 30%;
    }
    OutputTab #layer-color-detail:focus-within {
        border: solid $accent;
    }
    OutputTab #layer-colors-container {
        height: auto;
    }
    OutputTab .color-swatch {
        width: 4;
        height: 1;
        margin: 1 1 0 0;
        content-align: center middle;
    }
    OutputTab .swatch-spacer {
        width: 4;
        height: 1;
        margin: 1 1 0 0;
    }
    OutputTab .lc-swatch {
        width: 4;
        height: 1;
        dock: right;
        margin: 0 0 0 1;
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
        hold_position = style.get("hold_symbol_position", "outward")

        with VerticalScroll(can_focus=False):
            # --- Layout section ---
            with Vertical(classes="section"):
                yield Static("Layout", classes="section-title section-title-first")
                with Horizontal(classes="field-row"):
                    yield Label("Width:", classes="field-label")
                    yield Static(" ", classes="swatch-spacer")
                    yield Input(
                        value=str(layout.get("width", 800.0)),
                        id="layout-width",
                        placeholder="800.0",
                    )
                with Horizontal(classes="field-row"):
                    yield Label("Margin:", classes="field-label")
                    yield Static(" ", classes="swatch-spacer")
                    yield Input(
                        value=str(spacing.get("margin", 0.0)),
                        id="layout-margin",
                        placeholder="0.0",
                    )
                with Horizontal(classes="field-row"):
                    yield Label("Inset:", classes="field-label")
                    yield Static(" ", classes="swatch-spacer")
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
                    yield Static(" ", classes="swatch-spacer")
                    yield Switch(
                        value=style.get("use_layer_colors_on_keys", True),
                        id="use-layer-colors",
                    )
                with Horizontal(classes="field-row"):
                    yield Label("Hold symbol position:", classes="field-label")
                    yield Static(" ", classes="swatch-spacer")
                    yield Select(
                        options=_HOLD_SYMBOL_OPTIONS,
                        value=hold_position,
                        id="hold-symbol-position",
                    )
                with Horizontal(classes="field-row"):
                    yield Label("Show layer indicators:", classes="field-label")
                    yield Static(" ", classes="swatch-spacer")
                    yield Switch(
                        value=style.get("show_layer_indicators", True),
                        id="show-layer-indicators",
                    )
                with Horizontal(classes="field-row"):
                    yield Label("Use system fonts:", classes="field-label")
                    yield Static(" ", classes="swatch-spacer")
                    yield Switch(
                        value=style.get("use_system_fonts", False),
                        id="use-system-fonts",
                    )
                with Horizontal(classes="field-row"):
                    yield Label("Border enabled:", classes="field-label")
                    yield Static(" ", classes="swatch-spacer")
                    yield Switch(
                        value=border is not None,
                        id="border-enabled",
                    )
                with Horizontal(classes="field-row"):
                    yield Label("Border width:", classes="field-label")
                    yield Static(" ", classes="swatch-spacer")
                    yield Input(
                        value=str(border.get("width", 2.0)) if border else "2.0",
                        id="border-width",
                        placeholder="2.0",
                    )
                with Horizontal(classes="field-row"):
                    yield Label("Border radius:", classes="field-label")
                    yield Static(" ", classes="swatch-spacer")
                    yield Input(
                        value=str(border.get("radius", 10.0)) if border else "10.0",
                        id="border-radius",
                        placeholder="10.0",
                    )

            # --- Palette section ---
            with Vertical(classes="section"):
                yield Static("Palette", classes="section-title")
                for color_label, field_id, config_key, placeholder in [
                    ("Neutral color:", "palette-neutral-color", "neutral_color", "#6F768B"),
                    ("Text color:", "palette-text-color", "text_color", "black"),
                    ("Key label color:", "palette-key-label-color", "key_label_color", "white"),
                    ("Background color:", "palette-background-color", "background_color", "white"),
                    ("Border color:", "palette-border-color", "border_color", "black"),
                ]:
                    color_val = palette.get(config_key, "") or ""
                    with Horizontal(classes="field-row"):
                        yield Label(color_label, classes="field-label")
                        yield Static(" ", classes="color-swatch", id=f"swatch-{field_id}")
                        color_input = Input(
                            value=color_val, id=field_id,
                            placeholder=placeholder,
                            suggester=_COLOR_SUGGESTER,
                        )
                        yield color_input
                    yield ColorAutoComplete(color_input, candidates=_color_candidates)

            # --- Layer colors section ---
            with Vertical(classes="section"):
                yield Static("Layer Colors", classes="section-title")
                with Horizontal(id="layer-colors-container"):
                    with Vertical(classes="lc-list-col"):
                        yield ListView(id="layer-colors-list")
                        with Horizontal(classes="list-buttons"):
                            yield Button("+ Add (a)", id="add-layer-color", variant="success")
                            yield Button("- Delete (d)", id="remove-layer-color", variant="error")

                    with VerticalScroll(id="layer-color-detail", can_focus=False):
                        with Horizontal(classes="field-row"):
                            yield Label("Base color:", classes="field-label")
                            yield Static(" ", classes="color-swatch", id="swatch-lc-base-color")
                            lc_color_input = Input(
                                value="", id="lc-base-color",
                                placeholder="#RRGGBB", disabled=True,
                                suggester=_COLOR_SUGGESTER,
                            )
                            yield lc_color_input
                        yield ColorAutoComplete(lc_color_input, candidates=_color_candidates)
                        with Horizontal(classes="field-row"):
                            yield Label("Color index:", classes="field-label")
                            yield Static(" ", classes="swatch-spacer")
                            yield Input(
                                value="", id="lc-color-index",
                                placeholder="2", disabled=True,
                            )


    def on_mount(self) -> None:
        self._rebuild_layer_colors_list()
        layer_colors = self._layer_colors()
        if layer_colors:
            self._selected_layer_color = 0
            self._refresh_lc_fields()
        self._update_lc_list_state()
        self._update_all_palette_swatches()

    def _update_swatch(self, swatch_id: str, color: str) -> None:
        """Update a color swatch's background color, ignoring invalid values."""
        try:
            swatch = self.query_one(f"#{swatch_id}", Static)
            swatch.styles.background = color if color else "transparent"
        except Exception:
            pass

    @staticmethod
    def _safe_set_background(widget: Static, color: str) -> None:
        """Set background color, silently ignoring invalid values."""
        try:
            widget.styles.background = color if color else "transparent"
        except Exception:
            pass

    @staticmethod
    def _safe_set_color(widget: Static, color: str) -> None:
        """Set foreground color, silently ignoring invalid values."""
        try:
            widget.styles.color = color if color else "white"
        except Exception:
            pass

    def _update_all_palette_swatches(self) -> None:
        """Update all palette color swatches from current config values."""
        palette = self.config_data.get("output", {}).get("style", {}).get("palette", {})
        for field_id, config_key in _PALETTE_FIELD_MAP.items():
            color = palette.get(config_key, "")
            self._update_swatch(f"swatch-{field_id}", color)

    def _layer_colors(self) -> list[dict[str, Any]]:
        return self.config_data.get("output", {}).get("style", {}).get("palette", {}).get("layers", [])

    def _layer_name(self, index: int) -> str:
        layers = self.config_data.get("keyboard", {}).get("layers", [])
        if index < len(layers):
            return layers[index].get("name", "")
        return ""

    def _layer_qmk_index(self, index: int) -> int:
        layers = self.config_data.get("keyboard", {}).get("layers", [])
        if index < len(layers):
            return layers[index].get("index", index)
        return index

    def _lc_column_widths(self) -> tuple[int, int]:
        layer_colors = self._layer_colors()
        col0_w = 0
        col1_w = 0
        for i, lc in enumerate(layer_colors):
            name = self._layer_name(i)
            qmk_idx = self._layer_qmk_index(i)
            col0 = f"{name} ({qmk_idx})" if name else f"({qmk_idx})"
            col0_w = max(col0_w, len(col0))
            col1_w = max(col1_w, len(lc.get("base_color", "")))
        return col0_w, col1_w

    def _lc_text(self, index: int, lc: dict[str, Any], col0_w: int, col1_w: int) -> str:
        name = self._layer_name(index)
        qmk_idx = self._layer_qmk_index(index)
        col0 = f"{name} ({qmk_idx})" if name else f"({qmk_idx})"
        color = lc.get("base_color", "")
        return f"{col0:<{col0_w}}  {color:<{col1_w}}"

    def _make_lc_list_item(self, index: int, lc: dict[str, Any], col0_w: int, col1_w: int) -> ListItem:
        """Create a ListItem with text and a color swatch for a layer color."""
        color = lc.get("base_color", "")
        swatch = Static("\uebb4", classes="lc-swatch")
        self._safe_set_color(swatch, color)
        return ListItem(Static(self._lc_text(index, lc, col0_w, col1_w)), swatch)

    def _rebuild_layer_colors_list(self) -> None:
        layer_colors = self._layer_colors()
        col0_w, col1_w = self._lc_column_widths()
        list_view = self.query_one("#layer-colors-list", ListView)
        list_view.clear()
        for i, lc in enumerate(layer_colors):
            list_view.append(self._make_lc_list_item(i, lc, col0_w, col1_w))

    def _update_all_lc_list_items(self) -> None:
        """Update the text of all layer color list items in place (no clear/re-append)."""
        layer_colors = self._layer_colors()
        col0_w, col1_w = self._lc_column_widths()
        list_view = self.query_one("#layer-colors-list", ListView)
        for i, item in enumerate(list_view.children):
            if i < len(layer_colors):
                lc = layer_colors[i]
                item.query_one(Static).update(self._lc_text(i, lc, col0_w, col1_w))
                for s in item.query(".lc-swatch"):
                    self._safe_set_color(s, lc.get("base_color", ""))

    def _update_lc_list_item(self) -> None:
        layer_colors = self._layer_colors()
        if self._selected_layer_color >= len(layer_colors):
            return
        col0_w, col1_w = self._lc_column_widths()
        list_view = self.query_one("#layer-colors-list", ListView)
        if self._selected_layer_color < len(list_view.children):
            item = list_view.children[self._selected_layer_color]
            item.query_one(Static).update(
                self._lc_text(self._selected_layer_color, layer_colors[self._selected_layer_color], col0_w, col1_w)
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
        color = lc.get("base_color", "") or ""
        self.query_one("#lc-base-color", Input).value = color
        self.query_one("#lc-color-index", Input).value = str(lc.get("color_index", 0))
        self._update_swatch("swatch-lc-base-color", color)

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
        self._editing_lc = False
        self._lc_snapshot = None
        self._set_lc_fields_enabled(False)
        self._update_all_lc_list_items()
        lv = self.query_one("#layer-colors-list", ListView)
        lv.index = self._selected_layer_color
        lv.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id

        if button_id == "add-layer-color":
            layer_colors = self.config_data["output"]["style"]["palette"].setdefault("layers", [])
            new_index = len(layer_colors)
            new_lc = {"base_color": default_layer_color(new_index), "color_index": 2, "gradient": None}
            layer_colors.append(new_lc)
            self._rebuild_layer_colors_list()
            lv = self.query_one("#layer-colors-list", ListView)
            self._selected_layer_color = len(layer_colors) - 1
            self._refresh_lc_fields()
            lv.index = self._selected_layer_color
            self._update_lc_list_state()
            self.post_message(LayerAdded(new_index, "style"))
            self._enter_lc_edit_mode()

        elif button_id == "remove-layer-color":
            layer_colors = self._layer_colors()
            if not layer_colors or self._selected_layer_color >= len(layer_colors):
                return
            removed_index = self._selected_layer_color
            layer_colors.pop(removed_index)
            self._rebuild_layer_colors_list()
            if layer_colors:
                self._selected_layer_color = min(self._selected_layer_color, len(layer_colors) - 1)
                self._refresh_lc_fields()
                lv = self.query_one("#layer-colors-list", ListView)
                self.call_after_refresh(setattr, lv, "index", self._selected_layer_color)
            else:
                self._selected_layer_color = 0
                self._clear_lc_fields()
            self._update_lc_list_state()
            self.post_message(LayerRemoved(removed_index, "style"))
            if not layer_colors:
                self.query_one("#add-layer-color", Button).focus()

    def sync_layer_added(self, index: int) -> None:
        """Called when a layer is added in the Keyboard tab — add matching layer color."""
        layer_colors = self.config_data["output"]["style"]["palette"].setdefault("layers", [])
        new_lc = {"base_color": default_layer_color(index), "color_index": 2, "gradient": None}
        layer_colors.insert(index, new_lc)
        self._rebuild_layer_colors_list()
        self._selected_layer_color = index
        self._refresh_lc_fields()
        self._update_lc_list_state()

    def sync_layer_removed(self, index: int) -> None:
        """Called when a layer is removed in the Keyboard tab — remove matching layer color."""
        layer_colors = self._layer_colors()
        if index >= len(layer_colors):
            return
        layer_colors.pop(index)
        self._rebuild_layer_colors_list()
        if layer_colors:
            self._selected_layer_color = min(self._selected_layer_color, len(layer_colors) - 1)
            self._refresh_lc_fields()
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
        """Handle Enter/Escape in edit mode, a/d shortcuts on list."""
        if self._editing_lc:
            if event.key == "enter":
                event.prevent_default()
                event.stop()
                self._exit_lc_edit_mode(commit=True)
            elif event.key == "escape":
                event.prevent_default()
                event.stop()
                self._exit_lc_edit_mode(commit=False)
            return

        focused = self.app.focused
        if isinstance(focused, ListView) and focused.id == "layer-colors-list":
            if event.key == "a":
                event.prevent_default()
                event.stop()
                self.query_one("#add-layer-color", Button).press()
            elif event.key == "d":
                event.prevent_default()
                event.stop()
                self.query_one("#remove-layer-color", Button).press()

    _LC_FIELD_IDS = {"lc-base-color", "lc-color-index"}

    def on_descendant_blur(self, event: DescendantBlur) -> None:
        """Commit edit when focus leaves the editing pane."""
        if not self._editing_lc:
            return
        self.set_timer(0.05, self._check_focus_commit)

    def _check_focus_commit(self) -> None:
        if not self._editing_lc:
            return
        focused = self.app.focused
        if focused is None or not isinstance(focused, Input) or focused.id not in self._LC_FIELD_IDS:
            self._exit_lc_edit_mode(commit=True)

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
            self._update_swatch(f"swatch-{input_id}", value)

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
                self._update_swatch("swatch-lc-base-color", value)
                # Also update the swatch in the list item
                list_view = self.query_one("#layer-colors-list", ListView)
                if self._selected_layer_color < len(list_view.children):
                    item = list_view.children[self._selected_layer_color]
                    for s in item.query(".lc-swatch"):
                        self._safe_set_color(s, value)

        elif input_id == "lc-color-index":
            layer_colors = self._layer_colors()
            if self._selected_layer_color < len(layer_colors):
                try:
                    layer_colors[self._selected_layer_color]["color_index"] = int(value)
                except ValueError:
                    pass

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
