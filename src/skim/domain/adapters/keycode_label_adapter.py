# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Adapter for transforming QMK keycodes into human-readable display labels.

This module provides the KeycodeLabelAdapter class, which transforms raw QMK
keycode strings into user-friendly labels suitable for display on keymap
images. It handles various QMK constructs including:

- Basic keycodes (KC_A, KC_SPACE, etc.)
- Macro functions (LT, MO, MT, OSM, etc.)
- Modifier combinations (MOD_LCTL, MOD_LSFT|MOD_LALT, etc.)
- Alias references (@@KEYCODE; syntax for cross-referencing)

The transformation is driven by a YAML configuration file containing
keycode-to-label mappings and macro function templates.

Example:
    >>> from skim.application.loaders import load_keycode_mappings
    >>> from skim.data import SkimConfig
    >>> config = SkimConfig()
    >>> mappings = load_keycode_mappings(config.keycodes)
    >>> adapter = KeycodeLabelAdapter(config.keyboard, mappings)
    >>> label, layer = adapter.transform("KC_A")
    >>> label
    'A'
    >>> label, layer = adapter.transform("LT(1, KC_SPC)")
    >>> layer
    1

Attributes:
    _LAYER_FUNCTIONS: Trie containing layer-switching function prefixes.
    _LAYER_FUNCTIONS_HOLD: Set of layer functions that support hold behavior.
"""

import re

from skim.data import Keyboard, KeycodeMappings, Trie
from skim.domain import SEPARATOR_CHAR, SvalboardTargetKey

_LAYER_FUNCTIONS = Trie(["DF", "PDF", "MO", "LM", "LT", "OSL", "TG", "TO", "TT"])
"""Trie of QMK layer function prefixes for efficient prefix matching.

Contains the function names that switch or modify keyboard layers:
- DF: Set default layer
- PDF: Set default layer (persistent)
- MO: Momentary layer switch
- LM: Layer mod (layer + modifier)
- LT: Layer tap (tap for key, hold for layer)
- OSL: One-shot layer
- TG: Toggle layer
- TO: Turn on layer
- TT: Layer tap toggle
"""

_LAYER_FUNCTIONS_HOLD = {"LT", "LM"}
"""Set of layer functions that use hold behavior.

