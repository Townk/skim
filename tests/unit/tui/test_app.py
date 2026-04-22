"""Unit tests for skim.tui.app module."""

import pytest
import yaml

from skim.data.config import SkimConfig
from skim.tui.app import SkimConfigApp


class TestSkimConfigApp:
    """Tests for the main TUI app."""

    @pytest.fixture()
    def default_config_data(self) -> dict:
        return SkimConfig().model_dump(mode="json")

    @pytest.mark.asyncio()
    async def test_app_starts_with_three_tabs(self, default_config_data):
        """App has Keyboard, Keycodes, and Output tabs."""
        app = SkimConfigApp(config_data=default_config_data)
        async with app.run_test() as pilot:
            tabs = app.query("TabPane")
            assert len(tabs) == 3

    @pytest.mark.asyncio()
    async def test_app_has_footer(self, default_config_data):
        """App shows a footer with keybindings."""
        app = SkimConfigApp(config_data=default_config_data)
        async with app.run_test() as pilot:
            from textual.widgets import Footer

            footers = app.query(Footer)
            assert len(footers) == 1

    @pytest.mark.asyncio()
    async def test_app_starts_on_keyboard_tab(self, default_config_data):
        """App starts with the Keyboard tab active."""
        app = SkimConfigApp(config_data=default_config_data)
        async with app.run_test() as pilot:
            from textual.widgets import TabbedContent

            tabbed = app.query_one(TabbedContent)
            assert tabbed.active == "keyboard-tab"

    @pytest.mark.asyncio()
    async def test_quit_with_no_changes_exits(self, default_config_data):
        """Pressing ctrl+q with no changes exits immediately."""
        app = SkimConfigApp(config_data=default_config_data)
        async with app.run_test() as pilot:
            await pilot.press("ctrl+q")
            assert app.return_code is not None or not app.is_running
