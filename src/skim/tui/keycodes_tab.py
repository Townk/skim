# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Keycodes tab widget for the skim TUI configuration editor."""

import bisect
import re
from typing import Any

import yaml
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.content import Content
from textual.suggester import SuggestFromList
from textual.widget import Widget
from textual.widgets import Input, Label, Static
from textual_autocomplete import AutoComplete, DropdownItem, TargetState

from skim.application.loaders.keycode_mappings_loader import load_keycode_mappings
from skim.application.loaders.nerdfont_glyphs_loader import load_nerdfont_glyphs
from skim.assets import ASSETS
from skim.data.config import SkimConfig
from skim.domain import SEPARATOR_CHAR
from skim.domain.adapters.keycode_label_adapter import KeycodeLabelAdapter
from skim.tui.list_detail_pane import ListDetailPane
from skim.tui.widgets import SkimInput, SkimVerticalScroll


def _load_base_keycode_names() -> list[str]:
    """Load all keycode names and macro function names from the mappings YAML."""
    mapping = yaml.safe_load(ASSETS.keycode_mappings.read_text())
    names: set[str] = set()
    names.update(mapping.get("keycodes", {}).keys())
    for func_name in mapping.get("macro_functions", {}):
        names.add(f"{func_name}()")
    return sorted(names)


_BASE_KEYCODE_NAMES = _load_base_keycode_names()


def _all_keycode_names(config_data: dict[str, Any]) -> list[str]:
    """Return base keycodes merged with override keycodes from config."""
    names = set(_BASE_KEYCODE_NAMES)
    for entry in config_data.get("keycodes", {}).get("overrides", []):
        kc = entry.get("keycode", "")
        if kc:
            names.add(kc)
    return sorted(names)


def _make_keycode_candidates(config_data: dict[str, Any]):
    """Return a candidates callable that includes override keycodes."""

    def _candidates(state: TargetState) -> list[DropdownItem]:
        return [DropdownItem(main=name) for name in _all_keycode_names(config_data)]

    return _candidates


def _make_keycode_suggester(config_data: dict[str, Any]) -> SuggestFromList:
    """Return a suggester that includes override keycodes."""
    return SuggestFromList(_all_keycode_names(config_data), case_sensitive=False)


_NERDFONT_GLYPHS = load_nerdfont_glyphs()
_NERDFONT_NAMES = sorted(_NERDFONT_GLYPHS.keys())
# Items list aligned by index with _NERDFONT_NAMES for bisect lookups
_NERDFONT_ITEMS: list[DropdownItem] = [
    DropdownItem(
        main=Content.assemble(name, "  ", _NERDFONT_GLYPHS[name]),
    )
    for name in _NERDFONT_NAMES
]

_NERDFONT_MAX_RESULTS = 50


def _nerdfont_prefix_items(prefix: str) -> list[DropdownItem]:
    """Return up to _NERDFONT_MAX_RESULTS items whose name starts with prefix."""
    lo = bisect.bisect_left(_NERDFONT_NAMES, prefix)
    # Upper bound: increment the last character of prefix
    hi = bisect.bisect_left(_NERDFONT_NAMES, prefix[:-1] + chr(ord(prefix[-1]) + 1))
    return _NERDFONT_ITEMS[lo : min(hi, lo + _NERDFONT_MAX_RESULTS)]


_KEYCODE_SEPARATORS = frozenset("(,) ")
_KEYCODE_SHOW_AFTER = frozenset("(, ")


