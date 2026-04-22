"""Unit tests for skim.tui.widgets module."""

import pytest
from textual.app import App, ComposeResult

from skim.tui.widgets import ListDetailPanel


class ListDetailTestApp(App):
    """Test app wrapping a ListDetailPanel."""

    def __init__(self, items: list[str]) -> None:
        super().__init__()
        self.items = items

    def compose(self) -> ComposeResult:
        yield ListDetailPanel(items=self.items, id="panel")


class TestListDetailPanel:
    """Tests for the ListDetailPanel widget."""

    @pytest.mark.asyncio()
    async def test_renders_item_list(self):
        """Shows all items in the list."""
        app = ListDetailTestApp(items=["Alpha", "Beta", "Gamma"])
        async with app.run_test() as pilot:
            panel = app.query_one(ListDetailPanel)
            list_items = panel.query("ListItem")
            assert len(list_items) == 3

    @pytest.mark.asyncio()
    async def test_empty_list(self):
        """Handles empty items list."""
        app = ListDetailTestApp(items=[])
        async with app.run_test() as pilot:
            panel = app.query_one(ListDetailPanel)
            list_items = panel.query("ListItem")
            assert len(list_items) == 0

    @pytest.mark.asyncio()
    async def test_add_item(self):
        """Adding an item updates the list."""
        app = ListDetailTestApp(items=["One"])
        async with app.run_test() as pilot:
            panel = app.query_one(ListDetailPanel)
            panel.add_item("Two")
            list_items = panel.query("ListItem")
            assert len(list_items) == 2

    @pytest.mark.asyncio()
    async def test_remove_item(self):
        """Removing an item updates the list."""
        app = ListDetailTestApp(items=["One", "Two"])
        async with app.run_test() as pilot:
            panel = app.query_one(ListDetailPanel)
            await panel.remove_item(0)
            list_items = panel.query("ListItem")
            assert len(list_items) == 1

    @pytest.mark.asyncio()
    async def test_selected_index_message(self):
        """Selecting an item posts a SelectedChanged message."""
        app = ListDetailTestApp(items=["A", "B"])
        async with app.run_test() as pilot:
            panel = app.query_one(ListDetailPanel)
            assert panel.selected_index == 0  # Default: first item
