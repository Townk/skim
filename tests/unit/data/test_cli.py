"""Unit tests for skim.data.cli module.

Tests cover OutputFiles, InputFiles, and KeymapGeneratorTargets including
the from_args class method for parsing CLI layer arguments.
"""

from pathlib import Path

import pytest

from skim.data.cli import InputFiles, KeymapGeneratorTargets, OutputFiles, RenderEngine


class TestOutputFiles:
    """Tests for OutputFiles dataclass."""

    def test_default_values(self):
        """OutputFiles has sensible defaults."""
        output = OutputFiles()
        assert output.output_dir == Path()
        assert output.output_format == "svg"
        assert output.force_overwrite is False

    def test_custom_values(self):
        """OutputFiles accepts custom values."""
        output = OutputFiles(
            output_dir=Path("./images"),
            output_format="png",
            force_overwrite=True,
        )
        assert output.output_dir == Path("./images")
        assert output.output_format == "png"
        assert output.force_overwrite is True

    def test_is_frozen(self):
        """OutputFiles is immutable."""
        output = OutputFiles()
        with pytest.raises(AttributeError):
            output.output_format = "png"  # type: ignore[misc]


class TestInputFiles:
    """Tests for InputFiles dataclass."""

    def test_default_values(self):
        """InputFiles has sensible defaults."""
        inputs = InputFiles()
        assert inputs.config is None
        assert inputs.keymap is None
        assert inputs.force_stdin_keymap is False

    def test_with_config_and_keymap(self):
        """InputFiles accepts config and keymap paths."""
        inputs = InputFiles(
            config=Path("config.yaml"),
            keymap=Path("keymap.kbi"),
        )
        assert inputs.config == Path("config.yaml")
        assert inputs.keymap == Path("keymap.kbi")

    def test_force_stdin_keymap(self):
        """InputFiles can force stdin for keymap."""
        inputs = InputFiles(force_stdin_keymap=True)
        assert inputs.force_stdin_keymap is True

    def test_is_frozen(self):
        """InputFiles is immutable."""
        inputs = InputFiles()
        with pytest.raises(AttributeError):
            inputs.keymap = Path("new.kbi")  # type: ignore[misc]


class TestKeymapGeneratorTargetsDefaults:
    """Tests for KeymapGeneratorTargets default initialization."""

    def test_default_values(self):
        """KeymapGeneratorTargets has sensible defaults."""
        targets = KeymapGeneratorTargets()
        assert targets.all_layers is False
        assert targets.overview is False
        assert targets.selected_layers == []

    def test_custom_values(self):
        """KeymapGeneratorTargets accepts custom values."""
        targets = KeymapGeneratorTargets(
            all_layers=True,
            overview=True,
            selected_layers=[0, 1, 2],
        )
        assert targets.all_layers is True
        assert targets.overview is True
        assert targets.selected_layers == [0, 1, 2]

    def test_is_frozen(self):
        """KeymapGeneratorTargets is immutable."""
        targets = KeymapGeneratorTargets()
        with pytest.raises(AttributeError):
            targets.all_layers = True  # type: ignore[misc]


class TestKeymapGeneratorTargetsFromArgsEmpty:
    """Tests for from_args with empty input."""

    def test_empty_tuple_returns_all_with_overview(self):
        """Empty layer tuple returns all_layers=True and overview=True."""
        targets = KeymapGeneratorTargets.from_args(())
        assert targets.all_layers is True
        assert targets.overview is True
        assert targets.selected_layers == []


class TestKeymapGeneratorTargetsFromArgsSingleNumbers:
    """Tests for from_args with single layer numbers."""

    def test_single_layer_number(self):
        """Single layer number is parsed correctly."""
        targets = KeymapGeneratorTargets.from_args(("1",))
        assert targets.all_layers is False
        assert targets.overview is False
        assert targets.selected_layers == [1]

    def test_multiple_layer_numbers(self):
        """Multiple layer numbers are parsed correctly."""
        targets = KeymapGeneratorTargets.from_args(("1", "3", "5"))
        assert targets.selected_layers == [1, 3, 5]

    def test_layer_zero(self):
        """Layer 0 is valid."""
        targets = KeymapGeneratorTargets.from_args(("0",))
        assert targets.selected_layers == [0]