These functions activate their layer on hold rather than immediately.
LT and LM both require holding the key to activate the layer.
"""

_TRANSPARENT_KEYCODES = frozenset({"KC_TRANSPARENT", "KC_TRNS", "_______"})
"""QMK keycodes that mark a key as falling through to a lower layer."""


class KeycodeLabelAdapter:
    """Transforms QMK keycodes into human-readable display labels.

    This adapter processes raw QMK keycode strings and converts them to
    labels suitable for displaying on keymap visualization images. It
    supports basic keycodes, macro functions, modifier combinations, and
    cross-references between keycodes.

    The transformation process:
    1. Apply pre-processing rules (normalize/alias keycodes)
    2. Check for macro function syntax and expand templates
    3. Resolve keycode to label using the mapping dictionary
    4. Handle alias references (@@KEYCODE; syntax)

    Attributes:
        _keycodes: Dictionary mapping keycodes to their display labels.
        _pre_processing: Dictionary of pre-processing transformations.
        _macro_functions: Dictionary of macro function templates.
        _modifier_union: Dictionary mapping modifier constants to labels.
        _label_separator: Character used to separate tap/hold labels.

    Example:
        >>> from skim.application.loaders import load_keycode_mappings
        >>> from skim.data.config import SkimConfig
        >>> config = SkimConfig()
        >>> mappings = load_keycode_mappings()
        >>> adapter = KeycodeLabelAdapter(config.keyboard, mappings)
        >>> adapter.transform("KC_A")
        ('A', None)
        >>> adapter.transform("MO(2)")
        ('L3', 2)
    """

    _keycodes: dict[str, str]
    _pre_processing: dict[str, str]
    _macro_functions: dict[str, str]
    _modifier_union: dict[str, str]
    _label_separator: str
    _keyboard_config: Keyboard

    def __init__(self, keyboard_config: Keyboard, keycode_mappings: KeycodeMappings) -> None:
        """Initialize the adapter with keyboard configuration and keycode mappings.

        Args:
            keyboard_config: Keyboard configuration containing layer definitions.
                Used to resolve layer references by name (e.g., "nav", "sym")
                to their numeric indices.
            keycode_mappings: The keycode internal dictionary representing all
                the keycode mappings to labels. This dictionary must contain
                dictionaries for keycodes, pre_processing, macro_functions, and
                modifier_union.

        Example:
            >>> from skim.application.loaders import load_keycode_mappings
            >>> from skim.data import Keyboard, KeyboardLayer, SkimConfig
            >>> keyboard = Keyboard(layers=[KeyboardLayer(id="base", name="Base")])
            >>> config = SkimConfig()
            >>> mappings = load_keycode_mappings(config.keycodes)
            >>> adapter = KeycodeLabelAdapter(keyboard, mappings)
        """
        self._keycodes = keycode_mappings.get("keycodes", {})
        self._pre_processing = keycode_mappings.get("pre_processing", {})
        self._macro_functions = keycode_mappings.get("macro_functions", {})
        self._modifier_union = keycode_mappings.get("modifier_union", {})
        self._label_separator = SEPARATOR_CHAR
        self._keyboard_config = keyboard_config

    def transform(self, text: str) -> SvalboardTargetKey:
        """Transform a QMK keycode into a SvalboardTargetKey.

        Processes the keycode through pre-processing, macro expansion, and
        label resolution to produce a SvalboardTargetKey ready for rendering.

        Args:
            text: The raw QMK keycode string (e.g., "KC_A", "LT(1, KC_SPC)").

        Returns:
            A SvalboardTargetKey containing:
            - label: The human-readable display string
            - layer_switch: The layer index if this key switches layers,
              or None if no layer switching occurs.

        Example:
            >>> adapter.transform("KC_SPACE")
            SvalboardTargetKey(label='Space', layer_switch=None)
            >>> adapter.transform("MO(1)")
            SvalboardTargetKey(label='L2', layer_switch=1)
        """
        keycode = self._apply_pre_processing(text)

        macro_result, target_layer = self._parse_macro_function(keycode)
        if macro_result is not None:
            return SvalboardTargetKey(
                label=macro_result,
                layer_switch=target_layer,
            )

        is_transparent = keycode in _TRANSPARENT_KEYCODES
        return SvalboardTargetKey(
            label=self._resolve_keycode(keycode),
            is_transparent=is_transparent,
        )

    def _apply_pre_processing(self, keycode: str) -> str:
        """Apply pre-processing transformations to normalize keycodes.

        Args:
            keycode: The raw keycode string.

        Returns:
            The transformed keycode, or the original if no transformation
            is defined.
        """
        return self._pre_processing.get(keycode, keycode)

    def _parse_macro_function(self, keycode: str) -> tuple[str | None, int | None]:
        """Parse macro functions and resolve their templates.

        Handles QMK function-style keycodes by extracting the function name
        and arguments, looking up the template, and resolving placeholders.

        Template placeholders:
        - #N; - Layer argument at index N (1-indexed in display)
        - @N; - Keycode argument at index N (resolved to label)
        - |; - Separator character for tap/hold labels

        Args:
            keycode: The keycode string to parse (e.g., "LT(1, KC_A)").

        Returns:
            A tuple of (label, target_layer) where label is the resolved
            string or None if this is not a macro function, and target_layer
            is the layer index for layer-switching functions.
        """
        match = re.match(r"^([A-Z0-9_]+)\((.+)\)$", keycode)
        if not match:
            return None, None

        func_name = match.group(1)
        args_str = match.group(2)

        if func_name not in self._macro_functions:
            return None, None

        template = self._macro_functions[func_name]
        args = KeycodeLabelAdapter._parse_function_arguments(args_str)

        target_layer: int | str | None = None
        layer_func = _LAYER_FUNCTIONS.get_matching_prefix(func_name)
        if layer_func:
            target_layer_str = args[0]
            if layer_func in _LAYER_FUNCTIONS_HOLD and len(args) == 1:
                target_layer_str = func_name[len(layer_func) :]
            try:
                target_layer = int(target_layer_str)
            except ValueError:
                target_layer = self._keyboard_config.layer_index(target_layer_str)

        resolved = self._resolve_template_placeholders(template, args)
        label = self._resolve_label_reference(resolved, set())
        label = self._collapse_empty_dual_label(label)
        return label, target_layer

    def _collapse_empty_dual_label(self, label: str) -> str:
        """Drop the tap/hold separator when one side resolves to empty.

        Dual-purpose macros like ``LT(layer, KC_NO)`` produce labels of the
        form ``"<icon>│"`` because ``KC_NO`` resolves to an empty string.
        Rendering that as-is leaves the separator with nothing on one side.
        Treat those keys as single-label keys so they look like ``MO(layer)``.
        """
        if self._label_separator not in label:
            return label
        hold, _, tap = label.partition(self._label_separator)
        if not hold:
            return tap
        if not tap:
            return hold
        return label

    def _resolve_template_placeholders(self, template: str, args: list[str]) -> str:
        """Resolve placeholder tokens in a macro function template.

        Args:
            template: The template string with placeholders.
            args: List of argument strings from the macro call.

        Returns:
            The template with all placeholders replaced.
        """
        result = template

        result = result.replace("|;", self._label_separator)

        result = re.sub(
            r"#(\d+);",
            lambda m: self._resolve_layer_argument(args, int(m.group(1))),
            result,
        )

        result = re.sub(
            r"@(\d+);",
            lambda m: self._resolve_keycode_argument(args, int(m.group(1))),
            result,
        )

        return result

    def _resolve_keycode_argument(self, args: list[str], index: int) -> str:
        """Resolve a keycode argument to its display label.

        Args:
            args: List of argument strings from the macro call.
            index: Index of the argument to resolve.

        Returns:
            The resolved label for the argument, or empty string if index
            is out of bounds.
        """
        if index >= len(args):
            return ""

        arg = args[index]

        if arg in self._keycodes:
            return self._resolve_keycode(arg)

        if KeycodeLabelAdapter._is_modifier_union(arg):
            return self._resolve_modifier_union(arg)

        return self.transform(arg).label

    def _resolve_modifier_union(self, arg: str) -> str:
        """Resolve a modifier union expression to its display label.

        Modifier unions are pipe-separated combinations like "MOD_LCTL|MOD_LSFT".

        Args:
            arg: The modifier union expression.

        Returns:
            Space-separated string of resolved modifier labels.
        """
        parts = arg.split("|")
        resolved_parts = []

        for part in parts:
            part = part.strip()
            if part in self._modifier_union:
                label = self._modifier_union[part]
                resolved = self._resolve_label_reference(label, set())
                resolved_parts.append(resolved)
            else:
                resolved_parts.append(part)

        return " ".join(resolved_parts)

    def _resolve_label_reference(self, label: str, visited: set[str]) -> str:
        """Resolve alias references in a label string.

        Replaces @@KEYCODE; patterns with the resolved label for that keycode.

        Args:
            label: The label string potentially containing alias references.
            visited: Set of already-visited keycodes for cycle detection.

        Returns:
            The label with all alias references resolved.
        """
        pattern = r"@@([A-Z0-9_]+);"

        def replace_alias(match: re.Match[str]) -> str:
            alias_keycode = match.group(1)
            return self._resolve_keycode(alias_keycode, visited)

        return re.sub(pattern, replace_alias, label)

    def _resolve_keycode(self, keycode: str, visited: set[str] | None = None) -> str:
        """Resolve a keycode to its display label.

        Args:
            keycode: The keycode to resolve.
            visited: Set of already-visited keycodes for cycle detection.

        Returns:
            The display label for the keycode, or the keycode itself if
            no mapping is found.

        Raises:
            ValueError: If a circular alias reference is detected.
        """
        if visited is None:
            visited = set()

        if keycode in visited:
            raise ValueError(f"Circular alias detected: {' -> '.join(visited)} -> {keycode}")

        if keycode not in self._keycodes:
            return keycode

        label = self._keycodes[keycode]

        if "@@" not in label:
            return label

        visited.add(keycode)
        resolved_label = self._resolve_label_reference(label, visited)
        visited.remove(keycode)

        return resolved_label

    @staticmethod
    def _parse_function_arguments(args_str: str) -> list[str]:
        """Parse comma-separated function arguments with nested parentheses.

        Correctly handles nested function calls by tracking parenthesis depth.

        Args:
            args_str: The argument string (content between outer parentheses).

        Returns:
            List of individual argument strings.

        Example:
            >>> KeycodeLabelAdapter._parse_function_arguments("1, KC_A")
            ['1', 'KC_A']
            >>> KeycodeLabelAdapter._parse_function_arguments("1, MT(MOD_LCTL, KC_A)")
            ['1', 'MT(MOD_LCTL,KC_A)']
        """
        args: list[str] = []
        current: list[str] = []
        depth = 0

        for char in args_str:
            if char.isspace():
                continue
            elif char == "(":
                depth += 1
                current.append(char)
            elif char == ")":
                depth -= 1
                current.append(char)
            elif char == "," and depth == 0:
                args.append("".join(current).strip())
                current = []
            else:
                current.append(char)

        if current:
            args.append("".join(current))

        return args

    @staticmethod
    def _resolve_layer_argument(args: list[str], index: int) -> str:
        """Resolve a layer argument to its indexed value.

        Args:
            args: List of argument strings.
            index: Index of the argument to resolve.

        Returns:
            The indexed layer number as a string, or the original value
            if it's not a numeric layer index.
        """
        if index >= len(args):
            return ""

        return args[index]

    @staticmethod
    def _is_modifier_union(arg: str) -> bool:
        """Check if an argument is a modifier union expression.

        Args:
            arg: The argument string to check.

        Returns:
            True if the argument is a modifier constant or union of modifiers.
        """
        return arg.startswith("MOD_") or ("|" in arg and "MOD_" in arg)
