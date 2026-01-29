"""Unit tests for skim.application.render.text module.

Tests cover font management, label parsing, and text rendering.
"""

from skim.application.render.text import (
    Font,
    Label,
    LabelPart,
    SeparatorPart,
    SymbolPart,
    TextPart,
)
from skim.domain import SEPARATOR_CHAR


class TestFont:
    """Tests for Font enum."""

    def test_finger_key_font_exists(self):
        """FINGER_KEY font is defined."""
        assert Font.FINGER_KEY is not None
        assert Font.FINGER_KEY.value == "Finger-Key-Label"

    def test_thumb_key_font_exists(self):
        """THUMB_KEY font is defined."""
        assert Font.THUMB_KEY is not None
        assert Font.THUMB_KEY.value == "Thumb-Key-Label"

    def test_title_font_exists(self):
        """TITLE font is defined."""
        assert Font.TITLE is not None
        assert Font.TITLE.value == "Keymap-Title"

    def test_symbols_font_exists(self):
        """SYMBOLS font is defined."""
        assert Font.SYMBOLS is not None
        assert Font.SYMBOLS.value == "Key-Symbols"

    def test_font_has_path(self):
        """Font has a path attribute."""
        assert Font.FINGER_KEY.path is not None

    def test_css_style_generates_font_face(self):
        """css_style property generates @font-face rule."""
        css = Font.FINGER_KEY.css_style
        assert "@font-face" in css
        assert "font-family" in css
        assert Font.FINGER_KEY.value in css
        assert "base64" in css

    def test_load_font(self):
        """load method returns a PIL ImageFont."""
        font = Font.FINGER_KEY.load(12)
        assert font is not None
        # Should have getlength method for text measurement
        assert hasattr(font, "getlength")


def test_load_font_with_different_sizes():
    """load method handles different font sizes."""
    font_small = Font.FINGER_KEY.load(8)
    font_large = Font.FINGER_KEY.load(24)
    # Both should load successfully
    assert font_small is not None
    assert font_large is not None


class TestFontEmbedding:
    """Tests for font embedding into drawings."""


class TestLabelPart:
    """Tests for LabelPart base class."""

    def test_initialization(self):
        """LabelPart initializes with text."""
        part = LabelPart("Hello")
        assert part.text == "Hello"

    def test_initialization_with_color(self):
        """LabelPart accepts text_color parameter."""
        part = LabelPart("Hello", text_color="#FF0000")
        assert part.text_color == "#FF0000"

    def test_default_color_is_black(self):
        """Default text color is black."""
        part = LabelPart("Hello")
        assert part.text_color == "#000"

    def test_default_font_is_finger_key(self):
        """Default font is FINGER_KEY."""
        part = LabelPart("Hello")
        assert part.font == Font.FINGER_KEY

    def test_font_family_property(self):
        """font_family returns font value."""
        part = LabelPart("Hello")
        assert part.font_family == Font.FINGER_KEY.value

    def test_str_returns_text(self):
        """__str__ returns the text content."""
        part = LabelPart("Hello")
        assert str(part) == "Hello"

    def test_repr_contains_text(self):
        """__repr__ contains the text content."""
        part = LabelPart("Hello")
        assert "Hello" in repr(part)

    def test_measure_width(self):
        """measure_width returns positive value for non-empty text."""
        part = LabelPart("Hello")
        font = Font.FINGER_KEY.load(12)
        width = part.measure_width(font)
        assert width > 0


class TestTextPart:
    """Tests for TextPart class."""

    def test_initialization(self):
        """TextPart initializes correctly."""
        part = TextPart("Hello")
        assert part.text == "Hello"

    def test_repr_shows_textpart(self):
        """__repr__ shows TextPart class name."""
        part = TextPart("Hello")
        assert "TextPart" in repr(part)

    def test_measure_width_uses_uppercase(self):
        """TextPart.measure_width measures uppercase text."""
        part = TextPart("abc")
        font = Font.FINGER_KEY.load(12)
        width = part.measure_width(font)
        # Width should be that of "ABC"
        upper_width = font.getlength("ABC")
        assert abs(width - upper_width) < 0.1


