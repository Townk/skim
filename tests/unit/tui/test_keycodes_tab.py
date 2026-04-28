"""Unit tests for skim.tui.keycodes_tab module."""

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Button, Input, Static

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


class TestMacroListPane:
    """Tests for the new Macro list/detail pane."""

    @pytest.fixture()
    def config_with_macros(self) -> dict:
        config = SkimConfig().model_dump(mode="json")
        config["keycodes"]["macros"] = [
            {"id": "0", "name": "Em-dash", "preview": "[↓ E]"},
            {"id": "5", "name": None, "preview": "[↓↑ Q]"},
        ]
        return config

    @pytest.mark.asyncio()
    async def test_list_shows_entries(self, config_with_macros):
        app = KeycodesTabTestApp(config_data=config_with_macros)
        async with app.run_test(size=(120, 60)) as pilot:
            await pilot.pause()
            macro_list = app.query_one("#macro-list", SkimListView)
            assert len(macro_list.children) == 2

    @pytest.mark.asyncio()
    async def test_id_and_name_disabled_by_default(self, config_with_macros):
        app = KeycodesTabTestApp(config_data=config_with_macros)
        async with app.run_test(size=(120, 60)) as pilot:
            await pilot.pause()
            assert app.query_one("#macro-id", Input).disabled is True
            assert app.query_one("#macro-name", Input).disabled is True

    @pytest.mark.asyncio()
    async def test_preview_field_disabled(self, config_with_macros):
        app = KeycodesTabTestApp(config_data=config_with_macros)
        async with app.run_test(size=(120, 60)) as pilot:
            await pilot.pause()
            # Preview is always disabled (read-only)
            assert app.query_one("#macro-preview", Input).disabled is True

    @pytest.mark.asyncio()
    async def test_add_creates_undefined_entry(self, config_with_macros):
        app = KeycodesTabTestApp(config_data=config_with_macros)
        async with app.run_test(size=(120, 60)) as pilot:
            await pilot.pause()
            from skim.tui.keycodes_tab import MacroListPane

            pane = app.query_one(MacroListPane)
            pane._add_entry()
            await pilot.pause()
            entries = pane.get_entries()
            assert len(entries) == 3
            new_entry = entries[-1]
            assert new_entry["id"] == "1"  # 0 and 5 used; smallest free is 1
            assert new_entry["name"] is None
            assert new_entry["preview"] == "Undefined"

    @pytest.mark.asyncio()
    async def test_duplicate_id_reverts(self, config_with_macros):
        from skim.tui.keycodes_tab import MacroListPane

        app = KeycodesTabTestApp(config_data=config_with_macros)
        async with app.run_test(size=(120, 60)) as pilot:
            await pilot.pause()
            pane = app.query_one(MacroListPane)
            pane._selected = 0
            pane._enter_edit_mode()
            await pilot.pause()
            app.query_one("#macro-id", Input).value = "5"  # collides with row 1
            pane._exit_edit_mode(commit=True)
            await pilot.pause()
            # Snapshot reverted: row 0 keeps its original id
            entries = pane.get_entries()
            assert entries[0]["id"] == "0"

    @pytest.mark.asyncio()
    async def test_editing_name_writes_to_config(self, config_with_macros):
        from skim.tui.keycodes_tab import MacroListPane

        app = KeycodesTabTestApp(config_data=config_with_macros)
        async with app.run_test(size=(120, 60)) as pilot:
            await pilot.pause()
            pane = app.query_one(MacroListPane)
            pane._selected = 1
            pane._enter_edit_mode()
            await pilot.pause()
            app.query_one("#macro-name", Input).value = "Q-tap"
            pane._exit_edit_mode(commit=True)
            await pilot.pause()
            assert pane.get_entries()[1]["name"] == "Q-tap"

    @pytest.mark.asyncio()
    async def test_list_row_resolves_nerdfont_markers(self):
        from skim.application.loaders.nerdfont_glyphs_loader import (
            load_nerdfont_glyphs,
        )

        config = SkimConfig().model_dump(mode="json")
        config["keycodes"]["macros"] = [
            {"id": "0", "name": None, "preview": '%%nf-md-text_recognition; "hi"'},
        ]
        app = KeycodesTabTestApp(config_data=config)
        async with app.run_test(size=(120, 60)) as pilot:
            await pilot.pause()
            macro_list = app.query_one("#macro-list", SkimListView)
            item_text = macro_list.children[0].query_one(Static).content
            glyphs = load_nerdfont_glyphs()
            expected_glyph = glyphs["nf-md-text_recognition"]
            assert expected_glyph in str(item_text), (
                f"expected glyph {expected_glyph!r} in row text {item_text!r}"
            )
            assert "%%nf-md-text_recognition;" not in str(item_text)

    @pytest.mark.asyncio()
    async def test_add_starts_at_one_when_list_empty(self):
        from skim.tui.keycodes_tab import MacroListPane

        config = SkimConfig().model_dump(mode="json")
        config["keycodes"]["macros"] = []
        app = KeycodesTabTestApp(config_data=config)
        async with app.run_test(size=(120, 60)) as pilot:
            await pilot.pause()
            pane = app.query_one(MacroListPane)
            pane._add_entry()
            await pilot.pause()
            assert pane.get_entries()[0]["id"] == "1"

    @pytest.mark.asyncio()
    async def test_list_row_prefixes_macro_id_with_m(self):
        config = SkimConfig().model_dump(mode="json")
        config["keycodes"]["macros"] = [
            {"id": "1", "name": "First", "preview": ""},
            {"id": "42", "name": "Answer", "preview": ""},
        ]
        app = KeycodesTabTestApp(config_data=config)
        async with app.run_test(size=(120, 60)) as pilot:
            await pilot.pause()
            macro_list = app.query_one("#macro-list", SkimListView)
            row_texts = [str(child.query_one(Static).content) for child in macro_list.children]
            assert any("M1" in t for t in row_texts), row_texts
            assert any("M42" in t for t in row_texts), row_texts
            # Detail pane's ID input still shows the raw id
            macro_list.index = 0
            await pilot.pause()
            assert app.query_one("#macro-id", Input).value == "1"


