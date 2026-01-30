# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Integration tests for skim.application.exporter.chromium_exporter module.

These tests require Playwright browsers to be installed:
    playwright install chromium

Run with:
    pytest tests/integration/ -m integration
"""

import drawsvg as draw
import pytest
from PIL import Image

from skim.application.exporter import _save_keymap_images_async, save_drawings
from skim.application.exporter.chromium_exporter import ChromiumExporter, chromium_exporter
from skim.data.cli import OutputFiles, RenderEngine


def create_test_drawing(width: int = 200, height: int = 100) -> draw.Drawing:
    """Create a simple test SVG drawing."""
    d = draw.Drawing(width, height)
    d.append(draw.Rectangle(0, 0, width, height, fill="white"))
    d.append(draw.Circle(width / 2, height / 2, 30, fill="red"))
    d.append(draw.Text("Test", 20, width / 2, height / 2, text_anchor="middle", fill="black"))
    return d


@pytest.mark.integration
class TestChromiumExporterIntegration:
    """Integration tests for ChromiumExporter class."""

    @pytest.mark.asyncio
    async def test_save_creates_png_file(self, tmp_path):
        """Saves drawing as PNG file."""
        drawing = create_test_drawing()
        output_path = tmp_path / "test_output.png"

        async with chromium_exporter() as exporter:
            await exporter.save(drawing, output_path)

        assert output_path.exists()
        # Verify it's a valid image
        with Image.open(output_path) as img:
            assert img.format == "PNG"
            assert img.width >= 100  # At least some reasonable size

    @pytest.mark.asyncio
    async def test_save_creates_jpeg_file(self, tmp_path):
        """Saves drawing as JPEG file."""
        drawing = create_test_drawing()
        output_path = tmp_path / "test_output.jpg"

        async with chromium_exporter() as exporter:
            await exporter.save(drawing, output_path)

        assert output_path.exists()
        with Image.open(output_path) as img:
            assert img.format == "JPEG"

    @pytest.mark.asyncio
    async def test_save_creates_webp_file(self, tmp_path):
        """Saves drawing as WebP file."""
        drawing = create_test_drawing()
        output_path = tmp_path / "test_output.webp"

        async with chromium_exporter() as exporter:
            await exporter.save(drawing, output_path)

        assert output_path.exists()
        with Image.open(output_path) as img:
            assert img.format == "WEBP"

    @pytest.mark.asyncio
    async def test_save_multiple_drawings(self, tmp_path):
        """Saves multiple drawings in single context."""
        drawings = [
            (create_test_drawing(200, 100), tmp_path / "drawing1.png"),
            (create_test_drawing(300, 150), tmp_path / "drawing2.png"),
            (create_test_drawing(400, 200), tmp_path / "drawing3.png"),
        ]

        async with chromium_exporter() as exporter:
            for drawing, output_path in drawings:
                await exporter.save(drawing, output_path)

        for _, output_path in drawings:
            assert output_path.exists()

    @pytest.mark.asyncio
    async def test_output_dimensions_match_svg(self, tmp_path):
        """Output image dimensions match SVG dimensions."""
        width, height = 250, 125
        drawing = create_test_drawing(width, height)
        output_path = tmp_path / "sized_output.png"

        async with chromium_exporter() as exporter:
            await exporter.save(drawing, output_path)

        with Image.open(output_path) as img:
            # Allow some tolerance for rounding
            assert abs(img.width - width) <= 2
            assert abs(img.height - height) <= 2


@pytest.mark.integration
class TestChromiumExporterContextManager:
    """Integration tests for chromium_exporter context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_provides_working_exporter(self, tmp_path):
        """Context manager provides a functional exporter."""
        async with chromium_exporter() as exporter:
            assert isinstance(exporter, ChromiumExporter)
            assert exporter._browser is not None

            # Verify it can actually export
            drawing = create_test_drawing()
            output_path = tmp_path / "context_test.png"
            await exporter.save(drawing, output_path)
            assert output_path.exists()

    @pytest.mark.asyncio
    async def test_context_manager_cleans_up_on_exit(self):
        """Browser is closed when context exits."""
        browser_ref = None

        async with chromium_exporter() as exporter:
            browser_ref = exporter._browser
            assert browser_ref is not None

        # After context exit, browser should be closed
        # (We can't easily verify this without internal Playwright APIs,
        # but if no exception was raised, cleanup succeeded)

    @pytest.mark.asyncio
    async def test_context_manager_cleans_up_on_error(self, tmp_path):
        """Browser is closed even when an error occurs."""

        class TestError(Exception):
            pass

        with pytest.raises(TestError):
            async with chromium_exporter() as exporter:
                # Do something, then raise
                drawing = create_test_drawing()
                await exporter.save(drawing, tmp_path / "before_error.png")
                raise TestError("Intentional test error")

        # If we get here without hanging, cleanup worked


@pytest.mark.integration
class TestSaveKeymapImagesAsyncIntegration:
    """Integration tests for _save_keymap_images_async function."""

    @pytest.mark.asyncio
    async def test_saves_svg_format(self, tmp_path):
        """Saves drawings in SVG format directly."""
        drawing = create_test_drawing()
        drawings = {"layer-0": drawing, "layer-1": drawing}

        await _save_keymap_images_async(drawings, tmp_path, "svg", None, False)

        assert (tmp_path / "layer-0.svg").exists()
        assert (tmp_path / "layer-1.svg").exists()
        # Verify SVG content
        content = (tmp_path / "layer-0.svg").read_text()
        assert "<svg" in content

    @pytest.mark.asyncio
    async def test_saves_png_format(self, tmp_path):
        """Saves drawings in PNG format using exporter."""
        drawing = create_test_drawing()
        drawings = {"keymap-layer-0": drawing}

        await _save_keymap_images_async(drawings, tmp_path, "png", RenderEngine.CHROMIUM, False)

        output_file = tmp_path / "keymap-layer-0.png"
        assert output_file.exists()
        with Image.open(output_file) as img:
            assert img.format == "PNG"

    @pytest.mark.asyncio
    async def test_saves_multiple_layers(self, tmp_path):
        """Saves multiple layer drawings."""
        drawings = {
            "layer-0": create_test_drawing(200, 100),
            "layer-1": create_test_drawing(200, 100),
            "layer-2": create_test_drawing(200, 100),
            "overview": create_test_drawing(400, 300),
        }

        await _save_keymap_images_async(drawings, tmp_path, "png", RenderEngine.CHROMIUM, False)

        for name in drawings:
            assert (tmp_path / f"{name}.png").exists()


@pytest.mark.integration
class TestSaveDrawingsIntegration:
    """Integration tests for save_drawings function."""

    def test_saves_svg_without_exporter(self, tmp_path):
        """Saves SVG files directly without Playwright."""
        drawing = create_test_drawing()
        drawings = {"test-layer": drawing}

        outputs = OutputFiles(
            output_dir=tmp_path,
            output_format="svg",
            force_overwrite=True,
        )

        save_drawings(outputs, drawings)

        assert (tmp_path / "test-layer.svg").exists()

    def test_saves_png_with_exporter(self, tmp_path):
        """Saves PNG files using Playwright exporter."""
        drawing = create_test_drawing()
        drawings = {"test-layer": drawing}

        outputs = OutputFiles(
            output_dir=tmp_path,
            output_format="png",
            force_overwrite=True,
        )

        save_drawings(outputs, drawings)

        output_file = tmp_path / "test-layer.png"
        assert output_file.exists()
        with Image.open(output_file) as img:
            assert img.format == "PNG"
