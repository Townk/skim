# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.application.exporter module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from skim.application.exporter import _save_keymap_images_async, save_drawings
from skim.data.cli import OutputFiles


class TestSaveDrawingsRasterExport:
    """Tests for non-SVG export path using image_exporter."""

    @pytest.fixture
    def mock_drawing(self):
        """Create a mock drawing object."""
        drawing = MagicMock()
        drawing.width = 800
        drawing.height = 600
        drawing.as_svg.return_value = "<svg></svg>"
        return drawing

    @pytest.fixture
    def output_files(self, tmp_path):
        """Create OutputFiles for PNG export."""
        return OutputFiles(
            output_dir=tmp_path,
            output_format="png",
            force_overwrite=True,
        )

    @patch("skim.application.exporter._save_keymap_images")
    def test_saves_png_format(self, mock_save, mock_drawing, output_files):
        """Save drawings in PNG format."""
        drawings = {"test": mock_drawing}
        save_drawings(output_files, drawings)
        mock_save.assert_called_once_with(
            drawings, output_files.output_dir, "png", None, False, False
        )

    @patch("skim.application.exporter._save_keymap_images")
    def test_saves_jpeg_format(self, mock_save, tmp_path):
        """Save drawings in JPEG format."""
        drawing = MagicMock()
        drawing.width = 800
        drawing.height = 600

        output_files = OutputFiles(
            output_dir=tmp_path,
            output_format="jpeg",
            force_overwrite=True,
        )
        drawings = {"test": drawing}

        save_drawings(output_files, drawings)
        mock_save.assert_called_once_with(drawings, tmp_path, "jpeg", None, False, False)

    @patch("skim.application.exporter._save_keymap_images")
    def test_saves_webp_format(self, mock_save, tmp_path):
        """Save drawings in WebP format."""
        drawing = MagicMock()
        drawing.width = 800
        drawing.height = 600

        output_files = OutputFiles(
            output_dir=tmp_path,
            output_format="webp",
            force_overwrite=True,
        )
        drawings = {"test": drawing}

        save_drawings(output_files, drawings)
        mock_save.assert_called_once_with(drawings, tmp_path, "webp", None, False, False)


class TestSaveDrawingsConfirmation:
    """Tests for overwrite confirmation dialog."""

    @pytest.fixture
    def existing_drawing(self, tmp_path):
        """Create a drawing and existing file."""
        drawing = MagicMock()
        (tmp_path / "test.svg").write_text("existing content")
        drawing.save_svg = MagicMock()
        return drawing

    @patch("skim.application.exporter.sys")
    @patch("skim.application.exporter.click.confirm")
    def test_shows_confirmation_when_files_exist(
        self, mock_confirm, mock_sys, tmp_path
    ):
        """Shows confirmation when output files already exist."""
        mock_sys.stdin.isatty.return_value = True
        (tmp_path / "layer-0.svg").touch()
        drawing = MagicMock()
        drawing.save_svg = MagicMock()

        output_files = OutputFiles(
            output_dir=tmp_path,
            output_format="svg",
            force_overwrite=False,
        )
        drawings = {"layer-0": drawing}

        save_drawings(output_files, drawings)

        mock_confirm.assert_called_once()

    @patch("skim.application.exporter.sys")
    @patch("skim.application.exporter.click.confirm")
    def test_confirmation_lists_all_existing_files(
        self, mock_confirm, mock_sys, tmp_path
    ):
        """Confirmation lists all existing files."""
        mock_sys.stdin.isatty.return_value = True
        (tmp_path / "layer-1.svg").touch()
        (tmp_path / "layer-2.svg").touch()

        drawing = MagicMock()
        drawing.save_svg = MagicMock()

        output_files = OutputFiles(
            output_dir=tmp_path,
            output_format="svg",
            force_overwrite=False,
        )
        drawings = {"layer-1": drawing, "layer-2": drawing}

        save_drawings(output_files, drawings)

        assert mock_confirm.called

    def test_skips_confirmation_when_force_overwrite(self, tmp_path):
        """Skips confirmation when force_overwrite is True."""
        (tmp_path / "test.svg").touch()

        drawing = MagicMock()
        drawing.save_svg = MagicMock()

        output_files = OutputFiles(
            output_dir=tmp_path,
            output_format="svg",
            force_overwrite=True,
        )
        drawings = {"test": drawing}

        save_drawings(output_files, drawings)
        assert drawing.save_svg.called

    def test_skips_confirmation_when_no_existing_files(self, tmp_path):
        """Skips confirmation when no existing files."""
        drawing = MagicMock()
        drawing.save_svg = MagicMock()

        output_files = OutputFiles(
            output_dir=tmp_path,
            output_format="svg",
            force_overwrite=False,
        )
        drawings = {"test": drawing}

        save_drawings(output_files, drawings)
        assert drawing.save_svg.called

    @patch("skim.application.exporter.sys")
    @patch("skim.application.exporter.click.confirm")
    def test_aborts_when_user_denies_overwrite(
        self, mock_confirm, mock_sys, tmp_path
    ):
        """Aborts program when user denies overwrite confirmation."""
        mock_sys.stdin.isatty.return_value = True
        (tmp_path / "layer-0.svg").touch()
        drawing = MagicMock()
        drawing.save_svg = MagicMock()

        output_files = OutputFiles(
            output_dir=tmp_path,
            output_format="svg",
            force_overwrite=False,
        )
        drawings = {"layer-0": drawing}

        # click.confirm with abort=True raises click.Abort when user says No
        mock_confirm.side_effect = SystemExit(1)

        with pytest.raises(SystemExit):
            save_drawings(output_files, drawings)

        # Verify file was not overwritten
        assert drawing.save_svg.call_count == 0
        mock_confirm.assert_called_once()

    @patch("skim.application.exporter.sys")
    @patch("skim.application.exporter.click.confirm")
    @patch("skim.application.exporter._save_keymap_images")
    def test_overwrites_file_when_user_confirms(
        self, mock_save, mock_confirm, mock_sys, tmp_path
    ):
        """Overwrites existing file when user confirms overwrite."""
        mock_sys.stdin.isatty.return_value = True
        (tmp_path / "layer-0.svg").touch()
        drawing = MagicMock()
        drawing.save_svg = MagicMock()

        output_files = OutputFiles(
            output_dir=tmp_path,
            output_format="svg",
            force_overwrite=False,
        )
        drawings = {"layer-0": drawing}

        # click.confirm returns True when user says Yes
        mock_confirm.return_value = True

        save_drawings(output_files, drawings)

        # Verify confirmation was shown
        mock_confirm.assert_called_once()
        # Verify save operation was executed
        mock_save.assert_called_once_with(drawings, tmp_path, "svg", None, False, False)


