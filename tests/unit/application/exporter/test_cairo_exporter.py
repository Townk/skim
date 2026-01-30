# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for cairo_exporter module."""

from unittest.mock import MagicMock, patch

import drawsvg as draw
import pytest

from skim.application.exporter.cairo_exporter import CairoImageExporter


class TestCairoImageExporter:
    """Tests for CairoImageExporter class."""

    @pytest.fixture
    def exporter(self):
        """Create a CairoImageExporter instance."""
        return CairoImageExporter()

    @pytest.fixture
    def mock_font_path(self, tmp_path):
        """Create a mock font file path."""
        font_file = tmp_path / "test.ttf"
        font_file.touch()
        return font_file

    def test_init_creates_empty_converter_cache(self, exporter):
        """Initialize creates empty converter cache."""
        assert exporter._font_converters == {}

    @patch("skim.application.exporter.cairo_exporter.TextToPathConverter")
    def test_get_converter_creates_new_converter(
        self, mock_converter_class, exporter, mock_font_path
    ):
        """_get_converter creates new converter for uncached font."""
        mock_converter = MagicMock()
        mock_converter_class.return_value = mock_converter

        converter = exporter._get_converter(mock_font_path)

        mock_converter_class.assert_called_once_with(mock_font_path)
        assert converter is mock_converter
        assert mock_font_path in exporter._font_converters

    @patch("skim.application.exporter.cairo_exporter.TextToPathConverter")
    def test_get_converter_returns_cached_converter(
        self, mock_converter_class, exporter, mock_font_path
    ):
        """_get_converter returns cached converter for existing font."""
        mock_converter = MagicMock()
        mock_converter_class.return_value = mock_converter

        # First call creates the converter
        converter1 = exporter._get_converter(mock_font_path)
        # Second call should return cached
        converter2 = exporter._get_converter(mock_font_path)

        mock_converter_class.assert_called_once()
        assert converter1 is converter2

    def test_get_font_from_family_none_returns_default(self, exporter):
        """_get_font_from_family with None returns FINGER_KEY."""
        from skim.application.render.text import Font

        font = exporter._get_font_from_family(None)
        assert font == Font.FINGER_KEY

    def test_get_font_from_family_thumb_returns_thumb_key(self, exporter):
        """_get_font_from_family with 'thumb' returns THUMB_KEY."""
        from skim.application.render.text import Font

        font = exporter._get_font_from_family("MyThumbFont")
        assert font == Font.THUMB_KEY

    def test_get_font_from_family_black_returns_thumb_key(self, exporter):
        """_get_font_from_family with 'black' returns THUMB_KEY."""
        from skim.application.render.text import Font

        font = exporter._get_font_from_family("BlackFont")
        assert font == Font.THUMB_KEY

    def test_get_font_from_family_title_returns_title(self, exporter):
        """_get_font_from_family with 'title' returns TITLE."""
        from skim.application.render.text import Font

        font = exporter._get_font_from_family("TitleFont")
        assert font == Font.TITLE

    def test_get_font_from_family_thin_returns_title(self, exporter):
        """_get_font_from_family with 'thin' returns TITLE."""
        from skim.application.render.text import Font

        font = exporter._get_font_from_family("ThinFont")
        assert font == Font.TITLE

    def test_get_font_from_family_symbol_returns_symbols(self, exporter):
        """_get_font_from_family with 'symbol' returns SYMBOLS."""
        from skim.application.render.text import Font

        font = exporter._get_font_from_family("SymbolFont")
        assert font == Font.SYMBOLS

    def test_get_font_from_family_nerd_returns_symbols(self, exporter):
        """_get_font_from_family with 'nerd' returns SYMBOLS."""
        from skim.application.render.text import Font

        font = exporter._get_font_from_family("NerdFont")
        assert font == Font.SYMBOLS

    def test_get_font_from_family_other_returns_finger_key(self, exporter):
        """_get_font_from_family with unknown returns FINGER_KEY."""
        from skim.application.render.text import Font

        font = exporter._get_font_from_family("UnknownFont")
        assert font == Font.FINGER_KEY

    def test_close_closes_all_converters(self, exporter, mock_font_path):
        """close method closes all cached converters."""
        mock_converter = MagicMock()
        exporter._font_converters[mock_font_path] = mock_converter

        exporter.close()

        mock_converter.close.assert_called_once()
        assert exporter._font_converters == {}

    def test_context_manager_closes_on_exit(self, exporter, mock_font_path):
        """Context manager closes converters on exit."""
        mock_converter = MagicMock()
        exporter._font_converters[mock_font_path] = mock_converter

        with exporter:
            pass

        mock_converter.close.assert_called_once()

    @patch("skim.application.exporter.cairo_exporter.draw.Drawing")
    def test_convert_drawing_text_to_paths_returns_drawing(self, mock_drawing_class, exporter):
        """_convert_drawing_text_to_paths returns a new drawing."""
        mock_original = MagicMock()
        mock_original.width = 100
        mock_original.height = 100
        mock_original._css = "some css"
        mock_original.elements = []

        mock_new = MagicMock()
        mock_drawing_class.return_value = mock_new

        result = exporter._convert_drawing_text_to_paths(mock_original)

        mock_drawing_class.assert_called_once_with(100, 100)
        assert result is mock_new


