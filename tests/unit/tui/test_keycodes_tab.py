# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.tui.keycodes_tab module."""

import pytest
from textual.app import App, ComposeResult

from skim.data.config import SkimConfig
from skim.tui.keycodes_tab import KeycodesTab


class KeycodesTabTestApp(App):
    """Test app wrapping a KeycodesTab."""

    def __init__(self, config_data: dict) -> None:
        super().__init__()
        self.config_data = config_data

    def compose(self) -> ComposeResult:
        yield KeycodesTab(config_data=self.config_data)


class TestKeycodesTab:
    """Tests for the Keycodes tab."""

    @pytest.fixture()
    def config_with_keycodes(self) -> dict:
        config = SkimConfig().model_dump(mode="json")
        config["keycodes"]["pre_process"] = [
            {"keycode": "LSFT(KC_TAB)", "target": "MKC_BKTAB"},
        ]
        config["keycodes"]["overrides"] = [
            {"keycode": "MKC_BKTAB", "target": "%%nf-md-keyboard_tab_reverse;"},
            {"keycode": "KC_ESC", "target": "ESC"},
        ]
        return config

    @pytest.mark.asyncio()
    async def test_shows_pre_process_section(self, config_with_keycodes):
        """Has a pre-process list."""
        app = KeycodesTabTestApp(config_data=config_with_keycodes)
        async with app.run_test() as pilot:
            pre_list = app.query_one("#pre-process-list")
            assert pre_list is not None

    @pytest.mark.asyncio()
    async def test_shows_overrides_section(self, config_with_keycodes):
        """Has an overrides list."""
        app = KeycodesTabTestApp(config_data=config_with_keycodes)
        async with app.run_test() as pilot:
            overrides_list = app.query_one("#overrides-list")
            assert overrides_list is not None

    @pytest.mark.asyncio()
    async def test_pre_process_shows_entries(self, config_with_keycodes):
        """Pre-process list shows the configured entries."""
        app = KeycodesTabTestApp(config_data=config_with_keycodes)
        async with app.run_test() as pilot:
            from textual.widgets import ListView

            pre_list = app.query_one("#pre-process-list", ListView)
            assert len(pre_list.children) == 1

    @pytest.mark.asyncio()
    async def test_overrides_shows_entries(self, config_with_keycodes):
        """Overrides list shows the configured entries."""
        app = KeycodesTabTestApp(config_data=config_with_keycodes)
        async with app.run_test() as pilot:
            from textual.widgets import ListView

            overrides_list = app.query_one("#overrides-list", ListView)
            assert len(overrides_list.children) == 2

    @pytest.mark.asyncio()
    async def test_editing_override_updates_config(self, config_with_keycodes):
        """Changing an override field updates the config data."""
        app = KeycodesTabTestApp(config_data=config_with_keycodes)
        async with app.run_test() as pilot:
            from textual.widgets import Input

            target_input = app.query_one("#override-target", Input)
            target_input.value = "ESCAPE"
            await pilot.pause()
            assert app.config_data["keycodes"]["overrides"][0]["target"] == "ESCAPE"