class TestTapDanceListPane:
    """Tests for the new Tap-dance list/detail pane."""

    @pytest.fixture()
    def config_with_tap_dances(self) -> dict:
        config = SkimConfig().model_dump(mode="json")
        config["keycodes"]["tap_dances"] = [
            {"id": "0", "name": "Quick shift", "preview": "t:Q"},
            {"id": "3", "name": None, "preview": "t:A h:B"},
        ]
        return config

    @pytest.mark.asyncio()
    async def test_list_shows_entries(self, config_with_tap_dances):
        app = KeycodesTabTestApp(config_data=config_with_tap_dances)
        async with app.run_test(size=(120, 60)) as pilot:
            await pilot.pause()
            td_list = app.query_one("#tap-dance-list", SkimListView)
            assert len(td_list.children) == 2

    @pytest.mark.asyncio()
    async def test_id_and_name_disabled_by_default(self, config_with_tap_dances):
        app = KeycodesTabTestApp(config_data=config_with_tap_dances)
        async with app.run_test(size=(120, 60)) as pilot:
            await pilot.pause()
            assert app.query_one("#tap-dance-id", Input).disabled is True
            assert app.query_one("#tap-dance-name", Input).disabled is True

    @pytest.mark.asyncio()
    async def test_preview_field_disabled(self, config_with_tap_dances):
        app = KeycodesTabTestApp(config_data=config_with_tap_dances)
        async with app.run_test(size=(120, 60)) as pilot:
            await pilot.pause()
            assert app.query_one("#tap-dance-preview", Input).disabled is True

    @pytest.mark.asyncio()
    async def test_add_creates_undefined_entry(self, config_with_tap_dances):
        from skim.tui.keycodes_tab import TapDanceListPane

        app = KeycodesTabTestApp(config_data=config_with_tap_dances)
        async with app.run_test(size=(120, 60)) as pilot:
            await pilot.pause()
            pane = app.query_one(TapDanceListPane)
            pane._add_entry()
            await pilot.pause()
            entries = pane.get_entries()
            assert len(entries) == 3
            new_entry = entries[-1]
            assert new_entry["id"] == "1"
            assert new_entry["name"] is None
            assert new_entry["preview"] == "Undefined"

    @pytest.mark.asyncio()
    async def test_duplicate_id_reverts(self, config_with_tap_dances):
        from skim.tui.keycodes_tab import TapDanceListPane

        app = KeycodesTabTestApp(config_data=config_with_tap_dances)
        async with app.run_test(size=(120, 60)) as pilot:
            await pilot.pause()
            pane = app.query_one(TapDanceListPane)
            pane._selected = 0
            pane._enter_edit_mode()
            await pilot.pause()
            app.query_one("#tap-dance-id", Input).value = "3"
            pane._exit_edit_mode(commit=True)
            await pilot.pause()
            assert pane.get_entries()[0]["id"] == "0"

    @pytest.mark.asyncio()
    async def test_editing_name_writes_to_config(self, config_with_tap_dances):
        from skim.tui.keycodes_tab import TapDanceListPane

        app = KeycodesTabTestApp(config_data=config_with_tap_dances)
        async with app.run_test(size=(120, 60)) as pilot:
            await pilot.pause()
            pane = app.query_one(TapDanceListPane)
            pane._selected = 1
            pane._enter_edit_mode()
            await pilot.pause()
            app.query_one("#tap-dance-name", Input).value = "AB-tap"
            pane._exit_edit_mode(commit=True)
            await pilot.pause()
            assert pane.get_entries()[1]["name"] == "AB-tap"

    @pytest.mark.asyncio()
    async def test_list_row_resolves_nerdfont_markers(self):
        from skim.application.loaders.nerdfont_glyphs_loader import (
            load_nerdfont_glyphs,
        )

        config = SkimConfig().model_dump(mode="json")
        config["keycodes"]["tap_dances"] = [
            {"id": "0", "name": None, "preview": "t:%%nf-md-apple_keyboard_shift;"},
        ]
        app = KeycodesTabTestApp(config_data=config)
        async with app.run_test(size=(120, 60)) as pilot:
            await pilot.pause()
            td_list = app.query_one("#tap-dance-list", SkimListView)
            item_text = td_list.children[0].query_one(Static).content
            glyphs = load_nerdfont_glyphs()
            expected_glyph = glyphs["nf-md-apple_keyboard_shift"]
            assert expected_glyph in str(item_text)
            assert "%%nf-md-apple_keyboard_shift;" not in str(item_text)

    @pytest.mark.asyncio()
    async def test_list_row_wraps_tap_dance_id_in_td_parens(self):
        config = SkimConfig().model_dump(mode="json")
        config["keycodes"]["tap_dances"] = [
            {"id": "0", "name": "Quick shift", "preview": ""},
            {"id": "MY_TD", "name": None, "preview": ""},
        ]
        app = KeycodesTabTestApp(config_data=config)
        async with app.run_test(size=(120, 60)) as pilot:
            await pilot.pause()
            td_list = app.query_one("#tap-dance-list", SkimListView)
            row_texts = [str(child.query_one(Static).content) for child in td_list.children]
            assert any("TD(0)" in t for t in row_texts), row_texts
            assert any("TD(MY_TD)" in t for t in row_texts), row_texts
            # Detail pane's ID input still shows the raw id
            td_list.index = 0
            await pilot.pause()
            assert app.query_one("#tap-dance-id", Input).value == "0"