class TestCairoImageExporterSave:
    @pytest.fixture
    def exporter(self):
        return CairoImageExporter()

    @pytest.fixture
    def mock_drawing(self):
        d = draw.Drawing(100, 100)
        d.append(draw.Rectangle(0, 0, 100, 100, fill="white"))
        return d

    @patch("skim.application.exporter.cairo_exporter.Image")
    def test_save_calls_convert_when_flag_true(self, mock_image, exporter, mock_drawing, tmp_path):
        output_path = tmp_path / "test.png"
        with patch.object(exporter, "_convert_drawing_text_to_paths") as mock_convert:
            mock_converted = draw.Drawing(100, 100)
            mock_convert.return_value = mock_converted
            with patch.object(mock_converted, "save_png"):
                exporter.save(mock_drawing, output_path, convert_text_to_paths=True)
                mock_convert.assert_called_once_with(mock_drawing, False)

    @patch("skim.application.exporter.cairo_exporter.Image")
    def test_save_png_format_skips_image_open(self, mock_image, exporter, mock_drawing, tmp_path):
        output_path = tmp_path / "test.png"
        with patch.object(mock_drawing, "save_png") as mock_save_png:
            exporter.save(mock_drawing, output_path, convert_text_to_paths=False)
            mock_save_png.assert_called_once()
            mock_image.open.assert_not_called()

    @patch("skim.application.exporter.cairo_exporter.Image")
    def test_save_converts_to_target_format(self, mock_image, exporter, mock_drawing, tmp_path):
        output_path = tmp_path / "test.jpeg"
        png_path = tmp_path / "test.png"
        mock_img = MagicMock()
        mock_image.open.return_value.__enter__.return_value = mock_img

        def create_png_file(*args, **kwargs):
            png_path.touch()

        with patch.object(mock_drawing, "save_png", side_effect=create_png_file):
            exporter.save(mock_drawing, output_path, convert_text_to_paths=False)
            mock_img.save.assert_called_once_with(output_path)

    def test_save_raises_on_png_error(self, exporter, mock_drawing, tmp_path):
        output_path = tmp_path / "test.png"
        with patch.object(mock_drawing, "save_png") as mock_save_png:
            mock_save_png.side_effect = Exception("Cairo error")
            with pytest.raises(RuntimeError, match="Failed to rasterize with Cairo"):
                exporter.save(mock_drawing, output_path)


class TestCairoImageExporterConvertDrawing:
    @pytest.fixture
    def exporter(self):
        return CairoImageExporter()

    def test_convert_drawing_handles_list_result(self, exporter):
        original = draw.Drawing(100, 100)
        original.elements = [draw.Rectangle(0, 0, 50, 50)]
        with patch.object(exporter, "_convert_element") as mock_convert:
            mock_elem1 = draw.Rectangle(0, 0, 10, 10)
            mock_elem2 = draw.Rectangle(10, 10, 20, 20)
            mock_convert.return_value = [mock_elem1, mock_elem2]
            result = exporter._convert_drawing_text_to_paths(original)
            assert len(result.elements) == 2

    def test_convert_drawing_handles_single_element(self, exporter):
        original = draw.Drawing(100, 100)
        original.elements = [draw.Rectangle(0, 0, 50, 50)]
        with patch.object(exporter, "_convert_element") as mock_convert:
            mock_elem = draw.Rectangle(0, 0, 10, 10)
            mock_convert.return_value = mock_elem
            result = exporter._convert_drawing_text_to_paths(original)
            assert len(result.elements) == 1


