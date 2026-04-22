# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.application.doctor module."""

from unittest.mock import MagicMock, PropertyMock, patch

from skim.application.doctor import (
    CheckResult,
    check_installation_integrity,
    check_render_engines,
    check_system_fonts,
    check_textual_available,
    run_doctor_checks,
)


class TestDoctorChecks:
    """Tests for doctor check functions."""

    @patch("skim.application.doctor.ASSETS")
    def test_check_installation_integrity_success(self, mock_assets):
        """Passes when all assets are present."""
        # Setup mock to allow attribute access
        mock_assets.keycode_mappings = "path/to/mappings"
        mock_assets.nerd_font_glyphs = "path/to/glyphs"
        mock_assets.font_roboto_regular = "path/to/font"
        mock_assets.font_roboto_black = "path/to/font"
        mock_assets.font_roboto_thin = "path/to/font"
        mock_assets.font_symbols_nerd = "path/to/font"
        mock_assets.logo_svalboard = "path/to/logo"

        result = check_installation_integrity()
        assert result.passed
        assert "All bundled assets are present" in result.message

    @patch("skim.application.doctor.ASSETS")
    def test_check_installation_integrity_missing_asset(self, mock_assets):
        """Fails when an asset is missing."""
        # Mock raising FileNotFoundError for one attribute
        p = PropertyMock(side_effect=FileNotFoundError("Missing"))
        type(mock_assets).keycode_mappings = p

        result = check_installation_integrity()
        assert not result.passed
        assert "Missing bundled assets" in result.message
        assert "Keycode Mappings" in result.details

    @patch("skim.application.doctor.check_playwright_available")
    @patch("skim.application.doctor.check_cairo_available")
    def test_check_render_engines(self, mock_cairo, mock_playwright):
        """Checks both render engines."""
        mock_playwright.return_value = True
        mock_cairo.return_value = False

        results = list(check_render_engines())
        assert len(results) == 2

        pw_result = next(r for r in results if "Playwright" in r.name)
        assert pw_result.passed
        assert pw_result.message == "Available"

        cairo_result = next(r for r in results if "Cairo" in r.name)
        assert not cairo_result.passed
        assert cairo_result.message == "Not available"

    @patch("pathlib.Path.rglob")
    @patch("pathlib.Path.exists")
    def test_check_system_fonts_found(self, mock_exists, mock_rglob):
        """Checks if system fonts are found."""
        mock_exists.return_value = True
        # Mock rglob to yield something (indicating found)
        mock_rglob.return_value = [MagicMock()]

        results = list(check_system_fonts())
        # We check for 4 fonts
        assert len(results) == 4
        assert all(r.passed for r in results)
        assert all(r.message == "Found" for r in results)

    @patch("pathlib.Path.rglob")
    @patch("pathlib.Path.exists")
    def test_check_system_fonts_not_found(self, mock_exists, mock_rglob):
        """Checks if system fonts are not found."""
        mock_exists.return_value = True
        # Mock rglob to yield nothing
        mock_rglob.return_value = []

        results = list(check_system_fonts())
        assert len(results) == 4
        assert all(not r.passed for r in results)
        assert all(r.message == "Not found" for r in results)

    @patch("skim.application.doctor.check_installation_integrity")
    @patch("skim.application.doctor.check_render_engines")
    @patch("skim.application.doctor.check_system_fonts")
    @patch("skim.application.doctor.check_textual_available", return_value=True)
    def test_run_doctor_checks(self, mock_textual, mock_fonts, mock_engines, mock_integrity):
        """Aggregates all checks."""
        mock_integrity.return_value = CheckResult("Integrity", True, "OK")
        mock_engines.return_value = [CheckResult("Engine", True, "OK")]
        mock_fonts.return_value = [CheckResult("Font", True, "OK")]

        results = list(run_doctor_checks())
        assert len(results) == 4
        assert results[0].name == "Integrity"
        assert results[1].name == "Engine"
        assert results[2].name == "Font"
        assert results[3].name == "Textual (TUI)"


class TestTextualCheck:
    """Tests for textual availability check."""

    @patch("skim.application.doctor.check_textual_available", return_value=True)
    def test_check_textual_available(self, mock_check):
        """Textual check is included in doctor results."""
        results = list(run_doctor_checks())
        names = [r.name for r in results]
        assert "Textual (TUI)" in names

    @patch("skim.application.doctor.check_textual_available", return_value=True)
    def test_textual_available_passes(self, mock_check):
        """Reports pass when textual is installed."""
        results = list(run_doctor_checks())
        textual_result = next(r for r in results if "Textual" in r.name)
        assert textual_result.passed
        assert textual_result.message == "Available"

    @patch("skim.application.doctor.check_textual_available", return_value=False)
    def test_textual_unavailable_warns(self, mock_check):
        """Reports not available when textual is missing."""
        results = list(run_doctor_checks())
        textual_result = next(r for r in results if "Textual" in r.name)
        assert not textual_result.passed
        assert textual_result.message == "Not available"
