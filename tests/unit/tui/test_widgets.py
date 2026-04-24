"""Unit tests for skim.tui.widgets module."""

from skim.tui.widgets import (
    SkimButton,
    SkimInput,
    SkimListView,
    SkimSelect,
    SkimStandaloneInput,
    SkimSwitch,
)


class TestWidgetSubclasses:
    """Tests for the Skim widget subclasses."""

    def test_skim_input_has_bindings(self):
        """SkimInput has tab/shift+tab bindings."""
        keys = {b.key for b in SkimInput.BINDINGS}
        assert "tab" in keys
        assert "shift+tab" in keys

    def test_skim_list_view_has_bindings(self):
        """SkimListView has enter binding."""
        keys = {b.key for b in SkimListView.BINDINGS}
        assert "enter" in keys

    def test_skim_switch_has_bindings(self):
        """SkimSwitch has enter and space bindings."""
        keys = {b.key for b in SkimSwitch.BINDINGS}
        assert "enter" in keys
        assert "space" in keys

    def test_skim_select_has_bindings(self):
        """SkimSelect has enter, space, and escape bindings."""
        keys = {b.key for b in SkimSelect.BINDINGS}
        assert "enter" in keys
        assert "space" in keys
        assert "escape" in keys


class TestWidgetHelpKey:
    """Tests for the help_key parameter on custom widgets."""

    def test_skim_input_help_key_default_none(self):
        widget = SkimInput()
        assert widget.help_key is None

    def test_skim_input_help_key_set(self):
        widget = SkimInput(help_key="keyboard-layer-index")
        assert widget.help_key == "keyboard-layer-index"

    def test_skim_standalone_input_help_key_default_none(self):
        widget = SkimStandaloneInput()
        assert widget.help_key is None

    def test_skim_standalone_input_help_key_set(self):
        widget = SkimStandaloneInput(help_key="keyboard-info-title")
        assert widget.help_key == "keyboard-info-title"

    def test_skim_select_help_key_default_none(self):
        widget = SkimSelect(options=[("A", "a")])
        assert widget.help_key is None

    def test_skim_select_help_key_set(self):
        widget = SkimSelect(options=[("A", "a")], help_key="output-style-hold-symbol-position")
        assert widget.help_key == "output-style-hold-symbol-position"

    def test_skim_switch_help_key_default_none(self):
        widget = SkimSwitch()
        assert widget.help_key is None

    def test_skim_switch_help_key_set(self):
        widget = SkimSwitch(help_key="keyboard-feature-double-south")
        assert widget.help_key == "keyboard-feature-double-south"

    def test_skim_button_help_key_default_none(self):
        widget = SkimButton("Click")
        assert widget.help_key is None

    def test_skim_button_help_key_set(self):
        widget = SkimButton("Click", help_key="some-button")
        assert widget.help_key == "some-button"

    def test_skim_list_view_help_key_default_none(self):
        widget = SkimListView()
        assert widget.help_key is None

    def test_skim_list_view_help_key_set(self):
        widget = SkimListView(help_key="keyboard-layer-list")
        assert widget.help_key == "keyboard-layer-list"
