"""Unit tests for skim.tui.app module."""

import pytest

from skim.data.config import SkimConfig
from skim.tui.app import HelpScreen, SkimConfigApp


class TestSkimConfigApp:
    """Tests for the main TUI app."""

    @pytest.fixture()
    def default_config_data(self) -> dict:
        return SkimConfig().model_dump(mode="json")

    @pytest.mark.asyncio()
    async def test_app_starts_with_three_tabs(self, default_config_data):
        """App has Keyboard, Keycodes, and Output tabs."""
        app = SkimConfigApp(config_data=default_config_data)
        async with app.run_test():
            tabs = app.query("TabPane")
            assert len(tabs) == 3

    @pytest.mark.asyncio()
    async def test_app_has_footer(self, default_config_data):
        """App shows a footer with keybindings."""
        app = SkimConfigApp(config_data=default_config_data)
        async with app.run_test():
            from textual.widgets import Footer

            footers = app.query(Footer)
            assert len(footers) == 1

    @pytest.mark.asyncio()
    async def test_app_starts_on_keyboard_tab(self, default_config_data):
        """App starts with the Keyboard tab active."""
        app = SkimConfigApp(config_data=default_config_data)
        async with app.run_test():
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


class TestHelpScreen:
    """Tests for the HelpScreen modal."""

    @pytest.fixture()
    def default_config_data(self) -> dict:
        return SkimConfig().model_dump(mode="json")

    @pytest.mark.asyncio()
    async def test_f1_opens_help_screen(self, default_config_data):
        """Pressing F1 opens a HelpScreen."""
        app = SkimConfigApp(config_data=default_config_data)
        async with app.run_test() as pilot:
            await pilot.press("f1")
            assert isinstance(app.screen, HelpScreen)

    @pytest.mark.asyncio()
    async def test_help_screen_dismiss_with_escape(self, default_config_data):
        """HelpScreen can be dismissed with Escape."""
        app = SkimConfigApp(config_data=default_config_data)
        async with app.run_test() as pilot:
            await pilot.press("f1")
            assert isinstance(app.screen, HelpScreen)
            await pilot.press("escape")
            assert not isinstance(app.screen, HelpScreen)

    @pytest.mark.asyncio()
    async def test_help_screen_dismiss_with_q(self, default_config_data):
        """HelpScreen can be dismissed with q."""
        app = SkimConfigApp(config_data=default_config_data)
        async with app.run_test() as pilot:
            await pilot.press("f1")
            assert isinstance(app.screen, HelpScreen)
            await pilot.press("q")
            assert not isinstance(app.screen, HelpScreen)

    @pytest.mark.asyncio()
    async def test_help_screen_shows_general_by_default(self, default_config_data):
        """F1 with no help_key on focused widget shows general help."""
        app = SkimConfigApp(config_data=default_config_data)
        async with app.run_test() as pilot:
            await pilot.press("f1")
            from textual.widgets import Markdown

            md = app.screen.query_one(Markdown)
            assert md is not None


class TestHelpScreenIntegration:
    """Integration tests for contextual help per field."""

    @pytest.fixture()
    def default_config_data(self) -> dict:
        return SkimConfig().model_dump(mode="json")

    @pytest.mark.asyncio()
    async def test_f1_on_keymap_title_shows_specific_help(self, default_config_data):
        """F1 on keymap title field shows keymap-title help."""
        app = SkimConfigApp(config_data=default_config_data)
        async with app.run_test() as pilot:
            # Focus the keymap title input
            title_input = app.query_one("#keymap-title-text")
            title_input.focus()
            await pilot.pause()
            await pilot.press("f1")
            from textual.widgets import Markdown

            md = app.screen.query_one(Markdown)
            # The help screen should contain content from keymap-title.md
            assert "Keymap Title" in md.source

    @pytest.mark.asyncio()
    async def test_f1_on_widget_without_help_key_shows_general(self, default_config_data):
        """F1 on a widget without help_key falls back to general help."""
        app = SkimConfigApp(config_data=default_config_data)
        async with app.run_test() as pilot:
            await pilot.press("f1")
            from textual.widgets import Markdown

            md = app.screen.query_one(Markdown)
            assert "Navigation" in md.source
