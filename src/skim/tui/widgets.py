# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Shared reusable TUI widgets for skim configuration editor."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, ListItem, ListView, Static


class ListDetailPanel(Widget):
    """A split panel with a selectable list on the left and a detail area on the right.

    Posts a SelectedChanged message when the selection changes.
    Consumers mount their own detail widgets in the detail container.
    """

    DEFAULT_CSS = """
    ListDetailPanel {
        layout: horizontal;
        height: 1fr;
    }
    ListDetailPanel > .list-panel {
        width: 1fr;
        max-width: 40;
        height: 100%;
        border-right: solid $primary-background;
    }
    ListDetailPanel > .detail-panel {
        width: 3fr;
        height: 100%;
        padding: 0 1;
    }
    """

    selected_index: reactive[int] = reactive(0)

    class SelectedChanged(Message):
        """Posted when the selected item changes."""

        def __init__(self, index: int) -> None:
            super().__init__()
            self.index = index

    def __init__(
        self,
        items: list[str] | None = None,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self._items = list(items) if items else []

    def compose(self) -> ComposeResult:
        with Vertical(classes="list-panel"):
            list_view = ListView(
                *[ListItem(Label(text)) for text in self._items],
                id="item-list",
            )
            yield list_view
        with Vertical(classes="detail-panel"):
            yield Static("Select an item", id="detail-placeholder")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        index = event.list_view.index
        if index is not None:
            self.selected_index = index
            self.post_message(self.SelectedChanged(index))

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        index = event.list_view.index
        if index is not None:
            self.selected_index = index
            self.post_message(self.SelectedChanged(index))

    def add_item(self, text: str) -> None:
        """Add an item to the list."""
        self._items.append(text)
        list_view = self.query_one("#item-list", ListView)
        list_view.append(ListItem(Label(text)))

    async def remove_item(self, index: int) -> None:
        """Remove an item by index."""
        if 0 <= index < len(self._items):
            self._items.pop(index)
            list_view = self.query_one("#item-list", ListView)
            await list_view.pop(index)

    @property
    def item_count(self) -> int:
        return len(self._items)
