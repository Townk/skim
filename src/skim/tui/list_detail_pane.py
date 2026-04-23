# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Reusable list/detail pane base class for the skim TUI."""

from __future__ import annotations

import contextlib
import copy
from abc import abstractmethod
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import DescendantBlur
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Input, ListItem, Static

from skim.tui.widgets import SkimButton, SkimListView


class ListDetailPane(Widget):
    """Base class for a list/detail split pane.

    Provides: horizontal layout with a list column (35%) and a detail pane,
    edit mode lifecycle (enter/exit/commit/cancel), snapshot/rollback,
    focus-out commit, and key handling (Enter/Escape/a/d).

    Subclasses implement the abstract methods to supply data and fields.
    """

    DEFAULT_CSS = """
    ListDetailPane {
        height: auto;
    }
    ListDetailPane .ldp-container {
        height: auto;
    }
    ListDetailPane .ldp-list-col {
        width: 35%;
        min-width: 25;
        height: 100%;
    }
    ListDetailPane .ldp-list {
        height: 1fr;
        border: solid $accent 50%;
    }
    ListDetailPane .ldp-buttons {
        height: auto;
        width: 100%;
    }
    ListDetailPane .ldp-buttons Button {
        width: 50%;
    }
    ListDetailPane .ldp-detail {
        padding: 0 1;
        height: auto;
        overflow-x: hidden;
        border: solid $accent 30%;
    }
    ListDetailPane .ldp-detail:focus-within {
        border: solid $accent;
    }
    """

    class EntryAdded(Message):
        """Posted after an entry is added."""

        def __init__(self, index: int) -> None:
            super().__init__()
            self.index = index

    class EntryRemoved(Message):
        """Posted after an entry is removed."""

        def __init__(self, index: int) -> None:
            super().__init__()
            self.index = index

    class EntryUpdated(Message):
        """Posted after a successful commit."""

    def __init__(self, pane_id: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.pane_id = pane_id
        self._selected: int = 0
        self._editing: bool = False
        self._snapshot: dict | None = None
        self._adding: bool = False

    def compose(self) -> ComposeResult:
        with Horizontal(classes="ldp-container"):
            with Vertical(classes="ldp-list-col"):
                yield SkimListView(id=f"{self.pane_id}-list", classes="ldp-list")
                with Horizontal(classes="ldp-buttons"):
                    yield SkimButton("+ Add (a)", id=f"{self.pane_id}-add", variant="success")
                    yield SkimButton("- Delete (d)", id=f"{self.pane_id}-remove", variant="error")
            with Vertical(id=f"{self.pane_id}-detail", classes="ldp-detail"):
                yield from self.compose_detail_fields()

    # ------------------------------------------------------------------
    # Abstract methods
    # ------------------------------------------------------------------

    @abstractmethod
    def get_entries(self) -> list[dict]:
        """Return the mutable list of data entries."""

    @abstractmethod
    def format_entry(self, index: int, entry: dict) -> str:
        """Format entry text for the list display."""

    @abstractmethod
    def compose_detail_fields(self) -> ComposeResult:
        """Yield the detail field widgets."""

    @abstractmethod
    def detail_field_ids(self) -> set[str]:
        """Return the set of Input IDs in the detail pane."""

    @abstractmethod
    def refresh_fields(self, entry: dict) -> None:
        """Populate fields from entry data."""

    @abstractmethod
    def clear_fields(self) -> None:
        """Clear all fields."""

    @abstractmethod
    def create_entry(self, index: int) -> dict:
        """Create a new default entry for the given insertion index."""

    def validate_and_apply(self, entry: dict) -> bool:
        """Validate the edit, apply field values to the entry dict.

        Return True if valid, False to revert and show error.
        Default implementation is a no-op that returns True.
        """
        return True

    # ------------------------------------------------------------------
    # List helpers
    # ------------------------------------------------------------------

    def _make_list_item(self, index: int, entry: dict) -> ListItem:
        """Create a ListItem for an entry. Override for custom rendering."""
        return ListItem(Static(self.format_entry(index, entry)))

    def rebuild_list(self) -> None:
        """Rebuild the entire list from get_entries()."""
        entries = self.get_entries()
        list_view = self.query_one(f"#{self.pane_id}-list", SkimListView)
        list_view.clear()
        for i, entry in enumerate(entries):
            list_view.append(self._make_list_item(i, entry))

    def update_all_list_items(self) -> None:
        """Update the text of all list items in place."""
        entries = self.get_entries()
        list_view = self.query_one(f"#{self.pane_id}-list", SkimListView)
        for i, child in enumerate(list_view.children):
            if i < len(entries) and isinstance(child, ListItem):
                self._update_list_item_content(child, i, entries[i])

    def _update_list_item_content(self, item: ListItem, index: int, entry: dict) -> None:
        """Update a single list item's content. Override for custom rendering."""
        item.query_one(Static).update(self.format_entry(index, entry))

    def update_selected_list_item(self) -> None:
        """Update only the selected list item."""
        entries = self.get_entries()
        if self._selected >= len(entries):
            return
        list_view = self.query_one(f"#{self.pane_id}-list", SkimListView)
        if self._selected < len(list_view.children):
            child = list_view.children[self._selected]
            if isinstance(child, ListItem):
                self._update_list_item_content(child, self._selected, entries[self._selected])

    def _update_list_state(self) -> None:
        """Update list focusability and Remove button state."""
        has_entries = len(self.get_entries()) > 0
        self.query_one(f"#{self.pane_id}-list", SkimListView).can_focus = has_entries
        self.query_one(f"#{self.pane_id}-remove", Button).disabled = not has_entries

    # ------------------------------------------------------------------
    # Edit mode
    # ------------------------------------------------------------------

    def _set_fields_enabled(self, enabled: bool) -> None:
        """Enable or disable all detail Input fields."""
        for field_id in self.detail_field_ids():
            with contextlib.suppress(Exception):
                self.query_one(f"#{field_id}", Input).disabled = not enabled

    def _enter_edit_mode(self) -> None:
        """Enter edit mode: snapshot data, enable fields, focus first field."""
        entries = self.get_entries()
        if self._selected >= len(entries):
            return
        self._editing = True
        self._snapshot = copy.deepcopy(entries[self._selected])
        self._set_fields_enabled(True)
        self._focus_first_field()

    def _focus_first_field(self) -> None:
        """Focus the first editable field in the detail pane."""
        field_ids = self.detail_field_ids()
        if not field_ids:
            return
        # Try to find the first non-disabled, non-read-only input in compose order
        detail = self.query_one(f"#{self.pane_id}-detail")
        for inp in detail.query(Input):
            if inp.id in field_ids:
                inp.focus()
                return

    def _exit_edit_mode(self, commit: bool) -> None:
        """Exit edit mode: commit or rollback, disable fields, focus list."""
        if not commit and self._adding:
            # Cancel after add: remove the newly added entry entirely
            entries = self.get_entries()
            list_view = self.query_one(f"#{self.pane_id}-list", SkimListView)
            if self._selected < len(entries):
                entries.pop(self._selected)
            if self._selected < len(list_view.children):
                list_view.children[self._selected].remove()
            self._adding = False
            self._editing = False
            self._snapshot = None
            self._set_fields_enabled(False)
            if entries:
                self._selected = min(self._selected, len(entries) - 1)
                self.refresh_fields(entries[self._selected])
                list_view.index = self._selected
                list_view.focus()
            else:
                self._selected = 0
                self.clear_fields()
                self.query_one(f"#{self.pane_id}-add", Button).focus()
            self._update_list_state()
            return

        if not commit and self._snapshot is not None:
            entries = self.get_entries()
            if self._selected < len(entries):
                entries[self._selected] = self._snapshot
                self.refresh_fields(entries[self._selected])
        elif commit:
            entries = self.get_entries()
            if self._selected < len(entries) and not self.validate_and_apply(
                entries[self._selected]
            ):
                return  # validate_and_apply handles revert + error
        self._adding = False
        self._editing = False
        self._snapshot = None
        self._set_fields_enabled(False)
        self.update_all_list_items()
        list_view = self.query_one(f"#{self.pane_id}-list", SkimListView)
        list_view.index = self._selected
        list_view.focus()
        if commit:
            self.post_message(self.EntryUpdated())

    def _revert_and_show_error(self, message: str) -> None:
        """Revert from snapshot and show an error dialog."""
        from skim.tui.app import ErrorDialog

        entries = self.get_entries()
        if self._snapshot is not None and self._selected < len(entries):
            entries[self._selected] = self._snapshot
        self._editing = False
        self._snapshot = None
        self._set_fields_enabled(False)
        self.refresh_fields(entries[self._selected] if self._selected < len(entries) else {})
        self.update_all_list_items()
        list_view = self.query_one(f"#{self.pane_id}-list", SkimListView)
        list_view.index = self._selected
        list_view.focus()
        self.app.push_screen(ErrorDialog(message))

    # ------------------------------------------------------------------
    # Add / Remove
    # ------------------------------------------------------------------

    def _add_entry(self) -> None:
        """Add a new entry and enter edit mode."""
        entries = self.get_entries()
        idx = len(entries)
        new_entry = self.create_entry(idx)
        entries.append(new_entry)
        list_view = self.query_one(f"#{self.pane_id}-list", SkimListView)
        list_view.append(self._make_list_item(idx, new_entry))
        self._selected = idx
        self.refresh_fields(new_entry)
        self._update_list_state()
        self.post_message(self.EntryAdded(idx))
        self._adding = True
        # Defer index + edit mode until after layout so scroll-to-visible works
        self.call_after_refresh(self._finish_add, idx)

    def _finish_add(self, idx: int) -> None:
        """Set the list index (triggering scroll) and enter edit mode."""
        list_view = self.query_one(f"#{self.pane_id}-list", SkimListView)
        list_view.index = idx
        self._enter_edit_mode()

    def _remove_entry(self) -> None:
        """Remove the selected entry."""
        entries = self.get_entries()
        if not entries or self._selected >= len(entries):
            return
        removed_index = self._selected
        entries.pop(removed_index)
        list_view = self.query_one(f"#{self.pane_id}-list", SkimListView)
        if removed_index < len(list_view.children):
            list_view.children[removed_index].remove()
        self.update_all_list_items()
        if entries:
            self._selected = min(self._selected, len(entries) - 1)
            self.refresh_fields(entries[self._selected])
            list_view.index = self._selected
            list_view.focus()
        else:
            self._selected = 0
            self.clear_fields()
        self._update_list_state()
        self.post_message(self.EntryRemoved(removed_index))
        if not entries:
            self.query_one(f"#{self.pane_id}-add", Button).focus()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == f"{self.pane_id}-add":
            self._add_entry()
        elif event.button.id == f"{self.pane_id}-remove":
            self._remove_entry()

    def on_list_view_selected(self, event: SkimListView.Selected) -> None:
        if event.list_view.id != f"{self.pane_id}-list":
            return
        index = event.list_view.index
        if index is not None:
            self._selected = index
            self.refresh_fields(self.get_entries()[index])
            self._enter_edit_mode()

    def on_list_view_highlighted(self, event: SkimListView.Highlighted) -> None:
        if event.list_view.id != f"{self.pane_id}-list":
            return
        index = event.list_view.index
        if index is not None:
            self._selected = index
            entries = self.get_entries()
            if index < len(entries):
                self.refresh_fields(entries[index])

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
        if isinstance(focused, SkimListView) and focused.id == f"{self.pane_id}-list":
            if event.key == "a":
                event.prevent_default()
                event.stop()
                self.query_one(f"#{self.pane_id}-add", Button).press()
            elif event.key == "d":
                event.prevent_default()
                event.stop()
                self.query_one(f"#{self.pane_id}-remove", Button).press()

    def on_descendant_blur(self, event: DescendantBlur) -> None:
        """Commit edit when focus leaves the editing pane."""
        if not self._editing:
            return
        self.set_timer(0.05, self._check_focus_commit)

    def _check_focus_commit(self) -> None:
        if not self._editing:
            return
        focused = self.app.focused
        if (
            focused is None
            or not isinstance(focused, Input)
            or focused.id not in self.detail_field_ids()
        ):
            self._exit_edit_mode(commit=True)