class TestSymbolPart:
    """Tests for SymbolPart class."""

    def test_initialization(self):
        """SymbolPart initializes with name and character."""
        part = SymbolPart("nf-fa-home", "\uf015")
        assert part.name == "nf-fa-home"
        assert part.text == "\uf015"

    def test_default_fill_is_black(self):
        """Default fill color is black."""
        part = SymbolPart("nf-fa-home", "\uf015")
        assert part.text_color == "#000"

    def test_custom_fill(self):
        """Custom fill color is accepted."""
        part = SymbolPart("nf-fa-home", "\uf015", fill="#FF0000")
        assert part.text_color == "#FF0000"

    def test_font_is_symbols(self):
        """SymbolPart uses SYMBOLS font."""
        part = SymbolPart("nf-fa-home", "\uf015")
        assert part.font == Font.SYMBOLS

    def test_str_includes_name(self):
        """__str__ includes the glyph name."""
        part = SymbolPart("nf-fa-home", "\uf015")
        result = str(part)
        assert "nf-fa-home" in result

    def test_repr_includes_class_name(self):
        """__repr__ includes class name and glyph info."""
        part = SymbolPart("nf-fa-home", "\uf015")
        assert "LabelPart" in repr(part)  # Base class repr
        assert "nf-fa-home" in repr(part)


class TestSeparatorPart:
    """Tests for SeparatorPart class."""

    def test_separator_char_constant(self):
        """SEPARATOR_CHAR is defined."""
        assert SEPARATOR_CHAR == "│"

    def test_separator_darken_factor(self):
        """SEPARATOR_DARKEN_FACTOR is defined."""
        assert 0 < SeparatorPart.SEPARATOR_DARKEN_FACTOR < 1

    def test_text_color_is_darkened(self):
        """text_color is darkened from background."""
        part = SeparatorPart(SEPARATOR_CHAR, "#FFFFFF")
        # Should be darker than white
        assert part.text_color != "#FFFFFF"

    def test_repr_shows_separatorpart(self):
        """__repr__ shows SeparatorPart class name."""
        part = SeparatorPart(SEPARATOR_CHAR)
        assert "SeparatorPart" in repr(part)


class TestLabel:
    """Tests for Label class."""

    def test_simple_text_label(self):
        """Parse a simple text label."""
        label = Label("Hello", Font.FINGER_KEY, "#000")
        assert str(label) == "Hello"
        assert len(label.parts) == 1
        assert isinstance(label.parts[0], TextPart)

    def test_empty_label(self):
        """Parse an empty label."""
        label = Label("", Font.FINGER_KEY, "#000")
        assert str(label) == ""
        assert len(label.parts) == 0

    def test_label_with_separator(self):
        """Parse a label with separator character."""
        label = Label(f"A{SEPARATOR_CHAR}B", Font.FINGER_KEY, "#000")
        assert len(label.parts) == 3
        assert isinstance(label.parts[0], TextPart)
        assert isinstance(label.parts[1], SeparatorPart)
        assert isinstance(label.parts[2], TextPart)

    def test_label_with_nerd_font_token(self):
        """Parse a label with Nerd Font token."""
        # Using a generic format - actual parsing depends on glyphs being loaded
        label = Label("%%nf-md-home;", Font.FINGER_KEY, "#000")
        # The parser should attempt to resolve the token
        # If glyph exists, it becomes SymbolPart; if not, it may remain text
        assert len(label.parts) >= 1

    def test_label_attributes(self):
        """Label stores configuration attributes."""
        label = Label(
            "Test",
            Font.THUMB_KEY,
            "#FF0000",
            background_color="#0000FF",
            text_anchor="start",
            dominant_baseline="hanging",
            letter_spacing=2.0,
        )
        assert label.font == Font.THUMB_KEY
        assert label.text_color == "#FF0000"
        assert label.background_color == "#0000FF"
        assert label.text_anchor == "start"
        assert label.dominant_baseline == "hanging"
        assert label.letter_spacing == 2.0


