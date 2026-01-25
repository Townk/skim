"""Pytest configuration for integration tests.

Integration tests require external dependencies like Playwright browsers.
Run with: pytest tests/integration/ -m integration
"""

import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test (requires external dependencies)",
    )


@pytest.fixture(scope="session")
def check_playwright_installed():
    """Check that Playwright browsers are installed."""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            # Try to launch chromium to verify it's installed
            browser = p.chromium.launch()
            browser.close()
    except Exception as e:
        pytest.skip(
            f"Playwright chromium not installed. Run 'playwright install chromium'. Error: {e}"
        )