class TestKeycodesTabStructure:
    """Tests that the four sections compose in the correct order."""

    @pytest.mark.asyncio()
    async def test_all_four_sections_present(self):
        config = SkimConfig().model_dump(mode="json")
        app = KeycodesTabTestApp(config_data=config)
        async with app.run_test(size=(120, 60)) as pilot:
            await pilot.pause()
            for list_id in (
                "#pre-process-list",
                "#override-list",
                "#macro-list",
                "#tap-dance-list",
            ):
                assert app.query_one(list_id) is not None, f"missing {list_id}"

    @pytest.mark.asyncio()
    async def test_tab_uses_skim_vertical_scroll(self):
        from skim.tui.widgets import SkimVerticalScroll

        config = SkimConfig().model_dump(mode="json")
        app = KeycodesTabTestApp(config_data=config)
        async with app.run_test(size=(120, 60)) as pilot:
            await pilot.pause()
            tab = app.query_one(KeycodesTab)
            scrolls = list(tab.query(SkimVerticalScroll))
            assert scrolls, "KeycodesTab is not wrapped in a SkimVerticalScroll"

    @pytest.mark.asyncio()
    async def test_section_order_matches_spec(self):
        from skim.tui.list_detail_pane import ListDetailPane

        config = SkimConfig().model_dump(mode="json")
        app = KeycodesTabTestApp(config_data=config)
        async with app.run_test(size=(120, 60)) as pilot:
            await pilot.pause()
            tab = app.query_one(KeycodesTab)
            panes = list(tab.query(ListDetailPane))
            ids = [pane.pane_id for pane in panes]
            assert ids == ["pre-process", "override", "macro", "tap-dance"]
