"""Unit tests for skim.application.exporter.image_exporter module."""

from unittest.mock import MagicMock

from skim.application.exporter.image_exporter import ImageExporter


class TestImageExporter:
    """Tests for ImageExporter class."""

    def test_init_stores_browser(self):
        """Initializes with browser instance."""
        mock_browser = MagicMock()
        exporter = ImageExporter(mock_browser)
        assert exporter._browser is mock_browser

    def test_browser_accessible(self):
        """Browser instance is accessible."""
        mock_browser = MagicMock()
        exporter = ImageExporter(mock_browser)
        assert exporter._browser is mock_browser
