# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Keycodes tab widget for the skim TUI configuration editor."""

import copy
import re
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.events import DescendantBlur
from textual.widget import Widget
from textual.widgets import Button, Input, Label, ListItem, ListView, Static

from skim.application.loaders.keycode_mappings_loader import load_keycode_mappings
from skim.application.loaders.nerdfont_glyphs_loader import load_nerdfont_glyphs
from skim.data.config import SkimConfig
from skim.domain.adapters.keycode_label_adapter import KeycodeLabelAdapter


class KeycodesTab(Widget):
    """Keycodes configuration tab.

    Shows two sections — Pre-process and Overrides — each using a
    list/detail split for editing individual keycode mapping entries.

    Detail fields are disabled until Enter is pressed on a list item.
    Enter in a field commits, Escape rolls back.
    """

    DEFAULT_CSS = """
    KeycodesTab {
        height: 1fr;
        padding: 0 1;
    }
    KeycodesTab .keycodes-section {
        height: 50%;
    }
    KeycodesTab .list-col {
        width: 50%;
        min-width: 25;
        height: 100%;
    }
    KeycodesTab .keycode-list {
        max-height: 100%;
        border: solid $accent 50%;
    }
    KeycodesTab .list-buttons {
        dock: bottom;
        height: auto;
        width: 100%;
    }
    KeycodesTab .list-buttons Button {
        width: 50%;
    }
    KeycodesTab .keycode-detail {
        padding: 0 1;
        height: auto;
        overflow-x: hidden;
        border: solid $accent 30%;
    }
    KeycodesTab .keycode-detail:focus-within {
        border: solid $accent;
    }
    """

    def __init__(self, config_data: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.config_data = config_data
        self._selected_pre_process: int = 0
        self._selected_override: int = 0
        self._editing_section: str | None = None  # "pre-process" or "override"
        self._snapshot: dict[str, str] | None = None
        self._refreshing: bool = False

    @staticmethod
    def _entry_text(entry: dict[str, str], keycode_width: int = 0) -> str:
        kc = entry.get("keycode", "")
        return f"{kc:<{keycode_width}}  ->  {entry.get('target', '')}"

    def _override_entry_text(self, entry: dict[str, str], keycode_width: int = 0) -> str:
        kc = entry.get("keycode", "")
        preview = self._resolve_override_preview(kc)
        return f"{kc:<{keycode_width}}  ->  {preview}"

    def _keycode_width(self, section: str) -> int:
        """Max keycode length across all entries in a section."""
        entries = self._entries_for(section)
        return max((len(e.get("keycode", "")) for e in entries), default=0)

    def _resolve_override_preview(self, keycode: str) -> str:
        """Resolve a keycode to its display label using current config."""
        if not keycode:
            return ""
        try:
            config = SkimConfig.model_validate(self.config_data)
            mappings = load_keycode_mappings(config.keycodes)
            adapter = KeycodeLabelAdapter(config.keyboard, mappings)
            result = adapter.transform(keycode)
            label = result.label
            # Resolve %%nf-xxx; tokens to actual Unicode glyphs
            glyphs = load_nerdfont_glyphs()

            def _replace_nf(match: re.Match) -> str:
                name = match.group(1)
                key = name if name.startswith("nf-") else f"nf-{name}"
                return glyphs.get(key, match.group(0))

            label = re.sub(r"%%([^;]+);", _replace_nf, label)
            return label
        except Exception:
            return keycode

    def compose(self) -> ComposeResult:
        # Pre-process section
        with Vertical(id="pre-process-section", classes="keycodes-section"):
            yield Static("Pre-process", classes="section-title section-title-first")
            with Horizontal():
                with Vertical(classes="list-col"):
                    yield ListView(id="pre-process-list", classes="keycode-list")
                    with Horizontal(classes="list-buttons"):
                        yield Button("+ Add (a)", id="add-pre-process", variant="success")
                        yield Button("- Delete (d)", id="remove-pre-process", variant="error")

                with VerticalScroll(id="pre-process-detail", classes="keycode-detail", can_focus=False):
                    with Horizontal(classes="field-row"):
                        yield Label("Keycode:", classes="field-label")
                        yield Input(
                            value="", id="pre-process-keycode",
                            placeholder="e.g. MKC_BKTAB", disabled=True,
                        )
                    with Horizontal(classes="field-row"):
                        yield Label("Target:", classes="field-label")
                        yield Input(
                            value="", id="pre-process-target",
                            placeholder="e.g. LSFT(KC_TAB)", disabled=True,
                        )

        # Overrides section
        with Vertical(id="overrides-section", classes="keycodes-section"):
            yield Static("Overrides", classes="section-title")
            with Horizontal():
                with Vertical(classes="list-col"):
                    yield ListView(id="overrides-list", classes="keycode-list")
                    with Horizontal(classes="list-buttons"):
                        yield Button("+ Add (a)", id="add-override", variant="success")
                        yield Button("- Delete (d)", id="remove-override", variant="error")

                with VerticalScroll(id="override-detail", classes="keycode-detail", can_focus=False):
                    with Horizontal(classes="field-row"):
                        yield Label("Keycode:", classes="field-label")
                        yield Input(
                            value="", id="override-keycode",
                            placeholder="e.g. KC_ESC", disabled=True,
                        )
                    with Horizontal(classes="field-row"):
                        yield Label("Target:", classes="field-label")
                        yield Input(
                            value="", id="override-target",
                            placeholder="e.g. ESC", disabled=True,
                        )
                    with Horizontal(classes="field-row"):
                        yield Label("Preview:", classes="field-label")
                        yield Input(
                            value="", id="override-preview",
                            placeholder="resolved label",
                            disabled=True,
                        )

    def on_mount(self) -> None:
        self._rebuild_pre_process_list()
        self._rebuild_overrides_list()
        if self.config_data.get("keycodes", {}).get("pre_process", []):
            self._selected_pre_process = 0
            self._refresh_fields("pre-process")
        if self.config_data.get("keycodes", {}).get("overrides", []):
            self._selected_override = 0
            self._refresh_fields("override")
        self._update_list_states()

    def _entries_for(self, section: str) -> list[dict[str, str]]:
        """Get the entries list for a section."""
        key = "pre_process" if section == "pre-process" else "overrides"
        return self.config_data.get("keycodes", {}).get(key, [])

    def _selected_for(self, section: str) -> int:
        return self._selected_pre_process if section == "pre-process" else self._selected_override

    def _set_selected(self, section: str, index: int) -> None:
        if section == "pre-process":
            self._selected_pre_process = index
        else:
            self._selected_override = index

    def _list_id(self, section: str) -> str:
        return "pre-process-list" if section == "pre-process" else "overrides-list"

    def _entry_text_for(self, section: str, entry: dict[str, str], keycode_width: int = 0) -> str:
        if section == "override":
            return self._override_entry_text(entry, keycode_width)
        return self._entry_text(entry, keycode_width)

    def _rebuild_list(self, section: str) -> None:
        entries = self._entries_for(section)
        kw = self._keycode_width(section)
        list_view = self.query_one(f"#{self._list_id(section)}", ListView)
        list_view.clear()
        for entry in entries:
            list_view.append(ListItem(Static(self._entry_text_for(section, entry, kw))))

    def _rebuild_pre_process_list(self) -> None:
        self._rebuild_list("pre-process")

    def _rebuild_overrides_list(self) -> None:
        self._rebuild_list("override")

    def _realign_all_items(self, section: str) -> None:
        """Update all list item texts in-place to align columns."""
        entries = self._entries_for(section)
        kw = self._keycode_width(section)
        list_view = self.query_one(f"#{self._list_id(section)}", ListView)
        for i, entry in enumerate(entries):
            if i < len(list_view.children):
                list_view.children[i].query_one(Static).update(
                    self._entry_text_for(section, entry, kw)
                )

    def _update_list_item(self, section: str) -> None:
        """Update the current item and realign all items in-place."""
        self._realign_all_items(section)

    def _update_list_states(self) -> None:
        """Update list focusability and Remove button state for both sections."""
        for section, remove_id in [("pre-process", "remove-pre-process"), ("override", "remove-override")]:
            entries = self._entries_for(section)
            has_entries = len(entries) > 0
            self.query_one(f"#{self._list_id(section)}", ListView).can_focus = has_entries
            self.query_one(f"#{remove_id}", Button).disabled = not has_entries

    def _set_fields_enabled(self, section: str, enabled: bool) -> None:
        self.query_one(f"#{section}-keycode", Input).disabled = not enabled
        self.query_one(f"#{section}-target", Input).disabled = not enabled

    def _refresh_fields(self, section: str) -> None:
        entries = self._entries_for(section)
        index = self._selected_for(section)
        if index >= len(entries):
            return
        entry = entries[index]
        self._refreshing = True
        self.query_one(f"#{section}-keycode", Input).value = entry.get("keycode", "") or ""
        self.query_one(f"#{section}-target", Input).value = entry.get("target", "") or ""
        if section == "override":
            self._update_override_preview()
        self._refreshing = False

    def _clear_fields(self, section: str) -> None:
        self._refreshing = True
        self.query_one(f"#{section}-keycode", Input).value = ""
        self.query_one(f"#{section}-target", Input).value = ""
        if section == "override":
            self.query_one("#override-preview", Input).value = ""
        self._refreshing = False

    def _update_override_preview(self) -> None:
        keycode = self.query_one("#override-keycode", Input).value
        self.query_one("#override-preview", Input).value = self._resolve_override_preview(keycode)

    def _enter_edit_mode(self, section: str) -> None:
        entries = self._entries_for(section)
        index = self._selected_for(section)
        if index >= len(entries):
            return
        self._editing_section = section
        self._snapshot = copy.deepcopy(entries[index])
        self._set_fields_enabled(section, True)
        self.query_one(f"#{section}-keycode", Input).focus()

    def _exit_edit_mode(self, commit: bool) -> None:
        section = self._editing_section
        if section is None:
            return
        if not commit and self._snapshot is not None:
            entries = self._entries_for(section)
            index = self._selected_for(section)
            if index < len(entries):
                entries[index] = self._snapshot
                self._refresh_fields(section)
                self._update_list_item(section)
        self._editing_section = None
        self._snapshot = None
        self._set_fields_enabled(section, False)
        self.query_one(f"#{self._list_id(section)}", ListView).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id

        if button_id == "add-pre-process":
            entries = self.config_data.setdefault("keycodes", {}).setdefault("pre_process", [])
            entries.append({"keycode": "", "target": ""})
            lv = self.query_one("#pre-process-list", ListView)
            kw = self._keycode_width("pre-process")
            lv.append(ListItem(Static(self._entry_text(entries[-1], kw))))
            self._selected_pre_process = len(entries) - 1
            self._refresh_fields("pre-process")
            lv.index = self._selected_pre_process
            self._update_list_states()
            self._enter_edit_mode("pre-process")

        elif button_id == "remove-pre-process":
            entries = self._entries_for("pre-process")
            if not entries or self._selected_pre_process >= len(entries):
                return
            entries.pop(self._selected_pre_process)
            self._rebuild_pre_process_list()
            if entries:
                self._selected_pre_process = min(self._selected_pre_process, len(entries) - 1)
                self._refresh_fields("pre-process")
                lv = self.query_one("#pre-process-list", ListView)
                self.call_after_refresh(setattr, lv, "index", self._selected_pre_process)
            else:
                self._selected_pre_process = 0
                self._clear_fields("pre-process")
            self._update_list_states()
            if not entries:
                self.query_one("#add-pre-process", Button).focus()

        elif button_id == "add-override":
            entries = self.config_data.setdefault("keycodes", {}).setdefault("overrides", [])
            entries.append({"keycode": "", "target": ""})
            lv = self.query_one("#overrides-list", ListView)
            kw = self._keycode_width("override")
            lv.append(ListItem(Static(self._override_entry_text(entries[-1], kw))))
            self._selected_override = len(entries) - 1
            self._refresh_fields("override")
            lv.index = self._selected_override
            self._update_list_states()
            self._enter_edit_mode("override")

        elif button_id == "remove-override":
            entries = self._entries_for("override")
            if not entries or self._selected_override >= len(entries):
                return
            entries.pop(self._selected_override)
            self._rebuild_overrides_list()
            if entries:
                self._selected_override = min(self._selected_override, len(entries) - 1)
                self._refresh_fields("override")
                lv = self.query_one("#overrides-list", ListView)
                self.call_after_refresh(setattr, lv, "index", self._selected_override)
            else:
                self._selected_override = 0
                self._clear_fields("override")
            self._update_list_states()
            if not entries:
                self.query_one("#add-override", Button).focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Enter pressed on a list item — enter edit mode."""
        if event.list_view.id == "pre-process-list":
            index = event.list_view.index
            if index is not None:
                self._selected_pre_process = index
                self._refresh_fields("pre-process")
                self._enter_edit_mode("pre-process")
        elif event.list_view.id == "overrides-list":
            index = event.list_view.index
            if index is not None:
                self._selected_override = index
                self._refresh_fields("override")
                self._enter_edit_mode("override")

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.list_view.id == "pre-process-list":
            index = event.list_view.index
            if index is not None:
                self._selected_pre_process = index
                self._refresh_fields("pre-process")
        elif event.list_view.id == "overrides-list":
            index = event.list_view.index
            if index is not None:
                self._selected_override = index
                self._refresh_fields("override")

    def on_key(self, event) -> None:
        """Handle Enter/Escape in edit mode, a/d shortcuts on lists."""
        if self._editing_section is not None:
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
        if isinstance(focused, ListView):
            if focused.id == "pre-process-list":
                add_id, remove_id = "add-pre-process", "remove-pre-process"
            elif focused.id == "overrides-list":
                add_id, remove_id = "add-override", "remove-override"
            else:
                return
            if event.key == "a":
                event.prevent_default()
                event.stop()
                self.query_one(f"#{add_id}", Button).press()
            elif event.key == "d":
                event.prevent_default()
                event.stop()
                self.query_one(f"#{remove_id}", Button).press()

    _EDITING_FIELD_IDS = {
        "pre-process-keycode", "pre-process-target",
        "override-keycode", "override-target", "override-preview",
    }

    def on_descendant_blur(self, event: DescendantBlur) -> None:
        """Commit edit when focus leaves the editing pane."""
        if self._editing_section is None:
            return
        self.set_timer(0.05, self._check_focus_commit)

    def _check_focus_commit(self) -> None:
        if self._editing_section is None:
            return
        focused = self.app.focused
        if focused is None or not isinstance(focused, Input) or focused.id not in self._EDITING_FIELD_IDS:
            self._exit_edit_mode(commit=True)

    def on_input_changed(self, event: Input.Changed) -> None:
        if self._refreshing:
            return
        input_id = event.input.id or ""

        if input_id.startswith("pre-process-"):
            field = input_id[len("pre-process-"):]
            entries = self._entries_for("pre-process")
            if self._selected_pre_process < len(entries):
                entries[self._selected_pre_process][field] = event.value
                self._update_list_item("pre-process")

        elif input_id.startswith("override-") and input_id != "override-preview":
            field = input_id[len("override-"):]
            entries = self._entries_for("override")
            if self._selected_override < len(entries):
                entries[self._selected_override][field] = event.value
                self._update_list_item("override")
                self._update_override_preview()
