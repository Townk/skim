# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Symbol legend rendering — describes the non-obvious symbols used
on a layer (or across the keymap on the overview).

Walks each key's raw keycode (pre-resolution), recursing into wrapper
functions like ``LT(N, KC_A)`` and ``LCTL(KC_A)``, and tap-dance /
macro definitions.  Atomic keycodes resolve through the ``@@`` alias
chain; both the original name and every step in the chain are checked
against ``symbol_descriptions``.  Function names are checked against
``function_descriptions``.

``symbol_descriptions`` may also contain function-call patterns (e.g.
``A(KC_LEFT)``).  When a keycode matches such a pattern, a single
legend entry is produced and no recursive expansion is performed.

Public entry point: :func:`collect_used_descriptions`.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

import drawsvg as draw

from skim.application.render.legend import _legend_key_label
from skim.application.render.text import Font, Label, TextPart
from skim.data import KeycodeMappings, SvalboardKeymap
from skim.domain import SEPARATOR_CHAR, SvalboardTargetKey

_TRANSPARENT_KEYCODES = frozenset({"KC_TRANSPARENT", "KC_TRNS", "_______"})
_TRANSPARENT_GLYPH = "⛛"

if TYPE_CHECKING:
    from skim.domain.adapters.keycode_label_adapter import KeycodeLabelAdapter

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

_FUNC_RE = re.compile(r"^([A-Z][A-Z0-9_]*)\((.+)\)$")
"""Match ``FUNCNAME(args)`` at the top level."""

_ALIAS_RE = re.compile(r"@@([A-Z0-9_]+);")
"""Match ``@@KEYCODE;`` alias references inside a label string."""

_LAYER_FUNCTION_NAMES = frozenset(
    {"DF", "PDF", "MO", "LM", "LT", "OSL", "TG", "TO", "TT"}
)
"""Layer-switching function names for which a ``#`` layer-arg indicator is
appended to the display label when the rendered result doesn't already
contain one."""


@dataclass(frozen=True, slots=True)
class SymbolLegendEntry:
    """One row in the symbol legend.

    Attributes:
        display_label: The resolved label string shown in the legend's
            left "symbol" cell.
        description: Human-readable description from the yaml data.
        sort_key: Canonical keycode or function name used for deduplication
            and stable ordering.
    """

    display_label: str
    description: str
    sort_key: str


# ---------------------------------------------------------------------------
# Collection helpers
# ---------------------------------------------------------------------------

def _resolve_aliases(
    keycode: str,
    keycodes: dict[str, str],
) -> list[str]:
    """Return the chain of keycode names traversed when resolving ``keycode``.

    The first entry is ``keycode`` itself; subsequent entries are the
    keycodes found by following ``@@KEY;`` alias references, one level
    per step, stopping at cycles or non-alias labels.

    Only returns the *names* (keys), not the labels.  The last name in the
    list is the one whose label is not itself an alias.
    """
    chain: list[str] = []
    visited: set[str] = set()
    current = keycode
    while current not in visited:
        visited.add(current)
        chain.append(current)
        label = keycodes.get(current)
        if label is None:
            break
        alias_match = _ALIAS_RE.fullmatch(label.strip())
        if alias_match is None:
            break
        current = alias_match.group(1)
    return chain


def _count_placeholders(template: str) -> int:
    """Count ``@N;`` and ``#N;`` placeholders in a function template."""
    return len(re.findall(r"[@#]\d+;", template))


