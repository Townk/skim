# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.tui.output_tab module."""

import pytest
from textual.app import App, ComposeResult

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

    @pytest.mark.asyncio()
    async def test_shows_width_input(self, config_with_output):
        """Has a width input field."""
        app = OutputTabTestApp(config_data=config_with_output)
        async with app.run_test() as pilot:
            from textual.widgets import Input

            width_input = app.query_one("#layout-width", Input)
            assert width_input.value == "800.0"

    @pytest.mark.asyncio()
    async def test_shows_style_toggles(self, config_with_output):
        """Has style toggle switches."""
        app = OutputTabTestApp(config_data=config_with_output)
        async with app.run_test() as pilot:
            from textual.widgets import Switch

            switches = app.query(Switch)
            # use_layer_colors, show_layer_indicators, use_system_fonts, border enable
            assert len(switches) >= 3

    @pytest.mark.asyncio()
    async def test_shows_palette_color_inputs(self, config_with_output):
        """Has palette color input fields."""
        app = OutputTabTestApp(config_data=config_with_output)
        async with app.run_test() as pilot:
            from textual.widgets import Input

            neutral = app.query_one("#palette-neutral-color", Input)
            assert neutral.value == "#6F768B"

    @pytest.mark.asyncio()
    async def test_editing_width_updates_config(self, config_with_output):
        """Changing width updates the config data."""
        app = OutputTabTestApp(config_data=config_with_output)
        async with app.run_test() as pilot:
            from textual.widgets import Input

            width_input = app.query_one("#layout-width", Input)
            width_input.value = "1600"
            await pilot.pause()
            assert app.config_data["output"]["layout"]["width"] == 1600.0

    @pytest.mark.asyncio()
    async def test_shows_hold_symbol_select(self, config_with_output):
        """Has a select for hold_symbol_position."""
        app = OutputTabTestApp(config_data=config_with_output)
        async with app.run_test() as pilot:
            from textual.widgets import Select

            select = app.query_one("#hold-symbol-position", Select)
            assert select is not None

    @pytest.mark.asyncio()
    async def test_shows_layer_colors(self, config_with_output):
        """Shows layer color entries matching palette.layers."""
        app = OutputTabTestApp(config_data=config_with_output)
        async with app.run_test() as pilot:
            from textual.widgets import ListView

            color_list = app.query_one("#layer-colors-list", ListView)
            assert len(color_list.children) == 2
