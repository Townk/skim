# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Keyboard tab widget for the skim TUI configuration editor."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Input, Label, Static

from skim.tui.app import LayerAdded, LayerRemoved, LayerUpdated
from skim.tui.list_detail_pane import ListDetailPane
from skim.tui.widgets import SkimInput, SkimStandaloneInput, SkimSwitch, SkimVerticalScroll

_FIELD_MAP = {
    "layer-index": "index",
    "layer-label": "label",
    "layer-name": "name",
    "layer-id": "id",
    "layer-variant": "variant",
}


class LayerListPane(ListDetailPane):
    """List/detail pane for keyboard layers."""

    DEFAULT_CSS = """
    LayerListPane {
        height: auto;
    }
    """

    def __init__(self, config_data: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(pane_id="layer", **kwargs)
        self.config_data = config_data

    def get_entries(self) -> list[dict]:
        return self.config_data.get("keyboard", {}).get("layers", [])

    def _col0_text(self, index: int, layer: dict[str, Any]) -> str:
        qmk_idx = layer.get("index", index)
        layer_id = layer.get("id") or ""
        if layer_id:
            return f"{layer_id}[{qmk_idx}]:"
        return f"[{qmk_idx}]:"

    def _col2_text(self, layer: dict[str, Any]) -> str:
        name = layer.get("name", "")
        variant = layer.get("variant") or ""
        if variant:
            return f"{name} ({variant})"
        return name

    def _column_widths(self) -> tuple[int, int]:
        layers = self.get_entries()
        col0_w = max((len(self._col0_text(i, layer)) for i, layer in enumerate(layers)), default=0)
        col1_w = max((len(layer.get("label", "")) for layer in layers), default=0)
        return col0_w, col1_w

    def format_entry(self, index: int, entry: dict) -> str:
        col0_w, col1_w = self._column_widths()
        col0 = self._col0_text(index, entry)
        label = entry.get("label", "")
        col2 = self._col2_text(entry)
        return f"{col0:<{col0_w}}  {label:<{col1_w}}  {col2}"

    def compose_detail_fields(self) -> ComposeResult:
        with Horizontal(classes="field-row"):
            yield Label("Index:", classes="field-label")
            yield SkimInput(value="", id="layer-index", placeholder="e.g. 0", disabled=True)
        with Horizontal(classes="field-row"):
            yield Label("ID:", classes="field-label")
            yield SkimInput(
                value="", id="layer-id", placeholder="e.g. _BASE (optional)", disabled=True
            )
        with Horizontal(classes="field-row"):
            yield Label("Label:", classes="field-label")
            yield SkimInput(value="", id="layer-label", placeholder="e.g. BASE", disabled=True)
        with Horizontal(classes="field-row"):
            yield Label("Name:", classes="field-label")
            yield SkimInput(value="", id="layer-name", placeholder="e.g. Letters", disabled=True)
        with Horizontal(classes="field-row"):
            yield Label("Variant:", classes="field-label")
            yield SkimInput(
                value="", id="layer-variant", placeholder="e.g. COLEMAK (optional)", disabled=True
            )

    def detail_field_ids(self) -> set[str]:
        return set(_FIELD_MAP.keys())

    def refresh_fields(self, entry: dict) -> None:
        self.query_one("#layer-index", Input).value = str(entry.get("index", self._selected))
        self.query_one("#layer-label", Input).value = entry.get("label", "") or ""
        self.query_one("#layer-name", Input).value = entry.get("name", "") or ""
        self.query_one("#layer-id", Input).value = entry.get("id", "") or ""
        self.query_one("#layer-variant", Input).value = entry.get("variant", "") or ""

    def clear_fields(self) -> None:
        self.query_one("#layer-index", Input).value = ""
        self.query_one("#layer-label", Input).value = ""
        self.query_one("#layer-name", Input).value = ""
        self.query_one("#layer-id", Input).value = ""
        self.query_one("#layer-variant", Input).value = ""

    def create_entry(self, index: int) -> dict:
        layers = self.get_entries()
        used_indices = {
            layer.get("index", i) for i, layer in enumerate(layers) if layer is not layers[-1]
        }
        # When called from _add_entry, the new entry is already appended,
        # so exclude it from used_indices. But we also need to handle the
        # case where it hasn't been appended yet.
        next_index = 0
        while next_index in used_indices:
            next_index += 1
        return {
            "index": next_index,
            "label": f"L{next_index}",
            "name": f"Layer {next_index}",
            "id": None,
            "variant": None,
        }

    def _add_entry(self) -> None:
        """Override to compute next index before appending."""
        entries = self.get_entries()
        used_indices = {entry.get("index", i) for i, entry in enumerate(entries)}
        next_index = 0
        while next_index in used_indices:
            next_index += 1
        idx = len(entries)
        new_entry = {
            "index": next_index,
            "label": f"L{next_index}",
            "name": f"Layer {next_index}",
            "id": None,
            "variant": None,
        }
        entries.append(new_entry)
        from skim.tui.widgets import SkimListView

        list_view = self.query_one(f"#{self.pane_id}-list", SkimListView)
        list_view.append(self._make_list_item(idx, new_entry))
        self._selected = idx
        self.refresh_fields(new_entry)
        self._update_list_state()
        self.post_message(self.EntryAdded(idx))
        self._adding = True
        self.call_after_refresh(self._finish_add, idx)

    def validate_and_apply(self, entry: dict) -> bool:
        """Validate index (0-31, no duplicates), apply fields, re-sort."""
        index_str = self.query_one("#layer-index", Input).value.strip()
        try:
            new_index = int(index_str)
        except (ValueError, TypeError):
            self._revert_and_show_error("Index must be a valid integer.")
            return False
        if new_index < 0 or new_index > 31:
            self._revert_and_show_error("Index must be between 0 and 31.")
            return False
        layers = self.get_entries()
        for i, other in enumerate(layers):
            if i != self._selected and other.get("index", i) == new_index:
                self._revert_and_show_error(f"Index {new_index} is already used by another layer.")
                return False
        entry["index"] = new_index
        # Sort layers and palette.layers by index
        palette_layers = (
            self.config_data.get("output", {}).get("style", {}).get("palette", {}).get("layers", [])
        )
        if palette_layers and len(palette_layers) == len(layers):
            paired = list(zip(layers, palette_layers, strict=False))
            paired.sort(key=lambda p: p[0].get("index", 0))
            layers[:] = [p[0] for p in paired]
            palette_layers[:] = [p[1] for p in paired]
        else:
            layers.sort(key=lambda layer: layer.get("index", 0))
        self._selected = layers.index(entry)
        return True

    def on_input_changed(self, event: Input.Changed) -> None:
        input_id = event.input.id
        if input_id not in _FIELD_MAP:
            return
        config_key = _FIELD_MAP[input_id]
        if config_key == "index":
            return  # validated on commit
        layers = self.get_entries()
        if self._selected >= len(layers):
            return
        value: str | None = event.value
        if config_key in ("id", "variant") and value == "":
            value = None
        layers[self._selected][config_key] = value
        self.update_selected_list_item()


class KeyboardTab(Widget):
    """Keyboard configuration tab.

    Shows an Information section, a Features section, and a Layers section
    with a LayerListPane for editing individual layer metadata.
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
    """

    def __init__(self, config_data: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.config_data = config_data

    def compose(self) -> ComposeResult:
        features = self.config_data.get("keyboard", {}).get("features", {})
        double_south = features.get("double_south", False)
        keymap_title = self.config_data.get("output", {}).get("keymap_title") or ""
        copyright_text = self.config_data.get("output", {}).get("copyright") or ""

        with SkimVerticalScroll(can_focus=False):
            with Vertical(id="info-section"):
                yield Static("Information", classes="section-title section-title-first")
                with Horizontal(classes="field-row"):
                    yield Label("Keymap Title:", classes="field-label")
                    yield SkimStandaloneInput(
                        value=keymap_title,
                        id="keymap-title-text",
                        placeholder="e.g. My Keymap (leave empty for auto)",
                    )
                with Horizontal(classes="field-row"):
                    yield Label("Copyright:", classes="field-label")
                    yield SkimStandaloneInput(
                        value=copyright_text,
                        id="copyright-text",
                        placeholder="e.g. (c) 2024 Your Name (leave empty for none)",
                    )

            with Vertical(id="features-section"):
                yield Static("Features", classes="section-title")
                with Horizontal(id="features-row"):
                    yield Label("Double South: ", classes="field-label")
                    yield SkimSwitch(value=double_south, id="double-south")

            yield Static("Layers", classes="section-title")
            yield LayerListPane(config_data=self.config_data)

    def on_mount(self) -> None:
        pane = self.query_one(LayerListPane)
        pane.rebuild_list()
        entries = pane.get_entries()
        if entries:
            pane._selected = 0
            pane.refresh_fields(entries[0])
        pane._update_list_state()

    def on_switch_changed(self, event: SkimSwitch.Changed) -> None:
        if event.switch.id == "double-south":
            self.config_data.setdefault("keyboard", {}).setdefault("features", {})
            self.config_data["keyboard"]["features"]["double_south"] = event.value

    def on_input_changed(self, event: Input.Changed) -> None:
        input_id = event.input.id
        if input_id == "keymap-title-text":
            self.config_data["output"]["keymap_title"] = event.value if event.value else None
        elif input_id == "copyright-text":
            self.config_data["output"]["copyright"] = event.value if event.value else None

    # -- Cross-tab sync via ListDetailPane messages --

    def on_list_detail_pane_entry_added(self, event: ListDetailPane.EntryAdded) -> None:
        self.post_message(LayerAdded(event.index, "keyboard"))

    def on_list_detail_pane_entry_removed(self, event: ListDetailPane.EntryRemoved) -> None:
        self.post_message(LayerRemoved(event.index, "keyboard"))

    def on_list_detail_pane_entry_updated(self, event: ListDetailPane.EntryUpdated) -> None:
        self.post_message(LayerUpdated())

    # -- Sync methods called from app.py --

    def sync_layer_added(self, index: int) -> None:
        """Called when a layer color is added in the Style tab."""
        pane = self.query_one(LayerListPane)
        layers = pane.get_entries()
        used_indices = {layer.get("index", i) for i, layer in enumerate(layers)}
        next_index = 0
        while next_index in used_indices:
            next_index += 1
        new_layer = {
            "index": next_index,
            "label": f"L{next_index}",
            "name": f"Layer {next_index}",
            "id": None,
            "variant": None,
        }
        layers.insert(index, new_layer)
        pane.rebuild_list()
        pane._selected = index
        pane.refresh_fields(new_layer)
        pane._update_list_state()

    def sync_layer_removed(self, index: int) -> None:
        """Called when a layer color is removed in the Style tab."""
        pane = self.query_one(LayerListPane)
        layers = pane.get_entries()
        if index >= len(layers):
            return
        layers.pop(index)
        pane.rebuild_list()
        if layers:
            pane._selected = min(pane._selected, len(layers) - 1)
            pane.refresh_fields(layers[pane._selected])
        else:
            pane._selected = 0
            pane.clear_fields()
        pane._update_list_state()
