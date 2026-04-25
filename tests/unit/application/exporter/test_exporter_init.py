# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for exporter __init__ module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from skim.data.cli import OutputFiles, RenderEngine


class TestAvailabilityFunctions:
    def test_is_playwright_available_returns_bool(self):
        from skim.application.exporter import is_playwright_available

        result = is_playwright_available()
        assert isinstance(result, bool)

    def test_is_cairo_available_returns_bool(self):
        from skim.application.exporter import is_cairo_available

        result = is_cairo_available()
        assert isinstance(result, bool)


class TestGetAvailableFormats:
    def test_returns_svg_always(self):
        from skim.application.exporter import get_available_export_formats

        formats = get_available_export_formats()
        assert "svg" in formats

    def test_returns_list_of_strings(self):
        from skim.application.exporter import get_available_export_formats

        formats = get_available_export_formats()
        assert isinstance(formats, list)
        assert all(isinstance(f, str) for f in formats)


class TestGetAvailableRenderEngines:
    def test_returns_list_of_render_engines(self):
        from skim.application.exporter import get_available_render_engines

        engines = get_available_render_engines()
        assert isinstance(engines, list)
        assert all(isinstance(e, RenderEngine) for e in engines)


class TestGetRenderEngine:
    @patch("skim.application.exporter.get_available_render_engines")
    def test_raises_when_no_engines_available(self, mock_get_engines):
        from skim.application.exporter import _get_render_engine

        mock_get_engines.return_value = []

        with pytest.raises(RuntimeError, match="No render engines available"):
            _get_render_engine(None)

    @patch("skim.application.exporter.get_available_render_engines")
    def test_returns_first_when_none_requested(self, mock_get_engines):
        from skim.application.exporter import _get_render_engine

        mock_get_engines.return_value = [RenderEngine.CHROMIUM, RenderEngine.CAIRO]

        result = _get_render_engine(None)
        assert result == RenderEngine.CHROMIUM

    @patch("skim.application.exporter.get_available_render_engines")
    def test_returns_requested_when_available(self, mock_get_engines):
        from skim.application.exporter import _get_render_engine

        mock_get_engines.return_value = [RenderEngine.CHROMIUM, RenderEngine.CAIRO]

        result = _get_render_engine(RenderEngine.CAIRO)
        assert result == RenderEngine.CAIRO

    @patch("skim.application.exporter.get_available_render_engines")
    def test_raises_when_requested_not_available(self, mock_get_engines):
        from skim.application.exporter import _get_render_engine

        mock_get_engines.return_value = [RenderEngine.CHROMIUM]

        with pytest.raises(RuntimeError, match="Render engine cairo is not available"):
            _get_render_engine(RenderEngine.CAIRO)


class TestSaveKeymapImages:
    @patch("skim.application.exporter._save_keymap_images_async")
    def test_runs_async_function(self, mock_async):
        from skim.application.exporter import _save_keymap_images

        mock_drawing = MagicMock()
        drawings = {"test": mock_drawing}
        output_dir = Path("/tmp")

        _save_keymap_images(drawings, output_dir, "png")

        mock_async.assert_called_once()


class TestSaveDrawings:
    @patch("skim.application.exporter.sys")
    @patch("skim.application.exporter.click.confirm")
    @patch("skim.application.exporter._save_keymap_images")
    def test_confirms_when_files_exist(self, mock_save, mock_confirm, mock_sys, tmp_path):
        from skim.application.exporter import save_drawings

        mock_sys.stdin.isatty.return_value = True
        (tmp_path / "test.png").touch()
        mock_drawing = MagicMock()
        drawings = {"test": mock_drawing}
        outputs = OutputFiles(
            output_dir=tmp_path,
            output_format="png",
            force_overwrite=False,
            use_system_fonts=False,
        )

        save_drawings(outputs, drawings)

        mock_confirm.assert_called_once()

    @patch("skim.application.exporter._confirm_via_tty")
    @patch("skim.application.exporter.sys")
    @patch("skim.application.exporter._save_keymap_images")
    def test_confirms_via_tty_when_stdin_is_pipe(
        self, mock_save, mock_sys, mock_confirm_tty, tmp_path
    ):
        from skim.application.exporter import save_drawings

        mock_sys.stdin.isatty.return_value = False
        (tmp_path / "test.png").touch()
        mock_drawing = MagicMock()
        drawings = {"test": mock_drawing}
        outputs = OutputFiles(
            output_dir=tmp_path,
            output_format="png",
            force_overwrite=False,
            use_system_fonts=False,
        )

        save_drawings(outputs, drawings)

        mock_confirm_tty.assert_called_once()

    @patch("skim.application.exporter._save_keymap_images")
    def test_skips_confirm_when_force_overwrite(self, mock_save, tmp_path):
        from skim.application.exporter import save_drawings

        (tmp_path / "test.png").touch()
        mock_drawing = MagicMock()
        drawings = {"test": mock_drawing}
        outputs = OutputFiles(
            output_dir=tmp_path,
            output_format="png",
            force_overwrite=True,
            use_system_fonts=False,
        )

        save_drawings(outputs, drawings)

        mock_save.assert_called_once()


class TestCheckCairoAvailable:
    def test_returns_bool(self):
        from skim.application.exporter.availability import check_cairo_available

        result = check_cairo_available()
        assert isinstance(result, bool)
