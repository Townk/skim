"""Unit tests for skim.tui.output_tab module."""

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Button, Input, Select, Switch

from skim.data.config import SkimConfig
from skim.tui.output_tab import OutputTab
from skim.tui.widgets import SkimListView


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
        config["keyboard"]["layers"] = [
            {"name": "Base", "index": 0},
            {"name": "Nav", "index": 1},
        ]
        config["output"]["style"]["palette"]["layers"] = [
            {"base_color": "#347156", "color_index": 2, "gradient": None},
            {"base_color": "#89511C", "color_index": 2, "gradient": None},
        ]
        return config

    @pytest.fixture()
    def config_with_nonsequential_qmk_indices(self) -> dict:
        config = SkimConfig().model_dump(mode="json")
        config["keyboard"]["layers"] = [
            {"name": "Base", "index": 0},
            {"name": "Sym", "index": 15},
        ]
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
            assert width_input.value == "1600.0"

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
            color_list = app.query_one("#layer-colors-list", SkimListView)
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
            assert (
                app.config_data["output"]["style"]["palette"]["layers"][0]["base_color"]
                == "#347156"
            )

    @pytest.mark.asyncio()
    async def test_empty_lc_list_unfocusable(self, empty_config):
        """Empty layer colors list is not focusable, Remove is disabled."""
        app = OutputTabTestApp(config_data=empty_config)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert app.query_one("#layer-colors-list", SkimListView).can_focus is False
            assert app.query_one("#layer-colors-remove", Button).disabled is True

    @pytest.mark.asyncio()
    async def test_tab_from_tabbar_reaches_first_input(self, config_with_output):
        """The main VerticalScroll does not steal focus."""
        app = OutputTabTestApp(config_data=config_with_output)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            # The first focusable widget should be layout-width, not VerticalScroll
            width_input = app.query_one("#layout-width", Input)
            assert width_input.focusable is True

    def test_layer_qmk_index_uses_config_index(self, config_with_nonsequential_qmk_indices):
        """_layer_qmk_index returns the QMK index from config, not the position."""
        tab = OutputTab(config_data=config_with_nonsequential_qmk_indices)
        assert tab._layer_qmk_index(0) == 0
        assert tab._layer_qmk_index(1) == 15

    def test_layer_qmk_index_falls_back_to_position(self, empty_config):
        """_layer_qmk_index falls back to position index when layer not in config."""
        tab = OutputTab(config_data=empty_config)
        assert tab._layer_qmk_index(0) == 0
        assert tab._layer_qmk_index(3) == 3

    def test_lc_text_uses_qmk_index(self, config_with_nonsequential_qmk_indices):
        """_lc_text uses QMK index (15) not position index (1) for second layer."""
        tab = OutputTab(config_data=config_with_nonsequential_qmk_indices)
        lc = {"base_color": "#89511C"}
        text = tab._lc_text(1, lc, 10, 10)
        assert "(15)" in text
        assert "(1)" not in text

    def test_lc_column_widths_uses_qmk_index(self, config_with_nonsequential_qmk_indices):
        """_lc_column_widths accounts for the width of QMK index strings."""
        tab = OutputTab(config_data=config_with_nonsequential_qmk_indices)
        col0_w, _ = tab._lc_column_widths()
        # "Sym (15)" is 8 chars, "Base (0)" is 8 chars — col0_w should be at least 8
        assert col0_w >= len("Sym (15)")

    @pytest.mark.asyncio()
    async def test_manual_gradient_survives_load(self, config_with_output):
        """Loading a config with a manual gradient must not flip layer 0 to dynamic.

        Regression: a Select.Changed event fired during the gradient-type
        Select's mount used to run the manual→dynamic conversion before
        ``refresh_fields`` could mirror the loaded entry — wiping the
        saved gradient on layer 0.
        """
        config_with_output["output"]["style"]["palette"]["layers"][0] = {
            "base_color": "#FF0000",
            "color_index": 2,
            "gradient": [
                "#FF1111",
                "#EE2222",
                "#DD3333",
                "#CC4444",
                "#BB5555",
                "#AA6666",
            ],
        }
        app = OutputTabTestApp(config_data=config_with_output)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            layer0 = app.config_data["output"]["style"]["palette"]["layers"][0]
            assert layer0["gradient"] == [
                "#FF1111",
                "#EE2222",
                "#DD3333",
                "#CC4444",
                "#BB5555",
                "#AA6666",
            ]
            assert layer0["base_color"] == "#FF0000"

    @pytest.mark.asyncio()
    async def test_palette_includes_macro_and_tap_dance_color_inputs(self, config_with_output):
        app = OutputTabTestApp(config_data=config_with_output)
        async with app.run_test(size=(120, 80)) as pilot:
            await pilot.pause()
            macro_input = app.query_one("#palette-macro-color", Input)
            td_input = app.query_one("#palette-tap-dance-color", Input)
            assert macro_input.value == "#89511C"
            assert td_input.value == "#41687F"

    @pytest.mark.asyncio()
    async def test_editing_macro_color_writes_to_config(self, config_with_output):
        app = OutputTabTestApp(config_data=config_with_output)
        async with app.run_test(size=(120, 80)) as pilot:
            await pilot.pause()
            macro_input = app.query_one("#palette-macro-color", Input)
            macro_input.value = "#AAAAAA"
            await pilot.pause()
            assert config_with_output["output"]["style"]["palette"]["macro_color"] == "#AAAAAA"

    @pytest.mark.asyncio()
    async def test_alt_left_decreases_lightness_on_palette_color(self):
        from textual.app import App, ComposeResult
        from textual.widgets import Input

        from skim.data.config import SkimConfig
        from skim.tui.output_tab import OutputTab

        config_data = SkimConfig().model_dump(mode="json")

        class T(App):
            def compose(self) -> ComposeResult:
                yield OutputTab(config_data=config_data)

        app = T()
        async with app.run_test(size=(120, 80)) as pilot:
            await pilot.pause()
            macro_input = app.query_one("#palette-macro-color", Input)
            macro_input.focus()
            await pilot.pause()
            assert macro_input.value == "#89511C"
            await pilot.press("alt+left")
            await pilot.pause()
            # Value changed and is still a valid hex
            assert macro_input.value != "#89511C"
            assert macro_input.value.startswith("#")
            assert len(macro_input.value) == 7

    @pytest.mark.asyncio()
    async def test_alt_right_increases_lightness_on_palette_color(self):
        from textual.app import App, ComposeResult
        from textual.widgets import Input

        from skim.data.config import SkimConfig
        from skim.tui.output_tab import OutputTab

        config_data = SkimConfig().model_dump(mode="json")

        class T(App):
            def compose(self) -> ComposeResult:
                yield OutputTab(config_data=config_data)

        app = T()
        async with app.run_test(size=(120, 80)) as pilot:
            await pilot.pause()
            macro_input = app.query_one("#palette-macro-color", Input)
            macro_input.focus()
            await pilot.pause()
            await pilot.press("alt+right")
            await pilot.pause()
            assert macro_input.value != "#89511C"

    @pytest.mark.asyncio()
    async def test_alt_down_on_named_color_is_noop(self):
        from textual.app import App, ComposeResult
        from textual.widgets import Input

        from skim.data.config import SkimConfig
        from skim.tui.output_tab import OutputTab

        config_data = SkimConfig().model_dump(mode="json")

        class T(App):
            def compose(self) -> ComposeResult:
                yield OutputTab(config_data=config_data)

        app = T()
        async with app.run_test(size=(120, 80)) as pilot:
            await pilot.pause()
            bg_input = app.query_one("#palette-background-color", Input)
            assert bg_input.value == "white"
            bg_input.focus()
            await pilot.pause()
            await pilot.press("alt+down")
            await pilot.pause()
            # Named-color input: nudge is a no-op
            assert bg_input.value == "white"

    @pytest.mark.asyncio()
    async def test_alt_up_increases_saturation_on_palette_color(self):
        from textual.app import App, ComposeResult
        from textual.widgets import Input

        from skim.data.config import SkimConfig
        from skim.tui.output_tab import OutputTab

        config_data = SkimConfig().model_dump(mode="json")

        class T(App):
            def compose(self) -> ComposeResult:
                yield OutputTab(config_data=config_data)

        app = T()
        async with app.run_test(size=(120, 80)) as pilot:
            await pilot.pause()
            macro_input = app.query_one("#palette-macro-color", Input)
            macro_input.focus()
            await pilot.pause()
            original = macro_input.value
            await pilot.press("alt+up")
            await pilot.pause()
            assert macro_input.value != original
            assert macro_input.value.startswith("#")
            assert len(macro_input.value) == 7
