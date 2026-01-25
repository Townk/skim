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
    """
    mapping_path = ASSETS.keycode_mappings
    mapping = yaml.safe_load(mapping_path.read_text())
    for keycode in keycodes_config.pre_process:
        mapping["pre_processing"][keycode.keycode] = keycode.target
    for keycode in keycodes_config.overrides:
        mapping["keycodes"][keycode.keycode] = keycode.target
    return MappingProxyType(mapping)
