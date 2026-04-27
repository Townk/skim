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

    @pytest.mark.asyncio()
    async def test_layer_commit_keeps_selection_on_source_tab(self, default_config_data):
        """Committing a layer edit must not snap the source tab's list back to 0."""
        from skim.tui.keyboard_tab import LayerListPane
        from skim.tui.widgets import SkimListView

        default_config_data["keyboard"]["layers"] = [
            {"index": 0, "name": "Letters", "id": "_BASE", "variant": "COLEMAK"},
            {"index": 1, "name": "Navigation", "id": "_NAV", "variant": None},
            {"index": 2, "name": "Numbers", "id": "_NUM", "variant": None},
        ]
        # Palette must match the layer count so the OutputTab loads cleanly.
        default_config_data["output"]["style"]["palette"]["layers"] = [
            {"base_color": "#ff0000", "color_index": 2, "gradient": None},
            {"base_color": "#00ff00", "color_index": 2, "gradient": None},
            {"base_color": "#0000ff", "color_index": 2, "gradient": None},
        ]
        app = SkimConfigApp(config_data=default_config_data)
        async with app.run_test(size=(140, 50)) as pilot:
            await pilot.pause()
            pane = app.query_one(LayerListPane)
            list_view = app.query_one("#layer-list", SkimListView)
            list_view.focus()
            await pilot.pause()
            list_view.index = 2
            await pilot.pause()
            await pilot.press("enter")  # enter edit mode
            await pilot.pause()
            await pilot.press("enter")  # commit (no edits)
            # Two pauses so the EntryUpdated → LayerUpdated round-trip
            # finishes before assertions.
            await pilot.pause()
            await pilot.pause()
            assert pane._selected == 2
            assert list_view.index == 2


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