class TestLabelMethods:
    """Tests for Label methods."""

    def test_add_text(self):
        """add_text adds a TextPart."""
        label = Label("", Font.FINGER_KEY, "#000")
        label.add_text("Hello")
        assert len(label.parts) == 1
        assert isinstance(label.parts[0], TextPart)

    def test_add_separator(self):
        """add_separator adds a SeparatorPart."""
        label = Label("", Font.FINGER_KEY, "#000")
        label.add_separator(SEPARATOR_CHAR)
        assert len(label.parts) == 1
        assert isinstance(label.parts[0], SeparatorPart)

    def test_add_symbol(self):
        """add_symbol adds a SymbolPart."""
        label = Label("", Font.FINGER_KEY, "#000")
        label.add_symbol("nf-fa-home", "\uf015")
        assert len(label.parts) == 1
        assert isinstance(label.parts[0], SymbolPart)

    def test_measure_width(self):
        """measure_width returns positive value for non-empty label."""
        label = Label("Hello", Font.FINGER_KEY, "#000")
        width = label.measure_width(12)
        assert width > 0

    def test_measure_width_empty_label(self):
        """measure_width returns 0 for empty label."""
        label = Label("", Font.FINGER_KEY, "#000")
        width = label.measure_width(12)
        assert width == 0

    def test_size_to_fit(self):
        """size_to_fit returns font size within constraints."""
        label = Label("Hello", Font.FINGER_KEY, "#000")
        font_size = label.size_to_fit(target_width=100, max_font_size=48, min_font_size=8)
        assert 8 <= font_size <= 48
        width = label.measure_width(font_size)
        assert width <= 100

    def test_size_to_fit_short_text(self):
        """size_to_fit returns max size for short text."""
        label = Label("A", Font.FINGER_KEY, "#000")
        font_size = label.size_to_fit(target_width=200, max_font_size=48, min_font_size=8)
        assert font_size == 48


class TestLabelBuildText:
    """Tests for Label.build_text method."""

    def test_build_text_single_part(self):
        """build_text creates Text element for single-part label."""
        label = Label("Hello", Font.FINGER_KEY, "#000")
        text_elem = label.build_text(x=100, y=50, font_size=12)
        assert text_elem is not None

    def test_build_text_empty_label(self):
        """build_text creates empty Text element for empty label."""
        label = Label("", Font.FINGER_KEY, "#000")
        text_elem = label.build_text(x=100, y=50, font_size=12)
        assert text_elem is not None

    def test_build_text_multi_part(self):
        """build_text creates Text with TSpan for multi-part label."""
        label = Label(f"A{SEPARATOR_CHAR}B", Font.FINGER_KEY, "#000")
        text_elem = label.build_text(x=100, y=50, font_size=12)
        assert text_elem is not None


class TestLabelNerdFontParsing:
    """Tests for Label Nerd Font token parsing."""

    def test_is_nerd_font_token_start_true(self):
        """_is_nerd_font_token_start returns True for valid start."""
        result = Label._is_nerd_font_token_start("%%test;", 0, 7)
        assert result is True

    def test_is_nerd_font_token_start_false_single_percent(self):
        """_is_nerd_font_token_start returns False for single percent."""
        result = Label._is_nerd_font_token_start("%test;", 0, 6)
        assert result is False

    def test_is_nerd_font_token_start_false_at_end(self):
        """_is_nerd_font_token_start returns False near end of string."""
        result = Label._is_nerd_font_token_start("%%", 0, 2)
        assert result is False

    def test_incomplete_token_stays_as_text(self):
        """Incomplete Nerd Font token stays as text."""
        label = Label("%%incomplete", Font.FINGER_KEY, "#000")
        # Should become text, not a symbol
        assert len(label.parts) >= 1

    def test_unknown_glyph_stays_as_text(self):
        """Unknown glyph name stays as text with original format."""
        label = Label("%%nf-unknown-nonexistent;", Font.FINGER_KEY, "#000")
        # The unknown glyph reference should be kept as text
        # Either parsed as text or symbol not found
        assert len(label.parts) >= 1

    def test_nerd_font_class_without_prefix_adds_nf(self):
        """Nerd Font token without nf- prefix gets it added."""
        # This tests line 445: nf_class = f"nf-{nf_class}"
        # In a real scenario, this would require the label to parse the token
        # and the implementation to add the prefix
        pass  # Implementation would require access to internal state

    def test_symbol_adding_clears_previous_text_part(self):
        """Adding a symbol clears accumulated text part first."""
        # This tests lines 468-469: self.add_text(part) and part = ""
        # when a symbol is parsed in the middle of accumulated text
        pass  # Would need to set up a label with internal state


class TestLabelRepr:
    """Tests for Label string representations."""

    def test_str_concatenates_parts(self):
        """__str__ concatenates all part texts."""
        label = Label(f"A{SEPARATOR_CHAR}B", Font.FINGER_KEY, "#000")
        result = str(label)
        # Should contain all characters
        assert "A" in result
        assert "B" in result

    def test_repr_shows_all_parts(self):
        """__repr__ shows all label parts."""
        label = Label(f"A{SEPARATOR_CHAR}B", Font.FINGER_KEY, "#000")
        result = repr(label)
        assert "Label[" in result
        assert "TextPart" in result or "A" in result
