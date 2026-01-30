# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.application.exporter.chromium_exporter module."""

from unittest.mock import MagicMock

from skim.application.exporter.chromium_exporter import ChromiumExporter


class TestChromiumExporter:
    """Tests for ChromiumExporter class."""

    def test_init_stores_browser(self):
        """Initializes with browser instance."""
        mock_browser = MagicMock()
        exporter = ChromiumExporter(mock_browser)
        assert exporter._browser is mock_browser

    def test_browser_accessible(self):
        """Browser instance is accessible."""
        mock_browser = MagicMock()
        exporter = ChromiumExporter(mock_browser)
        assert exporter._browser is mock_browser
