# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Comprehensive unit tests for text_to_paths module to achieve 95%+ coverage."""

from unittest.mock import MagicMock, patch

import pytest

from skim.application.exporter.text_to_paths import (
    FontReader,
    GlyphMetrics,
    TextToPathConverter,
)


class TestFontReaderGetGlyphPathSuccess:
    @pytest.fixture
    def mock_font_path(self, tmp_path):
        font_file = tmp_path / "test.ttf"
        font_file.touch()
        return font_file

    @patch("skim.application.exporter.text_to_paths.TTFont")
    @patch("skim.application.exporter.text_to_paths.SVGPathPen")
    def test_get_glyph_path_success(self, mock_pen_class, mock_ttfont, mock_font_path):
        mock_font = MagicMock()
        mock_font.getBestCmap.return_value = {97: "a_glyph"}
        mock_font.getGlyphSet.return_value = {"a_glyph": MagicMock()}
        mock_ttfont.return_value = mock_font

        mock_pen = MagicMock()
        mock_pen.getCommands.return_value = "M0,0 L10,10"
        mock_pen_class.return_value = mock_pen

        reader = FontReader(mock_font_path)
        result = reader.get_glyph_path("a")

        assert result == "M0,0 L10,10"


class TestTextToPathConverterComplete:
    @pytest.fixture
    def mock_font_path(self, tmp_path):
        font_file = tmp_path / "test.ttf"
        font_file.touch()
        return font_file

    @patch("skim.application.exporter.text_to_paths.FontReader")
    def test_convert_text_empty_string(self, mock_reader_class, mock_font_path):
        mock_reader = MagicMock()
        mock_reader_class.return_value = mock_reader

        converter = TextToPathConverter(mock_font_path)
        paths, _ = converter.convert_text("", 10, 20, 12)

        assert paths == []

    @patch("skim.application.exporter.text_to_paths.FontReader")
    def test_convert_text_to_group(self, mock_reader_class, mock_font_path):
        import drawsvg as draw

        mock_reader = MagicMock()
        mock_reader.units_per_em = 1000
        mock_reader.ascent = 800
        mock_reader.get_glyph_path.return_value = "M0,0 L10,10"
        mock_reader.get_glyph_metrics.return_value = GlyphMetrics(50, 5, 0, 0, 50, 50)
        mock_reader_class.return_value = mock_reader

        converter = TextToPathConverter(mock_font_path)
        group = converter.convert_text_to_group("a", 10, 20, 12, fill="#000")

        assert isinstance(group, draw.Group)
        assert len(group.children) == 1

    @patch("skim.application.exporter.text_to_paths.FontReader")
    def test_get_text_width(self, mock_reader_class, mock_font_path):
        mock_reader = MagicMock()
        mock_reader.units_per_em = 1000
        mock_reader.get_text_width.return_value = 500
        mock_reader_class.return_value = mock_reader

        converter = TextToPathConverter(mock_font_path)
        width = converter.get_text_width("abc", 12)

        assert width == 6.0

    @patch("skim.application.exporter.text_to_paths.FontReader")
    def test_close(self, mock_reader_class, mock_font_path):
        mock_reader = MagicMock()
        mock_reader_class.return_value = mock_reader

        converter = TextToPathConverter(mock_font_path)
        converter.close()

        mock_reader.close.assert_called_once()

    @patch("skim.application.exporter.text_to_paths.FontReader")
    def test_context_manager(self, mock_reader_class, mock_font_path):
        mock_reader = MagicMock()
        mock_reader_class.return_value = mock_reader

        with TextToPathConverter(mock_font_path) as converter:
            assert converter is not None

        mock_reader.close.assert_called_once()
