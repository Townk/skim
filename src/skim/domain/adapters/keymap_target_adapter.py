# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Adapter for transforming keymaps from raw strings to renderable target keys.

This module provides the KeymapTargetAdapter class, which transforms a
SvalboardKeymap containing raw QMK keycode strings into a keymap of
SvalboardTargetKey objects ready for rendering.

The adapter combines the keycode-to-label transformation with layer
metadata extraction, producing keys that contain both display labels
and layer-switching information.

Example:
    >>> from skim.application.loaders import load_keycode_mappings
    >>> from skim.data import SkimConfig
    >>> from skim.domain.adapters import KeycodeLabelAdapter, KeymapTargetAdapter
    >>> config = SkimConfig()
    >>> mappings = load_keycode_mappings(config.keycodes)
    >>> label_adapter = KeycodeLabelAdapter(config.keyboard, mappings)
    >>> adapter = KeymapTargetAdapter(config, label_adapter)
    >>> target_keymap = adapter.transform(raw_keymap)
"""

from skim.data import SvalboardKeymap, SvalboardLayout
from skim.domain import SvalboardTargetKey

from .keycode_label_adapter import KeycodeLabelAdapter


class KeymapTargetAdapter:
    """Transforms keymaps from raw keycode strings to renderable target keys.

    This adapter is the final stage of keymap processing, converting raw
    QMK keycode strings into SvalboardTargetKey objects that contain all
    information needed for rendering: display labels and layer-switching
    metadata.

    The transformation uses a KeycodeLabelAdapter to resolve each keycode
    to its display label and extract any layer-switching behavior.

    Attributes:
        _label_adapter: The adapter used to transform individual keycodes.

    Example:
        >>> from skim.application.loaders import load_keycode_mappings
        >>> from skim.data import SkimConfig
        >>> from skim.domain.adapters import KeycodeLabelAdapter, KeymapTargetAdapter
        >>> config = SkimConfig()
        >>> mappings = load_keycode_mappings(config.keycodes)
        >>> label_adapter = KeycodeLabelAdapter(config.keyboard, mappings)
        >>> adapter = KeymapTargetAdapter(label_adapter)
    """

    _label_adapter: KeycodeLabelAdapter

    def __init__(self, label_adapter: KeycodeLabelAdapter) -> None:
        """Initialize the adapter with configuration and label transformer.

        Args:
            label_adapter: The adapter for transforming individual keycodes
                to labels.
        """
        self._label_adapter = label_adapter

    def transform(self, keymap: SvalboardKeymap[str]) -> SvalboardKeymap[SvalboardTargetKey]:
        """Transform an entire keymap from strings to target keys.

        Processes each layer in the keymap, converting raw keycode strings
        to SvalboardTargetKey objects containing display labels and layer
        metadata.

        Args:
            keymap: A keymap containing raw QMK keycode strings at each
                key position.

        Returns:
            A new keymap containing SvalboardTargetKey objects at each
            position, ready for rendering.
        """
        return SvalboardKeymap({idx: self._transform_layer(layer) for idx, layer in keymap.layers.items()})

    def _transform_layer(self, layer: SvalboardLayout[str]) -> SvalboardLayout[SvalboardTargetKey]:
        """Transform a single layer from strings to target keys.

        Args:
            layer: A layout containing raw QMK keycode strings.

        Returns:
            A layout containing SvalboardTargetKey objects with labels
            and layer-switching metadata.
        """
        return layer.map(self._label_adapter.transform)
