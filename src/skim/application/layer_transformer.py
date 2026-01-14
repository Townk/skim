"""Layer adaptor for transforming keymap layouts between formats.

This module provides the :class:`LayerAdaptor` which transforms keymap layer
data from Keybard and Vial source formats into the internal Skim format.
Different keyboard firmware tools use different key ordering conventions,
and this adaptor handles the necessary reordering.

The Svalboard keyboard has a specific physical layout:
    - 8 finger clusters (4 per hand, 6 keys each)
    - 2 thumb clusters (1 per hand, 6 keys each)
    - Total: 60 keys per layer

Source formats (Keybard/Vial) order keys as:
    Left Thumb → Left Fingers → Right Thumb → Right Fingers

Internal Skim format orders keys as:
    Right Fingers → Left Fingers → Right Thumb → Left Thumb

Example:
    Converting Keybard layers::

        from skim.application.layer_transformer import LayerAdaptor

        keybard_layers = [["KC_A", "KC_B", ...], ...]  # 60 keys per layer
        skim_layers = LayerAdaptor.from_keybard(keybard_layers)

    Converting Vial layers::

        vial_layers = [[[...], [...]], ...]  # Nested cluster format
        skim_layers = LayerAdaptor.from_vial(vial_layers)
"""


class LayerAdaptor:
    """Transforms keymap layer layouts from Keybard/Vial to Skim format.

    This class provides static methods for converting between different
    keymap file formats. The transformation involves reordering keys
    from source format conventions to the internal Skim rendering order.

    The Svalboard's physical layout requires specific cluster ordering
    for correct visual representation. This adaptor handles the mapping
    from how keyboard firmware stores keycodes to how Skim needs them
    for image generation.

    Note:
        All methods are class methods and don't require instantiation.
        The class is used as a namespace for related transformation functions.

    Example:
        >>> # Direct usage without instantiation
        >>> keybard_layer = ["KC_A"] * 60
        >>> skim_layers = LayerAdaptor.from_keybard([keybard_layer])
        >>> len(skim_layers[0])
        60
    """

    @classmethod
    def from_keybard(cls, layers: list[list[str]]) -> list[list[str]]:
        """Transform Keybard layer format to internal Skim format.

        Keybard stores keycodes as a flat list in source order.
        This method reorders the keys for each layer to match
        Skim's rendering expectations.

        Args:
            layers: List of layers, where each layer is a flat list
                of 60 keycode strings in Keybard order.

        Returns:
            List of layers with keycodes reordered to Skim format.

        Example:
            >>> keybard_layers = parser.parse(content)
            >>> skim_layers = LayerAdaptor.from_keybard(keybard_layers)
        """
        return [cls._single_layer_adaptor(layer) for layer in layers]

    @classmethod
    def from_vial(cls, layers: list[list[list[str]]]) -> list[list[str]]:
        """Transform Vial layer format to internal Skim format.

        Vial stores keycodes grouped by clusters (nested lists).
        This method flattens the cluster structure and reorders
        keys for each layer to match Skim's rendering expectations.

        Args:
            layers: List of layers, where each layer contains a list
                of clusters, and each cluster is a list of keycode strings.

        Returns:
            List of layers with keycodes flattened and reordered to Skim format.

        Example:
            >>> vial_layers = parser.parse(content)
            >>> skim_layers = LayerAdaptor.from_vial(vial_layers)
        """
        return [
            cls._single_layer_adaptor([label for cluster in layer for label in cluster])
            for layer in layers
        ]

    @classmethod
    def _single_layer_adaptor(cls, layer_keycodes: list[str]) -> list[str]:
        """Transform a single layer's keycodes to Skim rendering order.

        Remaps key positions from Keybard/Vial physical order to Skim's
        visual rendering order. The transformation accounts for the
        Svalboard's split keyboard layout with finger and thumb clusters.

        Source ordering (Keybard/Vial):
            - Indices 0-5: Left Thumb cluster
            - Indices 6-29: Left Finger clusters (4 clusters × 6 keys)
            - Indices 30-35: Right Thumb cluster
            - Indices 36-59: Right Finger clusters (4 clusters × 6 keys)

        Target ordering (Skim):
            - Indices 0-23: Right Finger clusters
            - Indices 24-47: Left Finger clusters
            - Indices 48-53: Right Thumb cluster
            - Indices 54-59: Left Thumb cluster

        Within each cluster, keys are also reordered according to specific
        thumb and finger mapping tables.

        Args:
            layer_keycodes: Flat list of 60 keycode strings in source order.

        Returns:
            Flat list of 60 keycode strings in Skim rendering order.
        """
        mapped_list: list[str] = [""] * 60
        thumb_mapping = [4, 2, -2, -2, -2, 0]
        finger_mapping = [3, 1, -2, -2, 0, 0]

        oIdx = 0
        for idx, label in enumerate(layer_keycodes[36:]):
            mapped_list[oIdx + finger_mapping[idx % 6]] = label
            oIdx += 1

        for idx, label in enumerate(layer_keycodes[6:30]):
            mapped_list[oIdx + finger_mapping[idx % 6]] = label
            oIdx += 1

        for idx, label in enumerate(layer_keycodes[30:36]):
            mapped_list[oIdx + thumb_mapping[idx % 6]] = label
            oIdx += 1

        for idx, label in enumerate(layer_keycodes[0:6]):
            mapped_list[oIdx + thumb_mapping[idx % 6]] = label
            oIdx += 1

        return mapped_list