class TestSaveKeymapImagesAsync:
    """Tests for _save_keymap_images_async function."""

    @pytest.mark.asyncio
    async def test_saves_svg_directly(self, tmp_path):
        """Saves SVG files directly without browser."""
        drawing = MagicMock()
        drawing.save_svg = MagicMock()

        drawings = {"layer-0": drawing, "layer-1": drawing}

        await _save_keymap_images_async(drawings, tmp_path, "svg", None, False, False)

        assert drawing.save_svg.call_count == 2

    @pytest.mark.asyncio
    async def test_saves_png_using_exporter(self, tmp_path):
        """Saves PNG files using image exporter."""
        drawing = MagicMock()
        drawings = {"layer-0": drawing}

        mock_exporter = AsyncMock()

        with (
            patch("skim.application.exporter._chromium_exporter") as mock_chromium_exporter,
            patch("skim.application.exporter._PLAYWRIGHT_AVAILABLE", True),
        ):
            mock_chromium_exporter.return_value.__aenter__ = AsyncMock(return_value=mock_exporter)
            mock_chromium_exporter.return_value.__aexit__ = AsyncMock(return_value=None)

            await _save_keymap_images_async(drawings, tmp_path, "png", None, False, False)

            mock_exporter.save.assert_called_once_with(drawing, tmp_path / "layer-0.png")

    @pytest.mark.asyncio
    async def test_saves_multiple_files_using_exporter(self, tmp_path):
        """Saves multiple files using image exporter."""
        drawing1 = MagicMock()
        drawing2 = MagicMock()
        drawings = {"layer-0": drawing1, "layer-1": drawing2}

        mock_exporter = AsyncMock()

        with (
            patch("skim.application.exporter._chromium_exporter") as mock_chromium_exporter,
            patch("skim.application.exporter._PLAYWRIGHT_AVAILABLE", True),
        ):
            mock_chromium_exporter.return_value.__aenter__ = AsyncMock(return_value=mock_exporter)
            mock_chromium_exporter.return_value.__aexit__ = AsyncMock(return_value=None)

            await _save_keymap_images_async(drawings, tmp_path, "jpeg", None, False, False)

            assert mock_exporter.save.call_count == 2
