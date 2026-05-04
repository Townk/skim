# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Image exporter using Playwright for high-fidelity SVG-to-image conversion.

This module provides the ChromiumExporter class and associated context manager
for converting SVG drawings to raster image formats (PNG, JPEG, WebP, AVIF)
using a headless Chromium browser via Playwright.

Using a real browser ensures perfect rendering of fonts, CSS, and complex
SVG features that might not be fully supported by pure Python SVG rasterizers.

Example:
    ```pycon
    >>> import asyncio
    >>> from pathlib import Path
    >>> import drawsvg as draw
    >>> from skim.application.exporter.chromium_exporter import chromium_exporter
    >>>
    >>> async def export_example():
    ...     drawing = draw.Drawing(100, 100)
    ...     drawing.append(draw.Circle(50, 50, 40, fill="red"))
    ...     async with chromium_exporter() as exporter:
    ...         await exporter.save(drawing, Path("output.png"))
    >>>
    >>> # asyncio.run(export_example())

    ```
"""

import io
import os
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import drawsvg as draw
from PIL import Image
from playwright.async_api import Browser, async_playwright


class ChromiumExporter:
    """Exports SVG drawings to raster image formats using a headless browser.

    This class uses Playwright to render SVG content in a headless Chromium
    browser, then captures screenshots to create high-fidelity raster images.
    This approach ensures accurate rendering of fonts, gradients, and other
    complex SVG features.

    The exporter requires an active Playwright browser instance, which should
    be obtained through the :func:`chromium_exporter` async context manager.

    Attributes:
        _browser: The Playwright Browser instance used for rendering.

    Example:
        ```pycon
        >>> async with chromium_exporter() as exporter:
        ...     await exporter.save(drawing, Path("keymap.png"))

        ```
    """

    _browser: Browser

    def __init__(self, browser: Browser) -> None:
        """Initialize the exporter with a Playwright browser instance.

        Args:
            browser: An active Playwright Browser instance. The browser
                should remain open for the lifetime of the exporter.
        """
        self._browser = browser

    async def save(self, drawing: draw.Drawing, output_path: Path) -> None:
        """Save an SVG drawing as a raster image file.

        Renders the SVG in a headless browser and saves a screenshot to the
        specified path. The output format is determined by the file extension
        (e.g., .png, .jpg, .webp).

        The method creates a temporary SVG file for browser loading, captures
        a screenshot at the exact SVG dimensions, and saves the result using
        Pillow.

        Args:
            drawing: A drawsvg Drawing object to export.
            output_path: Path where the image file will be saved. The file
                extension determines the output format.

        Note:
            The temporary SVG file is automatically cleaned up after export,
            even if an error occurs during the process.
        """
        fd, tmp_path = tempfile.mkstemp(suffix=".svg")
        tmp_svg = Path(tmp_path)
        try:
            os.close(fd)
            drawing.save_svg(str(tmp_svg))

            page = await self._browser.new_page()

            await page.goto(f"file://{tmp_svg.absolute()}")

            dims = await page.evaluate("""
                                       () => {
                                           const svg = document.querySelector('svg');
                                           const rect = svg.getBoundingClientRect();
                                           return { width: Math.ceil(rect.width), height: Math.ceil(rect.height) };
                                       }
                                       """)

            await page.set_viewport_size({"width": dims["width"], "height": dims["height"]})
            screenshot_bytes = await page.screenshot(full_page=False)
            image = Image.open(io.BytesIO(screenshot_bytes))
            image.save(output_path)
        finally:
            tmp_svg.unlink(missing_ok=True)


@asynccontextmanager
async def chromium_exporter() -> AsyncIterator[ChromiumExporter]:
    """Async context manager providing a ChromiumExporter instance.

    Creates a Playwright browser instance and yields a ChromiumExporter
    configured to use it. The browser is automatically closed when the
    context manager exits.

    This is the recommended way to obtain a ChromiumExporter instance, as
    it properly manages the browser lifecycle.

    Yields:
        A ChromiumExporter instance ready to save drawings.

    Example:
        ```pycon
        >>> async with chromium_exporter() as exporter:
        ...     await exporter.save(drawing1, Path("layer1.png"))
        ...     await exporter.save(drawing2, Path("layer2.png"))

        ```

    Note:
        Requires Playwright browsers to be installed. Run
        ``playwright install chromium`` if not already installed.
    """
    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch()
        try:
            yield ChromiumExporter(browser)
        finally:
            await browser.close()