def _resolve_description(
    raw_description: str,
    adapter: KeycodeLabelAdapter,
) -> str:
    """Resolve a function description with all placeholders substituted.

    Handles ``@N;`` / ``#N;`` (both substituted with the literal ``#``
    placeholder — descriptions are deduplicated by function name so the
    actual layer/keycode argument is not available), ``@@KEYCODE;``
    references (resolved through the adapter's alias chain), and ``|;``
    (replaced with :data:`~skim.domain.SEPARATOR_CHAR`).

    Parameters
    ----------
    raw_description:
        The raw description string from the yaml (e.g.
        ``"Change to layer #0; while holding"``).
    adapter:
        A :class:`~skim.domain.adapters.keycode_label_adapter.KeycodeLabelAdapter`
        instance used to resolve ``@@KEYCODE;`` references.

    Returns
    -------
    str
        The description with all placeholders resolved.
    """
    text = raw_description
    # @N; and #N; → literal "#" (generic layer/keycode-arg indicator)
    text = re.sub(r"[@#]\d+;", "#", text)
    # |; → separator character
    text = text.replace("|;", SEPARATOR_CHAR)
    # @@KEYCODE; → resolved symbol via the adapter
    text = adapter._resolve_label_reference(text, set())
    return text


def _is_per_instance_description(desc: str) -> bool:
    """Return True iff ``desc`` contains any ``@N;`` placeholder.

    When a description contains ``@N;`` placeholders, each unique
    (function, args) combination produces its own legend entry instead
    of a single generic entry per function name.
    """
    return bool(re.search(r"@\d+;", desc))


def _resolve_description_generic(
    raw: str,
    adapter: KeycodeLabelAdapter,
) -> str:
    """Resolve a generic function description.

    Both ``@N;`` and ``#N;`` are replaced with the literal ``#``; ``|;``
    becomes :data:`~skim.domain.SEPARATOR_CHAR`; ``@@KEYCODE;`` references
    are resolved through the adapter's alias chain.
    """
    text = re.sub(r"[@#]\d+;", "#", raw)
    text = text.replace("|;", SEPARATOR_CHAR)
    return adapter._resolve_label_reference(text, set())


def _resolve_description_per_instance(
    raw: str,
    args: list[str],
    adapter: KeycodeLabelAdapter,
) -> str:
    """Resolve a per-instance function description.

    ``#N;`` → literal ``#``; ``@N;`` → the recursively-resolved label of
    ``args[N]``; ``|;`` → :data:`~skim.domain.SEPARATOR_CHAR`; ``@@KEYCODE;``
    references are resolved through the adapter's alias chain.
    """
    # #N; → literal "#"
    text = re.sub(r"#\d+;", "#", raw)

    # @N; → recursively-resolved arg label
    def _replace_at(match: re.Match) -> str:
        idx = int(match.group(1))
        if idx >= len(args):
            return ""
        return adapter._resolve_keycode_argument(args, idx)

    text = re.sub(r"@(\d+);", _replace_at, text)
    text = text.replace("|;", SEPARATOR_CHAR)
    return adapter._resolve_label_reference(text, set())


def _function_display_label(
    func_name: str,
    macro_functions: dict[str, str],
    keycode_mappings: KeycodeMappings,
) -> str:
    """Render the display symbol for a function-description entry.

    Builds a synthetic keycode (``MO(#)``, ``LM(#,KC_NO)``, …) and runs
    it through the standard label adapter so glyphs render exactly as they
    do on a key.  ``#`` is used as the layer-arg placeholder.

    For layer functions, when the resolved label contains no layer reference
    (no ``#`` character and no separator), ``#`` is appended so the legend
    reader sees that a layer arg is part of the function.
    """
    from skim.data import Keyboard
    from skim.domain.adapters.keycode_label_adapter import KeycodeLabelAdapter

    adapter = KeycodeLabelAdapter(Keyboard(), keycode_mappings)

    template = macro_functions.get(func_name, "")
    arg_count = max(1, _count_placeholders(template))
    args = ["#"] + ["KC_NO"] * (arg_count - 1)
    synthetic = f"{func_name}({','.join(args)})"
    result = adapter.transform(synthetic)
    label = result.label or ""

    # If this is a layer function but the rendered label has no layer
    # reference, append ``#`` so the legend shows it takes a layer arg.
    if (
        func_name in _LAYER_FUNCTION_NAMES
        and "#" not in label
        and SEPARATOR_CHAR not in label
    ):
        label = f"{label} #" if label else "#"

    return label