class TestKeymapGeneratorTargetsFromArgsRanges:
    """Tests for from_args with layer ranges."""

    def test_simple_range(self):
        """Range like '1-3' expands to [1, 2, 3]."""
        targets = KeymapGeneratorTargets.from_args(("1-3",))
        assert targets.selected_layers == [1, 2, 3]

    def test_range_with_single_element(self):
        """Range like '5-5' expands to [5]."""
        targets = KeymapGeneratorTargets.from_args(("5-5",))
        assert targets.selected_layers == [5]

    def test_range_combined_with_numbers(self):
        """Ranges can be combined with single numbers."""
        targets = KeymapGeneratorTargets.from_args(("1", "3-5"))
        assert targets.selected_layers == [1, 3, 4, 5]

    def test_invalid_range_is_skipped(self):
        """Invalid range format logs warning and is skipped."""
        warnings = []
        targets = KeymapGeneratorTargets.from_args(("a-b",), logger=warnings.append)
        assert targets.selected_layers == []
        assert len(warnings) == 1
        assert "invalid layer range" in warnings[0].lower()

    def test_partial_invalid_range_is_skipped(self):
        """Partially invalid range (e.g., '1-x') is skipped."""
        warnings = []
        targets = KeymapGeneratorTargets.from_args(("1-x",), logger=warnings.append)
        assert targets.selected_layers == []
        assert len(warnings) == 1


class TestKeymapGeneratorTargetsFromArgsCommaSeparated:
    """Tests for from_args with comma-separated values."""

    def test_comma_separated_numbers(self):
        """Comma-separated numbers are parsed correctly."""
        targets = KeymapGeneratorTargets.from_args(("1,3,5",))
        assert targets.selected_layers == [1, 3, 5]

    def test_comma_separated_with_spaces(self):
        """Spaces around commas are handled."""
        targets = KeymapGeneratorTargets.from_args(("1, 3, 5",))
        assert targets.selected_layers == [1, 3, 5]

    def test_comma_separated_with_ranges(self):
        """Comma-separated values can include ranges."""
        targets = KeymapGeneratorTargets.from_args(("1,3-5,7",))
        assert targets.selected_layers == [1, 3, 4, 5, 7]

    def test_empty_tokens_are_skipped(self):
        """Empty tokens from trailing/leading commas are skipped."""
        targets = KeymapGeneratorTargets.from_args((",1,,3,",))
        assert targets.selected_layers == [1, 3]


class TestKeymapGeneratorTargetsFromArgsKeywords:
    """Tests for from_args with keyword arguments."""

    def test_overview_keyword(self):
        """'overview' keyword sets overview=True."""
        targets = KeymapGeneratorTargets.from_args(("overview",))
        assert targets.overview is True
        assert targets.all_layers is False
        assert targets.selected_layers == []

    def test_all_layers_keyword(self):
        """'all-layers' sets all_layers=True but not overview."""
        targets = KeymapGeneratorTargets.from_args(("all-layers",))
        assert targets.all_layers is True
        assert targets.overview is False
        assert targets.selected_layers == []

    def test_all_keyword_returns_immediately(self):
        """'all' keyword sets both and returns immediately."""
        targets = KeymapGeneratorTargets.from_args(("all",))
        assert targets.all_layers is True
        assert targets.overview is True
        assert targets.selected_layers == []

    def test_all_keyword_ignores_subsequent_args(self):
        """'all' keyword causes early return, ignoring subsequent args."""
        targets = KeymapGeneratorTargets.from_args(("all", "1", "2", "overview"))
        assert targets.all_layers is True
        assert targets.overview is True
        assert targets.selected_layers == []

    def test_overview_with_layers(self):
        """Overview can be combined with specific layers."""
        targets = KeymapGeneratorTargets.from_args(("1", "3", "overview"))
        assert targets.overview is True
        assert targets.selected_layers == [1, 3]

    def test_all_layers_clears_selected_layers(self):
        """'all-layers' clears any previously selected layers."""
        targets = KeymapGeneratorTargets.from_args(("1", "3", "all-layers"))
        assert targets.all_layers is True
        assert targets.selected_layers == []

    def test_numbers_after_all_layers_are_ignored(self):
        """Layer numbers after 'all-layers' are ignored."""
        targets = KeymapGeneratorTargets.from_args(("all-layers", "1", "3"))
        assert targets.all_layers is True
        assert targets.selected_layers == []


