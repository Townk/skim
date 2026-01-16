"""Transform QMK keycodes into display labels for keymap visualization.

This module provides the :class:`KeycodeTransformer` which converts raw QMK
keycode strings into human-readable labels suitable for display in keymap
images. The transformer handles various QMK keycode formats including:

    - Basic keycodes (KC_A, KC_SPACE, KC_ENTER)
    - Macro functions (S(KC_A), MO(1), LT(1,KC_SPACE), LSFT_T(KC_A))
    - Alias references (@@KEYCODE;)
    - NerdFont icons (%%nf-md-icon;)

Example:
    Basic transformation::

        transformer = KeycodeTransformer(
            keycodes={"KC_A": "A", "KC_SPACE": "Space"},
            reversed_alias={"LSFT(KC_1)": "@@KC_EXLM;"},
            macro_functions={
                "S": "@@KC_LEFT_SHIFT; @0;",
                "MO": "%%nf-md-layers_outline; #0;",
            },
            modifier_union={"MOD_LCTL": "@@KC_LEFT_CTRL;"},
        )
        label = transformer.transform("KC_A")  # Returns "A"
        label = transformer.transform("MO(2)")  # Returns "󰧾 2"

    Batch transformation::

        keycodes = ["KC_Q", "KC_W", "KC_E", "KC_R", "KC_T", "KC_Y"]
        labels = transformer.transform_list(keycodes)
"""

import re

SEPARATOR_CHAR = "│"


class KeycodeTransformer:
    """Transforms QMK keycodes into human-readable skim display labels.

    This class handles the complex mapping from QMK keycode syntax to
    the labels displayed on keyboard visualizations. It supports:

        - **Alias resolution**: ``@@KEYCODE;`` patterns are resolved to their
          corresponding labels, enabling label reuse and composition.
        - **Reversed alias mapping**: Converts modifier+key combinations to
          their alias forms (e.g., ``LSFT(KC_1)`` → ``KC_EXLM``).
        - **Macro functions**: Resolves function-style keycodes using templates
          with placeholders for layer numbers (#N;), keycodes (@N;), and
          separators (|;).
        - **NerdFont passthrough**: ``%%nf-CLASS;`` patterns are preserved
          for icon rendering in Typst.

    Attributes:
        _keycodes: Main keycode to label mapping dictionary.
        _reversed_alias: Keycode function pattern to alias mapping.
        _macro_functions: Macro function templates with placeholders.
        _modifier_union: Modifier bit to label mapping.

    Example:
        >>> transformer = KeycodeTransformer(
        ...     keycodes={"KC_A": "A", "KC_EXLM": "!"},
        ...     reversed_alias={"LSFT(KC_1)": "@@KC_EXLM;"},
        ...     macro_functions={"S": "@@KC_LEFT_SHIFT; @0;"},
        ...     modifier_union={"MOD_LCTL": "@@KC_LEFT_CTRL;"},
        ... )
        >>> transformer.transform("KC_A")
        'A'
        >>> transformer.transform("LSFT(KC_1)")
        '!'
    """

    def __init__(
        self,
        keycodes: dict[str, str],
        reversed_alias: dict[str, str],
        macro_functions: dict[str, str],
        modifier_union: dict[str, str],
    ) -> None:
        self._keycodes = keycodes
        self._reversed_alias = reversed_alias
        self._macro_functions = macro_functions
        self._modifier_union = modifier_union

    def transform(self, keycode: str) -> str:
        """Transform a single QMK keycode into a display label.

        Applies the full transformation pipeline:
        1. Apply reversed alias mapping if applicable (MUST be first)
        2. Parse and handle macro functions
        3. Resolve basic keycode lookup with alias expansion

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

        macro_result = self._parse_macro_function(keycode)
        if macro_result is not None:
            return macro_result

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

        # First resolve any reversed aliases (e.g., CKC_BSPC -> LT(_NAV, ...))
        # Note: We don't resolve standard aliases (@@...) here because
        # layer functions must be explicit in the raw keycode or reversed alias.
        resolved_keycode = self._apply_reversed_alias(keycode)

        match = re.match(r"^([A-Z0-9_]+)\(([^,)]+)(?:,.*)?\)$", resolved_keycode)
        if match:
            func_name = match.group(1)
            if func_name in layer_funcs:
                return match.group(2)
        return None

    def _apply_reversed_alias(self, keycode: str) -> str:
        if keycode in self._reversed_alias:
            alias_target = self._reversed_alias[keycode]
            return self._resolve_aliases_in_label(alias_target, set())
        return keycode

    def _parse_macro_function(self, keycode: str) -> str | None:
        """Parse macro functions and resolve their templates.

        Handles all QMK function-style keycodes by:
        1. Extracting function name and arguments
        2. Looking up the template in macro_functions
        3. Resolving placeholders (#N; for layers, @N; for keycodes, |; for separator)
        4. Recursively resolving the result
        """
        match = re.match(r"^([A-Z0-9_]+)\((.+)\)$", keycode)
        if not match:
            return None

        func_name = match.group(1)
        args_str = match.group(2)

        if func_name not in self._macro_functions:
            return None

        template = self._macro_functions[func_name]
        args = self._parse_function_arguments(args_str)

        resolved = self._resolve_template_placeholders(template, args)

        return self._resolve_aliases_in_label(resolved, set())

    def _parse_function_arguments(self, args_str: str) -> list[str]:
        args = []
        current = []
        depth = 0

        for char in args_str:
            if char == "(":
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
            args.append("".join(current).strip())

        return args

    def _resolve_template_placeholders(self, template: str, args: list[str]) -> str:
        result = template

        result = result.replace("|;", SEPARATOR_CHAR)

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

    def _resolve_layer_argument(self, args: list[str], index: int) -> str:
        if index >= len(args):
            return ""

        arg = args[index]
        if arg.isdigit():
            return str(int(arg) + 1)
        return arg

    def _resolve_keycode_argument(self, args: list[str], index: int) -> str:
        if index >= len(args):
            return ""

        arg = args[index]

        if arg in self._keycodes:
            return self._resolve_keycode(arg)

        if self._is_modifier_union(arg):
            return self._resolve_modifier_union(arg)

        return self.transform(arg)

    def _is_modifier_union(self, arg: str) -> bool:
        return arg.startswith("MOD_") or "|" in arg and "MOD_" in arg

    def _resolve_modifier_union(self, arg: str) -> str:
        parts = arg.split("|")
        resolved_parts = []

        for part in parts:
            part = part.strip()
            if part in self._modifier_union:
                label = self._modifier_union[part]
                resolved = self._resolve_aliases_in_label(label, set())
                resolved_parts.append(resolved)
            else:
                resolved_parts.append(part)

        return " ".join(resolved_parts)

    def _resolve_keycode(self, keycode: str, visited: set | None = None) -> str:
        if visited is None:
            visited = set()

        if keycode in visited:
            raise ValueError(
                f"Circular alias detected: {' -> '.join(visited)} -> {keycode}"
            )

        if keycode not in self._keycodes:
            return keycode

        label = self._keycodes[keycode]

        if "@@" not in label:
            return label

        visited.add(keycode)
        resolved_label = self._resolve_aliases_in_label(label, visited)
        visited.remove(keycode)

        return resolved_label

    def _resolve_aliases_in_label(self, label: str, visited: set) -> str:
        pattern = r"@@([A-Z0-9_]+);"

        def replace_alias(match: re.Match) -> str:
            alias_keycode = match.group(1)
            return self._resolve_keycode(alias_keycode, visited)

        return re.sub(pattern, replace_alias, label)