def _parse_function_args(args_str: str) -> list[str]:
    """Split comma-separated args respecting nested parentheses."""
    args: list[str] = []
    current: list[str] = []
    depth = 0
    for ch in args_str:
        if ch.isspace():
            continue
        elif ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            args.append("".join(current))
            current = []
        else:
            current.append(ch)
    if current:
        args.append("".join(current))
    return args


def _resolve_display_label(
    keycode: str,
    keycodes_dict: dict[str, str],
    macro_functions: dict[str, str],
) -> str:
    """Resolve a keycode (atomic or function-call) to its display label string.

    This is a lightweight resolver that works without a full ``Keyboard``
    config.  For function-call forms it expands the macro_functions template,
    substituting ``@@KEY;`` alias references and ``@N;`` argument placeholders.
    Layer-number placeholders (``#N;``) are left as-is (rare for display use).

    Returns the resolved label, or ``keycode`` itself as a fallback.
    """
    # Apply alias chain for atomic keycodes
    func_match = _FUNC_RE.match(keycode)
    if func_match:
        func_name = func_match.group(1)
        args_str = func_match.group(2)
        template = macro_functions.get(func_name)
        if template is None:
            return keycode
        args = _parse_function_args(args_str)
        # Substitute @N; argument placeholders
        def _sub_arg(m: re.Match[str]) -> str:
            idx = int(m.group(1))
            if idx >= len(args):
                return ""
            return _resolve_display_label(args[idx], keycodes_dict, macro_functions)

        result = re.sub(r"@(\d+);", _sub_arg, template)
        # Resolve @@KEY; alias references
        def _sub_alias(m: re.Match[str]) -> str:
            key = m.group(1)
            label = keycodes_dict.get(key, key)
            # Follow one level of alias if needed
            nested = _ALIAS_RE.fullmatch(label.strip())
            if nested:
                label = keycodes_dict.get(nested.group(1), nested.group(1))
            return label

        result = re.sub(r"@@([A-Z0-9_]+);", _sub_alias, result)
        # Drop |; separator (tap/hold — keep only first part for legend display)
        if "|;" in result:
            result = result.split("|;")[0].strip()
        return result.strip()

    # Atomic keycode — resolve through alias chain
    chain = _resolve_aliases(keycode, keycodes_dict)
    canonical = chain[-1]
    raw_label = keycodes_dict.get(canonical, canonical)
    display = re.sub(r"@@[A-Z0-9_]+;", "", raw_label).strip()
    return display if display else keycode