class TestKeymapGeneratorTargetsFromArgsInvalidInput:
    """Tests for from_args with invalid input."""

    def test_invalid_layer_string_is_skipped(self):
        """Non-numeric, non-keyword strings are skipped with warning."""
        warnings = []
        targets = KeymapGeneratorTargets.from_args(("foo",), logger=warnings.append)
        assert targets.selected_layers == []
        assert len(warnings) == 1
        assert "invalid layer selection" in warnings[0].lower()

    def test_mixed_valid_and_invalid(self):
        """Valid layers are kept, invalid ones are skipped."""
        warnings = []
        targets = KeymapGeneratorTargets.from_args(("1", "foo", "3"), logger=warnings.append)
        assert targets.selected_layers == [1, 3]
        assert len(warnings) == 1

    def test_multiple_invalid_inputs(self):
        """Multiple invalid inputs generate multiple warnings."""
        warnings = []
        targets = KeymapGeneratorTargets.from_args(("foo", "bar", "baz"), logger=warnings.append)
        assert targets.selected_layers == []
        assert len(warnings) == 3


class TestKeymapGeneratorTargetsFromArgsComplexCases:
    """Tests for from_args with complex input combinations."""

    def test_all_features_combined(self):
        """Complex combination of features."""
        targets = KeymapGeneratorTargets.from_args(("1,2-4", "6", "overview"))
        assert targets.overview is True
        assert targets.selected_layers == [1, 2, 3, 4, 6]

    def test_duplicate_layers_are_preserved(self):
        """Duplicate layer numbers are preserved (not deduplicated)."""
        targets = KeymapGeneratorTargets.from_args(("1", "1", "1"))
        assert targets.selected_layers == [1, 1, 1]

    def test_order_is_preserved(self):
        """Layer order is preserved as specified."""
        targets = KeymapGeneratorTargets.from_args(("5", "1", "3"))
        assert targets.selected_layers == [5, 1, 3]

    def test_default_logger_is_print(self):
        """Default logger is print (doesn't raise)."""
        targets = KeymapGeneratorTargets.from_args(("invalid",))
        assert targets.selected_layers == []


class TestRenderEngine:
    """Tests for RenderEngine enum."""

    def test_chromium_value(self):
        """CHROMIUM has correct value."""
        assert RenderEngine.CHROMIUM.value == "chromium"

    def test_cairo_value(self):
        """CAIRO has correct value."""
        assert RenderEngine.CAIRO.value == "cairo"

    def test_enum_comparison(self):
        """Can compare enum values."""
        assert RenderEngine.CHROMIUM != RenderEngine.CAIRO
        assert RenderEngine.CHROMIUM == RenderEngine.CHROMIUM


class TestOutputFilesWithRenderEngine:
    """Tests for OutputFiles with render_engine field."""

    def test_render_engine_defaults_to_none(self):
        """render_engine defaults to None."""
        output = OutputFiles()
        assert output.render_engine is None

    def test_render_engine_can_be_set(self):
        """render_engine can be set to a RenderEngine value."""
        output = OutputFiles(render_engine=RenderEngine.CAIRO)
        assert output.render_engine == RenderEngine.CAIRO

    def test_use_system_fonts_defaults_to_false(self):
        """use_system_fonts defaults to False."""
        output = OutputFiles()
        assert output.use_system_fonts is False

    def test_use_system_fonts_can_be_set(self):
        """use_system_fonts can be set to True."""
        output = OutputFiles(use_system_fonts=True)
        assert output.use_system_fonts is True
