"""Unit tests for skim.tui.widgets module."""

from skim.tui.widgets import SkimInput, SkimListView, SkimSelect, SkimSwitch


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
        """SkimSwitch has enter/space binding."""
        keys = {b.key for b in SkimSwitch.BINDINGS}
        assert "enter,space" in keys

    def test_skim_select_has_bindings(self):
        """SkimSelect has enter/space and escape bindings."""
        keys = {b.key for b in SkimSelect.BINDINGS}
        assert "enter,space" in keys
        assert "escape" in keys
