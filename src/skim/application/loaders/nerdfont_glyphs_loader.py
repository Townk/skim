# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Loader for Nerd Font glyph mappings.

This module provides a function to load Nerd Font glyph name-to-character
mappings from a bundled JSON file. The mappings allow keymap labels to
reference Nerd Font icons by name (e.g., "nf-md-home") rather than raw
Unicode codepoints.

The loaded mappings are cached using ``lru_cache`` for efficient repeated
access across multiple keymap generation runs.

Example:
    >>> from skim.application.loaders.nerdfont_glyphs_loader import load_nerdfont_glyphs
    >>> glyphs = load_nerdfont_glyphs()
    >>> "nf-md-home" in glyphs
    True
"""

import json
from functools import lru_cache

from skim.assets import ASSETS


@lru_cache(maxsize=1)
def load_nerdfont_glyphs() -> dict[str, str]:
    """Load Nerd Font glyph mappings from the bundled JSON file.

    Reads the nerd_glyphnames.json file from the assets directory and
    transforms it into a dictionary mapping prefixed glyph names to their
    corresponding Unicode characters.

    The function uses ``lru_cache`` to cache the loaded mappings, ensuring
    the JSON file is only read once per process lifetime.

    Returns:
        Dictionary mapping glyph names (prefixed with "nf-") to their
        corresponding Unicode characters. For example:
        ``{"nf-md-home": "\uf015", "nf-fa-star": "\uf005", ...}``

    Raises:
        FileNotFoundError: If the nerd_glyphnames.json file is not found
            in the assets/data directory.

    Example:
        >>> glyphs = load_nerdfont_glyphs()
        >>> char = glyphs.get("nf-md-home")
        >>> # char contains the Unicode home icon character
    """
    json_path = ASSETS.nerd_font_glyphs

    with json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    data.pop("METADATA", None)
    return {f"nf-{class_name}": info["char"] for class_name, info in data.items()}
