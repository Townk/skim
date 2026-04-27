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


def _substitute(
    key: SvalboardTargetKey,
    base_key: SvalboardTargetKey,
    current_layer_index: int,
) -> SvalboardTargetKey:
    """Resolve one transparent position against its layer-0 source."""
    if not key.is_transparent:
        return key
    if base_key.layer_switch == current_layer_index:
        return key
    return SvalboardTargetKey(
        label=base_key.label,
        layer_switch=base_key.layer_switch,
        is_transparent=True,
    )


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
    _fallthrough_to_layer_zero: bool

    def __init__(
        self,
        label_adapter: KeycodeLabelAdapter,
        fallthrough_to_layer_zero: bool = True,
    ) -> None:
        """Initialize the adapter with configuration and label transformer.

        Args:
            label_adapter: The adapter for transforming individual keycodes
                to labels.
            fallthrough_to_layer_zero: When True (default), transparent keys
                on layers above 0 borrow their display label from the same
                key position on layer 0. Set False to leave transparent keys
                blank.
        """
        self._label_adapter = label_adapter
        self._fallthrough_to_layer_zero = fallthrough_to_layer_zero

    def transform(self, keymap: SvalboardKeymap[str]) -> SvalboardKeymap[SvalboardTargetKey]:
        """Transform an entire keymap from strings to target keys.

        Processes each layer in the keymap, converting raw keycode strings
        to SvalboardTargetKey objects containing display labels and layer
        metadata. When fallthrough is enabled and layer 0 is present, any
        transparent key on a higher layer is rewritten to display the
        layer-0 label at the same position.

        Args:
            keymap: A keymap containing raw QMK keycode strings at each
                key position.

        Returns:
            A new keymap containing SvalboardTargetKey objects at each
            position, ready for rendering.
        """
        layers = {idx: self._transform_layer(layer) for idx, layer in keymap.layers.items()}

        base = layers.get(0)
        if self._fallthrough_to_layer_zero and base is not None:
            layers = {
                idx: self._apply_fallthrough(layer, base, idx) if idx != 0 else layer
                for idx, layer in layers.items()
            }

        return SvalboardKeymap(layers)

    @staticmethod
    def _apply_fallthrough(
        layer: SvalboardLayout[SvalboardTargetKey],
        base: SvalboardLayout[SvalboardTargetKey],
        current_layer_index: int,
    ) -> SvalboardLayout[SvalboardTargetKey]:
        """Substitute layer-0 labels into transparent positions of ``layer``.

        Transparent keys inherit both the label and the ``layer_switch`` from
        the corresponding layer-0 key, so a fall-through key whose base maps
        to a layer change is treated as a layer-changing key during
        rendering (layer-coloured background, layer indicator, connector).

        Self-referential cases — where the layer-0 source maps to
        ``current_layer_index`` (e.g. ``MO(1)`` viewed on layer 1) — are
        suppressed: the substitution is skipped and the position renders as
        a blank transparent key (no label, no layer indicator, no connector).
        """
        return SvalboardLayout.from_sequence(
            [
                _substitute(key, base_key, current_layer_index)
                for key, base_key in zip(layer, base, strict=True)
            ]
        )

    def _transform_layer(self, layer: SvalboardLayout[str]) -> SvalboardLayout[SvalboardTargetKey]:
        """Transform a single layer from strings to target keys.

        Args:
            layer: A layout containing raw QMK keycode strings.

        Returns:
            A layout containing SvalboardTargetKey objects with labels
            and layer-switching metadata.
        """
        return layer.map(self._label_adapter.transform)
