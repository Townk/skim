"""Transform QMK keycodes into display labels for keymap visualization.

This module provides the :class:`KeycodeTransformer` which converts raw QMK
keycode strings into human-readable labels suitable for display in keymap
images. The transformer handles various QMK keycode formats including:

    - Basic keycodes (KC_A, KC_SPACE, KC_ENTER)
    - Modifier functions (S(KC_A), C(KC_C), MEH(KC_X))
    - Layer functions (MO(1), TG(2), LT(3,KC_SPACE))
    - Alias references (@@KEYCODE;)
    - NerdFont icons (%%nf-md-icon;)

Example:
    Basic transformation::

        transformer = KeycodeTransformer(
            keycodes={"KC_A": "A", "KC_SPACE": "Space"},
            reversed_alias={"LSFT(KC_1)": "@@KC_EXLM;"},
            modifiers={"S": "@@MOD_SHIFT;"},
            layer_symbols={"MO": "⬓", "TG": "⬔"},
        )
        label = transformer.transform("KC_A")  # Returns "A"
        label = transformer.transform("MO(2)")  # Returns "⬓"

    Batch transformation::

        keycodes = ["KC_Q", "KC_W", "KC_E", "KC_R", "KC_T", "KC_Y"]
        labels = transformer.transform_list(keycodes)
"""

import re


