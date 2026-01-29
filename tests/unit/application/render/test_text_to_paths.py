"""Unit tests for text_to_paths module."""

from unittest.mock import MagicMock, patch

import pytest

from skim.application.render.text_to_paths import (
    FontReader,
    GlyphMetrics,
    GlyphNotFoundError,
)


class TestGlyphMetrics:
    """Tests for GlyphMetrics dataclass."""

    def test_glyph_metrics_creation(self):
        """Can create GlyphMetrics with all fields."""
        metrics = GlyphMetrics(
            advance_width=100.0,
            left_side_bearing=10.0,
            x_min=0.0,
            y_min=-10.0,
            x_max=100.0,
            y_max=90.0,
        )
        assert metrics.advance_width == 100.0
        assert metrics.left_side_bearing == 10.0
        assert metrics.x_min == 0.0
        assert metrics.y_min == -10.0
        assert metrics.x_max == 100.0
        assert metrics.y_max == 90.0


class TestFontReader:
    """Tests for FontReader class."""

    @pytest.fixture
    def mock_font_path(self, tmp_path):
        """Create a mock font file path."""
        font_file = tmp_path / "test.ttf"
        font_file.touch()
        return font_file

    @patch("skim.application.render.text_to_paths.TTFont")
    def test_init_loads_font(self, mock_ttfont, mock_font_path):
        """Initialize FontReader loads font file."""
        mock_font = MagicMock()
        mock_font["head"].unitsPerEm = 1000
        mock_font["hhea"].ascender = 800
        mock_font["hhea"].descender = -200
        mock_font.getGlyphSet.return_value = {}
        mock_ttfont.return_value = mock_font

        reader = FontReader(mock_font_path)

        assert reader.font_path == mock_font_path
        assert reader.units_per_em == 1000
        assert reader.ascent == 800
        assert reader.descent == -200
        mock_ttfont.assert_called_once_with(str(mock_font_path))

    @patch("skim.application.render.text_to_paths.TTFont")
    def test_get_glyph_path_single_char_only(self, mock_ttfont, mock_font_path):
        """get_glyph_path requires single character."""
        mock_font = MagicMock()
        mock_font.getGlyphSet.return_value = {}
        mock_font.getBestCmap.return_value = {}
        mock_ttfont.return_value = mock_font

        reader = FontReader(mock_font_path)

        with pytest.raises(ValueError, match="Expected single character"):
            reader.get_glyph_path("ab")

    @patch("skim.application.render.text_to_paths.TTFont")
    def test_get_glyph_path_no_cmap(self, mock_ttfont, mock_font_path):
        """get_glyph_path raises error when no cmap found."""
        mock_font = MagicMock()
        mock_font.getGlyphSet.return_value = {}
        mock_font.getBestCmap.return_value = None
        mock_ttfont.return_value = mock_font

        reader = FontReader(mock_font_path)

        with pytest.raises(GlyphNotFoundError, match="No cmap found"):
            reader.get_glyph_path("a")

    @patch("skim.application.render.text_to_paths.TTFont")
    def test_get_glyph_path_glyph_not_found(self, mock_ttfont, mock_font_path):
        """get_glyph_path raises error when glyph not in cmap."""
        mock_font = MagicMock()
        mock_font.getGlyphSet.return_value = {}
        mock_font.getBestCmap.return_value = {99: "c"}
        mock_ttfont.return_value = mock_font

        reader = FontReader(mock_font_path)

        with pytest.raises(GlyphNotFoundError, match="No glyph for"):
            reader.get_glyph_path("a")

    @patch("skim.application.render.text_to_paths.TTFont")
    def test_get_glyph_metrics_single_char_only(self, mock_ttfont, mock_font_path):
        """get_glyph_metrics requires single character."""
        mock_font = MagicMock()
        mock_font.getGlyphSet.return_value = {}
        mock_font.getBestCmap.return_value = {}
        mock_ttfont.return_value = mock_font

        reader = FontReader(mock_font_path)

        with pytest.raises(ValueError, match="Expected single character"):
            reader.get_glyph_metrics("ab")

    @patch("skim.application.render.text_to_paths.TTFont")
    def test_get_glyph_metrics_not_in_cmap(self, mock_ttfont, mock_font_path):
        """get_glyph_metrics returns zeros when glyph not in cmap."""
        mock_font = MagicMock()
        mock_font.getGlyphSet.return_value = {}
        mock_font.getBestCmap.return_value = {}
        mock_ttfont.return_value = mock_font

        reader = FontReader(mock_font_path)
        metrics = reader.get_glyph_metrics("a")

        assert metrics == GlyphMetrics(0, 0, 0, 0, 0, 0)

    @patch("skim.application.render.text_to_paths.TTFont")
    def test_get_text_width_sums_metrics(self, mock_ttfont, mock_font_path):
        """get_text_width sums advance widths of all characters."""
        mock_font = MagicMock()
        mock_font.getBestCmap.return_value = {97: "a_glyph", 98: "b_glyph"}

        hmtx_table = {"a_glyph": (50, 5), "b_glyph": (60, 6)}
        mock_font.__getitem__.side_effect = lambda key: hmtx_table if key == "hmtx" else MagicMock()

        glyph_a = MagicMock()
        glyph_a.bounds = (0, 0, 50, 50)
        glyph_b = MagicMock()
        glyph_b.bounds = (0, 0, 60, 60)

        glyph_set = {"a_glyph": glyph_a, "b_glyph": glyph_b}
        mock_font.getGlyphSet.return_value = glyph_set
        mock_ttfont.return_value = mock_font

        reader = FontReader(mock_font_path)
        width = reader.get_text_width("ab")

        assert width == 110

    @patch("skim.application.render.text_to_paths.TTFont")
    def test_close_closes_font(self, mock_ttfont, mock_font_path):
        """close method closes the underlying font."""
        mock_font = MagicMock()
        mock_font.getGlyphSet.return_value = {}
        mock_ttfont.return_value = mock_font

        reader = FontReader(mock_font_path)
        reader.close()

        mock_font.close.assert_called_once()

    @patch("skim.application.render.text_to_paths.TTFont")
    def test_context_manager_closes_font(self, mock_ttfont, mock_font_path):
        """Context manager closes font on exit."""
        mock_font = MagicMock()
        mock_font.getGlyphSet.return_value = {}
        mock_ttfont.return_value = mock_font

        with FontReader(mock_font_path) as reader:
            assert reader is not None

        mock_font.close.assert_called_once()