def _collect_raw(
    keycodes_raw: Iterable[str],
    keymap: SvalboardKeymap[str] | SvalboardKeymap[SvalboardTargetKey] | None,
    keycode_mappings: KeycodeMappings,
    out: dict[str, SymbolLegendEntry],
    visited_funcs: set[str],
) -> None:
    """Recursive worker that populates ``out`` (sort_key → entry).

    Parameters
    ----------
    keycodes_raw:
        Raw keycode strings to inspect (pre-pre-processing).
    keymap:
        The full keymap object, used to recurse into tap-dance variants
        and macro action keys.  May be ``None`` if unavailable.
    keycode_mappings:
        Full yaml dict (keycodes, pre_processing, macro_functions,
        modifier_union, symbol_descriptions, function_descriptions).
    out:
        Accumulator dict keyed by ``sort_key``.
    visited_funcs:
        Guards against recursive expansion of the same function name.
    """
    keycodes_dict: dict[str, str] = keycode_mappings.get("keycodes", {})
    pre_proc: dict[str, str] = keycode_mappings.get("pre_processing", {})
    macro_functions: dict[str, str] = keycode_mappings.get("macro_functions", {})
    symbol_desc: dict[str, str] = keycode_mappings.get("symbol_descriptions", {})
    func_desc: dict[str, str | dict] = keycode_mappings.get("function_descriptions", {})

    for raw in keycodes_raw:
        # Apply pre-processing normalisation
        keycode = pre_proc.get(raw, raw)

        # --- Special-case the transparent family ---
        # ``KC_TRANSPARENT``, ``KC_TRNS`` and ``_______`` all resolve to
        # an empty label in keycode-mappings.yaml (rendered as nothing
        # on the key — the layer-0 fallthrough fills the slot). For the
        # legend, collapse all three to a single entry with the
        # Vial-style ⛛ glyph and the description on KC_TRANSPARENT.
        if keycode in _TRANSPARENT_KEYCODES:
            sort_k = "KC_TRANSPARENT"
            if sort_k not in out and "KC_TRANSPARENT" in symbol_desc:
                out[sort_k] = SymbolLegendEntry(
                    display_label=_TRANSPARENT_GLYPH,
                    description=symbol_desc["KC_TRANSPARENT"],
                    sort_key=sort_k,
                )
            continue

        # --- Check the WHOLE keycode against symbol_descriptions first ---
        # This handles both atomic matches AND function-call patterns like
        # "A(KC_LEFT)" that are listed verbatim in symbol_descriptions.
        if keycode in symbol_desc:
            desc = symbol_desc[keycode]
            display = _resolve_display_label(keycode, keycodes_dict, macro_functions)
            sort_k = keycode
            if sort_k not in out:
                out[sort_k] = SymbolLegendEntry(
                    display_label=display,
                    description=desc,
                    sort_key=sort_k,
                )
            continue  # Do NOT recurse — one entry for the whole pattern

        # --- Function call? ---
        func_match = _FUNC_RE.match(keycode)
        if func_match:
            func_name = func_match.group(1)
            args_str = func_match.group(2)

            # Check function_descriptions
            if func_name in func_desc and func_name not in visited_funcs:
                from skim.data import Keyboard
                from skim.domain.adapters.keycode_label_adapter import KeycodeLabelAdapter

                fd_entry = func_desc[func_name]
                raw_desc = fd_entry["description"] if isinstance(fd_entry, dict) else fd_entry
                adapter = KeycodeLabelAdapter(Keyboard(), keycode_mappings)

                if _is_per_instance_description(raw_desc):
                    # Per-instance mode: one entry per unique (func, args).
                    inst_args = _parse_function_args(args_str)
                    desc = _resolve_description_per_instance(raw_desc, inst_args, adapter)
                    target_key = adapter.transform(keycode)
                    display_label = _legend_key_label(target_key)
                    sort_k = keycode  # e.g. "MO(5)" — one entry per unique call
                    if sort_k not in out:
                        out[sort_k] = SymbolLegendEntry(
                            display_label=display_label,
                            description=desc,
                            sort_key=sort_k,
                        )
                    # Do NOT recurse — description covers the function as a whole.
                    continue
                else:
                    # Generic mode: one entry per function name (deduped).
                    desc = _resolve_description_generic(raw_desc, adapter)
                    label = _function_display_label(
                        func_name, macro_functions, keycode_mappings
                    )
                    sort_k = func_name
                    if sort_k not in out:
                        out[sort_k] = SymbolLegendEntry(
                            display_label=label,
                            description=desc,
                            sort_key=sort_k,
                        )
                    # Fall through to recurse into args below.

            # Recurse into args (no function_descriptions entry, already visited,
            # or generic-mode entry that may have described-atomic args).
            args = _parse_function_args(args_str)
            _collect_raw(args, keymap, keycode_mappings, out, visited_funcs)
            continue

        # --- TD(id)? ---
        td_match = re.match(r"^TD\((\w+)\)$", keycode)
        if td_match and keymap is not None:
            td_id = td_match.group(1)
            td_by_id = {t.id: t for t in keymap.tap_dances}
            if td_id in td_by_id:
                td = td_by_id[td_id]
                variant_keycodes: list[str] = []
                for variant in (td.tap, td.hold, td.double_tap, td.tap_then_hold):
                    if variant is not None:
                        kc = variant if isinstance(variant, str) else getattr(variant, "label", None)
                        if kc:
                            variant_keycodes.append(kc)
                _collect_raw(variant_keycodes, keymap, keycode_mappings, out, visited_funcs)
            continue

        # --- MACRO_id or Mdigit? ---
        macro_match = re.match(r"^(?:MACRO_(\w+)|M(\d+))$", keycode)
        if macro_match and keymap is not None:
            macro_id = macro_match.group(1) or macro_match.group(2)
            macro_by_id = {m.id: m for m in keymap.macros}
            if macro_id in macro_by_id:
                macro = macro_by_id[macro_id]
                action_keycodes: list[str] = []
                for action in macro.actions:
                    for key in action.keys:
                        kc = key if isinstance(key, str) else getattr(key, "label", None)
                        if kc:
                            action_keycodes.append(kc)
                _collect_raw(action_keycodes, keymap, keycode_mappings, out, visited_funcs)
            continue

        # --- Plain atomic keycode ---
        chain = _resolve_aliases(keycode, keycodes_dict)
        for name in chain:
            if name in symbol_desc:
                desc = symbol_desc[name]
                # The display label is the resolved label of the *original* keycode
                # (post pre-processing, through the full alias chain)
                canonical = chain[-1]
                raw_label = keycodes_dict.get(canonical, canonical)
                # Strip any remaining @@; or %% tokens for a clean label
                display = re.sub(r"@@[A-Z0-9_]+;", "", raw_label).strip()
                if not display:
                    # Fall back to the resolved keycode label via the first name
                    first_label = keycodes_dict.get(keycode, keycode)
                    display = re.sub(r"@@[A-Z0-9_]+;", "", first_label).strip() or keycode
                sort_k = name
                if sort_k not in out:
                    out[sort_k] = SymbolLegendEntry(
                        display_label=display,
                        description=desc,
                        sort_key=sort_k,
                    )
                break  # Use the first matching step in the chain