class KeycodeTransformer:
    """Transforms QMK keycodes into human-readable skim display labels.

    This class handles the complex mapping from QMK keycode syntax to
    the labels displayed on keyboard visualizations. It supports:

        - **Alias resolution**: ``@@KEYCODE;`` patterns are resolved to their
          corresponding labels, enabling label reuse and composition.
        - **Reversed alias mapping**: Converts modifier+key combinations to
          their alias forms (e.g., ``LSFT(KC_1)`` → ``KC_EXLM``).
        - **Modifier functions**: Prefixes labels with modifier symbols for
          ``S()``, ``C()``, ``A()``, ``G()``, ``MEH()``, ``HYPR()`` functions.
        - **Layer functions**: Converts layer-switching keycodes (``MO()``,
          ``TG()``, ``LT()``, etc.) to symbolic representations.
        - **NerdFont passthrough**: ``%%nf-CLASS;`` patterns are preserved
          for icon rendering in Typst.

    Attributes:
        _keycodes: Main keycode to label mapping dictionary.
        _reversed_alias: Keycode function pattern to alias mapping.
        _modifiers: Modifier function name to prefix label mapping.
        _layer_symbols: Layer function name to symbol mapping.

    Example:
        >>> transformer = KeycodeTransformer(
        ...     keycodes={"KC_A": "A", "KC_EXLM": "!"},
        ...     reversed_alias={"LSFT(KC_1)": "@@KC_EXLM;"},
        ...     modifiers={"S": "Shift"},
        ...     layer_symbols={"MO": "⬓"},
        ... )
        >>> transformer.transform("KC_A")
        'A'
        >>> transformer.transform("LSFT(KC_1)")
        '!'
        >>> transformer.transform("MO(2)")
        '⬓'
    """

    def __init__(
        self,
        keycodes: dict[str, str],
        reversed_alias: dict[str, str],
        modifiers: dict[str, str],
        layer_symbols: dict[str, str],
    ) -> None:
        """Initialize the keycode transformer with mapping dictionaries.

        Args:
            keycodes: Dictionary mapping QMK keycode names to display labels.
                Example: {"KC_A": "A", "KC_SPACE": "Space"}
            reversed_alias: Dictionary mapping keycode function patterns to
                alias references. Example: {"LSFT(KC_1)": "@@KC_EXLM;"}
            modifiers: Dictionary mapping modifier function names to their
                display prefixes. Example: {"S": "@@MOD_SHIFT;", "C": "Ctrl"}
            layer_symbols: Dictionary mapping layer function names to their
                symbolic representations. Example: {"MO": "⬓", "TG": "⬔"}
        """
        self._keycodes = keycodes
        self._reversed_alias = reversed_alias
        self._modifiers = modifiers
        self._layer_symbols = layer_symbols

    def transform(self, keycode: str) -> str:
        """Transform a single QMK keycode into a display label.

        Applies the full transformation pipeline:
        1. Apply reversed alias mapping if applicable
        2. Parse and handle modifier functions (S, C, A, G, MEH, HYPR)
        3. Parse and handle layer functions (MO, TG, LT, etc.)
        4. Resolve basic keycode lookup with alias expansion

        Args:
            keycode: QMK keycode string to transform.
                Examples: "KC_A", "S(KC_B)", "MO(2)", "LT(1,KC_SPACE)"

        Returns:
            Human-readable label string for display. Empty string if
            the keycode is empty or None.

        Raises:
            ValueError: If a circular alias reference is detected during
                resolution (e.g., A references B which references A).

        Example:
            >>> transformer.transform("KC_SPACE")
            'Space'
            >>> transformer.transform("S(KC_A)")
            'Shift A'
            >>> transformer.transform("")
            ''
        """
        if not keycode:
            return ""

        keycode = self._apply_reversed_alias(keycode)

        modifier_result = self._parse_modifier_function(keycode)
        if modifier_result:
            return modifier_result

        layer_result = self._parse_layer_function(keycode)
        if layer_result:
            return layer_result

        return self._resolve_keycode(keycode)

    def transform_list(self, keycodes: list[str]) -> list[str]:
        """Transform a list of keycodes to display labels.

        Convenience method for batch transforming multiple keycodes.

        Args:
            keycodes: List of QMK keycode strings to transform.

        Returns:
            List of transformed label strings in the same order.

        Example:
            >>> transformer.transform_list(["KC_A", "KC_B", "KC_C"])
            ['A', 'B', 'C']
        """
        return [self.transform(kc) for kc in keycodes]

    def extract_layer_id(self, keycode: str) -> str | None:
        """Extract the target layer ID from a layer-switching keycode.

        Parses layer function keycodes to extract the layer identifier
        used for building layer toggle matrices.

        Supported layer functions: MO, LM, LT, OSL, TG, TO, TT, DF, PDF

        Args:
            keycode: Keycode string to analyze.
                Examples: "MO(2)", "TG(_SYS)", "LT(1,KC_SPACE)"

        Returns:
            Layer identifier string if the keycode is a layer function,
            None otherwise. The identifier may be numeric ("2") or
            symbolic ("_NAV").

        Example:
            >>> transformer.extract_layer_id("MO(2)")
            '2'
            >>> transformer.extract_layer_id("TG(_NAV)")
            '_NAV'
            >>> transformer.extract_layer_id("KC_A")
            None
        """
        layer_funcs = ["MO", "LM", "LT", "OSL", "TG", "TO", "TT", "DF", "PDF"]

        match = re.match(r"^([A-Z]+)\(([^,)]+)(?:,.*)?\)$", keycode)
        if match:
            func_name = match.group(1)
            if func_name in layer_funcs:
                return match.group(2)
        return None

    def _apply_reversed_alias(self, keycode: str) -> str:
        """Apply reversed alias mapping as the first transformation step.

        Checks if the keycode has a reversed alias mapping (e.g.,
        LSFT(KC_1) -> @@KC_EXLM;) and applies it before further processing.

        Args:
            keycode: Original keycode string.

        Returns:
            Resolved keycode if an alias was found, original otherwise.
        """
        if keycode in self._reversed_alias:
            alias_target = self._reversed_alias[keycode]
            return self._resolve_aliases_in_label(alias_target, set())
        return keycode

    def _parse_modifier_function(self, keycode: str) -> str | None:
        """Parse modifier functions like S(KC_A), MEH(KC_B), etc.

        Handles QMK modifier wrapper functions by extracting the modifier
        prefix and recursively transforming the inner keycode.

        Args:
            keycode: Keycode string that may contain a modifier function.

        Returns:
            Combined "modifier inner_label" string if this is a modifier
            function, None if not a modifier function.

        Example:
            Input: "S(KC_A)" with modifiers={"S": "Shift"}
            Output: "Shift A"
        """
        match = re.match(r"^([A-Z]+)\((.+)\)$", keycode)
        if not match:
            return None

        func_name = match.group(1)
        inner_keycode = match.group(2)

        if func_name not in self._modifiers:
            return None

        modifier_prefix = self._modifiers[func_name]
        modifier_label = self._resolve_aliases_in_label(modifier_prefix, set())

        inner_label = self.transform(inner_keycode)

        return f"{modifier_label} {inner_label}"

    def _parse_layer_function(self, keycode: str) -> str | None:
        """Parse layer functions like MO(2), TG(3), LT(2,KC_SPACE), etc.

        Converts layer-switching keycodes to their symbolic representation
        from the layer_symbols mapping.

        Args:
            keycode: Keycode string that may contain a layer function.

        Returns:
            Layer symbol string if this is a recognized layer function,
            None if not a layer function.

        Example:
            Input: "MO(2)" with layer_symbols={"MO": "⬓"}
            Output: "⬓"
        """
        match = re.match(r"^([A-Z]+)\(([^,)]+)(?:,.*)?\)$", keycode)
        if match:
            func_name = match.group(1)

            if func_name in self._layer_symbols:
                return self._layer_symbols[func_name]

        return None

    def _resolve_keycode(self, keycode: str, visited: set | None = None) -> str:
        """Recursively resolve a keycode to its final display label.

        Looks up the keycode in the keycodes dictionary and resolves any
        alias references (@@KEYCODE;) found in the label. Tracks visited
        keycodes to detect and prevent circular references.

        Args:
            keycode: Keycode or alias to resolve.
            visited: Set of already-visited keycodes for cycle detection.

        Returns:
            Final resolved display label. Returns the original keycode
            if no mapping is found.

        Raises:
            ValueError: If a circular alias reference is detected.

        Example:
            >>> # With keycodes={"KC_A": "A", "MY_KEY": "@@KC_A;"}
            >>> transformer._resolve_keycode("MY_KEY")
            'A'
        """
        if visited is None:
            visited = set()

        if keycode in visited:
            raise ValueError(
                f"Circular alias detected: {' -> '.join(visited)} -> {keycode}"
            )

        if keycode not in self._keycodes:
            return keycode

        label = self._keycodes[keycode]

        if not self._contains_alias(label):
            return label

        visited.add(keycode)
        resolved_label = self._resolve_aliases_in_label(label, visited)
        visited.remove(keycode)

        return resolved_label

    def _contains_alias(self, label: str) -> bool:
        """Check if a label string contains alias references.

        Args:
            label: Label string to check.

        Returns:
            True if the label contains ``@@KEYCODE;`` patterns.
        """
        return "@@" in label

    def _resolve_aliases_in_label(self, label: str, visited: set) -> str:
        """Resolve all alias references in a label string.

        Finds all ``@@KEYCODE;`` patterns in the label and replaces them
        with their resolved labels.

        Args:
            label: Label string potentially containing aliases.
            visited: Set of visited keycodes for cycle detection.

        Returns:
            Label with all aliases resolved to their final values.
        """
        pattern = r"@@([A-Z0-9_]+);"

        def replace_alias(match: re.Match) -> str:
            alias_keycode = match.group(1)
            return self._resolve_keycode(alias_keycode, visited)

        return re.sub(pattern, replace_alias, label)
