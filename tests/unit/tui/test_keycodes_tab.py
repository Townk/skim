"""Unit tests for skim.tui.keycodes_tab module."""

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Button, Input

from skim.data.config import SkimConfig
from skim.tui.keycodes_tab import KeycodesTab
from skim.tui.widgets import SkimListView


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

    @pytest.fixture()
    def empty_config(self) -> dict:
        return SkimConfig().model_dump(mode="json")

    @pytest.mark.asyncio()
    async def test_shows_pre_process_section(self, config_with_keycodes):
        """Has a pre-process list."""
        app = KeycodesTabTestApp(config_data=config_with_keycodes)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            pre_list = app.query_one("#pre-process-list")
            assert pre_list is not None

    @pytest.mark.asyncio()
    async def test_shows_overrides_section(self, config_with_keycodes):
        """Has an overrides list."""
        app = KeycodesTabTestApp(config_data=config_with_keycodes)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            overrides_list = app.query_one("#override-list")
            assert overrides_list is not None

    @pytest.mark.asyncio()
    async def test_pre_process_shows_entries(self, config_with_keycodes):
        """Pre-process list shows the configured entries."""
        app = KeycodesTabTestApp(config_data=config_with_keycodes)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            pre_list = app.query_one("#pre-process-list", SkimListView)
            assert len(pre_list.children) == 1

    @pytest.mark.asyncio()
    async def test_overrides_shows_entries(self, config_with_keycodes):
        """Overrides list shows the configured entries."""
        app = KeycodesTabTestApp(config_data=config_with_keycodes)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            overrides_list = app.query_one("#override-list", SkimListView)
            assert len(overrides_list.children) == 2

    @pytest.mark.asyncio()
    async def test_fields_disabled_by_default(self, config_with_keycodes):
        """Detail fields are disabled until Enter is pressed."""
        app = KeycodesTabTestApp(config_data=config_with_keycodes)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            for fid in [
                "override-keycode",
                "override-target",
                "pre-process-keycode",
                "pre-process-target",
            ]:
                assert app.query_one(f"#{fid}", Input).disabled is True

    @pytest.mark.asyncio()
    async def test_enter_edit_mode_enables_fields(self, config_with_keycodes):
        """Entering edit mode enables fields for that section."""
        app = KeycodesTabTestApp(config_data=config_with_keycodes)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            tab = app.query_one(KeycodesTab)
            tab._enter_edit_mode("override")
            await pilot.pause()
            assert app.query_one("#override-keycode", Input).disabled is False
            assert app.query_one("#override-target", Input).disabled is False
            # Other section still disabled
            assert app.query_one("#pre-process-keycode", Input).disabled is True

    @pytest.mark.asyncio()
    async def test_editing_override_updates_config(self, config_with_keycodes):
        """Changing an override field in edit mode updates the config data."""
        app = KeycodesTabTestApp(config_data=config_with_keycodes)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            tab = app.query_one(KeycodesTab)
            tab._enter_edit_mode("override")
            await pilot.pause()
            target_input = app.query_one("#override-target", Input)
            target_input.value = "ESCAPE"
            await pilot.pause()
            assert app.config_data["keycodes"]["overrides"][0]["target"] == "ESCAPE"

    @pytest.mark.asyncio()
    async def test_exit_edit_mode_rollback(self, config_with_keycodes):
        """Exiting edit mode with commit=False rolls back changes."""
        app = KeycodesTabTestApp(config_data=config_with_keycodes)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            tab = app.query_one(KeycodesTab)
            tab._enter_edit_mode("override")
            await pilot.pause()
            app.query_one("#override-target", Input).value = "CHANGED"
            await pilot.pause()
            tab._exit_edit_mode(commit=False)
            await pilot.pause()
            assert (
                app.config_data["keycodes"]["overrides"][0]["target"]
                == "%%nf-md-keyboard_tab_reverse;"
            )

    @pytest.mark.asyncio()
    async def test_empty_list_unfocusable(self, empty_config):
        """Empty lists are not focusable, Remove buttons are disabled."""
        app = KeycodesTabTestApp(config_data=empty_config)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert app.query_one("#pre-process-list", SkimListView).can_focus is False
            assert app.query_one("#override-list", SkimListView).can_focus is False
            assert app.query_one("#pre-process-remove", Button).disabled is True
            assert app.query_one("#override-remove", Button).disabled is True