def collect_used_descriptions(
    keycodes: Iterable[str],
    keymap: SvalboardKeymap[str] | SvalboardKeymap[SvalboardTargetKey] | None,
    keycode_mappings: KeycodeMappings,
) -> list[SymbolLegendEntry]:
    """Return description entries for the symbols used in ``keycodes``.

    Parameters
    ----------
    keycodes:
        Raw keycode strings as they appear in the keymap (pre-resolution).
    keymap:
        Full keymap object (for tap-dance and macro recursion).
    keycode_mappings:
        Loaded yaml dict (from ``load_keycode_mappings``).

    Returns
    -------
    list[SymbolLegendEntry]
        Sorted list of entries, one per distinct canonical keycode or
        function name found in ``symbol_descriptions`` /
        ``function_descriptions``.
    """
    out: dict[str, SymbolLegendEntry] = {}
    _collect_raw(keycodes, keymap, keycode_mappings, out, set())
    return sorted(out.values(), key=lambda e: e.sort_key)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

# Geometry constants
_SYMBOL_HEADER_HEIGHT = 28
_ENTRY_ROW_HEIGHT = 16
_SYMBOL_FONT_SIZE = 10
_DESC_FONT_SIZE = 10
_COLUMN_GAP = 18.0
_GLYPH_DESC_GAP = 6.0    # gap between glyph cell and description text
_ROW_GAP = 1.0
_ENTRY_RIGHT_PAD = 6.0   # pad between adjacent column entries


def _measure_label_width(label: str, font_size: float) -> float:
    """Measure the rendered width of ``label`` at ``font_size``."""
    label_obj = Label(label, Font.FINGER_KEY, text_color="#000")
    width = 0.0
    for part in label_obj.parts:
        font = part.font.load(font_size)
        if isinstance(part, TextPart):
            width += font.getlength(part.text)
        else:
            width += part.measure_width(font)
    return max(width, 4.0)