class KeycodeAutoComplete(AutoComplete):
    """Token-aware autocomplete for keycode/macro fields.

    Splits input on separator characters so autocomplete works inside
    macro arguments (e.g. ``LSFT(KC_SPC)``).  Macro completions like
    ``LSFT()`` are inserted as ``LSFT(`` so the user can continue
    filling in the argument.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._just_completed: bool = False

    @staticmethod
    def _token_start(text: str, cursor: int) -> int:
        """Return the start position of the current token at cursor."""
        for i in range(cursor - 1, -1, -1):
            if text[i] in _KEYCODE_SEPARATORS:
                return i + 1
        return 0

    def get_search_string(self, target_state: TargetState) -> str:
        start = self._token_start(target_state.text, target_state.cursor_position)
        return target_state.text[start : target_state.cursor_position]

    def apply_completion(self, value: str, state: TargetState) -> None:
        start = self._token_start(state.text, state.cursor_position)
        # For macros ending with (), insert only the opening paren
        if value.endswith("()"):
            value = value[:-1]
        before = state.text[:start]
        after = state.text[state.cursor_position :]
        self.target.value = f"{before}{value}{after}"
        self.target.cursor_position = start + len(value)

    def should_show_dropdown(self, search_string: str) -> bool:
        option_list = self.option_list
        if option_list.option_count == 0:
            return False
        if not search_string:
            # Show all candidates right after a separator like ( or ,
            state = self._get_target_state()
            before = state.text[: state.cursor_position]
            return bool(before) and before[-1] in _KEYCODE_SHOW_AFTER
        if option_list.option_count <= 1:
            return False
        return super().should_show_dropdown(search_string)

    def post_completion(self) -> None:
        self._just_completed = True
        super().post_completion()
        self.target.post_message(Input.Changed(self.target, self.target.value))

    def _handle_target_update(self) -> None:
        if self._just_completed:
            self._just_completed = False
            # After completing a macro (cursor right after a separator),
            # re-show the dropdown for the argument
            state = self._get_target_state()
            before = state.text[: state.cursor_position]
            if before and before[-1] in _KEYCODE_SHOW_AFTER:
                super()._handle_target_update()
                return
            return
        super()._handle_target_update()


def _find_active_prefix(text: str, cursor: int) -> tuple[str, int] | None:
    """Find an active @@ or %% prefix at the cursor position.

    Scans backwards from the cursor to find the nearest ``@@`` or ``%%``
    that does not have a closing ``;`` between it and the cursor.

    Returns:
        A tuple of (prefix_marker, prefix_start_index) or None.
    """
    before = text[:cursor]
    for marker in ("@@", "%%"):
        pos = before.rfind(marker)
        if pos == -1:
            continue
        # Check there's no closing ';' between the marker and cursor
        between = before[pos + len(marker) :]
        if ";" not in between:
            return marker, pos
    return None


class OverrideTargetAutoComplete(AutoComplete):
    """Context-aware autocomplete for the Override Target field.

    Detects ``@@`` (keycode reference) and ``%%`` (NerdFont glyph) prefixes
    at the cursor position and provides appropriate candidates.
    On completion, inserts the value with a trailing ``;``.
    """

    def __init__(self, target: Input, config_data: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(target, candidates=None, **kwargs)
        self._config_data = config_data
        self._just_completed: bool = False

    def get_search_string(self, target_state: TargetState) -> str:
        result = _find_active_prefix(target_state.text, target_state.cursor_position)
        if result is None:
            return ""
        marker, pos = result
        return target_state.text[pos + len(marker) : target_state.cursor_position]

    def get_candidates(self, target_state: TargetState) -> list[DropdownItem]:
        result = _find_active_prefix(target_state.text, target_state.cursor_position)
        if result is None:
            return []
        marker, pos = result
        if marker == "@@":
            return [DropdownItem(main=name) for name in _all_keycode_names(self._config_data)]
        # %% — use prefix lookup on the sorted names list
        search = target_state.text[pos + len(marker) : target_state.cursor_position]
        if not search:
            return _NERDFONT_ITEMS[:_NERDFONT_MAX_RESULTS]
        return _nerdfont_prefix_items(search)

    def apply_completion(self, value: str, state: TargetState) -> None:
        result = _find_active_prefix(state.text, state.cursor_position)
        if result is None:
            return
        marker, pos = result
        # For NerdFont items, extract just the name (before the glyph preview)
        if marker == "%%":
            value = value.split()[0] if value.strip() else value
        before = state.text[:pos]
        after = state.text[state.cursor_position :]
        completed = f"{before}{marker}{value};{after}"
        self.target.value = completed
        self.target.cursor_position = pos + len(marker) + len(value) + 1  # after ';'

    def should_show_dropdown(self, search_string: str) -> bool:
        # Show dropdown as soon as @@ or %% is typed (even with empty search)
        state = self._get_target_state()
        if not search_string and _find_active_prefix(state.text, state.cursor_position) is None:
            return False
        option_list = self.option_list
        if option_list.option_count == 0:
            return False
        if option_list.option_count == 1:
            first_option = option_list.get_option_at_index(0).prompt
            plain = first_option.plain if hasattr(first_option, "plain") else str(first_option)  # type: ignore[union-attr]
            if plain.split()[0] == search_string:
                return False
        return True

    def post_completion(self) -> None:
        self._just_completed = True
        super().post_completion()
        self.target.post_message(Input.Changed(self.target, self.target.value))

    def _handle_target_update(self) -> None:
        if self._just_completed:
            self._just_completed = False
            return
        super()._handle_target_update()


class PreProcessListPane(ListDetailPane):
    """List/detail pane for pre-process keycode entries."""

    def __init__(self, config_data: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(pane_id="pre-process", list_help_key="keycodes-pre-proc-list", **kwargs)
        self.config_data = config_data
        self._refreshing: bool = False

    def get_entries(self) -> list[dict]:
        return self.config_data.get("keycodes", {}).get("pre_process", [])

    def format_entry(self, index: int, entry: dict) -> str:
        entries = self.get_entries()
        kw = max((len(e.get("keycode", "")) for e in entries), default=0)
        kc = entry.get("keycode", "")
        return f"{kc:<{kw}}  ->  {entry.get('target', '')}"

    def _resolve_target_preview(self, target: str) -> str:
        """Resolve a target keycode to its display label."""
        if not target:
            return ""
        try:
            config = SkimConfig.model_validate(self.config_data)
            mappings = load_keycode_mappings(config.keycodes)
            adapter = KeycodeLabelAdapter(config.keyboard, mappings)
            result = adapter.transform(target)
            label: str = (result.label or target).replace(SEPARATOR_CHAR, " | ")
            glyphs = load_nerdfont_glyphs()

            def _replace_nf(match: re.Match) -> str:
                name = match.group(1)
                key = name if name.startswith("nf-") else f"nf-{name}"
                return glyphs.get(key, match.group(0) or "")

            label = re.sub(r"%%([^;]+);", _replace_nf, label)
            return label
        except Exception:
            return target or ""

    def compose_detail_fields(self) -> ComposeResult:
        suggester = _make_keycode_suggester(self.config_data)
        candidates = _make_keycode_candidates(self.config_data)
        with Horizontal(classes="field-row"):
            yield Label("Keycode:", classes="field-label")
            pp_kc_input = SkimInput(
                value="",
                id="pre-process-keycode",
                placeholder="e.g. MKC_BKTAB",
                disabled=True,
                suggester=suggester,
                help_key="keycodes-pre-proc-keycode",
            )
            yield pp_kc_input
        yield KeycodeAutoComplete(pp_kc_input, candidates=candidates)
        with Horizontal(classes="field-row"):
            yield Label("Target:", classes="field-label")
            pp_tg_input = SkimInput(
                value="",
                id="pre-process-target",
                placeholder="e.g. LSFT(KC_TAB)",
                disabled=True,
                suggester=suggester,
                help_key="keycodes-pre-proc-target",
            )
            yield pp_tg_input
        yield KeycodeAutoComplete(pp_tg_input, candidates=candidates)
        with Horizontal(classes="field-row"):
            yield Label("Preview:", classes="field-label")
            yield SkimInput(
                value="",
                id="pre-process-preview",
                placeholder="resolved label",
                disabled=True,
            )

    def detail_field_ids(self) -> set[str]:
        return {"pre-process-keycode", "pre-process-target"}

    def refresh_fields(self, entry: dict) -> None:
        self._refreshing = True
        self.query_one("#pre-process-keycode", Input).value = entry.get("keycode", "") or ""
        self.query_one("#pre-process-target", Input).value = entry.get("target", "") or ""
        self._update_target_preview()
        self._refreshing = False

    def clear_fields(self) -> None:
        self._refreshing = True
        self.query_one("#pre-process-keycode", Input).value = ""
        self.query_one("#pre-process-target", Input).value = ""
        self.query_one("#pre-process-preview", Input).value = ""
        self._refreshing = False

    def create_entry(self, index: int) -> dict:
        return {"keycode": "", "target": ""}

    def _update_target_preview(self) -> None:
        target = self.query_one("#pre-process-target", Input).value
        self.query_one("#pre-process-preview", Input).value = self._resolve_target_preview(target)

    def _check_focus_commit(self) -> None:
        """Override to keep editing when preview field is focused."""
        if not self._editing:
            return
        focused = self.app.focused
        all_fields = self.detail_field_ids() | {"pre-process-preview"}
        if focused is None or not isinstance(focused, Input) or focused.id not in all_fields:
            self._exit_edit_mode(commit=True)

    def on_input_changed(self, event: Input.Changed) -> None:
        if self._refreshing:
            return
        input_id = event.input.id or ""
        if input_id.startswith("pre-process-") and input_id != "pre-process-preview":
            field = input_id[len("pre-process-") :]
            entries = self.get_entries()
            if self._selected < len(entries):
                entries[self._selected][field] = event.value
                self.update_all_list_items()
                if input_id == "pre-process-target":
                    self._update_target_preview()


class OverrideListPane(ListDetailPane):
    """List/detail pane for override keycode entries."""

    def __init__(self, config_data: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(pane_id="override", list_help_key="keycodes-override-list", **kwargs)
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
            label: str = result.label or keycode
            glyphs = load_nerdfont_glyphs()

            def _replace_nf(match: re.Match) -> str:
                name = match.group(1)
                key = name if name.startswith("nf-") else f"nf-{name}"
                return glyphs.get(key, match.group(0) or "")

            label = re.sub(r"%%([^;]+);", _replace_nf, label)
            return label
        except Exception:
            return keycode or ""

    def format_entry(self, index: int, entry: dict) -> str:
        entries = self.get_entries()
        kw = max((len(e.get("keycode", "")) for e in entries), default=0)
        kc = entry.get("keycode", "")
        preview = self._resolve_override_preview(kc)
        return f"{kc:<{kw}}  ->  {preview}"

    def compose_detail_fields(self) -> ComposeResult:
        suggester = _make_keycode_suggester(self.config_data)
        candidates = _make_keycode_candidates(self.config_data)
        with Horizontal(classes="field-row"):
            yield Label("Keycode:", classes="field-label")
            ov_kc_input = SkimInput(
                value="",
                id="override-keycode",
                placeholder="e.g. KC_ESC",
                disabled=True,
                suggester=suggester,
                help_key="keycodes-override-keycode",
            )
            yield ov_kc_input
        yield KeycodeAutoComplete(ov_kc_input, candidates=candidates)
        with Horizontal(classes="field-row"):
            yield Label("Target:", classes="field-label")
            ov_tg_input = SkimInput(
                value="",
                id="override-target",
                placeholder="e.g. @@KC_ESC; or %%nf-md-icon;",
                disabled=True,
                help_key="keycodes-override-target",
            )
            yield ov_tg_input
        yield OverrideTargetAutoComplete(ov_tg_input, config_data=self.config_data)
        with Horizontal(classes="field-row"):
            yield Label("Preview:", classes="field-label")
            yield SkimInput(
                value="",
                id="override-preview",
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
            field = input_id[len("override-") :]
            entries = self.get_entries()
            if self._selected < len(entries):
                entries[self._selected][field] = event.value
                self.update_all_list_items()
                self._update_override_preview()


class MacroListPane(ListDetailPane):
    """List/detail pane for macro definitions."""

    def __init__(self, config_data: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(pane_id="macro", list_help_key="keycodes-macro-list", **kwargs)
        self.config_data = config_data
        self._refreshing: bool = False

    def get_entries(self) -> list[dict]:
        return self.config_data.get("keycodes", {}).get("macros", [])

    def format_entry(self, index: int, entry: dict) -> str:
        entries = self.get_entries()
        idw = max((len(e.get("id", "") or "") for e in entries), default=0)
        id_ = entry.get("id", "") or ""
        label = entry.get("name") or entry.get("preview", "") or ""
        return f"{id_:<{idw}}  ->  {label}"

    def _resolve_preview(self, raw: str) -> str:
        """Resolve NerdFont markers in a preview string for display."""
        if not raw:
            return ""
        glyphs = load_nerdfont_glyphs()

        def _replace_nf(match: re.Match) -> str:
            name = match.group(1)
            key = name if name.startswith("nf-") else f"nf-{name}"
            return glyphs.get(key, match.group(0) or "")

        return re.sub(r"%%([^;]+);", _replace_nf, raw)

    def compose_detail_fields(self) -> ComposeResult:
        with Horizontal(classes="field-row"):
            yield Label("ID:", classes="field-label")
            yield SkimInput(
                value="",
                id="macro-id",
                placeholder="e.g. 0",
                disabled=True,
                help_key="keycodes-macro-id",
            )
        with Horizontal(classes="field-row"):
            yield Label("Name:", classes="field-label")
            yield SkimInput(
                value="",
                id="macro-name",
                placeholder="e.g. Em-dash",
                disabled=True,
                help_key="keycodes-macro-name",
            )
        with Horizontal(classes="field-row"):
            yield Label("Preview:", classes="field-label")
            yield SkimInput(
                value="",
                id="macro-preview",
                placeholder="resolved preview",
                disabled=True,
            )

    def detail_field_ids(self) -> set[str]:
        return {"macro-id", "macro-name"}

    def refresh_fields(self, entry: dict) -> None:
        self._refreshing = True
        self.query_one("#macro-id", Input).value = entry.get("id", "") or ""
        self.query_one("#macro-name", Input).value = entry.get("name", "") or ""
        self.query_one("#macro-preview", Input).value = self._resolve_preview(
            entry.get("preview", "") or ""
        )
        self._refreshing = False

    def clear_fields(self) -> None:
        self._refreshing = True
        self.query_one("#macro-id", Input).value = ""
        self.query_one("#macro-name", Input).value = ""
        self.query_one("#macro-preview", Input).value = ""
        self._refreshing = False

    def create_entry(self, index: int) -> dict:
        entries = self.get_entries()
        used = {e.get("id", "") or "" for e in entries}
        candidate = 0
        while str(candidate) in used:
            candidate += 1
        return {"id": str(candidate), "name": None, "preview": "Undefined"}

    def validate_and_apply(self, entry: dict) -> bool:
        new_id = (self.query_one("#macro-id", Input).value or "").strip()
        if not new_id:
            self._revert_and_show_error("Macro ID cannot be empty.")
            return False
        entries = self.get_entries()
        for i, other in enumerate(entries):
            if i == self._selected:
                continue
            if (other.get("id", "") or "") == new_id:
                self._revert_and_show_error(f"Macro ID '{new_id}' is already used.")
                return False
        entry["id"] = new_id
        entry["name"] = (self.query_one("#macro-name", Input).value or "").strip() or None
        return True

    def _enter_edit_mode(self) -> None:
        """Override to refresh fields from the selected entry before entering edit mode."""
        entries = self.get_entries()
        if self._selected < len(entries):
            self.refresh_fields(entries[self._selected])
        super()._enter_edit_mode()

    def _check_focus_commit(self) -> None:
        """Override to keep editing while preview field is focused."""
        if not self._editing:
            return
        focused = self.app.focused
        all_fields = self.detail_field_ids() | {"macro-preview"}
        if focused is None or not isinstance(focused, Input) or focused.id not in all_fields:
            self._exit_edit_mode(commit=True)

    def on_input_changed(self, event: Input.Changed) -> None:
        if self._refreshing:
            return
        input_id = event.input.id or ""
        if input_id == "macro-id":
            entries = self.get_entries()
            if self._selected < len(entries):
                entries[self._selected]["id"] = event.value
                self.update_all_list_items()
        elif input_id == "macro-name":
            entries = self.get_entries()
            if self._selected < len(entries):
                entries[self._selected]["name"] = event.value or None
                self.update_all_list_items()


class TapDanceListPane(ListDetailPane):
    """List/detail pane for tap-dance definitions."""

    def __init__(self, config_data: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(pane_id="tap-dance", list_help_key="keycodes-tap-dance-list", **kwargs)
        self.config_data = config_data
        self._refreshing: bool = False

    def get_entries(self) -> list[dict]:
        return self.config_data.get("keycodes", {}).get("tap_dances", [])

    def format_entry(self, index: int, entry: dict) -> str:
        entries = self.get_entries()
        idw = max((len(e.get("id", "") or "") for e in entries), default=0)
        id_ = entry.get("id", "") or ""
        label = entry.get("name") or entry.get("preview", "") or ""
        return f"{id_:<{idw}}  ->  {label}"

    def _resolve_preview(self, raw: str) -> str:
        """Resolve NerdFont markers in a preview string for display."""
        if not raw:
            return ""
        glyphs = load_nerdfont_glyphs()

        def _replace_nf(match: re.Match) -> str:
            name = match.group(1)
            key = name if name.startswith("nf-") else f"nf-{name}"
            return glyphs.get(key, match.group(0) or "")

        return re.sub(r"%%([^;]+);", _replace_nf, raw)

    def compose_detail_fields(self) -> ComposeResult:
        with Horizontal(classes="field-row"):
            yield Label("ID:", classes="field-label")
            yield SkimInput(
                value="",
                id="tap-dance-id",
                placeholder="e.g. 0",
                disabled=True,
                help_key="keycodes-tap-dance-id",
            )
        with Horizontal(classes="field-row"):
            yield Label("Name:", classes="field-label")
            yield SkimInput(
                value="",
                id="tap-dance-name",
                placeholder="e.g. Quick shift",
                disabled=True,
                help_key="keycodes-tap-dance-name",
            )
        with Horizontal(classes="field-row"):
            yield Label("Preview:", classes="field-label")
            yield SkimInput(
                value="",
                id="tap-dance-preview",
                placeholder="resolved preview",
                disabled=True,
            )

    def detail_field_ids(self) -> set[str]:
        return {"tap-dance-id", "tap-dance-name"}

    def refresh_fields(self, entry: dict) -> None:
        self._refreshing = True
        self.query_one("#tap-dance-id", Input).value = entry.get("id", "") or ""
        self.query_one("#tap-dance-name", Input).value = entry.get("name", "") or ""
        self.query_one("#tap-dance-preview", Input).value = self._resolve_preview(
            entry.get("preview", "") or ""
        )
        self._refreshing = False

    def clear_fields(self) -> None:
        self._refreshing = True
        self.query_one("#tap-dance-id", Input).value = ""
        self.query_one("#tap-dance-name", Input).value = ""
        self.query_one("#tap-dance-preview", Input).value = ""
        self._refreshing = False

    def create_entry(self, index: int) -> dict:
        entries = self.get_entries()
        used = {e.get("id", "") or "" for e in entries}
        candidate = 0
        while str(candidate) in used:
            candidate += 1
        return {"id": str(candidate), "name": None, "preview": "Undefined"}

    def validate_and_apply(self, entry: dict) -> bool:
        new_id = (self.query_one("#tap-dance-id", Input).value or "").strip()
        if not new_id:
            self._revert_and_show_error("Tap-dance ID cannot be empty.")
            return False
        entries = self.get_entries()
        for i, other in enumerate(entries):
            if i == self._selected:
                continue
            if (other.get("id", "") or "") == new_id:
                self._revert_and_show_error(f"Tap-dance ID '{new_id}' is already used.")
                return False
        entry["id"] = new_id
        entry["name"] = (self.query_one("#tap-dance-name", Input).value or "").strip() or None
        return True

    def _enter_edit_mode(self) -> None:
        """Refresh fields from the selected entry, then enter edit mode.

        Mirrors MacroListPane: ensures the input widgets reflect the
        currently-selected entry even when ``_selected`` is set
        programmatically (e.g. in unit tests) without going through the
        list-view event flow.
        """
        entries = self.get_entries()
        if 0 <= self._selected < len(entries):
            self.refresh_fields(entries[self._selected])
        super()._enter_edit_mode()

    def _check_focus_commit(self) -> None:
        if not self._editing:
            return
        focused = self.app.focused
        all_fields = self.detail_field_ids() | {"tap-dance-preview"}
        if focused is None or not isinstance(focused, Input) or focused.id not in all_fields:
            self._exit_edit_mode(commit=True)

    def on_input_changed(self, event: Input.Changed) -> None:
        if self._refreshing:
            return
        input_id = event.input.id or ""
        if input_id == "tap-dance-id":
            entries = self.get_entries()
            if self._selected < len(entries):
                entries[self._selected]["id"] = event.value
                self.update_all_list_items()
        elif input_id == "tap-dance-name":
            entries = self.get_entries()
            if self._selected < len(entries):
                entries[self._selected]["name"] = event.value or None
                self.update_all_list_items()


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
    KeycodesTab .keycodes-section ListDetailPane .ldp-container {
        height: 100%;
    }
    KeycodesTab .keycodes-section ListDetailPane .ldp-list-col {
        width: 35%;
        min-width: 25;
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
        with SkimVerticalScroll(can_focus=False):
            with Vertical(id="pre-process-section", classes="keycodes-section"):
                yield Static("Pre-process", classes="section-title section-title-first")
                yield PreProcessListPane(config_data=self.config_data)

            with Vertical(id="overrides-section", classes="keycodes-section"):
                yield Static("Overrides", classes="section-title")
                yield OverrideListPane(config_data=self.config_data)

            with Vertical(id="macros-section", classes="keycodes-section"):
                yield Static("Macros", classes="section-title")
                yield MacroListPane(config_data=self.config_data)

            with Vertical(id="tap-dances-section", classes="keycodes-section"):
                yield Static("Tap-dances", classes="section-title")
                yield TapDanceListPane(config_data=self.config_data)

    def on_mount(self) -> None:
        for pane_cls in (
            PreProcessListPane,
            OverrideListPane,
            MacroListPane,
            TapDanceListPane,
        ):
            pane = self.query_one(pane_cls)
            pane.rebuild_list()
            entries = pane.get_entries()
            if entries:
                pane._selected = 0
                pane.refresh_fields(entries[0])
            pane._update_list_state()

    # Compatibility: expose _enter_edit_mode and _exit_edit_mode for tests
    def _enter_edit_mode(self, section: str) -> None:
        mapping = {
            "pre-process": PreProcessListPane,
            "override": OverrideListPane,
            "macro": MacroListPane,
            "tap-dance": TapDanceListPane,
        }
        pane_cls = mapping.get(section)
        if pane_cls is not None:
            self.query_one(pane_cls)._enter_edit_mode()

    def _exit_edit_mode(self, commit: bool) -> None:
        """Exit edit mode on whichever pane is currently editing."""
        for pane_cls in (
            PreProcessListPane,
            OverrideListPane,
            MacroListPane,
            TapDanceListPane,
        ):
            pane = self.query_one(pane_cls)
            if pane._editing:
                pane._exit_edit_mode(commit=commit)
                return