class TestCairoImageExporterConvertElement:
    @pytest.fixture
    def exporter(self):
        return CairoImageExporter()

    def test_convert_element_returns_text_for_text(self, exporter):
        text_elem = draw.Text("Hello", 12, 10, 10)
        with patch.object(exporter, "_convert_text_element") as mock_convert:
            mock_group = draw.Group()
            mock_convert.return_value = mock_group
            result = exporter._convert_element(text_elem)
            assert result is mock_group

    def test_convert_element_handles_group(self, exporter):
        group = draw.Group()
        group.append(draw.Rectangle(0, 0, 10, 10))
        result = exporter._convert_element(group)
        assert isinstance(result, draw.Group)

    def test_convert_element_handles_group_with_transform(self, exporter):
        group = draw.Group(transform="translate(10, 10)")
        result = exporter._convert_element(group)
        assert isinstance(result, draw.Group)

        test_drawing = draw.Drawing(100, 100)
        test_drawing.append(result)
        svg_output = test_drawing.as_svg()
        assert svg_output is not None
        assert 'transform="translate(10, 10)"' in svg_output

    def test_convert_element_returns_element_unchanged(self, exporter):
        rect = draw.Rectangle(0, 0, 10, 10)
        result = exporter._convert_element(rect)
        assert result is rect


class TestCairoImageExporterConvertTextElement:
    @pytest.fixture
    def exporter(self):
        return CairoImageExporter()

    @pytest.fixture
    def mock_font_path(self, tmp_path):
        font_file = tmp_path / "test.ttf"
        font_file.touch()
        return font_file

    @patch("skim.application.exporter.cairo_exporter.TextToPathConverter")
    def test_convert_text_element_middle_anchor(
        self, mock_converter_class, exporter, mock_font_path
    ):
        from skim.application.render.text import Font

        text_elem = draw.Text("Hello", 12, 100, 10, text_anchor="middle")
        mock_converter = MagicMock()
        mock_converter.get_text_width.return_value = 50
        mock_converter.convert_text.return_value = ([], 100.0)
        mock_converter_class.return_value = mock_converter
        with (
            patch.object(exporter, "_get_font_from_family", return_value=Font.FINGER_KEY),
            patch.object(Font.FINGER_KEY, "path", mock_font_path),
        ):
            result = exporter._convert_text_element(text_elem)
        assert isinstance(result, draw.Group)

    @patch("skim.application.exporter.cairo_exporter.TextToPathConverter")
    def test_convert_text_element_end_anchor(self, mock_converter_class, exporter, mock_font_path):
        from skim.application.render.text import Font

        text_elem = draw.Text("Hello", 12, 100, 10, text_anchor="end")
        mock_converter = MagicMock()
        mock_converter.get_text_width.return_value = 50
        mock_converter.convert_text.return_value = ([], 100.0)
        mock_converter_class.return_value = mock_converter
        with (
            patch.object(exporter, "_get_font_from_family", return_value=Font.FINGER_KEY),
            patch.object(Font.FINGER_KEY, "path", mock_font_path),
        ):
            result = exporter._convert_text_element(text_elem)
        assert isinstance(result, draw.Group)

    @patch("skim.application.exporter.cairo_exporter.TextToPathConverter")
    def test_convert_text_element_with_tspan(self, mock_converter_class, exporter, mock_font_path):
        from skim.application.render.text import Font

        text_elem = draw.Text("Hello", 12, 10, 10)
        text_elem.append(draw.TSpan("World"))
        mock_converter = MagicMock()
        mock_converter.get_text_width.return_value = 30
        mock_converter.convert_text.return_value = (
            [{"d": "M0,0", "transform": "", "fill": "#000"}],
            40.0,
        )
        mock_converter_class.return_value = mock_converter
        with (
            patch.object(exporter, "_get_font_from_family", return_value=Font.FINGER_KEY),
            patch.object(Font.FINGER_KEY, "path", mock_font_path),
        ):
            result = exporter._convert_text_element(text_elem)
        assert isinstance(result, draw.Group)
