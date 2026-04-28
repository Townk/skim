# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for the assets module.

Tests cover the BundleAssets dataclass and ASSETS singleton,
ensuring all bundled assets exist and are accessible.
"""

from pathlib import Path

import pytest

from skim.assets import ASSETS, BundleAssets


class TestBundleAssets:
    """Tests for the BundleAssets dataclass."""

    def test_can_instantiate(self):
        """BundleAssets can be instantiated."""
        assets = BundleAssets()
        assert isinstance(assets, BundleAssets)

    def test_is_frozen(self):
        """BundleAssets is frozen (immutable)."""
        assets = BundleAssets()
        with pytest.raises((AttributeError, TypeError)):
            assets.keycode_mappings = Path("/tmp/test.yaml")

    def test_uses_slots(self):
        """BundleAssets uses slots for memory efficiency."""
        assets = BundleAssets()
        with pytest.raises((AttributeError, TypeError)):
            assets.new_attribute = "test"

    def test_keycode_mappings_returns_path(self):
        """keycode_mappings returns a Path."""
        assets = BundleAssets()
        path = assets.keycode_mappings
        assert isinstance(path, Path)

    def test_keycode_mappings_file_exists(self):
        """keycode_mappings file exists."""
        assets = BundleAssets()
        assert assets.keycode_mappings.is_file()

    def test_keycode_mappings_is_yaml(self):
        """keycode_mappings has .yaml extension."""
        assets = BundleAssets()
        assert assets.keycode_mappings.suffix == ".yaml"

    def test_nerd_font_glyphs_returns_path(self):
        """nerd_font_glyphs returns a Path."""
        assets = BundleAssets()
        path = assets.nerd_font_glyphs
        assert isinstance(path, Path)

    def test_nerd_font_glyphs_file_exists(self):
        """nerd_font_glyphs file exists."""
        assets = BundleAssets()
        assert assets.nerd_font_glyphs.is_file()

    def test_nerd_font_glyphs_is_json(self):
        """nerd_font_glyphs has .json extension."""
        assets = BundleAssets()
        assert assets.nerd_font_glyphs.suffix == ".json"

    def test_font_roboto_regular_returns_path(self):
        """font_roboto_regular returns a Path."""
        assets = BundleAssets()
        path = assets.font_roboto_regular
        assert isinstance(path, Path)

    def test_font_roboto_regular_file_exists(self):
        """font_roboto_regular file exists."""
        assets = BundleAssets()
        assert assets.font_roboto_regular.is_file()

    def test_font_roboto_regular_is_ttf(self):
        """font_roboto_regular has .ttf extension."""
        assets = BundleAssets()
        assert assets.font_roboto_regular.suffix == ".ttf"

    def test_font_roboto_black_returns_path(self):
        """font_roboto_black returns a Path."""
        assets = BundleAssets()
        path = assets.font_roboto_black
        assert isinstance(path, Path)

    def test_font_roboto_black_file_exists(self):
        """font_roboto_black file exists."""
        assets = BundleAssets()
        assert assets.font_roboto_black.is_file()

    def test_font_roboto_thin_returns_path(self):
        """font_roboto_thin returns a Path."""
        assets = BundleAssets()
        path = assets.font_roboto_thin
        assert isinstance(path, Path)

    def test_font_roboto_thin_file_exists(self):
        """font_roboto_thin file exists."""
        assets = BundleAssets()
        assert assets.font_roboto_thin.is_file()

    def test_font_symbols_nerd_returns_path(self):
        """font_symbols_nerd returns a Path."""
        assets = BundleAssets()
        path = assets.font_symbols_nerd
        assert isinstance(path, Path)

    def test_font_symbols_nerd_file_exists(self):
        """font_symbols_nerd file exists."""
        assets = BundleAssets()
        assert assets.font_symbols_nerd.is_file()

    def test_logo_svalboard_returns_path(self):
        """logo_svalboard returns a Path."""
        assets = BundleAssets()
        path = assets.logo_svalboard
        assert isinstance(path, Path)

    def test_logo_svalboard_file_exists(self):
        """logo_svalboard file exists."""
        assets = BundleAssets()
        assert assets.logo_svalboard.is_file()

    def test_logo_svalboard_is_svg(self):
        """logo_svalboard has .svg extension."""
        assets = BundleAssets()
        assert assets.logo_svalboard.suffix == ".svg"

    def test_caching(self):
        """Asset paths are cached (same object returned)."""
        assets = BundleAssets()
        path1 = assets.keycode_mappings
        path2 = assets.keycode_mappings
        assert path1 is path2


class TestAssetsSingleton:
    """Tests for the module-level ASSETS singleton."""

    def test_assets_is_bundle_assets(self):
        """ASSETS is a BundleAssets instance."""
        assert isinstance(ASSETS, BundleAssets)

    def test_assets_singleton_same_instance(self):
        """ASSETS is a true singleton (same instance on reimport)."""
        from skim.assets import ASSETS as ASSETS2

        assert ASSETS is ASSETS2

    def test_assets_keycode_mappings_accessible(self):
        """ASSETS.keycode_mappings is accessible."""
        path = ASSETS.keycode_mappings
        assert isinstance(path, Path)
        assert path.is_file()

    def test_assets_nerd_font_glyphs_accessible(self):
        """ASSETS.nerd_font_glyphs is accessible."""
        path = ASSETS.nerd_font_glyphs
        assert isinstance(path, Path)
        assert path.is_file()

    def test_assets_all_fonts_accessible(self):
        """All font paths on ASSETS are accessible."""
        assert ASSETS.font_roboto_regular.is_file()
        assert ASSETS.font_roboto_black.is_file()
        assert ASSETS.font_roboto_thin.is_file()
        assert ASSETS.font_symbols_nerd.is_file()

    def test_assets_logo_accessible(self):
        """ASSETS.logo_svalboard is accessible."""
        path = ASSETS.logo_svalboard
        assert isinstance(path, Path)
        assert path.is_file()


class TestAssetContent:
    """Tests for asset file contents."""

    def test_keycode_mappings_is_valid_yaml(self):
        """keycode_mappings file contains valid YAML."""
        import yaml

        content = ASSETS.keycode_mappings.read_text()
        data = yaml.safe_load(content)
        assert isinstance(data, dict)
        assert "keycodes" in data

    def test_nerd_font_glyphs_is_valid_json(self):
        """nerd_font_glyphs file contains valid JSON."""
        import json

        content = ASSETS.nerd_font_glyphs.read_text()
        data = json.loads(content)
        assert isinstance(data, dict)

    def test_fonts_are_readable(self):
        """Font files can be opened and read."""
        for font_path in [
            ASSETS.font_roboto_regular,
            ASSETS.font_roboto_black,
            ASSETS.font_roboto_thin,
            ASSETS.font_symbols_nerd,
        ]:
            data = font_path.read_bytes()
            assert len(data) > 0
            # TTF files start with specific magic bytes
            assert data[:4] == b"\x00\x01\x00\x00" or data[:4] == b"OTTO"

    def test_logo_is_valid_svg(self):
        """Logo file contains valid SVG content."""
        content = ASSETS.logo_svalboard.read_text()
        assert "<svg" in content
        assert "</svg>" in content


class TestHelpText:
    """Tests for the help_text method."""

    def test_help_text_returns_string(self):
        """help_text returns a string for an existing key."""
        assets = BundleAssets()
        content = assets.help_text("general")
        assert isinstance(content, str)
        assert len(content) > 0

    def test_help_text_general_contains_navigation(self):
        """general.md contains navigation info."""
        assets = BundleAssets()
        content = assets.help_text("general")
        assert "Navigation" in content

    def test_help_text_missing_key_falls_back_to_general(self):
        """Missing key falls back to general.md content."""
        assets = BundleAssets()
        general = assets.help_text("general")
        fallback = assets.help_text("nonexistent-key-xyz")
        assert fallback == general

    def test_help_text_fallback_when_no_general(self, tmp_path, monkeypatch):
        """Raises FileNotFoundError when general.md is also missing."""
        import importlib.resources

        original_files = importlib.resources.files

        def fake_files(package):
            if package == "skim.assets":
                return tmp_path
            return original_files(package)

        monkeypatch.setattr(importlib.resources, "files", fake_files)
        assets = BundleAssets()
        with pytest.raises(FileNotFoundError):
            assets.help_text("anything")


class TestMacroAndTapDanceHelpFiles:
    """The new TUI help files are bundled and loadable."""

    def test_all_six_help_files_resolve(self):
        from skim.assets import ASSETS

        for key in (
            "keycodes-macro-list",
            "keycodes-macro-id",
            "keycodes-macro-name",
            "keycodes-tap-dance-list",
            "keycodes-tap-dance-id",
            "keycodes-tap-dance-name",
        ):
            content = ASSETS.help_text(key)
            assert content.strip(), f"Help text for '{key}' is empty"
            assert content != ASSETS.help_text("general"), (
                f"Help text for '{key}' fell back to general.md"
            )
