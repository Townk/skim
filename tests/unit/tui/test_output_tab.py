"""Unit tests for skim.tui.output_tab module."""

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Button, Input, ListView, Select, Switch

from skim.data.config import SkimConfig
from skim.tui.output_tab import OutputTab


class OutputTabTestApp(App):
    """Test app wrapping an OutputTab."""

    def __init__(self, config_data: dict) -> None:
        super().__init__()
        self.config_data = config_data

    def compose(self) -> ComposeResult:
        yield OutputTab(config_data=self.config_data)


class TestOutputTab:
    """Tests for the Output tab."""

    @pytest.fixture()
    def config_with_output(self) -> dict:
        config = SkimConfig().model_dump(mode="json")
        config["output"]["style"]["palette"]["layers"] = [
            {"base_color": "#347156", "color_index": 2, "gradient": None},
            {"base_color": "#89511C", "color_index": 2, "gradient": None},
        ]
        return config

    @pytest.fixture()
    def empty_config(self) -> dict:
        return SkimConfig().model_dump(mode="json")

    @pytest.mark.asyncio()
    async def test_shows_width_input(self, config_with_output):
        """Has a width input field."""
        app = OutputTabTestApp(config_data=config_with_output)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            width_input = app.query_one("#layout-width", Input)
            assert width_input.value == "800.0"

    @pytest.mark.asyncio()
    async def test_shows_style_toggles(self, config_with_output):
        """Has style toggle switches."""
        app = OutputTabTestApp(config_data=config_with_output)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            switches = app.query(Switch)
            assert len(switches) >= 3

    @pytest.mark.asyncio()
    async def test_shows_palette_color_inputs(self, config_with_output):
        """Has palette color input fields."""
        app = OutputTabTestApp(config_data=config_with_output)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            neutral = app.query_one("#palette-neutral-color", Input)
            assert neutral.value == "#6F768B"

    @pytest.mark.asyncio()
    async def test_editing_width_updates_config(self, config_with_output):
        """Changing width updates the config data."""
        app = OutputTabTestApp(config_data=config_with_output)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            width_input = app.query_one("#layout-width", Input)
            width_input.value = "1600"
            await pilot.pause()
            assert app.config_data["output"]["layout"]["width"] == 1600.0

    @pytest.mark.asyncio()
    async def test_shows_hold_symbol_select(self, config_with_output):
        """Has a select for hold_symbol_position."""
        app = OutputTabTestApp(config_data=config_with_output)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            select = app.query_one("#hold-symbol-position", Select)
            assert select is not None

    @pytest.mark.asyncio()
    async def test_shows_layer_colors(self, config_with_output):
        """Shows layer color entries matching palette.layers."""
        app = OutputTabTestApp(config_data=config_with_output)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            color_list = app.query_one("#layer-colors-list", ListView)
            assert len(color_list.children) == 2

    @pytest.mark.asyncio()
    async def test_lc_fields_disabled_by_default(self, config_with_output):
        """Layer color detail fields are disabled until Enter."""
        app = OutputTabTestApp(config_data=config_with_output)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert app.query_one("#lc-base-color", Input).disabled is True
            assert app.query_one("#lc-color-index", Input).disabled is True

    @pytest.mark.asyncio()
    async def test_enter_lc_edit_mode_enables_fields(self, config_with_output):
        """Entering layer color edit mode enables fields."""
        app = OutputTabTestApp(config_data=config_with_output)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            tab = app.query_one(OutputTab)
            tab._enter_lc_edit_mode()
            await pilot.pause()
            assert app.query_one("#lc-base-color", Input).disabled is False

    @pytest.mark.asyncio()
    async def test_exit_lc_edit_mode_rollback(self, config_with_output):
        """Exiting layer color edit mode with commit=False rolls back."""
        app = OutputTabTestApp(config_data=config_with_output)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            tab = app.query_one(OutputTab)
            tab._enter_lc_edit_mode()
            await pilot.pause()
            app.query_one("#lc-base-color", Input).value = "#FFFFFF"
            await pilot.pause()
            tab._exit_lc_edit_mode(commit=False)
            await pilot.pause()
            assert app.config_data["output"]["style"]["palette"]["layers"][0]["base_color"] == "#347156"

    @pytest.mark.asyncio()
    async def test_empty_lc_list_unfocusable(self, empty_config):
        """Empty layer colors list is not focusable, Remove is disabled."""
        app = OutputTabTestApp(config_data=empty_config)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert app.query_one("#layer-colors-list", ListView).can_focus is False
            assert app.query_one("#remove-layer-color", Button).disabled is True

    @pytest.mark.asyncio()
    async def test_tab_from_tabbar_reaches_first_input(self, config_with_output):
        """The main VerticalScroll does not steal focus."""
        app = OutputTabTestApp(config_data=config_with_output)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            # The first focusable widget should be layout-width, not VerticalScroll
            width_input = app.query_one("#layout-width", Input)
            assert width_input.focusable is True
