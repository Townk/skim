"""Unit tests for skim.tui.keyboard_tab module."""

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Input, ListView, Switch

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
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            switches = app.query(Switch)
            assert len(switches) >= 1

    @pytest.mark.asyncio()
    async def test_shows_layer_list(self, config_with_layers):
        """Shows layers in the list panel."""
        app = KeyboardTabTestApp(config_data=config_with_layers)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            list_view = app.query_one("#layer-list", ListView)
            assert len(list_view.children) == 2

    @pytest.mark.asyncio()
    async def test_detail_fields_disabled_by_default(self, config_with_layers):
        """Detail Input fields are disabled until Enter is pressed on a layer."""
        app = KeyboardTabTestApp(config_data=config_with_layers)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            for field_id in ["layer-label", "layer-name", "layer-id", "layer-subtitle"]:
                inp = app.query_one(f"#{field_id}", Input)
                assert inp.disabled is True

    @pytest.mark.asyncio()
    async def test_enter_edit_mode_enables_fields(self, config_with_layers):
        """Entering edit mode enables detail fields."""
        app = KeyboardTabTestApp(config_data=config_with_layers)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            tab = app.query_one(KeyboardTab)
            tab._enter_edit_mode()
            await pilot.pause()
            inp = app.query_one("#layer-label", Input)
            assert inp.disabled is False

    @pytest.mark.asyncio()
    async def test_editing_layer_name_updates_config(self, config_with_layers):
        """Changing a layer name input updates the config data."""
        app = KeyboardTabTestApp(config_data=config_with_layers)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            # Enter edit mode
            list_view = app.query_one("#layer-list", ListView)
            list_view.focus()
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            # Edit the name field
            name_input = app.query_one("#layer-name", Input)
            name_input.value = "Base Layer"
            await pilot.pause()
            assert app.config_data["keyboard"]["layers"][0]["name"] == "Base Layer"

    @pytest.mark.asyncio()
    async def test_exit_edit_mode_rollback(self, config_with_layers):
        """Exiting edit mode with commit=False rolls back changes."""
        app = KeyboardTabTestApp(config_data=config_with_layers)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            tab = app.query_one(KeyboardTab)
            tab._enter_edit_mode()
            await pilot.pause()
            # Change the name
            name_input = app.query_one("#layer-name", Input)
            name_input.value = "Changed"
            await pilot.pause()
            assert app.config_data["keyboard"]["layers"][0]["name"] == "Changed"
            # Rollback
            tab._exit_edit_mode(commit=False)
            await pilot.pause()
            assert app.config_data["keyboard"]["layers"][0]["name"] == "Letters"
            # Fields should be disabled again
            assert name_input.disabled is True

    @pytest.mark.asyncio()
    async def test_double_south_toggle_updates_config(self, config_with_layers):
        """Toggling double_south updates the config data."""
        app = KeyboardTabTestApp(config_data=config_with_layers)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            switch = app.query_one("#double-south", Switch)
            switch.toggle()
            await pilot.pause()
            assert app.config_data["keyboard"]["features"]["double_south"] is True
