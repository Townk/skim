# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Loader for keycode-to-label mapping configuration.

This module provides the load_keycode_mappings function, which loads and
merges keycode mapping data from the bundled YAML file and user-provided
configuration overrides.

The mappings control how QMK keycodes are transformed into human-readable
labels for display on keymap images.

Example:
    >>> from skim.data.config import SkimConfig
    >>> from skim.application.loaders import load_keycode_mappings
    >>> config = SkimConfig()
    >>> mappings = load_keycode_mappings(config.keycodes)
    >>> "KC_A" in mappings["keycodes"]
    True
"""

from functools import lru_cache
from types import MappingProxyType

import yaml

from skim.assets import ASSETS
from skim.data import KeycodeMappings, Keycodes

_UNCATEGORIZED = "(uncategorized)"


def _merge_nested_descriptions(
    bundled: dict,
    user: dict,
) -> dict:
    """Deep-merge user nested descriptions into bundled.

    Bundled is ``{category: {keycode: description}}``. User has the same
    shape. User entries override bundled entries with the same keycode in
    the same category. New categories from user are appended after the
    bundled ones.
    """
    out: dict = {}
    # Start with bundled
    for cat, entries in bundled.items():
        if isinstance(entries, dict):
            out[cat] = dict(entries)  # shallow copy so we don't mutate input
        else:
            # Flat-format entry — keep as-is for legacy yaml support
            out[cat] = entries
    # Apply user overrides
    for cat, entries in user.items():
        if not isinstance(entries, dict):
            continue
        if cat in out and isinstance(out[cat], dict):
            out[cat].update(entries)
        else:
            out[cat] = dict(entries)
    return out


def _flatten_descriptions(
    raw: dict,
) -> tuple[dict[str, str], dict[str, str]]:
    """Flatten a possibly-nested descriptions dict into a flat mapping and a
    category map.

    Supports two formats:

    * **Flat** ``{keycode: description}`` — all entries are assigned to the
      ``"(uncategorized)"`` category.
    * **Nested** ``{category_name: {keycode: description}}`` — each keycode is
      assigned to its category.  A mix is allowed: top-level ``str`` values
      are treated as uncategorized entries.

    Returns
    -------
    tuple[dict[str, str], dict[str, str]]
        ``(flat, categories)`` where *flat* maps each keycode to its
        description string and *categories* maps each keycode to its category
        name.
    """
    flat: dict[str, str] = {}
    categories: dict[str, str] = {}

    for key, value in raw.items():
        if isinstance(value, dict):
            # Nested format: key is the category name, value is {kc: desc}.
            category_name = key
            for keycode, desc in value.items():
                flat[keycode] = desc
                categories[keycode] = category_name
        else:
            # Flat format: key is the keycode, value is the description string.
            flat[key] = value
            categories[key] = _UNCATEGORIZED

    return flat, categories


@lru_cache(maxsize=1)
def load_keycode_mappings(keycodes_config: Keycodes) -> KeycodeMappings:
    """Load and merge keycode mappings.

    Loads the bundled keycode-mappings.yaml file and applies any
    user-provided pre-processing and override mappings from the
    skim configuration.

    Args:
        keycodes_config: The keycode overrides from the skim configuration
            (SkimConfig.keycodes).

    Returns:
        Dictionary containing merged keycode mappings with keys:
        - ``keycodes``: Keycode to label mappings
        - ``pre_processing``: Keycode normalization rules
        - ``macro_functions``: Macro template definitions
        - ``modifier_union``: Modifier constant mappings
        - ``symbol_descriptions``: Flat keycode-to-description map
        - ``symbol_categories``: Keycode-to-category-name map
        - ``function_descriptions``: Flat function-name-to-description map
        - ``function_categories``: Function-name-to-category-name map
    """
    mapping_path = ASSETS.keycode_mappings
    mapping = yaml.safe_load(mapping_path.read_text())
    for keycode in keycodes_config.pre_process:
        mapping["pre_processing"][keycode.keycode] = keycode.target
    for keycode in keycodes_config.overrides:
        mapping["keycodes"][keycode.keycode] = keycode.target

    # Merge user-provided symbol/function descriptions and aliases before
    # flattening so the category structure is preserved through the merge.
    mapping["symbol_descriptions"] = _merge_nested_descriptions(
        mapping.get("symbol_descriptions", {}),
        keycodes_config.symbol_descriptions,
    )
    mapping["function_descriptions"] = _merge_nested_descriptions(
        mapping.get("function_descriptions", {}),
        keycodes_config.function_descriptions,
    )
    # Aliases are flat — shallow merge
    aliases = dict(mapping.get("symbol_legend_aliases", {}))
    aliases.update(keycodes_config.symbol_legend_aliases)
    mapping["symbol_legend_aliases"] = aliases

    # Flatten nested symbol_descriptions and function_descriptions, building
    # parallel category maps for use by the symbol legend renderer.
    raw_symbol = mapping["symbol_descriptions"]
    flat_symbol, sym_cats = _flatten_descriptions(raw_symbol)
    mapping["symbol_descriptions"] = flat_symbol
    mapping["symbol_categories"] = sym_cats

    raw_func = mapping["function_descriptions"]
    flat_func, func_cats = _flatten_descriptions(raw_func)
    mapping["function_descriptions"] = flat_func
    mapping["function_categories"] = func_cats

    return MappingProxyType(mapping)
