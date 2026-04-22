# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Keyboard tab widget for the skim TUI configuration editor."""

import copy
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.events import DescendantBlur
from textual.widget import Widget
from textual.widgets import Button, Input, Label, ListItem, ListView, Static, Switch

from skim.tui.app import ErrorDialog, LayerAdded, LayerRemoved, LayerUpdated


_FIELD_MAP = {
    "layer-index": "index",
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
    KeyboardTab #info-section {
        height: auto;
    }
    KeyboardTab #features-section {
        height: auto;
    }
    KeyboardTab #features-row {
        height: auto;
    }
    KeyboardTab #layers-section {
        height: auto;
    }
    KeyboardTab .list-col {
        width: 1fr;
        max-width: 33%;
        min-width: 25;
        height: auto;
    }
    KeyboardTab #layer-list {
        height: 1fr;
        border: solid $accent 50%;
    }
    KeyboardTab .list-buttons {
        dock: bottom;
        height: auto;
        width: 100%;
    }
    KeyboardTab .list-buttons Button {
        width: 50%;
    }
    KeyboardTab #layer-detail {
        padding: 0 1;
        height: auto;
        overflow-x: hidden;
        border: solid $accent 30%;
    }
    KeyboardTab #layer-detail:focus-within {
        border: solid $accent;
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
        keymap_title = self.config_data.get("output", {}).get("keymap_title") or ""
        copyright_text = self.config_data.get("output", {}).get("copyright") or ""

        with VerticalScroll(can_focus=False):
            with Vertical(id="info-section"):
                yield Static("Information", classes="section-title section-title-first")
                with Horizontal(classes="field-row"):
                    yield Label("Keymap Title:", classes="field-label")
                    yield Input(
                        value=keymap_title,
                        id="keymap-title-text",
                        placeholder="e.g. My Keymap (leave empty for auto)",
                    )
                with Horizontal(classes="field-row"):
                    yield Label("Copyright:", classes="field-label")
                    yield Input(
                        value=copyright_text,
                        id="copyright-text",
                        placeholder="e.g. (c) 2024 Your Name (leave empty for none)",
                    )

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
                        yield Button("+ Add (a)", id="add-layer", variant="success")
                        yield Button("- Delete (d)", id="remove-layer", variant="error")

                with Vertical(id="layer-detail"):
                    yield Static("Press Enter on a layer to edit", id="layer-detail-hint")
                    with Horizontal(classes="field-row"):
                        yield Label("Index:", classes="field-label")
                        yield Input(value="", id="layer-index", placeholder="e.g. 0", disabled=True)
                    with Horizontal(classes="field-row"):
                        yield Label("ID:", classes="field-label")
                        yield Input(value="", id="layer-id", placeholder="e.g. _BASE (optional)", disabled=True)
                    with Horizontal(classes="field-row"):
                        yield Label("Label:", classes="field-label")
                        yield Input(value="", id="layer-label", placeholder="e.g. BASE", disabled=True)
                    with Horizontal(classes="field-row"):
                        yield Label("Name:", classes="field-label")
                        yield Input(value="", id="layer-name", placeholder="e.g. Letters", disabled=True)
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

    def _col0_text(self, index: int, layer: dict[str, Any]) -> str:
        qmk_idx = layer.get("index", index)
        layer_id = layer.get("id") or ""
        if layer_id:
            return f"{layer_id}[{qmk_idx}]:"
        return f"[{qmk_idx}]:"

    def _col2_text(self, layer: dict[str, Any]) -> str:
        name = layer.get("name", "")
        subtitle = layer.get("subtitle") or ""
        if subtitle:
            return f"{name} ({subtitle})"
        return name

    def _column_widths(self) -> tuple[int, int]:
        layers = self.config_data.get("keyboard", {}).get("layers", [])
        col0_w = max((len(self._col0_text(i, l)) for i, l in enumerate(layers)), default=0)
        col1_w = max((len(l.get("label", "")) for l in layers), default=0)
        return col0_w, col1_w

    def _layer_text(self, index: int, layer: dict[str, Any], col0_w: int, col1_w: int) -> str:
        col0 = self._col0_text(index, layer)
        label = layer.get("label", "")
        col2 = self._col2_text(layer)
        return f"{col0:<{col0_w}}  {label:<{col1_w}}  {col2}"

    def _rebuild_list(self) -> None:
        layers = self.config_data.get("keyboard", {}).get("layers", [])
        col0_w, col1_w = self._column_widths()
        list_view = self.query_one("#layer-list", ListView)
        list_view.clear()
        for i, layer in enumerate(layers):
            list_view.append(ListItem(Static(self._layer_text(i, layer, col0_w, col1_w))))

    def _update_all_list_items(self) -> None:
        """Update the text of all list items in place (no clear/re-append)."""
        layers = self.config_data.get("keyboard", {}).get("layers", [])
        col0_w, col1_w = self._column_widths()
        list_view = self.query_one("#layer-list", ListView)
        for i, item in enumerate(list_view.children):
            if i < len(layers):
                item.query_one(Static).update(self._layer_text(i, layers[i], col0_w, col1_w))

    def _update_selected_list_item(self) -> None:
        layers = self.config_data.get("keyboard", {}).get("layers", [])
        if self._selected_layer >= len(layers):
            return
        col0_w, col1_w = self._column_widths()
        list_view = self.query_one("#layer-list", ListView)
        if self._selected_layer < len(list_view.children):
            item = list_view.children[self._selected_layer]
            static = item.query_one(Static)
            static.update(self._layer_text(self._selected_layer, layers[self._selected_layer], col0_w, col1_w))

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
        self.query_one("#layer-index", Input).focus()

    def _exit_edit_mode(self, commit: bool) -> None:
        """Exit edit mode: commit or rollback, disable fields, focus list."""
        if not commit and self._snapshot is not None:
            layers = self.config_data.get("keyboard", {}).get("layers", [])
            if self._selected_layer < len(layers):
                layers[self._selected_layer] = self._snapshot
                self._refresh_detail_fields()
        elif commit:
            # Validate and apply index before committing
            layers = self.config_data.get("keyboard", {}).get("layers", [])
            if self._selected_layer < len(layers):
                index_str = self.query_one("#layer-index", Input).value.strip()
                try:
                    new_index = int(index_str)
                except (ValueError, TypeError):
                    self._revert_and_show_error("Index must be a valid integer.")
                    return
                if new_index < 0 or new_index > 31:
                    self._revert_and_show_error("Index must be between 0 and 31.")
                    return
                # Check for duplicates
                current_layer = layers[self._selected_layer]
                for i, other in enumerate(layers):
                    if i != self._selected_layer and other.get("index", i) == new_index:
                        self._revert_and_show_error(
                            f"Index {new_index} is already used by another layer."
                        )
                        return
                # Apply the new index
                current_layer["index"] = new_index
                # Sort layers and palette.layers by index
                palette_layers = (
                    self.config_data.get("output", {})
                    .get("palette", {})
                    .get("layers", [])
                )
                # Build paired list to sort together
                if palette_layers and len(palette_layers) == len(layers):
                    paired = list(zip(layers, palette_layers))
                    paired.sort(key=lambda p: p[0].get("index", 0))
                    layers[:] = [p[0] for p in paired]
                    palette_layers[:] = [p[1] for p in paired]
                else:
                    layers.sort(key=lambda l: l.get("index", 0))
                # Update selected layer to follow the moved layer
                self._selected_layer = layers.index(current_layer)
                self._rebuild_list()
        self._editing = False
        self._snapshot = None
        self._set_fields_enabled(False)
        self._update_all_list_items()
        list_view = self.query_one("#layer-list", ListView)
        list_view.index = self._selected_layer
        list_view.focus()
        if commit:
            self.post_message(LayerUpdated())

    def _revert_and_show_error(self, message: str) -> None:
        """Revert from snapshot and show an error dialog."""
        layers = self.config_data.get("keyboard", {}).get("layers", [])
        if self._snapshot is not None and self._selected_layer < len(layers):
            layers[self._selected_layer] = self._snapshot
        self._editing = False
        self._snapshot = None
        self._set_fields_enabled(False)
        self._refresh_detail_fields()
        self._update_all_list_items()
        list_view = self.query_one("#layer-list", ListView)
        list_view.index = self._selected_layer
        list_view.focus()
        self.app.push_screen(ErrorDialog(message))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-layer":
            layers = self.config_data.setdefault("keyboard", {}).setdefault("layers", [])
            idx = len(layers)
            used_indices = {l.get("index", i) for i, l in enumerate(layers)}
            next_index = 0
            while next_index in used_indices:
                next_index += 1
            new_layer = {
                "index": next_index,
                "label": f"L{next_index}",
                "name": f"Layer {next_index}",
                "id": None,
                "subtitle": None,
            }
            layers.append(new_layer)
            self._rebuild_list()
            list_view = self.query_one("#layer-list", ListView)
            self._selected_layer = idx
            self._refresh_detail_fields()
            list_view.index = idx
            self._update_list_state()
            self.post_message(LayerAdded(idx, "keyboard"))
            # Immediately enter edit mode for the new layer
            self._enter_edit_mode()

        elif event.button.id == "remove-layer":
            layers = self.config_data.get("keyboard", {}).get("layers", [])
            if not layers or self._selected_layer >= len(layers):
                return
            removed_index = self._selected_layer
            layers.pop(removed_index)
            self._rebuild_list()
            if layers:
                self._selected_layer = min(self._selected_layer, len(layers) - 1)
                self._refresh_detail_fields()
                list_view = self.query_one("#layer-list", ListView)
                self.call_after_refresh(setattr, list_view, "index", self._selected_layer)
            else:
                self._selected_layer = 0
                self._clear_detail_fields()
            self._update_list_state()
            self.post_message(LayerRemoved(removed_index, "keyboard"))
            if not layers:
                self.query_one("#add-layer", Button).focus()

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
        """Handle Enter/Escape in edit mode, a/d shortcuts on list."""
        if self._editing:
            if event.key == "enter":
                event.prevent_default()
                event.stop()
                self._exit_edit_mode(commit=True)
            elif event.key == "escape":
                event.prevent_default()
                event.stop()
                self._exit_edit_mode(commit=False)
            return

        focused = self.app.focused
        if isinstance(focused, ListView) and focused.id == "layer-list":
            if event.key == "a":
                event.prevent_default()
                event.stop()
                self.query_one("#add-layer", Button).press()
            elif event.key == "d":
                event.prevent_default()
                event.stop()
                self.query_one("#remove-layer", Button).press()

    def on_descendant_blur(self, event: DescendantBlur) -> None:
        """Commit edit when focus leaves the editing pane."""
        if not self._editing:
            return
        self.set_timer(0.05, self._check_focus_commit)

    def _check_focus_commit(self) -> None:
        if not self._editing:
            return
        focused = self.app.focused
        if focused is None or not isinstance(focused, Input) or focused.id not in _FIELD_MAP:
            self._exit_edit_mode(commit=True)

    def _refresh_detail_fields(self) -> None:
        layers = self.config_data.get("keyboard", {}).get("layers", [])
        if self._selected_layer >= len(layers):
            return
        layer = layers[self._selected_layer]
        self.query_one("#layer-index", Input).value = str(layer.get("index", self._selected_layer))
        self.query_one("#layer-label", Input).value = layer.get("label", "") or ""
        self.query_one("#layer-name", Input).value = layer.get("name", "") or ""
        self.query_one("#layer-id", Input).value = layer.get("id", "") or ""
        self.query_one("#layer-subtitle", Input).value = layer.get("subtitle", "") or ""

    def _clear_detail_fields(self) -> None:
        self.query_one("#layer-index", Input).value = ""
        self.query_one("#layer-label", Input).value = ""
        self.query_one("#layer-name", Input).value = ""
        self.query_one("#layer-id", Input).value = ""
        self.query_one("#layer-subtitle", Input).value = ""

    def sync_layer_added(self, index: int) -> None:
        """Called when a layer color is added in the Style tab — add matching keyboard layer."""
        layers = self.config_data.setdefault("keyboard", {}).setdefault("layers", [])
        used_indices = {l.get("index", i) for i, l in enumerate(layers)}
        next_index = 0
        while next_index in used_indices:
            next_index += 1
        new_layer = {
            "index": next_index,
            "label": f"L{next_index}",
            "name": f"Layer {next_index}",
            "id": None,
            "subtitle": None,
        }
        layers.insert(index, new_layer)
        self._rebuild_list()
        self._selected_layer = index
        self._refresh_detail_fields()
        self._update_list_state()

    def sync_layer_removed(self, index: int) -> None:
        """Called when a layer color is removed in the Style tab — remove matching keyboard layer."""
        layers = self.config_data.get("keyboard", {}).get("layers", [])
        if index >= len(layers):
            return
        layers.pop(index)
        self._rebuild_list()
        if layers:
            self._selected_layer = min(self._selected_layer, len(layers) - 1)
            self._refresh_detail_fields()
        else:
            self._selected_layer = 0
            self._clear_detail_fields()
        self._update_list_state()

    def on_input_changed(self, event: Input.Changed) -> None:
        input_id = event.input.id
        if input_id == "keymap-title-text":
            self.config_data["output"]["keymap_title"] = event.value if event.value else None
            return
        if input_id == "copyright-text":
            self.config_data["output"]["copyright"] = event.value if event.value else None
            return
        if input_id not in _FIELD_MAP:
            return
        config_key = _FIELD_MAP[input_id]
        if config_key == "index":
            return  # index is validated on commit, not on change
        layers = self.config_data.get("keyboard", {}).get("layers", [])
        if self._selected_layer >= len(layers):
            return
        value: str | None = event.value
        if config_key in ("id", "subtitle") and value == "":
            value = None
        layers[self._selected_layer][config_key] = value
        self._update_selected_list_item()
