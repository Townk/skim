"""Adapter for transforming keymap JSON data between different formats.

This module provides the KeymapJsonAdapter class, which normalizes keymap
data from various source formats (Vial, Keybard, QMK c2json) into a
consistent internal representation matching QMK's key ordering.

The Svalboard keyboard has 60 keys total (30 per side), but different
applications export these keys in different orders. This adapter handles
the reordering necessary to match QMK's expected key positions.

Attributes:
    CONFIG_UI_RIGHT_FINGER_CLUSTERS_KEYS: Slice for right finger keys in
        Vial/Keybard format (indices 36-59).
    CONFIG_UI_LEFT_FINGER_CLUSTERS_KEYS: Slice for left finger keys in
        Vial/Keybard format (indices 6-29).
    CONFIG_UI_RIGHT_THUMB_CLUSTER_KEYS: Slice for right thumb keys in
        Vial/Keybard format (indices 30-35).
    CONFIG_UI_LEFT_THUMB_CLUSTER_KEYS: Slice for left thumb keys in
        Vial/Keybard format (indices 0-5).

Example:
    >>> from skim.domain.adapters import KeymapJsonAdapter
    >>> from skim.domain import KeymapType
    >>> raw_layers = [[["KC_A"] * 6] * 10]  # Vial format
    >>> normalized = KeymapJsonAdapter.transform(raw_layers, KeymapType.VIAL)
"""

from typing import Any

from skim.domain import KeymapType

CONFIG_UI_RIGHT_FINGER_CLUSTERS_KEYS = slice(36, 60)
"""Slice for right-hand finger cluster keys in Vial/Keybard export format.

In the Vial/Keybard export schema, the right-hand finger clusters (index,
middle, ring, pinky) occupy indices 36-59 (24 keys total).
"""

CONFIG_UI_LEFT_FINGER_CLUSTERS_KEYS = slice(6, 30)
"""Slice for left-hand finger cluster keys in Vial/Keybard export format.

In the Vial/Keybard export schema, the left-hand finger clusters (index,
middle, ring, pinky) occupy indices 6-29 (24 keys total).
"""

CONFIG_UI_RIGHT_THUMB_CLUSTER_KEYS = slice(30, 36)
"""Slice for right-hand thumb cluster keys in Vial/Keybard export format.

In the Vial/Keybard export schema, the right thumb cluster occupies
indices 30-35 (6 keys total).
"""

CONFIG_UI_LEFT_THUMB_CLUSTER_KEYS = slice(0, 6)
"""Slice for left-hand thumb cluster keys in Vial/Keybard export format.

In the Vial/Keybard export schema, the left thumb cluster occupies
indices 0-5 (6 keys total).
"""


class KeymapJsonAdapter:
    """Adapts keymap JSON data from various formats to QMK ordering.

    This adapter normalizes keymap data exported from different applications
    (Vial, Keybard) into the key ordering expected by QMK firmware. This is
    necessary because each application has its own internal key ordering
    that differs from QMK's standard layout.

    The adapter is stateless and uses only static methods, making it suitable
    for use as a utility class without instantiation.

    Example:
        >>> from skim.domain.domain_types import KeymapType
        >>> # Transform Keybard format to QMK ordering
        >>> keybard_layers = [["KC_A"] * 60, ["KC_B"] * 60]
        >>> qmk_layers = KeymapJsonAdapter.transform(keybard_layers, KeymapType.KEYBARD)
    """

    @staticmethod
    def transform(json_data: Any, data_type: KeymapType) -> list[list[str]]:
        """Transform keymap data from a source format to QMK ordering.

        Args:
            json_data: The raw keymap data from the source format. Structure
                varies by format:
                - VIAL: list[list[list[str]]] (layers → clusters → keys)
                - KEYBARD: list[list[str]] (layers → keys)
                - C2JSON: list[list[str]] (layers → keys, already QMK order)
            data_type: The source format type indicating how to interpret
                and transform the data.

        Returns:
            Normalized keymap data as list[list[str]] where each inner list
            contains 60 keycode strings in QMK's expected order.

        Example:
            >>> KeymapJsonAdapter.transform([["KC_A"] * 60], KeymapType.C2JSON)
            [['KC_A', 'KC_A', ...]]  # Returned unchanged
        """
        if data_type == KeymapType.VIAL:
            return KeymapJsonAdapter._from_vial(json_data)

        if data_type == KeymapType.KEYBARD:
            return KeymapJsonAdapter._from_keybard(json_data)

        return json_data

    @staticmethod
    def _from_keybard(layers: list[list[str]]) -> list[list[str]]:
        """Transform Keybard format layers to QMK ordering.

        Args:
            layers: List of layers, each containing 60 keycode strings
                in Keybard's export ordering.

        Returns:
            List of layers with keys reordered to match QMK.
        """
        return [KeymapJsonAdapter._single_layer_adaptor(layer) for layer in layers]

    @staticmethod
    def _from_vial(layers: list[list[list[str]]]) -> list[list[str]]:
        """Transform Vial format layers to QMK ordering.

        Vial exports layers as nested lists (clusters within layers), so
        this first flattens the structure before reordering.

        Args:
            layers: List of layers, each containing cluster sublists,
                each containing keycode strings.

        Returns:
            List of flattened and reordered layers matching QMK.
        """
        return [
            KeymapJsonAdapter._single_layer_adaptor(
                [label for cluster in layer for label in cluster]
            )
            for layer in layers
        ]

    @staticmethod
    def _single_layer_adaptor(layer_keycodes: list[str]) -> list[str]:
        """Reorder a single layer's keys from Vial/Keybard to QMK order.

        Vial and Keybard export keys in a different order than QMK firmware
        expects. This method applies index offset mappings to reposition
        each key to its correct QMK index.

        The mapping works by applying an offset to each key's source index
        based on its position within its cluster. For example, in thumb
        clusters:

        - Knuckle (index 0) → offset +4 → position 4
        - Nail (index 1) → offset +2 → position 3
        - Down (index 2) → offset -2 → position 0
        - etc.

        Args:
            layer_keycodes: List of 60 keycode strings in Vial/Keybard order.

        Returns:
            List of 60 keycode strings reordered to match QMK firmware's
            expected positions.
        """
        mapped_list: list[str] = [""] * 60

        # Index offset mappings to convert from Vial/Keybard order to QMK order.
        # Each value is added to the sequential output index to get the correct
        # destination position.
        thumb_mapping = [4, 2, -2, -2, -2, 0]
        finger_mapping = [3, 1, -2, -2, 0, 0]

        o_idx = 0
        for idx, label in enumerate(layer_keycodes[CONFIG_UI_RIGHT_FINGER_CLUSTERS_KEYS]):
            mapped_list[o_idx + finger_mapping[idx % 6]] = label
            o_idx += 1

        for idx, label in enumerate(layer_keycodes[CONFIG_UI_LEFT_FINGER_CLUSTERS_KEYS]):
            mapped_list[o_idx + finger_mapping[idx % 6]] = label
            o_idx += 1

        for idx, label in enumerate(layer_keycodes[CONFIG_UI_RIGHT_THUMB_CLUSTER_KEYS]):
            mapped_list[o_idx + thumb_mapping[idx % 6]] = label
            o_idx += 1

        for idx, label in enumerate(layer_keycodes[CONFIG_UI_LEFT_THUMB_CLUSTER_KEYS]):
            mapped_list[o_idx + thumb_mapping[idx % 6]] = label
            o_idx += 1

        return mapped_list
