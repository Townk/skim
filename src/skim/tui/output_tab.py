# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Output tab widget for the skim TUI configuration editor."""

import contextlib
from typing import Any

import webcolors
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.content import Content
from textual.events import DescendantBlur
from textual.suggester import SuggestFromList
from textual.widget import Widget
from textual.widgets import Input, Label, ListItem, Static
from textual_autocomplete import AutoComplete, DropdownItem, TargetState

from skim.application.render.styling import default_layer_color, make_gradient
from skim.tui.app import LayerAdded, LayerRemoved
from skim.tui.list_detail_pane import ListDetailPane
from skim.tui.widgets import SkimInput, SkimSelect, SkimStandaloneInput, SkimSwitch, SkimVerticalScroll

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


class LayerColorListPane(ListDetailPane):
    """List/detail pane for layer colors."""

    DEFAULT_CSS = """
    LayerColorListPane {
        height: auto;
    }
    LayerColorListPane .lc-swatch {
        width: 4;
        height: 1;
        dock: right;
        margin: 0 0 0 1;
    }
    LayerColorListPane .color-swatch {
        width: 4;
        height: 1;
        margin: 1 1 0 0;
        content-align: center middle;
    }
    LayerColorListPane .swatch-spacer {
        width: 4;
        height: 1;
        margin: 1 1 0 0;
    }
    LayerColorListPane .gradient-swatch {
        width: 4;
        height: 3;
        content-align: center middle;
    }
    LayerColorListPane .gradient-preview {
        height: 3;
        width: auto;
        layout: horizontal;
        padding: 0 2;
    }
    LayerColorListPane .gradient-dark {
        background: #1b1b1b;
        margin: 0 0 0 2;
    }
    LayerColorListPane .gradient-light {
        background: #ffffff;
        margin: 0 0 0 1;
    }
    LayerColorListPane .lc-manual-step {
        display: none;
    }
    LayerColorListPane.manual-mode .lc-manual-step {
        display: block;
    }
    LayerColorListPane.manual-mode #lc-dynamic-color {
        display: none;
    }
    LayerColorListPane.manual-mode #lc-dynamic-preview {
        display: none;
    }
    """

    def __init__(self, config_data: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(pane_id="layer-colors", **kwargs)
        self.config_data = config_data
        self._select_active: bool = False

    def get_entries(self) -> list[dict]:
        return (
            self.config_data.get("output", {}).get("style", {}).get("palette", {}).get("layers", [])
        )

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
        layer_colors = self.get_entries()
        col0_w = 0
        col1_w = 0
        for i, lc in enumerate(layer_colors):
            name = self._layer_name(i)
            qmk_idx = self._layer_qmk_index(i)
            col0 = f"{name} ({qmk_idx})" if name else f"({qmk_idx})"
            col0_w = max(col0_w, len(col0))
            col1_w = max(col1_w, len(lc.get("base_color", "")))
        return col0_w, col1_w

    def format_entry(self, index: int, entry: dict) -> str:
        col0_w, col1_w = self._lc_column_widths()
        name = self._layer_name(index)
        qmk_idx = self._layer_qmk_index(index)
        col0 = f"{name} ({qmk_idx})" if name else f"({qmk_idx})"
        color = entry.get("base_color", "")
        return f"{col0:<{col0_w}}  {color:<{col1_w}}"

    @staticmethod
    def _safe_set_color(widget: Static, color: str) -> None:
        """Set foreground color, silently ignoring invalid values."""
        with contextlib.suppress(Exception):
            widget.styles.color = color if color else "white"

    def _make_list_item(self, index: int, entry: dict) -> ListItem:
        color = entry.get("base_color", "")
        swatch = Static("\uebb4", classes="lc-swatch")
        self._safe_set_color(swatch, color)
        return ListItem(Static(self.format_entry(index, entry)), swatch)

    def _update_list_item_content(self, item: ListItem, index: int, entry: dict) -> None:
        item.query_one(Static).update(self.format_entry(index, entry))
        for s in item.query(Static).filter(".lc-swatch"):
            self._safe_set_color(s, entry.get("base_color", ""))

    def compose_detail_fields(self) -> ComposeResult:
        with Horizontal(classes="field-row"):
            yield Label("Gradient type:", classes="field-label")
            yield Static(" ", classes="swatch-spacer")
            yield SkimSelect(
                options=[("Dynamic", "dynamic"), ("Manual", "manual")],
                value="dynamic",
                id="lc-gradient-type",
                disabled=True,
            )
        with Horizontal(classes="field-row"):
            yield Label("Main gradient step index:", classes="field-label")
            yield Static(" ", classes="swatch-spacer")
            yield SkimInput(
                value="",
                id="lc-color-index",
                placeholder="2",
                disabled=True,
            )
        # --- Dynamic mode fields ---
        with Horizontal(classes="field-row", id="lc-dynamic-color"):
            yield Label("Main gradient step color:", classes="field-label")
            yield Static(
                "\ue0b6\u2588\u2588\ue0b4", classes="color-swatch", id="swatch-lc-base-color"
            )
            lc_color_input = SkimInput(
                value="",
                id="lc-base-color",
                placeholder="#RRGGBB",
                disabled=True,
                suggester=_COLOR_SUGGESTER,
            )
            yield lc_color_input
        yield ColorAutoComplete(lc_color_input, candidates=_color_candidates)
        with Horizontal(classes="field-row", id="lc-dynamic-preview"):
            yield Label("Layer gradient:", classes="field-label")
            yield Static(" ", classes="swatch-spacer")
            with Horizontal(classes="gradient-preview gradient-dark"):
                for i in range(6):
                    yield Static(
                        f"   \n\ue0b6\u2588\ue0b4\n {i} ",
                        classes="gradient-swatch",
                        id=f"gradient-dark-{i}",
                    )
            with Horizontal(classes="gradient-preview gradient-light"):
                for i in range(6):
                    yield Static(
                        f"   \n\ue0b6\u2588\ue0b4\n {i} ",
                        classes="gradient-swatch",
                        id=f"gradient-light-{i}",
                    )
        # --- Manual mode fields (hidden by default) ---
        for i in range(6):
            with Horizontal(classes="field-row lc-manual-step", id=f"lc-manual-step-{i}"):
                yield Label(f"Step {i}:", classes="field-label")
                yield Static(
                    "\ue0b6\u2588\u2588\ue0b4",
                    classes="color-swatch",
                    id=f"swatch-lc-step-{i}",
                )
                step_input = SkimInput(
                    value="",
                    id=f"lc-step-{i}",
                    placeholder="#RRGGBB",
                    disabled=True,
                    suggester=_COLOR_SUGGESTER,
                )
                yield step_input
            yield ColorAutoComplete(step_input, candidates=_color_candidates)

    def detail_field_ids(self) -> set[str]:
        ids = {"lc-base-color", "lc-color-index", "lc-gradient-type"}
        for i in range(6):
            ids.add(f"lc-step-{i}")
        return ids

    def _focus_first_field(self) -> None:
        """Focus the gradient type Select as the first field."""
        try:
            self.query_one("#lc-gradient-type", SkimSelect).focus()
        except Exception:
            super()._focus_first_field()

    def _is_inside_select(self) -> bool:
        """Check if the currently focused widget is inside a SkimSelect."""
        focused = self.app.focused
        if focused is None:
            return False
        node = focused
        while node is not None:
            if isinstance(node, SkimSelect):
                return True
            node = node.parent
        return False

    def on_key(self, event) -> None:
        """Override to let Select handle keys normally.

        Textual's on_key fires during event bubbling BEFORE the App-level
        binding system runs. We must stop the event (to prevent other
        handlers from interfering) and manually trigger binding checks.
        """
        if self._editing and (self._select_active or self._is_inside_select()):
            if event.key in ("enter", "space", "up", "down"):
                if not self._select_active:
                    self._select_active = True
                event.stop()
                event.prevent_default()
                self.call_later(self.app._check_bindings, event.key)
                # Clear flag after selection in case value didn't change
                # (on_select_changed only fires when value actually changes)
                if self._select_active and event.key in ("enter", "space"):
                    self.set_timer(0.15, self._clear_select_active)
                return
            if event.key == "escape" and self._select_active:
                event.stop()
                event.prevent_default()
                self._dismiss_select_overlay()
                return
                # Escape on closed Select — fall through to base (cancel edit)
        super().on_key(event)

    def on_descendant_blur(self, event: DescendantBlur) -> None:
        """Suppress focus-out commit while Select overlay is open."""
        if self._select_active:
            return
        super().on_descendant_blur(event)

    def _dismiss_select_overlay(self) -> None:
        """Dismiss the overlay and clear _select_active after focus settles."""
        try:
            select = self.query_one("#lc-gradient-type", SkimSelect)
            select.query_one("SelectOverlay").action_dismiss()  # type: ignore[attr-defined]
        except Exception:
            pass
        self.set_timer(0.1, self._clear_select_active)

    def _clear_select_active(self) -> None:
        self._select_active = False

    def on_select_changed(self, event: SkimSelect.Changed) -> None:
        self._select_active = False
        if event.select.id == "lc-gradient-type" and event.value is not SkimSelect.BLANK:
            self._on_gradient_type_changed(str(event.value))

    def _exit_edit_mode(self, commit: bool) -> None:
        """Override to block exit while Select overlay is active."""
        if self._select_active:
            return
        super()._exit_edit_mode(commit)

    def _set_fields_enabled(self, enabled: bool) -> None:
        """Override to also enable/disable the gradient type Select."""
        super()._set_fields_enabled(enabled)
        with contextlib.suppress(Exception):
            self.query_one("#lc-gradient-type", SkimSelect).disabled = not enabled

    def _check_focus_commit(self) -> None:
        """Override to keep editing when Select or its overlay is focused."""
        if not self._editing:
            return
        if self._select_active:
            return  # overlay is open, don't commit
        focused = self.app.focused
        if focused is not None:
            # Check if focused widget is inside this pane's detail area
            all_ids = self.detail_field_ids()
            if hasattr(focused, "id") and focused.id in all_ids:
                return
            # Check if focused widget is a descendant of this pane
            # (e.g. Select overlay/OptionList)
            node = focused
            while node is not None:
                if node is self:
                    return
                node = node.parent
        self._exit_edit_mode(commit=True)

    def _is_manual_mode(self, entry: dict) -> bool:
        return entry.get("gradient") is not None

    def _set_mode(self, manual: bool) -> None:
        if manual:
            self.add_class("manual-mode")
        else:
            self.remove_class("manual-mode")

    def refresh_fields(self, entry: dict) -> None:
        color = entry.get("base_color", "") or ""
        color_index = entry.get("color_index", 2)
        manual = self._is_manual_mode(entry)

        self._set_mode(manual)
        self.query_one("#lc-gradient-type", SkimSelect).value = "manual" if manual else "dynamic"
        self.query_one("#lc-color-index", Input).value = str(color_index)

        if manual:
            gradient = entry.get("gradient", ()) or ()
            for i in range(6):
                step_color = gradient[i] if i < len(gradient) else ""
                self.query_one(f"#lc-step-{i}", Input).value = step_color
                self._update_swatch(f"swatch-lc-step-{i}", step_color)
        else:
            self.query_one("#lc-base-color", Input).value = color
            self._update_swatch("swatch-lc-base-color", color)
            self._update_gradient_preview(color, color_index)

    def clear_fields(self) -> None:
        self._set_mode(False)
        self.query_one("#lc-gradient-type", SkimSelect).value = "dynamic"
        self.query_one("#lc-base-color", Input).value = ""
        self.query_one("#lc-color-index", Input).value = ""
        for i in range(6):
            self.query_one(f"#lc-step-{i}", Input).value = ""
            self._update_swatch(f"swatch-lc-step-{i}", "")
            for prefix, label_color in (("gradient-dark", "white"), ("gradient-light", "black")):
                try:
                    swatch = self.query_one(f"#{prefix}-{i}", Static)
                    swatch.update(self._make_swatch_text(i, "", -1, label_color))
                except Exception:
                    pass

    def create_entry(self, index: int) -> dict:
        return {"base_color": default_layer_color(index), "color_index": 2, "gradient": None}

    def _update_swatch(self, swatch_id: str, color: str) -> None:
        try:
            swatch = self.query_one(f"#{swatch_id}", Static)
            swatch.styles.color = color if color else "white"
        except Exception:
            pass

    @staticmethod
    def _make_swatch_text(i: int, color: str, color_index: int, label_color: str) -> Text:
        """Build a 3-line Rich Text for a gradient swatch."""
        arrow = " \u25bc " if i == color_index else "   "
        t = Text()
        t.append(arrow, style=label_color)
        t.append("\n")
        t.append("\ue0b6\u2588\ue0b4", style=color if color else label_color)
        t.append("\n")
        t.append(f" {i} ", style=label_color)
        return t

    def _update_gradient_preview(self, base_color: str, color_index: int) -> None:
        """Update gradient swatch colors on both dark and light backgrounds."""
        try:
            gradient = make_gradient(base_color, color_index)
        except Exception:
            gradient = ("",) * 6
        for i, color in enumerate(gradient):
            for prefix, label_color in (("gradient-dark", "white"), ("gradient-light", "black")):
                try:
                    swatch = self.query_one(f"#{prefix}-{i}", Static)
                    swatch.update(self._make_swatch_text(i, color, color_index, label_color))
                except Exception:
                    pass

    def _current_gradient_params(self) -> tuple[str, int]:
        """Get current base color and color index from the fields."""
        base_color = self.query_one("#lc-base-color", Input).value
        try:
            color_index = int(self.query_one("#lc-color-index", Input).value)
        except (ValueError, TypeError):
            color_index = 2
        return base_color, color_index

    def _on_gradient_type_changed(self, value: str) -> None:
        """Handle switching between Dynamic and Manual gradient modes."""
        entries = self.get_entries()
        if self._selected >= len(entries):
            return
        entry = entries[self._selected]
        manual = value == "manual"

        if manual and entry.get("gradient") is None:
            # Switching to manual: pre-populate with auto-generated gradient
            base_color = entry.get("base_color", "")
            color_index = entry.get("color_index", 2)
            try:
                gradient = list(make_gradient(base_color, color_index))
            except Exception:
                gradient = [""] * 6
            entry["gradient"] = gradient
        elif not manual and entry.get("gradient") is not None:
            # Switching to dynamic: set base_color from the step at color_index
            gradient = entry.get("gradient", [])
            color_index = entry.get("color_index", 2)
            if gradient and 0 <= color_index < len(gradient):
                entry["base_color"] = gradient[color_index]
            entry["gradient"] = None

        self._set_mode(manual)
        self.refresh_fields(entry)
        self.update_selected_list_item()

    def _update_list_swatch(self, color: str) -> None:
        """Update the color swatch in the currently selected list item."""
        from skim.tui.widgets import SkimListView

        list_view = self.query_one(f"#{self.pane_id}-list", SkimListView)
        if self._selected < len(list_view.children):
            item = list_view.children[self._selected]
            for s in item.query(Static).filter(".lc-swatch"):
                self._safe_set_color(s, color)

    def on_input_changed(self, event: Input.Changed) -> None:
        input_id = event.input.id or ""
        if input_id == "lc-base-color":
            layer_colors = self.get_entries()
            if self._selected < len(layer_colors):
                layer_colors[self._selected]["base_color"] = event.value
                self.update_selected_list_item()
                self._update_swatch("swatch-lc-base-color", event.value)
                self._update_list_swatch(event.value)
                base_color, color_index = self._current_gradient_params()
                self._update_gradient_preview(base_color, color_index)
        elif input_id == "lc-color-index":
            layer_colors = self.get_entries()
            if self._selected < len(layer_colors):
                with contextlib.suppress(ValueError):
                    layer_colors[self._selected]["color_index"] = int(event.value)
                base_color, color_index = self._current_gradient_params()
                self._update_gradient_preview(base_color, color_index)
        elif input_id.startswith("lc-step-"):
            # Manual gradient step color changed
            step = int(input_id[len("lc-step-") :])
            layer_colors = self.get_entries()
            if self._selected < len(layer_colors):
                entry = layer_colors[self._selected]
                gradient = entry.get("gradient")
                if gradient is not None:
                    if isinstance(gradient, tuple):
                        gradient = list(gradient)
                        entry["gradient"] = gradient
                    if step < len(gradient):
                        gradient[step] = event.value
                    self._update_swatch(f"swatch-lc-step-{step}", event.value)
                    # Update base_color if this is the main step
                    color_index = entry.get("color_index", 2)
                    if step == color_index:
                        entry["base_color"] = event.value
                        self.update_selected_list_item()
                        self._update_list_swatch(event.value)


class OutputTab(Widget):
    """Output configuration tab.

    Has sections for layout, style, palette, and layer colors.
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
    OutputTab .color-swatch {
        width: 5;
        height: 1;
        margin: 1 1 0 0;
        content-align: center middle;
    }
    OutputTab .swatch-spacer {
        width: 4;
        height: 1;
        margin: 1 1 0 0;
    }
    """

    def __init__(self, config_data: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.config_data = config_data

    def compose(self) -> ComposeResult:
        output = self.config_data.get("output", {})
        layout = output.get("layout", {})
        spacing = layout.get("spacing", {})
        style = output.get("style", {})
        palette = style.get("palette", {})
        border = style.get("border")
        hold_position = style.get("hold_symbol_position", "outward")

        with SkimVerticalScroll(can_focus=False):
            # --- Layout section ---
            with Vertical(classes="section"):
                yield Static("Layout", classes="section-title section-title-first")
                with Horizontal(classes="field-row"):
                    yield Label("Width:", classes="field-label")
                    yield Static(" ", classes="swatch-spacer")
                    yield SkimStandaloneInput(
                        value=str(layout.get("width", 800.0)),
                        id="layout-width",
                        placeholder="800.0",
                    )
                with Horizontal(classes="field-row"):
                    yield Label("Margin:", classes="field-label")
                    yield Static(" ", classes="swatch-spacer")
                    yield SkimStandaloneInput(
                        value=str(spacing.get("margin", 0.0)),
                        id="layout-margin",
                        placeholder="0.0",
                    )
                with Horizontal(classes="field-row"):
                    yield Label("Inset:", classes="field-label")
                    yield Static(" ", classes="swatch-spacer")
                    yield SkimStandaloneInput(
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
                    yield SkimSwitch(
                        value=style.get("use_layer_colors_on_keys", True),
                        id="use-layer-colors",
                    )
                with Horizontal(classes="field-row"):
                    yield Label("Hold symbol position:", classes="field-label")
                    yield Static(" ", classes="swatch-spacer")
                    yield SkimSelect(
                        options=_HOLD_SYMBOL_OPTIONS,
                        value=hold_position,
                        id="hold-symbol-position",
                    )
                with Horizontal(classes="field-row"):
                    yield Label("Show layer indicators:", classes="field-label")
                    yield Static(" ", classes="swatch-spacer")
                    yield SkimSwitch(
                        value=style.get("show_layer_indicators", True),
                        id="show-layer-indicators",
                    )
                with Horizontal(classes="field-row"):
                    yield Label("Show layer connectors:", classes="field-label")
                    yield Static(" ", classes="swatch-spacer")
                    yield SkimSwitch(
                        value=style.get("show_layer_connectors", True),
                        id="show-layer-connectors",
                    )
                with Horizontal(classes="field-row"):
                    yield Label("Use system fonts:", classes="field-label")
                    yield Static(" ", classes="swatch-spacer")
                    yield SkimSwitch(
                        value=style.get("use_system_fonts", False),
                        id="use-system-fonts",
                    )
                with Horizontal(classes="field-row"):
                    yield Label("Border enabled:", classes="field-label")
                    yield Static(" ", classes="swatch-spacer")
                    yield SkimSwitch(
                        value=border is not None,
                        id="border-enabled",
                    )
                with Horizontal(classes="field-row"):
                    yield Label("Border width:", classes="field-label")
                    yield Static(" ", classes="swatch-spacer")
                    yield SkimStandaloneInput(
                        value=str(border.get("width", 2.0)) if border else "2.0",
                        id="border-width",
                        placeholder="2.0",
                    )
                with Horizontal(classes="field-row"):
                    yield Label("Border radius:", classes="field-label")
                    yield Static(" ", classes="swatch-spacer")
                    yield SkimStandaloneInput(
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
                        yield Static(
                            "\ue0b6\u2588\u2588\ue0b4",
                            classes="color-swatch",
                            id=f"swatch-{field_id}",
                        )
                        color_input = SkimStandaloneInput(
                            value=color_val,
                            id=field_id,
                            placeholder=placeholder,
                            suggester=_COLOR_SUGGESTER,
                        )
                        yield color_input
                    yield ColorAutoComplete(color_input, candidates=_color_candidates)

            # --- Layer colors section ---
            with Vertical(classes="section"):
                yield Static("Layer Colors", classes="section-title")
                yield LayerColorListPane(config_data=self.config_data)

    def on_mount(self) -> None:
        pane = self.query_one(LayerColorListPane)
        pane.rebuild_list()
        entries = pane.get_entries()
        if entries:
            pane._selected = 0
            pane.refresh_fields(entries[0])
        pane._update_list_state()
        self._update_all_palette_swatches()

    def _update_swatch(self, swatch_id: str, color: str) -> None:
        try:
            swatch = self.query_one(f"#{swatch_id}", Static)
            swatch.styles.color = color if color else "white"
        except Exception:
            pass

    @staticmethod
    def _safe_set_background(widget: Static, color: str) -> None:
        with contextlib.suppress(Exception):
            widget.styles.background = color if color else "transparent"

    @staticmethod
    def _safe_set_color(widget: Static, color: str) -> None:
        with contextlib.suppress(Exception):
            widget.styles.color = color if color else "white"

    def _update_all_palette_swatches(self) -> None:
        palette = self.config_data.get("output", {}).get("style", {}).get("palette", {})
        for field_id, config_key in _PALETTE_FIELD_MAP.items():
            color = palette.get(config_key, "")
            self._update_swatch(f"swatch-{field_id}", color)

    # Keep these methods on the tab for test compatibility
    def _layer_qmk_index(self, index: int) -> int:
        layers = self.config_data.get("keyboard", {}).get("layers", [])
        if index < len(layers):
            return layers[index].get("index", index)
        return index

    def _layer_name(self, index: int) -> str:
        layers = self.config_data.get("keyboard", {}).get("layers", [])
        if index < len(layers):
            return layers[index].get("name", "")
        return ""

    def _layer_colors(self) -> list[dict[str, Any]]:
        return (
            self.config_data.get("output", {}).get("style", {}).get("palette", {}).get("layers", [])
        )

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

    def _enter_lc_edit_mode(self) -> None:
        """Delegate to the pane. Kept for test compatibility."""
        pane = self.query_one(LayerColorListPane)
        pane._enter_edit_mode()

    def _exit_lc_edit_mode(self, commit: bool) -> None:
        """Delegate to the pane. Kept for test compatibility."""
        pane = self.query_one(LayerColorListPane)
        pane._exit_edit_mode(commit=commit)

    def _rebuild_layer_colors_list(self) -> None:
        """Delegate to the pane. Called from app.py on LayerUpdated."""
        pane = self.query_one(LayerColorListPane)
        pane.rebuild_list()

    # -- Cross-tab sync via ListDetailPane messages --

    def on_list_detail_pane_entry_added(self, event: ListDetailPane.EntryAdded) -> None:
        self.post_message(LayerAdded(event.index, "style"))

    def on_list_detail_pane_entry_removed(self, event: ListDetailPane.EntryRemoved) -> None:
        self.post_message(LayerRemoved(event.index, "style"))

    def sync_layer_added(self, index: int) -> None:
        """Called when a layer is added in the Keyboard tab."""
        pane = self.query_one(LayerColorListPane)
        layer_colors = pane.get_entries()
        new_lc = {"base_color": default_layer_color(index), "color_index": 2, "gradient": None}
        layer_colors.insert(index, new_lc)
        pane.rebuild_list()
        pane._selected = index
        pane.refresh_fields(new_lc)
        pane._update_list_state()

    def sync_layer_removed(self, index: int) -> None:
        """Called when a layer is removed in the Keyboard tab."""
        pane = self.query_one(LayerColorListPane)
        layer_colors = pane.get_entries()
        if index >= len(layer_colors):
            return
        layer_colors.pop(index)
        pane.rebuild_list()
        if layer_colors:
            pane._selected = min(pane._selected, len(layer_colors) - 1)
            pane.refresh_fields(layer_colors[pane._selected])
        else:
            pane._selected = 0
            pane.clear_fields()
        pane._update_list_state()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Route input changes to the correct config path."""
        input_id = event.input.id or ""
        value = event.value

        if input_id == "layout-width":
            with contextlib.suppress(ValueError):
                self.config_data["output"]["layout"]["width"] = float(value)

        elif input_id == "layout-margin":
            with contextlib.suppress(ValueError):
                self.config_data["output"]["layout"]["spacing"]["margin"] = float(value)

        elif input_id == "layout-inset":
            with contextlib.suppress(ValueError):
                self.config_data["output"]["layout"]["spacing"]["inset"] = float(value)

        elif input_id in _PALETTE_FIELD_MAP:
            config_key = _PALETTE_FIELD_MAP[input_id]
            self.config_data["output"]["style"]["palette"][config_key] = value
            self._update_swatch(f"swatch-{input_id}", value)

        elif input_id == "border-width":
            border = self.config_data["output"]["style"].get("border")
            if border is not None:
                with contextlib.suppress(ValueError):
                    border["width"] = float(value)

        elif input_id == "border-radius":
            border = self.config_data["output"]["style"].get("border")
            if border is not None:
                with contextlib.suppress(ValueError):
                    border["radius"] = float(value)

    def on_switch_changed(self, event: SkimSwitch.Changed) -> None:
        switch_id = event.switch.id or ""
        value = event.value

        if switch_id == "use-layer-colors":
            self.config_data["output"]["style"]["use_layer_colors_on_keys"] = value
        elif switch_id == "show-layer-indicators":
            self.config_data["output"]["style"]["show_layer_indicators"] = value
        elif switch_id == "show-layer-connectors":
            self.config_data["output"]["style"]["show_layer_connectors"] = value
        elif switch_id == "use-system-fonts":
            self.config_data["output"]["style"]["use_system_fonts"] = value
        elif switch_id == "border-enabled":
            if value:
                current = self.config_data["output"]["style"].get("border")
                if current is None:
                    self.config_data["output"]["style"]["border"] = {"width": 2.0, "radius": 10.0}
            else:
                self.config_data["output"]["style"]["border"] = None

    def on_select_changed(self, event: SkimSelect.Changed) -> None:
        if event.select.id == "hold-symbol-position" and event.value is not SkimSelect.BLANK:
            self.config_data["output"]["style"]["hold_symbol_position"] = str(event.value)
