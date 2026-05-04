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
    ```pycon
    >>> from skim.application.loaders import load_keycode_mappings
    >>> from skim.data import SkimConfig
    >>> from skim.domain.adapters import KeycodeLabelAdapter, KeymapTargetAdapter
    >>> config = SkimConfig()
    >>> mappings = load_keycode_mappings(config.keycodes)
    >>> label_adapter = KeycodeLabelAdapter(config.keyboard, mappings)
    >>> adapter = KeymapTargetAdapter(config, label_adapter)
    >>> target_keymap = adapter.transform(raw_keymap)

    ```
"""

from skim.data import SvalboardKeymap, SvalboardLayout
from skim.domain import (
    SvalboardMacro,
    SvalboardMacroAction,
    SvalboardTapDance,
    SvalboardTargetKey,
)

from .keycode_label_adapter import KeycodeLabelAdapter

_TRANSPARENT_GLYPH = "⛛"
"""Vial-style inverted triangle drawn on transparent keys when
fall-through-to-layer-zero is disabled."""


def _detect_special_ids(
    keycode: str,
    macros: tuple[SvalboardMacro[str], ...],
    tap_dances: tuple[SvalboardTapDance[str], ...],
) -> tuple[str | None, str | None]:
    """Return ``(macro_id, tap_dance_id)`` for ``keycode`` by lookup.

    A macro matches when the keycode equals ``f"M{m.id}"`` (Vial form) or
    ``f"MACRO_{m.id}"`` (QMK form). A tap-dance matches when the keycode
    equals ``f"TD({t.id})"``. No regex; pure string equality against the
    known definitions so only actually-defined ids are stamped.
    """
    for m in macros:
        if keycode == f"M{m.id}" or keycode == f"MACRO_{m.id}":
            return m.id, None
    for t in tap_dances:
        if keycode == f"TD({t.id})":
            return None, t.id
    return None, None


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
        macro_id=base_key.macro_id,
        tap_dance_id=base_key.tap_dance_id,
    )


def _stamp_transparent_glyph(key: SvalboardTargetKey) -> SvalboardTargetKey:
    """Replace a transparent key's empty label with the ⛛ glyph."""
    if not key.is_transparent or key.label:
        return key
    return SvalboardTargetKey(
        label=_TRANSPARENT_GLYPH,
        layer_switch=key.layer_switch,
        is_transparent=True,
        macro_id=key.macro_id,
        tap_dance_id=key.tap_dance_id,
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
        ```pycon
        >>> from skim.application.loaders import load_keycode_mappings
        >>> from skim.data import SkimConfig
        >>> from skim.domain.adapters import KeycodeLabelAdapter, KeymapTargetAdapter
        >>> config = SkimConfig()
        >>> mappings = load_keycode_mappings(config.keycodes)
        >>> label_adapter = KeycodeLabelAdapter(config.keyboard, mappings)
        >>> adapter = KeymapTargetAdapter(label_adapter)

        ```
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
        layers = {
            idx: self._transform_layer(layer, keymap.macros, keymap.tap_dances)
            for idx, layer in keymap.layers.items()
        }

        base = layers.get(0)
        if self._fallthrough_to_layer_zero and base is not None:
            layers = {
                idx: self._apply_fallthrough(layer, base, idx) if idx != 0 else layer
                for idx, layer in layers.items()
            }
        elif not self._fallthrough_to_layer_zero:
            # Without fall-through, transparent keys would otherwise render
            # blank.  Stamp the Vial-style ⛛ glyph on each transparent
            # position so users can still see where the transparent keys
            # are.  The ghost colour applied at render time uses the same
            # ``is_transparent`` flag, so the glyph appears faded.
            layers = {idx: layer.map(_stamp_transparent_glyph) for idx, layer in layers.items()}

        tap_dances = tuple(self._transform_tap_dance(td) for td in keymap.tap_dances)
        macros = tuple(self._transform_macro(macro) for macro in keymap.macros)

        return SvalboardKeymap(layers=layers, tap_dances=tap_dances, macros=macros)

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

    def _transform_layer(
        self,
        layer: SvalboardLayout[str],
        macros: tuple[SvalboardMacro[str], ...],
        tap_dances: tuple[SvalboardTapDance[str], ...],
    ) -> SvalboardLayout[SvalboardTargetKey]:
        """Transform a single layer from strings to target keys.

        Each key's raw keycode is looked up against the known macro and
        tap-dance definitions to stamp ``macro_id`` / ``tap_dance_id``
        without relying on regular expressions.

        Args:
            layer: A layout containing raw QMK keycode strings.
            macros: Macro definitions from the parsed keymap.
            tap_dances: Tap-dance definitions from the parsed keymap.

        Returns:
            A layout containing SvalboardTargetKey objects with labels,
            layer-switching metadata, and special ids where applicable.
        """

        def _convert(keycode: str) -> SvalboardTargetKey:
            target = self._label_adapter.transform(keycode)
            macro_id, tap_dance_id = _detect_special_ids(keycode, macros, tap_dances)
            if macro_id is None and tap_dance_id is None:
                return target
            return SvalboardTargetKey(
                label=target.label,
                layer_switch=target.layer_switch,
                is_transparent=target.is_transparent,
                macro_id=macro_id,
                tap_dance_id=tap_dance_id,
            )

        return layer.map(_convert)

    def _transform_optional_keycode(self, keycode: str | None) -> SvalboardTargetKey | None:
        """Apply the label adapter to an optional keycode string."""
        if keycode is None:
            return None
        return self._label_adapter.transform(keycode)

    def _transform_tap_dance(
        self, tap_dance: SvalboardTapDance[str]
    ) -> SvalboardTapDance[SvalboardTargetKey]:
        """Rewrite each keycode field of a tap dance via the label adapter."""
        return SvalboardTapDance[SvalboardTargetKey](
            id=tap_dance.id,
            tap=self._transform_optional_keycode(tap_dance.tap),
            hold=self._transform_optional_keycode(tap_dance.hold),
            double_tap=self._transform_optional_keycode(tap_dance.double_tap),
            tap_then_hold=self._transform_optional_keycode(tap_dance.tap_then_hold),
            tapping_term=tap_dance.tapping_term,
            name=tap_dance.name,
        )

    def _transform_macro_action(
        self, action: SvalboardMacroAction[str]
    ) -> SvalboardMacroAction[SvalboardTargetKey]:
        """Rewrite a macro action's keys via the label adapter."""
        return SvalboardMacroAction[SvalboardTargetKey](
            kind=action.kind,
            keys=tuple(self._label_adapter.transform(k) for k in action.keys),
            text=action.text,
            duration_ms=action.duration_ms,
        )

    def _transform_macro(self, macro: SvalboardMacro[str]) -> SvalboardMacro[SvalboardTargetKey]:
        """Rewrite each action of a macro via the label adapter."""
        return SvalboardMacro[SvalboardTargetKey](
            id=macro.id,
            actions=tuple(self._transform_macro_action(a) for a in macro.actions),
            name=macro.name,
        )
