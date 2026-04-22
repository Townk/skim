# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Keycodes tab widget for the skim TUI configuration editor."""

import re
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Input, Label, Static

from skim.application.loaders.keycode_mappings_loader import load_keycode_mappings
from skim.application.loaders.nerdfont_glyphs_loader import load_nerdfont_glyphs
from skim.data.config import SkimConfig
from skim.domain.adapters.keycode_label_adapter import KeycodeLabelAdapter
from skim.tui.list_detail_pane import ListDetailPane
from skim.tui.widgets import SkimInput


class PreProcessListPane(ListDetailPane):
    """List/detail pane for pre-process keycode entries."""

    def __init__(self, config_data: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(pane_id="pre-process", **kwargs)
        self.config_data = config_data

    def get_entries(self) -> list[dict]:
        return self.config_data.get("keycodes", {}).get("pre_process", [])

    def format_entry(self, index: int, entry: dict) -> str:
        entries = self.get_entries()
        kw = max((len(e.get("keycode", "")) for e in entries), default=0)
        kc = entry.get("keycode", "")
        return f"{kc:<{kw}}  ->  {entry.get('target', '')}"

    def compose_detail_fields(self) -> ComposeResult:
        with Horizontal(classes="field-row"):
            yield Label("Keycode:", classes="field-label")
            yield SkimInput(
                value="", id="pre-process-keycode",
                placeholder="e.g. MKC_BKTAB", disabled=True,
            )
        with Horizontal(classes="field-row"):
            yield Label("Target:", classes="field-label")
            yield SkimInput(
                value="", id="pre-process-target",
                placeholder="e.g. LSFT(KC_TAB)", disabled=True,
            )

    def detail_field_ids(self) -> set[str]:
        return {"pre-process-keycode", "pre-process-target"}

    def refresh_fields(self, entry: dict) -> None:
        self.query_one("#pre-process-keycode", Input).value = entry.get("keycode", "") or ""
        self.query_one("#pre-process-target", Input).value = entry.get("target", "") or ""

    def clear_fields(self) -> None:
        self.query_one("#pre-process-keycode", Input).value = ""
        self.query_one("#pre-process-target", Input).value = ""

    def create_entry(self, index: int) -> dict:
        return {"keycode": "", "target": ""}

    def on_input_changed(self, event: Input.Changed) -> None:
        input_id = event.input.id or ""
        if input_id.startswith("pre-process-"):
            field = input_id[len("pre-process-"):]
            entries = self.get_entries()
            if self._selected < len(entries):
                entries[self._selected][field] = event.value
                self.update_all_list_items()


class OverrideListPane(ListDetailPane):
    """List/detail pane for override keycode entries."""

    def __init__(self, config_data: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(pane_id="override", **kwargs)
        self.config_data = config_data
        self._refreshing: bool = False

    def get_entries(self) -> list[dict]:
        return self.config_data.get("keycodes", {}).get("overrides", [])

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
            glyphs = load_nerdfont_glyphs()

            def _replace_nf(match: re.Match) -> str:
                name = match.group(1)
                key = name if name.startswith("nf-") else f"nf-{name}"
                return glyphs.get(key, match.group(0))

            label = re.sub(r"%%([^;]+);", _replace_nf, label)
            return label
        except Exception:
            return keycode

    def format_entry(self, index: int, entry: dict) -> str:
        entries = self.get_entries()
        kw = max((len(e.get("keycode", "")) for e in entries), default=0)
        kc = entry.get("keycode", "")
        preview = self._resolve_override_preview(kc)
        return f"{kc:<{kw}}  ->  {preview}"

    def compose_detail_fields(self) -> ComposeResult:
        with Horizontal(classes="field-row"):
            yield Label("Keycode:", classes="field-label")
            yield SkimInput(
                value="", id="override-keycode",
                placeholder="e.g. KC_ESC", disabled=True,
            )
        with Horizontal(classes="field-row"):
            yield Label("Target:", classes="field-label")
            yield SkimInput(
                value="", id="override-target",
                placeholder="e.g. ESC", disabled=True,
            )
        with Horizontal(classes="field-row"):
            yield Label("Preview:", classes="field-label")
            yield SkimInput(
                value="", id="override-preview",
                placeholder="resolved label",
                disabled=True,
            )

    def detail_field_ids(self) -> set[str]:
        return {"override-keycode", "override-target"}

    def refresh_fields(self, entry: dict) -> None:
        self._refreshing = True
        self.query_one("#override-keycode", Input).value = entry.get("keycode", "") or ""
        self.query_one("#override-target", Input).value = entry.get("target", "") or ""
        self._update_override_preview()
        self._refreshing = False

    def clear_fields(self) -> None:
        self._refreshing = True
        self.query_one("#override-keycode", Input).value = ""
        self.query_one("#override-target", Input).value = ""
        self.query_one("#override-preview", Input).value = ""
        self._refreshing = False

    def create_entry(self, index: int) -> dict:
        return {"keycode": "", "target": ""}

    def _update_override_preview(self) -> None:
        keycode = self.query_one("#override-keycode", Input).value
        self.query_one("#override-preview", Input).value = self._resolve_override_preview(keycode)

    def _check_focus_commit(self) -> None:
        """Override to also keep editing when preview field is focused."""
        if not self._editing:
            return
        focused = self.app.focused
        all_fields = self.detail_field_ids() | {"override-preview"}
        if focused is None or not isinstance(focused, Input) or focused.id not in all_fields:
            self._exit_edit_mode(commit=True)

    def on_input_changed(self, event: Input.Changed) -> None:
        if self._refreshing:
            return
        input_id = event.input.id or ""
        if input_id.startswith("override-") and input_id != "override-preview":
            field = input_id[len("override-"):]
            entries = self.get_entries()
            if self._selected < len(entries):
                entries[self._selected][field] = event.value
                self.update_all_list_items()
                self._update_override_preview()


class KeycodesTab(Widget):
    """Keycodes configuration tab.

    Shows two sections -- Pre-process and Overrides -- each using a
    ListDetailPane subclass for editing individual keycode mapping entries.
    """

    DEFAULT_CSS = """
    KeycodesTab {
        height: 1fr;
        padding: 0 1;
    }
    KeycodesTab .keycodes-section {
        height: 1fr;
    }
    KeycodesTab .keycodes-section ListDetailPane {
        height: 1fr;
    }
    KeycodesTab .keycodes-section ListDetailPane .ldp-list-col {
        width: 50%;
        min-width: 25;
        height: 100%;
    }
    KeycodesTab .keycodes-section ListDetailPane .ldp-list {
        height: 1fr;
        border: solid $accent 50%;
    }
    KeycodesTab .keycodes-section ListDetailPane .ldp-detail {
        padding: 0 1;
        height: auto;
        overflow-x: hidden;
        border: solid $accent 30%;
    }
    KeycodesTab .keycodes-section ListDetailPane .ldp-detail:focus-within {
        border: solid $accent;
    }
    """

    def __init__(self, config_data: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.config_data = config_data

    def compose(self) -> ComposeResult:
        with Vertical(id="pre-process-section", classes="keycodes-section"):
            yield Static("Pre-process", classes="section-title section-title-first")
            yield PreProcessListPane(config_data=self.config_data)

        with Vertical(id="overrides-section", classes="keycodes-section"):
            yield Static("Overrides", classes="section-title")
            yield OverrideListPane(config_data=self.config_data)

    def on_mount(self) -> None:
        pp_pane = self.query_one(PreProcessListPane)
        pp_pane.rebuild_list()
        pp_entries = pp_pane.get_entries()
        if pp_entries:
            pp_pane._selected = 0
            pp_pane.refresh_fields(pp_entries[0])
        pp_pane._update_list_state()

        ov_pane = self.query_one(OverrideListPane)
        ov_pane.rebuild_list()
        ov_entries = ov_pane.get_entries()
        if ov_entries:
            ov_pane._selected = 0
            ov_pane.refresh_fields(ov_entries[0])
        ov_pane._update_list_state()

    # Compatibility: expose _enter_edit_mode and _exit_edit_mode for tests
    def _enter_edit_mode(self, section: str) -> None:
        if section == "pre-process":
            self.query_one(PreProcessListPane)._enter_edit_mode()
        elif section == "override":
            self.query_one(OverrideListPane)._enter_edit_mode()

    def _exit_edit_mode(self, commit: bool) -> None:
        """Exit edit mode on whichever pane is currently editing."""
        pp_pane = self.query_one(PreProcessListPane)
        ov_pane = self.query_one(OverrideListPane)
        if pp_pane._editing:
            pp_pane._exit_edit_mode(commit=commit)
        elif ov_pane._editing:
            ov_pane._exit_edit_mode(commit=commit)
