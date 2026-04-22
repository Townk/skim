# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.tui.keyboard_tab module."""

import pytest
from textual.app import App, ComposeResult

from skim.data.config import SkimConfig
from skim.tui.keyboard_tab import KeyboardTab


class KeyboardTabTestApp(App):
    """Test app wrapping a KeyboardTab."""

    def __init__(self, config_data: dict) -> None:
        super().__init__()
        self.config_data = config_data

    def compose(self) -> ComposeResult:
        yield KeyboardTab(config_data=self.config_data)


class TestKeyboardTab:
    """Tests for the Keyboard tab."""

    @pytest.fixture()
    def config_with_layers(self) -> dict:
        config = SkimConfig().model_dump(mode="json")
        config["keyboard"]["layers"] = [
            {"label": "BASE", "name": "Letters", "id": "_BASE", "subtitle": "COLEMAK"},
            {"label": "NAV", "name": "Navigation", "id": "_NAV", "subtitle": None},
        ]
        return config

    @pytest.mark.asyncio()
    async def test_shows_double_south_switch(self, config_with_layers):
        """Has a switch for double_south feature."""
        app = KeyboardTabTestApp(config_data=config_with_layers)
        async with app.run_test() as pilot:
            from textual.widgets import Switch

            switches = app.query(Switch)
            assert len(switches) >= 1

    @pytest.mark.asyncio()
    async def test_shows_layer_list(self, config_with_layers):
        """Shows layers in the list panel."""
        app = KeyboardTabTestApp(config_data=config_with_layers)
        async with app.run_test() as pilot:
            from textual.widgets import ListItem

            items = app.query(ListItem)
            assert len(items) == 2

    @pytest.mark.asyncio()
    async def test_layer_detail_shows_fields(self, config_with_layers):
        """Selecting a layer shows its editable fields."""
        app = KeyboardTabTestApp(config_data=config_with_layers)
        async with app.run_test() as pilot:
            from textual.widgets import Input

            inputs = app.query(Input)
            # Should have label, name, id, subtitle fields
            assert len(inputs) >= 4

    @pytest.mark.asyncio()
    async def test_editing_layer_name_updates_config(self, config_with_layers):
        """Changing a layer name input updates the config data."""
        app = KeyboardTabTestApp(config_data=config_with_layers)
        async with app.run_test() as pilot:
            from textual.widgets import Input

            name_input = app.query_one("#layer-name", Input)
            name_input.value = "Base Layer"
            await pilot.pause()
            assert app.config_data["keyboard"]["layers"][0]["name"] == "Base Layer"

    @pytest.mark.asyncio()
    async def test_double_south_toggle_updates_config(self, config_with_layers):
        """Toggling double_south updates the config data."""
        app = KeyboardTabTestApp(config_data=config_with_layers)
        async with app.run_test() as pilot:
            from textual.widgets import Switch

            switch = app.query_one("#double-south", Switch)
            switch.toggle()
            await pilot.pause()
            assert app.config_data["keyboard"]["features"]["double_south"] is True
