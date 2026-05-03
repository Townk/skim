# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Centralized access to bundled package assets with validation.

Provides a frozen, slotted dataclass that validates all bundled assets
exist at first access—fail fast on broken installations.

Example:
    >>> from skim.assets import ASSETS
    >>> mappings_path = ASSETS.keycode_mappings
    >>> font_path = ASSETS.font_roboto_regular
"""

from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import cast


@dataclass(frozen=True, slots=True)
class BundleAssets:
    """Centralized access to bundled package assets.

    All properties are cached and validated on first access.
    Missing assets raise FileNotFoundError immediately.

    Example:
        >>> assets = BundleAssets()
        >>> str(assets.keycode_mappings)
        '.../assets/data/keycode-mappings.yaml'
    """

    _cache: dict[str, Path] = field(default_factory=dict, init=False, repr=False, compare=False)

    @property
    def keycode_mappings(self) -> Path:
        """Path to the keycode-mappings.yaml file.

        Returns:
            Path to the bundled keycode mappings configuration.

        Raises:
            FileNotFoundError: If the file is missing from the installation.
        """
        return self._get_cached("keycode_mappings", "data", "keycode-mappings.yaml")

    @property
    def nerd_font_glyphs(self) -> Path:
        """Path to the nerd_glyphnames.json file.

        Returns:
            Path to the bundled Nerd Font glyph mappings.

        Raises:
            FileNotFoundError: If the file is missing from the installation.
        """
        return self._get_cached("nerd_font_glyphs", "data", "nerd_glyphnames.json")

    @property
    def font_roboto_regular(self) -> Path:
        """Path to the Roboto-Regular.ttf font file.

        Returns:
            Path to the bundled Roboto Regular font.

        Raises:
            FileNotFoundError: If the file is missing from the installation.
        """
        return self._get_cached("font_roboto_regular", "fonts", "Roboto-Regular.ttf")

    @property
    def font_roboto_black(self) -> Path:
        """Path to the Roboto-Black.ttf font file.

        Returns:
            Path to the bundled Roboto Black font.

        Raises:
            FileNotFoundError: If the file is missing from the installation.
        """
        return self._get_cached("font_roboto_black", "fonts", "Roboto-Black.ttf")

    @property
    def font_roboto_thin(self) -> Path:
        """Path to the Roboto-Thin.ttf font file.

        Returns:
            Path to the bundled Roboto Thin font.

        Raises:
            FileNotFoundError: If the file is missing from the installation.
        """
        return self._get_cached("font_roboto_thin", "fonts", "Roboto-Thin.ttf")

    @property
    def font_symbols_nerd(self) -> Path:
        """Path to the SymbolsNerdFont-Regular.ttf font file.

        Returns:
            Path to the bundled Nerd Font symbols font.

        Raises:
            FileNotFoundError: If the file is missing from the installation.
        """
        return self._get_cached("font_symbols_nerd", "fonts", "SymbolsNerdFont-Regular.ttf")

    @property
    def font_dejavu_sans_bold(self) -> Path:
        """Path to the DejaVuSans-Bold.ttf font file.

        Used as a Unicode-symbol fallback for characters the Roboto
        family doesn't carry — the keyboard-symbol block (⎇, ⌘, ⌥,
        ⌃, ⇧, ↹, ⏎, ␣, ⌫, ⌦), the box-drawing separator (│), and
        other miscellaneous-technical glyphs that show up in keymap
        labels. DejaVu Sans Bold is part of the well-tested DejaVu
        family (Bitstream Vera-derived, free for any use); the bold
        weight specifically covers ⎇ (U+2387) which the regular and
        mono variants lack along with most UI / programming fonts.

        Returns:
            Path to the bundled DejaVu Sans Bold font.

        Raises:
            FileNotFoundError: If the file is missing from the installation.
        """
        return self._get_cached("font_dejavu_sans_bold", "fonts", "DejaVuSans-Bold.ttf")

    @property
    def logo_svalboard(self) -> Path:
        """Path to the svalboard-logo.svg image file.

        Returns:
            Path to the bundled Svalboard logo SVG.

        Raises:
            FileNotFoundError: If the file is missing from the installation.
        """
        return self._get_cached("logo_svalboard", "images", "svalboard-logo.svg")

    def _get_cached(self, cache_key: str, *parts: str) -> Path:
        """Get asset path from cache or resolve and cache it.

        Args:
            cache_key: Key for the cache dictionary.
            *parts: Path components relative to the assets package.

        Returns:
            Absolute path to the asset file.

        Raises:
            FileNotFoundError: If the asset file does not exist.
        """
        if cache_key not in self._cache:
            object.__setattr__(self, "_cache", {**self._cache, cache_key: self._resolve(*parts)})
        return self._cache[cache_key]

    def _resolve(self, *parts: str) -> Path:
        """Resolve asset path and validate existence.

        Args:
            *parts: Path components relative to the assets package.

        Returns:
            Absolute path to the asset file.

        Raises:
            FileNotFoundError: If the asset file does not exist.
        """
        path = resources.files("skim.assets")
        for part in parts:
            path = path / part

        path_obj = cast(Path, path)

        if not path_obj.is_file():
            raise FileNotFoundError(
                f"Bundled asset missing: {path_obj}. Installation may be corrupted."
            )
        return path_obj

    def help_text(self, key: str) -> str:
        """Load markdown help content for the given key.

        Falls back to 'general' if the specific file doesn't exist.

        Args:
            key: Help topic key (maps to help/{key}.md).

        Returns:
            Markdown content as a string.

        Raises:
            FileNotFoundError: If neither the key file nor general.md exists.
        """
        return self._resolve_help(key).read_text()

    def _resolve_help(self, key: str) -> Path:
        """Resolve help asset path with fallback to general.md.

        Args:
            key: Help topic key.

        Returns:
            Path to the help markdown file.

        Raises:
            FileNotFoundError: If neither the key file nor general.md exists.
        """
        path = cast(Path, resources.files("skim.assets") / "help" / f"{key}.md")
        if path.is_file():
            return path
        fallback = cast(Path, resources.files("skim.assets") / "help" / "general.md")
        if fallback.is_file():
            return fallback
        raise FileNotFoundError("No help content available.")


# Module-level singleton for direct import
ASSETS = BundleAssets()