def symbol_legend_height(
    entries: list[SymbolLegendEntry],
    content_width: float,
) -> float:
    """Return the total height the symbol legend block needs.

    Returns 0 when ``entries`` is empty.
    """
    if not entries:
        return 0.0

    # Uniform glyph cell width = widest glyph across all entries
    max_glyph_w = max(
        _measure_label_width(e.display_label, _SYMBOL_FONT_SIZE) for e in entries
    )

    # Description text widths — use the same Label-parts-aware measurement
    # as the glyph column so NerdFont/symbol fragments and other non-BMP
    # codepoints in resolved descriptions are sized correctly.
    max_desc_w = max(
        _measure_label_width(e.description, _DESC_FONT_SIZE) for e in entries
    )

    entry_w = max_glyph_w + _GLYPH_DESC_GAP + max_desc_w + _ENTRY_RIGHT_PAD
    col_count = max(1, int((content_width + _COLUMN_GAP) / (entry_w + _COLUMN_GAP)))
    row_count = (len(entries) + col_count - 1) // col_count

    return _SYMBOL_HEADER_HEIGHT + row_count * (_ENTRY_ROW_HEIGHT + _ROW_GAP)


def build_symbol_legend(
    entries: list[SymbolLegendEntry],
    x: float,
    y: float,
    content_width: float,
    palette: object,  # Palette (avoid circular import by keeping loose type)
    use_system_fonts: bool = False,
) -> draw.Group | None:
    """Render the symbol legend block at ``(x, y)``.

    Returns ``None`` when ``entries`` is empty.
    """
    if not entries:
        return None

    from skim.data import Palette

    assert isinstance(palette, Palette)
    text_color = palette.text_color
    accent_line = "#888888"  # neutral-gray, independent of any per-layer color

    # Compute layout geometry — inline style (no surrounding rectangle)
    max_glyph_w = max(
        _measure_label_width(e.display_label, _SYMBOL_FONT_SIZE) for e in entries
    )

    max_desc_w = max(
        _measure_label_width(e.description, _DESC_FONT_SIZE) for e in entries
    )

    entry_w = max_glyph_w + _GLYPH_DESC_GAP + max_desc_w + _ENTRY_RIGHT_PAD
    col_count = max(1, int((content_width + _COLUMN_GAP) / (entry_w + _COLUMN_GAP)))

    g = draw.Group()

    label_font = (
        Font.FINGER_KEY.get_system_font_family() if use_system_fonts else Font.FINGER_KEY.value
    )

    # Section header
    g.append(draw.Text(
        "SYMBOLS",
        x=x, y=y + 12,
        font_size=11, font_weight="700", letter_spacing=3,
        text_anchor="start", font_family=label_font, fill=accent_line,
    ))
    g.append(draw.Line(
        sx=x, sy=y + 20, ex=x + content_width, ey=y + 20,
        stroke=accent_line, stroke_opacity=0.5, stroke_width=1.2,
    ))

    # Entries in row-major column flow — inline ACTION-KEY style (no surrounding box)
    content_y = y + _SYMBOL_HEADER_HEIGHT
    for idx, entry in enumerate(entries):
        col = idx % col_count
        row = idx // col_count
        # Column x: evenly distribute
        col_x = x + col * (entry_w + _COLUMN_GAP)
        row_y = content_y + row * (_ENTRY_ROW_HEIGHT + _ROW_GAP)
        cell_mid_y = row_y + _ENTRY_ROW_HEIGHT / 2

        # Symbol glyph — centred within the uniform glyph cell
        g.append(
            Label(
                entry.display_label,
                Font.FINGER_KEY,
                text_color=text_color,
                text_anchor="middle",
                dominant_baseline="central",
            ).build_text(
                col_x + max_glyph_w / 2,
                cell_mid_y + 0.5,
                _SYMBOL_FONT_SIZE,
                use_system_fonts,
            )
        )
        # Description text — left-aligned immediately after the glyph cell
        g.append(draw.Text(
            entry.description,
            x=col_x + max_glyph_w + _GLYPH_DESC_GAP,
            y=cell_mid_y + 0.5,
            font_size=_DESC_FONT_SIZE,
            dominant_baseline="central",
            font_family=label_font,
            fill=text_color,
            opacity=0.75,
        ))

    return g
